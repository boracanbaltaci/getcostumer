from __future__ import annotations

import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    ACTIVITY_TYPES, ANKARA_DISTRICTS, COMPANY_TYPES, CONTACT_TYPES, IYS_STATUSES, ROLE_LABELS, SERVICE_LINES, STAGES,
)
from app.database import get_db
from app.deps import audit, get_current_user, require_role
from app.models import Activity, Business, ContactPoint, Opportunity, Quote, RawRecord, User, utcnow
from app.schemas import BusinessUpdate, ComplianceUpdate, ContactCreate, ContactUpdate, MergeIn
from app.serializers import activity_out, business_detail, business_summary, quote_out, raw_out
from app.services import dedup, retention
from app.services.contacts import add_contact
from app.services.enrichment.orchestrator import enrich_business
from app.services.enrichment.providers import google_place_live_details
from app.services.normalize import clean_mersis, clean_nace, fold, normalize_trade_name, registry_key
from app.services.reports import TZ, has_contact_clause, ref_date_col
from app.services.scoring.engine import analyze_business
from app.services.scoring.sectors import SECTORS

router = APIRouter(tags=["businesses"])


@router.get("/meta")
def meta(_: User = Depends(get_current_user)):
    return {
        "districts": ANKARA_DISTRICTS, "stages": [{"key": k, "label": v} for k, v in STAGES],
        "company_types": [{"key": k, "label": v} for k, v in COMPANY_TYPES.items()],
        "sectors": [{"key": k, "label": v["label"]} for k, v in SECTORS.items()],
        "service_lines": [{"key": k, "label": v} for k, v in SERVICE_LINES.items()],
        "contact_types": CONTACT_TYPES, "activity_types": ACTIVITY_TYPES, "iys_statuses": IYS_STATUSES,
        "roles": ROLE_LABELS,
    }


def build_query(
    q: Optional[str] = None, district: Optional[List[str]] = None, date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None, sector: Optional[List[str]] = None, company_type: Optional[List[str]] = None,
    isg_min: Optional[int] = None, software_min: Optional[int] = None, has_contact: Optional[bool] = None,
    sales_status: Optional[List[str]] = None, priority: Optional[List[str]] = None,
    service_line: Optional[str] = None, stage: Optional[List[str]] = None, owner_id: Optional[int] = None,
    detected_from: Optional[dt.date] = None, include_inactive: bool = False, sort: str = "-total_score",
) -> Select:
    stmt = select(Business)
    if not include_inactive:
        stmt = stmt.where(Business.is_active.is_(True))
    if q:
        fq = fold(q)
        digits = "".join(ch for ch in q if ch.isdigit())
        conds = [Business.name_normalized.like(f"%{fq}%")]
        if len(digits) >= 4:
            conds += [Business.mersis_no.like(f"%{digits}%"), Business.registry_no.like(f"%{digits}%")]
        stmt = stmt.where(or_(*conds))
    if district:
        stmt = stmt.where(Business.district.in_(district))
    if date_from:
        stmt = stmt.where(ref_date_col() >= date_from)
    if date_to:
        stmt = stmt.where(ref_date_col() <= date_to)
    if detected_from:
        stmt = stmt.where(Business.first_seen_at >= dt.datetime.combine(detected_from, dt.time.min, tzinfo=TZ))
    if sector:
        stmt = stmt.where(Business.sector.in_(sector))
    if company_type:
        stmt = stmt.where(Business.company_type.in_(company_type))
    if isg_min is not None:
        stmt = stmt.where(Business.isg_score >= isg_min)
    if software_min is not None:
        stmt = stmt.where(Business.software_score >= software_min)
    if has_contact is True:
        stmt = stmt.where(has_contact_clause())
    elif has_contact is False:
        stmt = stmt.where(~has_contact_clause())
    if sales_status:
        stmt = stmt.where(Business.sales_status.in_(sales_status))
    if priority:
        stmt = stmt.where(Business.priority.in_(priority))
    if owner_id:
        stmt = stmt.where(Business.owner_id == owner_id)
    if stage:
        conds = [Opportunity.business_id == Business.id, Opportunity.stage.in_(stage)]
        if service_line:
            conds.append(Opportunity.service_line == service_line)
        stmt = stmt.where(exists().where(and_(*conds)))
    sort_map = {
        "total_score": Business.total_score, "isg_score": Business.isg_score, "software_score": Business.software_score,
        "establishment_date": ref_date_col(), "first_seen_at": Business.first_seen_at, "trade_name": Business.name_normalized,
    }
    desc = sort.startswith("-")
    col = sort_map.get(sort.lstrip("-"), Business.total_score)
    stmt = stmt.order_by(col.desc().nulls_last() if desc else col.asc().nulls_last(), Business.id.desc())
    return stmt


def list_params(
    q: Optional[str] = None, district: Optional[List[str]] = Query(None), date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None, sector: Optional[List[str]] = Query(None),
    company_type: Optional[List[str]] = Query(None), isg_min: Optional[int] = None, software_min: Optional[int] = None,
    has_contact: Optional[bool] = None, sales_status: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None), service_line: Optional[str] = None,
    stage: Optional[List[str]] = Query(None), owner_id: Optional[int] = None, detected_from: Optional[dt.date] = None,
    include_inactive: bool = False, sort: str = "-total_score",
):
    return dict(q=q, district=district, date_from=date_from, date_to=date_to, sector=sector, company_type=company_type,
                isg_min=isg_min, software_min=software_min, has_contact=has_contact, sales_status=sales_status,
                priority=priority, service_line=service_line, stage=stage, owner_id=owner_id,
                detected_from=detected_from, include_inactive=include_inactive, sort=sort)


@router.get("/businesses")
def list_businesses(params: dict = Depends(list_params), page: int = 1, page_size: int = Query(50, le=200),
                    db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = build_query(**params)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.options(selectinload(Business.contacts), selectinload(Business.opportunities))
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [business_summary(b) for b in rows]}


def _get(db: Session, bid: int) -> Business:
    b = db.get(Business, bid)
    if not b:
        raise HTTPException(404, "İşletme bulunamadı")
    return b


@router.get("/businesses/merge-candidates")
def merge_candidates(threshold: int = 90, db: Session = Depends(get_db), _: User = Depends(require_role("sales"))):
    return dedup.find_merge_candidates(db, threshold=threshold)


@router.post("/businesses/merge")
def merge(body: MergeIn, db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    try:
        tgt = dedup.merge_businesses(db, body.source_id, body.target_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    tgt.analyzed_at = None
    audit(db, user, "business_merge", "business", tgt.id, {"merged": body.source_id})
    db.commit()
    return business_detail(tgt)


@router.get("/businesses/{bid}")
def get_business(bid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    b = _get(db, bid)
    d = business_detail(b)
    d["activities"] = [activity_out(a) for a in db.scalars(
        select(Activity).where(Activity.business_id == bid).order_by(Activity.occurred_at.desc())).all()]
    d["quotes"] = [quote_out(q) for q in db.scalars(
        select(Quote).where(Quote.business_id == bid).order_by(Quote.created_at.desc())).all()]
    d["raw_records"] = [raw_out(r) for r in db.scalars(
        select(RawRecord).where(RawRecord.business_id == bid).order_by(RawRecord.fetched_at.desc()).limit(20)).all()]
    audit(db, user, "business_view", "business", bid, request=request)
    db.commit()
    return d


@router.patch("/businesses/{bid}")
def update_business(bid: int, body: BusinessUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    data = body.model_dump(exclude_unset=True)
    if "mersis_no" in data:
        data["mersis_no"] = clean_mersis(data["mersis_no"]) if data["mersis_no"] else None
        if data["mersis_no"] and db.scalar(select(Business.id).where(Business.mersis_no == data["mersis_no"], Business.id != bid)):
            raise HTTPException(400, "Bu MERSİS numarası başka bir işletmede kayıtlı (birleştirme kullanın)")
    if "nace_code" in data:
        data["nace_code"] = clean_nace(data["nace_code"])
    for k, v in data.items():
        setattr(b, k, v)
    if "trade_name" in data:
        b.name_normalized = normalize_trade_name(b.trade_name)
    if "registry_no" in data or "registry_office" in data:
        rk = registry_key(b.registry_office, b.registry_no)
        if rk and db.scalar(select(Business.id).where(Business.registry_key == rk, Business.id != bid)):
            raise HTTPException(400, "Bu sicil numarası başka bir işletmede kayıtlı (birleştirme kullanın)")
        b.registry_key = rk
    if data.get("verification_status") == "manuel_dogrulandi":
        b.verified_at = utcnow()
    b.analyzed_at = None
    audit(db, user, "business_update", "business", bid, {k: str(v) for k, v in data.items()})
    db.commit()
    analyze_business(db, b, use_llm=False)
    db.commit()
    return business_detail(b)


@router.post("/businesses/{bid}/enrich")
def enrich(bid: int, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    log = enrich_business(db, b)
    analyze_business(db, b, use_llm=False)
    audit(db, user, "business_enrich", "business", bid)
    db.commit()
    return {"log": log, "business": business_detail(b)}


@router.post("/businesses/{bid}/analyze")
def analyze(bid: int, use_llm: bool = True, db: Session = Depends(get_db), _: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    analyze_business(db, b, use_llm=use_llm)
    db.commit()
    return business_detail(b)


@router.post("/businesses/{bid}/contacts")
def add_contact_ep(bid: int, body: ContactCreate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    cp, why = add_contact(db, b, body.type, body.value, source_name=body.source_name, source_url=body.source_url,
                          confidence=80 if body.source_url else 60, evidence=body.note or f"{user.full_name} tarafından eklendi",
                          status="dogrulandi" if body.source_url else "aday")
    if not cp:
        raise HTTPException(400, f"Kaydedilmedi: {why}")
    if cp.status == "dogrulandi":
        cp.verified_at, cp.verified_by = utcnow(), user.id
    b.analyzed_at = None
    if b.enrichment_status in ("bekliyor", "bulunamadi"):
        b.enrichment_status = "tamamlandi"
    audit(db, user, "contact_add", "business", bid, {"type": body.type})
    db.commit()
    analyze_business(db, b, use_llm=False)
    db.commit()
    return business_detail(b)


@router.patch("/contacts/{cid}")
def update_contact(cid: int, body: ContactUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    c = db.get(ContactPoint, cid)
    if not c:
        raise HTTPException(404, "Kayıt bulunamadı")
    c.status = body.status
    c.verified_at = utcnow() if body.status == "dogrulandi" else None
    c.verified_by = user.id if body.status == "dogrulandi" else None
    b = c.business
    audit(db, user, "contact_status", "contact", cid, {"status": body.status})
    db.commit()
    analyze_business(db, b, use_llm=False)
    db.commit()
    return business_detail(b)


@router.delete("/contacts/{cid}")
def delete_contact(cid: int, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    c = db.get(ContactPoint, cid)
    if not c:
        raise HTTPException(404, "Kayıt bulunamadı")
    b = c.business
    db.delete(c)
    audit(db, user, "contact_delete", "contact", cid)
    db.commit()
    db.refresh(b)
    return business_detail(b)


@router.get("/businesses/{bid}/places-live")
def places_live(bid: int, db: Session = Depends(get_db), _: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    gp = next((c for c in b.contacts if c.type == "map_profile" and "place_id:" in c.value), None)
    if not gp:
        raise HTTPException(404, "Google Places eşleşmesi yok")
    try:
        return google_place_live_details(gp.value.split("place_id:")[1])
    except Exception as exc:
        raise HTTPException(502, f"Google Places erişilemedi: {exc}")


@router.post("/businesses/{bid}/compliance")
def compliance(bid: int, body: ComplianceUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    b = _get(db, bid)
    if body.iys_status is not None:
        b.iys_status = body.iys_status
        b.iys_checked_at = utcnow()
    if body.do_not_contact is not None:
        b.do_not_contact = body.do_not_contact
    audit(db, user, "compliance_update", "business", bid, body.model_dump(exclude_none=True))
    db.commit()
    return business_detail(b)


@router.get("/businesses/{bid}/outreach-check")
def outreach_check(bid: int, channel: str = "email", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Ticari ileti göndermeden önce hukuki uygunluk kontrolü (6563 sayılı Kanun / İYS / KVKK)."""
    b = _get(db, bid)
    blockers, warnings = [], []
    if b.do_not_contact:
        blockers.append("İşletme 'iletişime geçme' olarak işaretli")
    if b.iys_status == "ret":
        blockers.append("İYS'de ret / itiraz kaydı var")
    if b.anonymized_at:
        blockers.append("Kayıt KVKK kapsamında anonimleştirilmiş")
    if channel in ("email", "sms") and b.iys_status == "bilinmiyor":
        blockers.append("Elektronik ticari ileti öncesi İYS kontrolü yapılmalı (tacir/esnaf alıcılar ret hakkına sahiptir)")
    if b.company_type == "SAHIS":
        warnings.append("Gerçek kişi ticari işletmesi: iletişim bilgileri kişisel veri sayılabilir; KVKK aydınlatma "
                        "yükümlülüğünü yerine getirin")
    target = {"email": "email", "sms": "phone", "phone": "phone"}.get(channel, "email")
    c = [x for x in b.contacts if x.type == target and x.status != "reddedildi"]
    if not c:
        blockers.append("Bu kanal için kayıtlı kurumsal iletişim bilgisi yok")
    elif any(x.personal_data_risk for x in c):
        warnings.append("İletişim bilgisi kişisel veri olabilir")
    warnings.append("Sistem otomatik pazarlama iletisi göndermez; ileti içeriği ve ret bağlantısı mevzuata uygun olmalıdır")
    return {"allowed": not blockers, "blockers": blockers, "warnings": warnings}


@router.post("/businesses/{bid}/kvkk/anonymize")
def kvkk_anonymize(bid: int, reason: str = "İlgili kişi talebi", db: Session = Depends(get_db),
                   user: User = Depends(require_role("manager"))):
    b = _get(db, bid)
    retention.anonymize_business(db, b, user.id, reason)
    db.commit()
    return business_detail(b)
