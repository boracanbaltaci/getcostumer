"""Veri kaynağı tanımları ve otomatik kaynak adaptörleri.

Otomatik adaptörler YALNIZCA yetkili erişim yollarını kullanır:
  * ttsg_ws        – TOBB TTSG 'Veri Aboneliği' web servisi (ücretli abonelik + sözleşme)
  * licensed_feed  – Lisanslı ticari veri sağlayıcısının API'si / dosya akışı
  * ttsg_inbox     – Satın alınan günlük elektronik gazete / fihrist dosyalarının bırakıldığı klasör
Diğer resmî kaynaklar 'reference' olarak listelenir; erişim kısıtlı olduğu için otomasyon yapılmaz.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DataSource, ImportBatch, SourceCoverage, utcnow
from app.services import ingestion
from app.services.coverage import mark_coverage

SOURCE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "ttsg_ws", "name": "TTSG Veri Aboneliği – Web Servis (TOBB)", "kind": "webservice", "automated": True,
        "url": "https://www.ticaretsicil.gov.tr/view/hizlierisim/goster.php?Guid=4fb204d4-8b72-11e9-a292-54e058904e0d",
        "legal_basis": "TOBB Türkiye Ticaret Sicili Gazetesi Müdürlüğü ile imzalanan veri aboneliği sözleşmesi "
                       "(Düzey_1/2/3). Teslim şekli: web servis.",
        "access_notes": "En hızlı ve tek resmî otomatik kanal. Düzey_2: MERSİS no ve kuruluş adresi; Düzey_3: "
                        "ek olarak NACE kodları, amaç-konu, sermaye, UAVT adres kodu. Web servis teknik dokümanı "
                        "abonelik sonrası verilir; alan eşlemesi TTSG_WS_FIELD_MAP ile ayarlanır.",
    },
    {
        "key": "ttsg_inbox", "name": "TTSG Günlük Elektronik Gazete (satın alınan PDF/fihrist – klasör)",
        "kind": "inbox", "automated": True,
        "url": "https://www.ticaretsicil.gov.tr/view/hizlierisim/goster.php?Guid=4fb204d4-8b72-11e9-a292-54e058904e0d",
        "legal_basis": "TOBB'dan ücret karşılığı temin edilen 'Bir Günlük Elektronik Gazete' (PDF + fihrist Excel) "
                       "veya Düzey_1 abonelik PDF'leri.",
        "access_notes": "Dosyalar INBOX_DIR klasörüne bırakılır; günlük görev otomatik içe aktarır. Fihrist Excel "
                        "ilan türünü içerdiğinden kuruluş ilanları güvenle filtrelenir.",
    },
    {
        "key": "licensed_feed", "name": "Lisanslı Ticari Veri Sağlayıcı Akışı", "kind": "feed", "automated": True,
        "legal_basis": "Sağlayıcı ile yapılan lisans sözleşmesi; verinin satış/pazarlama amaçlı işlenmesine izin "
                       "verdiği ve KVKK aydınlatma yükümlülüklerini karşıladığı teyit edilmelidir.",
        "access_notes": "JSON veya CSV; LICENSED_FEED_URL içinde {date_from} ve {date_to} yer tutucuları kullanılabilir.",
    },
    {
        "key": "manual_import", "name": "Manuel İçe Aktarma (CSV / Excel / PDF)", "kind": "manual", "automated": False,
        "legal_basis": "Kullanıcının hukuka uygun yoldan edindiği dosyalar (ör. TTSG üyeliğiyle görüntülenip indirilen "
                       "ilanlar, oda/sicil müdürlüğünden yazılı talep ile alınan listeler).",
        "access_notes": "Arayüzdeki 'İçe Aktar' ekranından yüklenir.",
    },
    {
        "key": "ttsg_web", "name": "ticaretsicil.gov.tr – İlan Görüntüleme", "kind": "reference", "automated": False,
        "url": "https://www.ticaretsicil.gov.tr/view/hizlierisim/ilangoruntuleme.php",
        "legal_basis": "Ücretsiz üyelik veya e-Devlet ile kişisel görüntüleme.",
        "access_notes": "Üye girişi + güvenlik kodu (CAPTCHA) zorunlu. Otomatik tarama YAPILMAZ. Kullanıcı ilanı "
                        "kendisi görüntüleyip PDF olarak indirebilir ve Manuel İçe Aktarma ile yükleyebilir.",
    },
    {
        "key": "mersis", "name": "MERSİS (Ticaret Bakanlığı)", "kind": "reference", "automated": False,
        "url": "https://mersis.gtb.gov.tr/",
        "legal_basis": "e-Devlet / e-imza / mobil imza ile kimlik doğrulamalı erişim.",
        "access_notes": "Kamuya açık toplu sorgu veya API yok. Firma sorgusu kimlik doğrulaması gerektirir; "
                        "otomasyon yapılmaz. MERSİS numarası TTSG Düzey_2/3 aboneliğinden gelir.",
    },
    {
        "key": "ato", "name": "Ankara Ticaret Odası / Ankara Ticaret Sicili Müdürlüğü", "kind": "reference",
        "automated": False, "url": "https://www.atonet.org.tr/",
        "legal_basis": "Yeni kayıt listesi için kamuya açık bir veri seti tespit edilmedi.",
        "access_notes": "Toplu yeni kayıt listesi yalnızca yazılı talep / protokol ile mümkün olabilir. Gelen "
                        "listeler Manuel İçe Aktarma ile yüklenebilir.",
    },
    {
        "key": "aso", "name": "Ankara Sanayi Odası", "kind": "reference", "automated": False,
        "url": "https://www.aso.org.tr/",
        "legal_basis": "Üye sanayicilere yönelik kayıt; yeni kuruluş ilanı yayımlamaz.",
        "access_notes": "Sanayi sicil/üye bilgisi yeni kuruluş tespiti için gecikmeli ve sınırlıdır.",
    },
    {
        "key": "tobb_stats", "name": "TOBB Kurulan/Kapanan Şirket İstatistikleri", "kind": "reference",
        "automated": False,
        "url": "https://www.tobb.org.tr/BilgiErisimMudurlugu/Sayfalar/KurulanKapananSirketistatistikleri.php",
        "legal_basis": "Kamuya açık istatistik.",
        "access_notes": "Yalnızca toplu sayılar (il/ay bazında); şirket bazlı kayıt içermez. Kapsam kontrolü "
                        "(aylık beklenen kuruluş sayısı ile karşılaştırma) için kullanılabilir.",
    },
]


def seed_sources(db: Session) -> None:
    for d in SOURCE_DEFINITIONS:
        src = db.scalar(select(DataSource).where(DataSource.key == d["key"]))
        if src is None:
            src = DataSource(key=d["key"], enabled=d["kind"] in ("manual", "inbox"), config={})
            db.add(src)
        src.name = d["name"]
        src.kind = d["kind"]
        src.automated = d["automated"]
        src.url = d.get("url")
        src.legal_basis = d.get("legal_basis")
        src.access_notes = d.get("access_notes")
        if d["kind"] == "reference":
            src.health = "manual"
            src.enabled = False
        elif d["kind"] == "manual":
            src.health = "manual"
    db.flush()


def get_source(db: Session, key: str) -> DataSource:
    src = db.scalar(select(DataSource).where(DataSource.key == key))
    if src is None:
        seed_sources(db)
        src = db.scalar(select(DataSource).where(DataSource.key == key))
    return src


# ----------------------------------------------------------------------------------------------
# Adaptörler
# ----------------------------------------------------------------------------------------------

@dataclass
class AdapterResult:
    days: Dict[str, str] = field(default_factory=dict)  # gün -> covered | failed
    created: int = 0
    stats: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    log: List[str] = field(default_factory=list)


class BaseAdapter:
    key = ""

    def is_configured(self) -> Tuple[bool, str]:
        return False, "Yapılandırılmadı"

    def run(self, db: Session, source: DataSource, start: dt.date, end: dt.date, job_id: Optional[int]) -> AdapterResult:
        raise NotImplementedError

    @staticmethod
    def _ingest_day(db: Session, source: DataSource, day: dt.date, records: List[Dict[str, Any]],
                    job_id: Optional[int], res: AdapterResult) -> None:
        created = 0
        for rec in records:
            rec.setdefault("gazette_date", day.isoformat())
            with db.begin_nested():
                r = ingestion.ingest_record(db, source, rec, raw_text=rec.pop("_raw_text", None),
                                            payload=dict(rec), declared_establishment=False)
            res.stats[r.status] = res.stats.get(r.status, 0) + 1
            if r.status == "created":
                created += 1
        res.created += created
        res.days[day.isoformat()] = "covered"
        mark_coverage(db, source, day, "covered", records_found=len(records), new_businesses=created, job_run_id=job_id)


def _load_map(raw: Optional[str], default: Dict[str, Any]) -> Dict[str, Any]:
    if not raw:
        return default
    try:
        cfg = json.loads(raw)
        merged = dict(default)
        merged.update(cfg)
        if "fields" in cfg:
            f = dict(default.get("fields", {}))
            f.update(cfg["fields"])
            merged["fields"] = f
        return merged
    except json.JSONDecodeError:
        return default


def _map_item(item: Dict[str, Any], fields: Dict[str, str]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {}
    for canon, src_key in fields.items():
        val: Any = item
        for part in str(src_key).split("."):
            val = val.get(part) if isinstance(val, dict) else None
        if isinstance(val, list):
            val = ", ".join(str(v.get("kod", v)) if isinstance(v, dict) else str(v) for v in val)
        if val not in (None, ""):
            rec[canon] = val
    return rec


def _daterange(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


class TtsgWebServiceAdapter(BaseAdapter):
    """TTSG Veri Aboneliği web servisi.

    Varsayılan alan adları abonelik sayfasında listelenen veri seti başlıklarından türetilmiştir
    (TSM, TSM No, Unvan1, Unvan2, İlan Türü, Yayın Tarihi, Sayısı, Baş Sayfa, MERSİS No, Adres,
    Ana NACE Kodu, Amaç Konu, Toplam Sermaye). Gerçek JSON anahtarları TOBB'un vereceği teknik
    dokümana göre TTSG_WS_FIELD_MAP ile güncellenmelidir.
    """
    key = "ttsg_ws"
    DEFAULT_MAP: Dict[str, Any] = {
        "path": "/ilanlar?yayinTarihi={date}",
        "items_key": "ilanlar",
        "auth": "basic",  # basic | bearer | header
        "auth_header": "Authorization",
        "nace_is_official": True,
        "fields": {
            "registry_office": "TSM", "registry_no": "TSMNo", "trade_name": "Unvan1", "trade_name_2": "Unvan2",
            "announcement_type": "IlanTuru", "gazette_date": "YayinTarihi", "gazette_no": "Sayisi",
            "gazette_page": "BasSayfa", "mersis_no": "MersisNo", "address": "Adres", "nace_code": "AnaNaceKodu",
            "nace_description": "AnaNaceKonuAciklamasi", "activity_text": "AmacKonu", "capital": "ToplamSermaye",
            "tax_no": "VergiNo", "external_id": "IlanId", "announcement_url": "IlanUrl",
        },
    }

    def is_configured(self) -> Tuple[bool, str]:
        if not settings.TTSG_WS_ENABLED:
            return False, "TTSG_WS_ENABLED=false (abonelik bilgileri girilmedi)"
        if not settings.TTSG_WS_BASE_URL:
            return False, "TTSG_WS_BASE_URL tanımlı değil"
        if not (settings.TTSG_WS_TOKEN or (settings.TTSG_WS_USERNAME and settings.TTSG_WS_PASSWORD)):
            return False, "Web servis kimlik bilgileri tanımlı değil"
        return True, "Yapılandırıldı"

    def _client(self, cfg: Dict[str, Any]) -> httpx.Client:
        headers = {"Accept": "application/json", "User-Agent": settings.ENRICHMENT_USER_AGENT}
        auth = None
        if settings.TTSG_WS_TOKEN:
            if cfg.get("auth") == "header":
                headers[cfg.get("auth_header", "Authorization")] = settings.TTSG_WS_TOKEN
            else:
                headers["Authorization"] = f"Bearer {settings.TTSG_WS_TOKEN}"
        elif settings.TTSG_WS_USERNAME:
            auth = (settings.TTSG_WS_USERNAME, settings.TTSG_WS_PASSWORD or "")
        return httpx.Client(base_url=settings.TTSG_WS_BASE_URL.rstrip("/"), headers=headers, auth=auth, timeout=60)

    def run(self, db, source, start, end, job_id) -> AdapterResult:
        res = AdapterResult()
        cfg = _load_map(settings.TTSG_WS_FIELD_MAP, self.DEFAULT_MAP)
        with self._client(cfg) as client:
            for day in _daterange(start, end):
                path = cfg["path"].format(date=day.isoformat(), date_tr=day.strftime("%d.%m.%Y"))
                try:
                    resp = client.get(path)
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get(cfg["items_key"], []) if isinstance(data, dict) else data
                    records = []
                    for it in items or []:
                        rec = _map_item(it, cfg["fields"])
                        if rec.get("trade_name_2"):
                            rec["trade_name"] = f"{rec.get('trade_name', '')} {rec.pop('trade_name_2')}".strip()
                        rec["nace_verified"] = bool(cfg.get("nace_is_official") and rec.get("nace_code"))
                        rec.setdefault("source_reference", f"TTSG WS {day.isoformat()} #{rec.get('external_id', '')}")
                        records.append(rec)
                    self._ingest_day(db, source, day, records, job_id, res)
                    res.log.append(f"{day}: {len(records)} ilan alındı")
                except Exception as exc:  # gün bazında hata → o gün 'taranamadı'
                    res.days[day.isoformat()] = "failed"
                    res.errors.append(f"{day}: {exc}")
                    mark_coverage(db, source, day, "failed", job_run_id=job_id, notes=str(exc)[:500])
        return res


class LicensedFeedAdapter(BaseAdapter):
    key = "licensed_feed"
    DEFAULT_MAP: Dict[str, Any] = {"items_key": "data", "fields": {
        "trade_name": "trade_name", "establishment_date": "establishment_date", "registry_office": "registry_office",
        "registry_no": "registry_no", "mersis_no": "mersis_no", "address": "address", "district": "district",
        "province": "province", "activity_text": "activity", "nace_code": "nace_code",
        "announcement_type": "announcement_type", "announcement_url": "announcement_url",
        "gazette_date": "gazette_date", "external_id": "id", "company_type": "company_type", "capital": "capital",
    }, "nace_is_official": False}

    def is_configured(self) -> Tuple[bool, str]:
        if not settings.LICENSED_FEED_ENABLED:
            return False, "LICENSED_FEED_ENABLED=false"
        if not settings.LICENSED_FEED_URL:
            return False, "LICENSED_FEED_URL tanımlı değil"
        return True, "Yapılandırıldı"

    def run(self, db, source, start, end, job_id) -> AdapterResult:
        res = AdapterResult()
        cfg = _load_map(settings.LICENSED_FEED_FIELD_MAP, self.DEFAULT_MAP)
        url = settings.LICENSED_FEED_URL.format(date_from=start.isoformat(), date_to=end.isoformat())
        headers = {"User-Agent": settings.ENRICHMENT_USER_AGENT}
        if settings.LICENSED_FEED_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LICENSED_FEED_API_KEY}"
        try:
            resp = httpx.get(url, headers=headers, timeout=120)
            resp.raise_for_status()
            if settings.LICENSED_FEED_FORMAT == "csv":
                items = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig"))))
            else:
                data = resp.json()
                items = data.get(cfg["items_key"], []) if isinstance(data, dict) else data
        except Exception as exc:
            for day in _daterange(start, end):
                res.days[day.isoformat()] = "failed"
                mark_coverage(db, source, day, "failed", job_run_id=job_id, notes=str(exc)[:500])
            res.errors.append(str(exc))
            return res
        by_day: Dict[dt.date, List[Dict[str, Any]]] = {d: [] for d in _daterange(start, end)}
        from app.services.normalize import parse_date
        for it in items:
            rec = _map_item(it, cfg["fields"])
            rec["nace_verified"] = bool(cfg.get("nace_is_official") and rec.get("nace_code"))
            d = parse_date(rec.get("gazette_date")) or parse_date(rec.get("establishment_date")) or end
            by_day.setdefault(d, []).append(rec)
        for day, recs in sorted(by_day.items()):
            self._ingest_day(db, source, day, recs, job_id, res)
        return res


class InboxAdapter(BaseAdapter):
    """INBOX_DIR klasörüne bırakılan günlük gazete PDF'lerini / fihrist Excel dosyalarını içe aktarır."""
    key = "ttsg_inbox"
    EXTS = (".pdf", ".xlsx", ".xlsm", ".csv")

    def is_configured(self) -> Tuple[bool, str]:
        if not os.path.isdir(settings.INBOX_DIR):
            return False, f"Klasör bulunamadı: {settings.INBOX_DIR}"
        return True, "Klasör hazır"

    def pending_files(self) -> List[str]:
        if not os.path.isdir(settings.INBOX_DIR):
            return []
        return sorted(
            os.path.join(settings.INBOX_DIR, f) for f in os.listdir(settings.INBOX_DIR)
            if f.lower().endswith(self.EXTS) and os.path.isfile(os.path.join(settings.INBOX_DIR, f))
        )

    def run(self, db, source, start, end, job_id) -> AdapterResult:
        from app.services.importers.runner import already_imported, run_import
        res = AdapterResult()
        processed_dir = os.path.join(settings.INBOX_DIR, "islenen")
        failed_dir = os.path.join(settings.INBOX_DIR, "hatali")
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(failed_dir, exist_ok=True)
        for path in self.pending_files():
            name = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            if already_imported(db, data):
                res.log.append(f"{name}: daha önce içe aktarılmış, atlandı")
                shutil.move(path, os.path.join(processed_dir, name))
                continue
            batch: ImportBatch = run_import(db, source, name, data, declared_establishment=False,
                                            marks_full_day=True, job_run_id=job_id)
            for k, v in (batch.stats or {}).items():
                if isinstance(v, int):
                    res.stats[k] = res.stats.get(k, 0) + v
            res.created += (batch.stats or {}).get("created", 0)
            if batch.status == "completed":
                res.log.append(f"{name}: {batch.stats}")
                shutil.move(path, os.path.join(processed_dir, name))
            else:
                res.errors.append(f"{name}: {batch.errors[:1]}")
                shutil.move(path, os.path.join(failed_dir, name))
        if job_id:
            for cov in db.scalars(select(SourceCoverage).where(SourceCoverage.source_id == source.id,
                                                               SourceCoverage.job_run_id == job_id)).all():
                res.days[cov.coverage_date.isoformat()] = cov.status
        if not res.log and not res.errors:
            res.log.append("Klasörde yeni dosya yok")
        return res


ADAPTERS: Dict[str, BaseAdapter] = {
    "ttsg_ws": TtsgWebServiceAdapter(),
    "ttsg_inbox": InboxAdapter(),
    "licensed_feed": LicensedFeedAdapter(),
}


def last_covered_date(db: Session, source: DataSource) -> Optional[dt.date]:
    return db.scalar(select(func.max(SourceCoverage.coverage_date)).where(
        SourceCoverage.source_id == source.id, SourceCoverage.status == "covered"))


def check_health(db: Session, source: DataSource) -> Tuple[str, str]:
    adapter = ADAPTERS.get(source.key)
    if source.kind in ("reference", "manual") or adapter is None:
        return "manual", source.access_notes or ""
    ok, msg = adapter.is_configured()
    source.last_checked_at = utcnow()
    if not ok:
        source.health = "not_configured"
        source.last_error = msg
        return "not_configured", msg
    if source.health not in ("ok", "error"):
        source.health = "ok"
    return source.health, msg
