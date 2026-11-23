"""Kaynaklardan gelen kayıtları doğrulayıp veritabanına işleyen ortak katman.

Her kaynak (web servis, lisanslı akış, CSV/Excel, PDF) kayıtlarını bu modülün beklediği
kanonik sözlük biçimine dönüştürür. Bu katman:
  * ham kaydı kanıt olarak saklar (aynı içerik ikinci kez işlenmez → idempotent),
  * yalnızca YENİ KURULUŞ ilanlarını kabul eder (şube, nakil, değişiklik vb. dışarıda kalır),
  * hedef il dışındaki kayıtları ayıklar,
  * mükerrer işletmeleri kesin anahtarlarla (MERSİS, sicil no, tam unvan) birleştirir,
  * belirsiz kayıtları tahminle doldurmak yerine 'inceleme bekliyor' olarak işaretler.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ANKARA_DISTRICTS
from app.models import Business, DataSource, ImportBatch, Opportunity, RawRecord, utcnow
from app.services import ttsg_parser
from app.services.dedup import find_existing
from app.services.normalize import (
    clean_mersis, clean_nace, clean_registry_no, content_hash, detect_company_type, detect_district,
    normalize_trade_name, parse_date, parse_decimal, registry_key,
)

# Başka illerde de bulunan ilçe adları: tek başına Ankara kanıtı sayılmaz
AMBIGUOUS_DISTRICTS = {"Gölbaşı", "Evren"}

CANONICAL_FIELDS = [
    "trade_name", "establishment_date", "registry_office", "registry_no", "mersis_no", "tax_no", "province",
    "district", "address", "activity_text", "nace_code", "nace_description", "nace_verified", "company_type",
    "capital", "announcement_url", "announcement_type", "gazette_date", "gazette_no", "gazette_page",
    "external_id", "source_reference",
]


@dataclass
class IngestResult:
    status: str  # created | updated | duplicate_raw | skipped_not_establishment | skipped_other_province | needs_review | error
    business_id: Optional[int] = None
    reason: Optional[str] = None
    raw_record_id: Optional[int] = None


def _canonicalize(rec: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: rec.get(k) for k in CANONICAL_FIELDS}
    for k, v in list(out.items()):
        if isinstance(v, str):
            v = v.strip()
            out[k] = v or None
    out["mersis_no"] = clean_mersis(out.get("mersis_no"))
    out["registry_no"] = clean_registry_no(out.get("registry_no"))
    out["nace_code"] = clean_nace(out.get("nace_code"))
    out["establishment_date"] = parse_date(out.get("establishment_date"))
    out["gazette_date"] = parse_date(out.get("gazette_date"))
    out["capital"] = parse_decimal(out.get("capital"))
    if not out.get("district") and out.get("address"):
        out["district"] = detect_district(out["address"])
    elif out.get("district"):
        out["district"] = detect_district(out["district"]) or out["district"]
    if not out.get("company_type") or out["company_type"] not in {"AS", "LTD", "KOLL", "KOM", "KOOP", "SAHIS", "DIGER"}:
        out["company_type"] = detect_company_type(out.get("trade_name"), out.get("company_type"))
    out["nace_verified"] = bool(out.get("nace_verified")) and bool(out.get("nace_code"))
    return out


def ingest_record(
    db: Session,
    source: DataSource,
    rec: Dict[str, Any],
    *,
    batch: Optional[ImportBatch] = None,
    raw_text: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    declared_establishment: bool = False,
    reviewed_by_user: bool = False,
) -> IngestResult:
    """Tek bir kaydı işler. Çağıran taraf commit eder."""
    payload = payload if payload is not None else {k: (str(v) if v is not None else None) for k, v in rec.items()}
    h = content_hash(raw_text if raw_text else payload)
    existing_raw = db.scalar(select(RawRecord).where(RawRecord.source_id == source.id, RawRecord.content_hash == h))
    if existing_raw and not reviewed_by_user:
        return IngestResult("duplicate_raw", existing_raw.business_id, "Bu kayıt daha önce işlendi", existing_raw.id)

    c = _canonicalize(rec)
    raw = existing_raw or RawRecord(
        source_id=source.id, import_batch_id=batch.id if batch else None, external_id=c.get("external_id"),
        content_hash=h, announcement_type=c.get("announcement_type"),
        published_date=c.get("gazette_date"), payload=payload, raw_text=raw_text,
    )
    if not existing_raw:
        db.add(raw)
        db.flush()

    def finish(status: str, reason: str, business_id: Optional[int] = None) -> IngestResult:
        raw.status = status
        raw.skip_reason = reason[:255] if reason else None
        raw.business_id = business_id
        return IngestResult(status, business_id, reason, raw.id)

    # 1) Yalnızca yeni kuruluşlar
    if reviewed_by_user:
        cls, why = ttsg_parser.ESTABLISHMENT, "Kullanıcı tarafından incelenip onaylandı"
    else:
        cls, why = ttsg_parser.classify_announcement(c.get("announcement_type"), raw_text)
        if cls == ttsg_parser.UNKNOWN and declared_establishment and not c.get("announcement_type"):
            cls, why = ttsg_parser.ESTABLISHMENT, "İçe aktaran kullanıcı kaydı yeni kuruluş olarak beyan etti"
    if cls == ttsg_parser.EXCLUDED:
        return finish("skipped_not_establishment", why)

    # 2) Hedef il
    province = settings.TARGET_PROVINCE
    in_target, why_prov = ttsg_parser.is_target_office(c.get("registry_office"), c.get("address"), province)
    if c.get("province") and in_target is None:
        in_target = c["province"].strip().upper().replace("İ", "I") in {province.upper(), "ANKARA"}
        why_prov = f"Kaynakta il alanı: {c['province']}"
    if in_target is None and declared_establishment and province.upper() == "ANKARA" \
            and c.get("district") in ANKARA_DISTRICTS and c.get("district") not in AMBIGUOUS_DISTRICTS:
        in_target, why_prov = True, f"Kullanıcı listesinde ilçe: {c['district']} (Ankara ilçesi)"
    if in_target is False:
        return finish("skipped_other_province", why_prov)

    if not c.get("trade_name"):
        return finish("needs_review", "Ticaret unvanı ayrıştırılamadı")
    if cls == ttsg_parser.UNKNOWN and not reviewed_by_user:
        return finish("needs_review", why)
    if in_target is None and not reviewed_by_user:
        return finish("needs_review", why_prov)

    # 3) Mükerrer kontrolü
    prov_label = "Ankara" if province.upper() == "ANKARA" else province.title()
    existing = find_existing(
        db, mersis_no=c.get("mersis_no"), registry_office=c.get("registry_office") or prov_label,
        registry_no=c.get("registry_no"), trade_name=c.get("trade_name"), province=prov_label,
    )
    now = utcnow()
    if existing:
        changed = _fill_missing(existing, c)
        if changed:
            existing.verified_at = now
            existing.analyzed_at = None  # yeni bilgiyle yeniden analiz
        return finish("updated" if changed else "duplicate_business", "Mevcut işletmeyle eşleşti", existing.id)

    b = Business(
        trade_name=c["trade_name"],
        name_normalized=normalize_trade_name(c["trade_name"]),
        establishment_date=c.get("establishment_date"),
        registry_office=c.get("registry_office") or prov_label,
        registry_no=c.get("registry_no"),
        registry_key=registry_key(c.get("registry_office") or prov_label, c.get("registry_no")),
        mersis_no=c.get("mersis_no"), tax_no=c.get("tax_no"),
        province=prov_label, district=c.get("district"), address=c.get("address"),
        activity_text=c.get("activity_text"), nace_code=c.get("nace_code"),
        nace_description=c.get("nace_description"), nace_verified=c.get("nace_verified", False),
        company_type=c.get("company_type"), capital=c.get("capital"),
        announcement_url=c.get("announcement_url"), gazette_date=c.get("gazette_date"),
        gazette_no=c.get("gazette_no"), gazette_page=c.get("gazette_page"),
        source_id=source.id, source_reference=c.get("source_reference"),
        verified_at=now,
        verification_status="manuel_dogrulandi" if reviewed_by_user else "kaynaktan_otomatik",
        first_seen_at=now, enrichment_status="bekliyor", sales_status="yeni",
    )
    db.add(b)
    db.flush()
    for line in ("isg", "yazilim"):
        db.add(Opportunity(business_id=b.id, service_line=line, stage="yeni", stage_changed_at=now))
    return finish("created", why, b.id)


def _fill_missing(b: Business, c: Dict[str, Any]) -> bool:
    changed = False
    mapping = {
        "establishment_date": "establishment_date", "registry_no": "registry_no", "mersis_no": "mersis_no",
        "tax_no": "tax_no", "district": "district", "address": "address", "activity_text": "activity_text",
        "nace_code": "nace_code", "nace_description": "nace_description", "capital": "capital",
        "announcement_url": "announcement_url", "gazette_date": "gazette_date", "gazette_no": "gazette_no",
        "gazette_page": "gazette_page",
    }
    for src_key, attr in mapping.items():
        if getattr(b, attr) in (None, "") and c.get(src_key) not in (None, ""):
            setattr(b, attr, c[src_key])
            changed = True
    if c.get("nace_verified") and c.get("nace_code") and not b.nace_verified:
        b.nace_code = c["nace_code"]
        b.nace_verified = True
        changed = True
    if b.registry_no and not b.registry_key:
        b.registry_key = registry_key(b.registry_office, b.registry_no)
    return changed


def summarize(results) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def today_tr() -> dt.date:
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo(settings.TIMEZONE)).date()
