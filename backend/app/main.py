from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (BusinessFavoriteOut, BusinessOut, ConfigOut, FavoriteBusinessIn,
                         LoginRequest, QuickMessageIn, QuickMessageOut, ScanRecordOut,
                         ScanRequest, ScanResponse, ScanStats, ScanSummaryOut, UserOut)
from app.services import auth, places, sitescan, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.init_db()
    # Postgres'e ilk geçişte eski SQLite dosyası boş DB'ye tek sefer aktarılır
    # (admin seed'inden önce çalışmalı ki users tablosu boş görünsün).
    moved = store.import_sqlite_if_empty(settings.db_path)
    if moved:
        logger.info("SQLite'tan PostgreSQL'e %s kayıt aktarıldı.", moved)
    # Kullanıcı yoksa admin/admin aç; eski sahipsiz taramaları bu hesaba bağla.
    store.claim_unowned_scans(auth.ensure_admin()["id"])
    yield


app = FastAPI(title="İşletme Radarı API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"api": "ok"}


@app.get("/api/config", response_model=ConfigOut)
def get_config():
    return ConfigOut(google_places_configured=settings.google_configured)


# ---- Auth ----


@app.post("/api/auth/login", response_model=UserOut)
def login(req: LoginRequest, response: Response):
    user = auth.authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")
    response.set_cookie(
        auth.SESSION_COOKIE, auth.open_session(user["id"]),
        path="/", httponly=True, samesite="lax",
        max_age=settings.SESSION_TTL_DAYS * 86400,
    )
    return UserOut(username=user["username"])


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.close_session(token)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")


@app.get("/api/auth/me", response_model=UserOut)
def me(user: dict = Depends(auth.get_current_user)):
    return UserOut(username=user["username"])


@app.post("/api/scan", response_model=ScanResponse)
def scan(req: ScanRequest, user: dict = Depends(auth.get_current_user)):
    if not settings.google_configured:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_PLACES_API_KEY tanımlı değil; backend .env dosyasına ekleyip yeniden başlatın.",
        )
    try:
        records, warnings = places.search_nearby(req.lat, req.lng, req.radius_m)
    except Exception as exc:  # Places istemcisi beklenmeyen hata
        logger.exception("Places taraması başarısız")
        raise HTTPException(status_code=502, detail=f"Google Places isteği başarısız: {exc}")

    stats = ScanStats(found=len(records))
    now_year = dt.date.today().year

    # Web sitesi olan işletmeleri eşzamanlı incele; tek kayıt hatası akışı durdurmaz.
    def inspect(rec: dict) -> BusinessOut | None:
        url = rec["website"]
        if sitescan.is_social_site(url):
            return BusinessOut(**rec, website_status="yok",
                               website_notes=["site yerine sosyal medya bağlantısı"])
        try:
            verdict = sitescan.check_website(url, now_year)
        except Exception as exc:  # dayanıklı kayıt: site analizi patlarsa 'erişilemedi' say
            logger.warning("Site analizi başarısız %s: %s", url, exc)
            return BusinessOut(**rec, website_status="erisilemedi",
                               website_notes=[f"analiz hatası: {exc.__class__.__name__}"])
        if verdict.status == "modern":
            return None
        return BusinessOut(**{**rec, "website": verdict.final_url or url},
                           website_status=verdict.status, website_notes=verdict.notes)

    checked = [r for r in records if r.get("website")][: settings.WEBSITE_CHECK_LIMIT]
    if len([r for r in records if r.get("website")]) > settings.WEBSITE_CHECK_LIMIT:
        warnings.append(f"Site kontrolü ilk {settings.WEBSITE_CHECK_LIMIT} işletmeyle sınırlandı")

    results: dict[str, BusinessOut] = {
        r["place_id"]: BusinessOut(**r, website_status="yok")
        for r in records if not r.get("website")
    }
    with ThreadPoolExecutor(max_workers=settings.WEBSITE_CHECK_WORKERS) as pool:
        for out in pool.map(inspect, checked):
            if out is None:  # modern sitesi olanlar tabloya girmez
                stats.filtered_modern += 1
                continue
            results[out.place_id] = out

    for b in results.values():
        if b.website_status == "yok":
            stats.without_website += 1
        elif b.website_status == "eski":
            stats.outdated_website += 1
        else:
            stats.unreachable_website += 1

    order = {"yok": 0, "erisilemedi": 1, "eski": 2}
    businesses = sorted(results.values(), key=lambda b: (order[b.website_status], b.name.lower()))
    stats.shown = len(businesses)

    try:  # geçmiş kaydı: yazma hatası tarama sonucunu etkilemesin
        store.insert_scan(user["id"], req.lat, req.lng, req.radius_m,
                          stats.model_dump(), [b.model_dump() for b in businesses])
    except Exception as exc:
        logger.warning("Tarama kaydı yazılamadı: %s", exc)
        warnings.append("Tarama geçmişe kaydedilemedi")

    return ScanResponse(businesses=businesses, stats=stats, warnings=warnings)


@app.get("/api/scans", response_model=list[ScanSummaryOut])
def list_scans(user: dict = Depends(auth.get_current_user)):
    return store.list_scans(user["id"])


@app.get("/api/scans/{scan_id}", response_model=ScanRecordOut)
def get_scan(scan_id: str, user: dict = Depends(auth.get_current_user)):
    rec = store.get_scan(scan_id, user["id"])
    if rec is None:
        raise HTTPException(status_code=404, detail="Tarama kaydı bulunamadı")
    return rec


@app.delete("/api/scans/{scan_id}", status_code=204)
def remove_scan(scan_id: str, user: dict = Depends(auth.get_current_user)):
    if not store.delete_scan(scan_id, user["id"]):
        raise HTTPException(status_code=404, detail="Tarama kaydı bulunamadı")


# ---- Favoriler ----


@app.get("/api/favorites", response_model=list[ScanSummaryOut])
def list_favorites(user: dict = Depends(auth.get_current_user)):
    return store.list_favorites(user["id"])


@app.put("/api/favorites/{scan_id}", status_code=204)
def add_favorite(scan_id: str, user: dict = Depends(auth.get_current_user)):
    if not store.add_favorite(user["id"], scan_id):
        raise HTTPException(status_code=404, detail="Tarama kaydı bulunamadı")


@app.delete("/api/favorites/{scan_id}", status_code=204)
def remove_favorite(scan_id: str, user: dict = Depends(auth.get_current_user)):
    if not store.remove_favorite(user["id"], scan_id):
        raise HTTPException(status_code=404, detail="Tarama kaydı bulunamadı")


# ---- İşletme favorileri ----


@app.get("/api/business-favorites", response_model=list[BusinessFavoriteOut])
def list_business_favorites(user: dict = Depends(auth.get_current_user)):
    return store.list_business_favorites(user["id"])


@app.put("/api/business-favorites/{place_id}", status_code=204)
def add_business_favorite(place_id: str, req: FavoriteBusinessIn,
                          user: dict = Depends(auth.get_current_user)):
    if place_id != req.business.place_id:
        raise HTTPException(status_code=400, detail="place_id uyuşmuyor")
    store.add_business_favorite(user["id"], place_id,
                                req.business.model_dump(), req.scan_id or "")


@app.delete("/api/business-favorites/{place_id}", status_code=204)
def remove_business_favorite(place_id: str, user: dict = Depends(auth.get_current_user)):
    if not store.remove_business_favorite(user["id"], place_id):
        raise HTTPException(status_code=404, detail="Favori kaydı bulunamadı")


# ---- Hızlı mesajlar ----


@app.get("/api/quick-messages", response_model=list[QuickMessageOut])
def list_quick_messages(user: dict = Depends(auth.get_current_user)):
    return store.list_quick_messages(user["id"])


@app.post("/api/quick-messages", status_code=201, response_model=QuickMessageOut)
def add_quick_message(req: QuickMessageIn, user: dict = Depends(auth.get_current_user)):
    return store.add_quick_message(user["id"], req.text)


@app.delete("/api/quick-messages/{msg_id}", status_code=204)
def remove_quick_message(msg_id: str, user: dict = Depends(auth.get_current_user)):
    if not store.delete_quick_message(user["id"], msg_id):
        raise HTTPException(status_code=404, detail="Mesaj kaydı bulunamadı")
