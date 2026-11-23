"""Model → JSON dönüştürücüler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.constants import COMPANY_TYPES, STAGE_LABELS
from app.models import Activity, Business, ContactPoint, Opportunity, Quote, RawRecord, User
from app.services.contacts import best_contacts
from app.services.scoring.sectors import HAZARD_LABELS, SECTORS


def _f(v):
    return float(v) if v is not None else None


def user_out(u: Optional[User]) -> Optional[Dict[str, Any]]:
    if not u:
        return None
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
            "last_login_at": u.last_login_at, "created_at": u.created_at}


def contact_out(c: Optional[ContactPoint]) -> Optional[Dict[str, Any]]:
    if not c:
        return None
    return {"id": c.id, "type": c.type, "value": c.value, "source_name": c.source_name, "source_url": c.source_url,
            "confidence": c.confidence, "confidence_level": c.confidence_level, "evidence": c.evidence,
            "status": c.status, "is_corporate": c.is_corporate, "personal_data_risk": c.personal_data_risk,
            "found_at": c.found_at, "verified_at": c.verified_at}


def opportunity_out(o: Opportunity) -> Dict[str, Any]:
    return {"id": o.id, "business_id": o.business_id, "service_line": o.service_line, "stage": o.stage,
            "stage_label": STAGE_LABELS.get(o.stage, o.stage), "owner": user_out(o.owner),
            "owner_id": o.owner_id, "estimated_value": _f(o.estimated_value), "currency": o.currency,
            "next_action": o.next_action, "next_action_date": o.next_action_date, "lost_reason": o.lost_reason,
            "stage_changed_at": o.stage_changed_at, "won_at": o.won_at, "updated_at": o.updated_at}


def business_summary(b: Business) -> Dict[str, Any]:
    c = best_contacts(b)
    hide = b.do_not_contact
    return {
        "id": b.id, "trade_name": b.trade_name, "establishment_date": b.establishment_date,
        "gazette_date": b.gazette_date, "first_seen_at": b.first_seen_at, "district": b.district,
        "province": b.province, "company_type": b.company_type,
        "company_type_label": COMPANY_TYPES.get(b.company_type or "", b.company_type),
        "sector": b.sector, "sector_label": SECTORS.get(b.sector or "", {}).get("label"),
        "sector_basis": b.sector_basis, "nace_code": b.nace_code, "nace_verified": b.nace_verified,
        "isg_score": b.isg_score, "software_score": b.software_score, "total_score": b.total_score,
        "priority": b.priority, "sales_status": b.sales_status,
        "sales_status_label": STAGE_LABELS.get(b.sales_status, b.sales_status),
        "phone": None if hide else contact_out(c["phone"]), "email": None if hide else contact_out(c["email"]),
        "website": contact_out(c["website"]), "enrichment_status": b.enrichment_status,
        "do_not_contact": b.do_not_contact, "iys_status": b.iys_status,
        "opportunities": {o.service_line: {"id": o.id, "stage": o.stage, "stage_label": STAGE_LABELS.get(o.stage)}
                          for o in b.opportunities},
        "is_active": b.is_active, "merged_into_id": b.merged_into_id,
    }


def business_detail(b: Business) -> Dict[str, Any]:
    d = business_summary(b)
    d.update({
        "name_normalized": b.name_normalized, "registry_office": b.registry_office, "registry_no": b.registry_no,
        "mersis_no": b.mersis_no, "tax_no": b.tax_no, "address": b.address, "activity_text": b.activity_text,
        "nace_description": b.nace_description, "capital": _f(b.capital), "announcement_url": b.announcement_url,
        "gazette_no": b.gazette_no, "gazette_page": b.gazette_page,
        "source": {"id": b.source.id, "key": b.source.key, "name": b.source.name} if b.source else None,
        "source_reference": b.source_reference, "verified_at": b.verified_at,
        "verification_status": b.verification_status, "hazard_class": b.hazard_class,
        "hazard_label": HAZARD_LABELS.get(b.hazard_class or ""), "hazard_basis": b.hazard_basis,
        "analysis": b.analysis or {}, "analysis_method": b.analysis_method, "analyzed_at": b.analyzed_at,
        "enriched_at": b.enriched_at, "enrichment_log": b.enrichment_log or [],
        "contacts": [contact_out(c) for c in sorted(b.contacts, key=lambda c: (c.type, -c.confidence))
                     if not (b.do_not_contact and c.type in ("phone", "email"))],
        "opportunity_list": [opportunity_out(o) for o in sorted(b.opportunities, key=lambda o: o.service_line)],
        "owner": user_out(b.owner), "owner_id": b.owner_id, "iys_checked_at": b.iys_checked_at,
        "anonymized_at": b.anonymized_at, "created_at": b.created_at, "updated_at": b.updated_at,
    })
    return d


def activity_out(a: Activity) -> Dict[str, Any]:
    return {"id": a.id, "business_id": a.business_id, "opportunity_id": a.opportunity_id, "type": a.type,
            "content": a.content, "occurred_at": a.occurred_at, "follow_up_date": a.follow_up_date,
            "follow_up_done": a.follow_up_done, "user": user_out(a.user), "created_at": a.created_at}


def quote_out(q: Quote) -> Dict[str, Any]:
    return {"id": q.id, "number": q.number, "opportunity_id": q.opportunity_id, "business_id": q.business_id,
            "title": q.title, "items": q.items, "subtotal": _f(q.subtotal), "vat_total": _f(q.vat_total),
            "total": _f(q.total), "currency": q.currency, "valid_until": q.valid_until, "status": q.status,
            "notes": q.notes, "created_at": q.created_at, "updated_at": q.updated_at}


def raw_out(r: RawRecord, with_text: bool = True) -> Dict[str, Any]:
    d = {"id": r.id, "source_id": r.source_id, "import_batch_id": r.import_batch_id, "external_id": r.external_id,
         "announcement_type": r.announcement_type, "published_date": r.published_date, "status": r.status,
         "skip_reason": r.skip_reason, "business_id": r.business_id, "fetched_at": r.fetched_at, "payload": r.payload}
    if with_text:
        d["raw_text"] = r.raw_text
    return d
