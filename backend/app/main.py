from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import BusinessOut, ConfigOut, ScanRequest, ScanResponse, ScanStats
from app.services import places, sitescan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="İşletme Radarı API", version="1.0.0",
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"api": "ok"}


@app.get("/api/config", response_model=ConfigOut)
def get_config():
    return ConfigOut(google_places_configured=settings.google_configured)


@app.post("/api/scan", response_model=ScanResponse)
def scan(req: ScanRequest):
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
        try:
            verdict = sitescan.check_website(rec["website"], now_year)
        except Exception as exc:  # dayanıklı kayıt: site analizi patlarsa 'erişilemedi' say
            logger.warning("Site analizi başarısız %s: %s", rec.get("website"), exc)
            return BusinessOut(**rec, website_status="erisilemedi",
                               website_notes=[f"analiz hatası: {exc.__class__.__name__}"])
        if verdict.status == "modern":
            return None
        return BusinessOut(**rec, website_status=verdict.status,
                           website=verdict.final_url or rec["website"],
                           website_notes=verdict.notes)

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
    return ScanResponse(businesses=businesses, stats=stats, warnings=warnings)
