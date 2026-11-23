"""CRM yardımcıları: aşama geçişleri, satış durumu, hatırlatmalar, teklif numarası."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import STAGE_KEYS
from app.models import Activity, Business, Opportunity, Quote, StageHistory, utcnow


def compute_sales_status(b: Business) -> str:
    stages = [o.stage for o in b.opportunities]
    if not stages:
        return "yeni"
    if "kazanildi" in stages:
        return "kazanildi"
    open_ = [s for s in stages if s != "olumsuz"]
    if not open_:
        return "olumsuz"
    return max(open_, key=STAGE_KEYS.index)


def change_stage(db: Session, opp: Opportunity, new_stage: str, user_id: Optional[int], lost_reason: Optional[str] = None):
    if new_stage not in STAGE_KEYS:
        raise ValueError("Geçersiz aşama")
    if new_stage == opp.stage:
        return opp
    db.add(StageHistory(opportunity_id=opp.id, from_stage=opp.stage, to_stage=new_stage, changed_by=user_id))
    opp.stage = new_stage
    opp.stage_changed_at = utcnow()
    if new_stage == "kazanildi":
        opp.won_at = utcnow()
    if new_stage == "olumsuz" and lost_reason:
        opp.lost_reason = lost_reason
    db.flush()
    b = opp.business
    b.sales_status = compute_sales_status(b)
    b.last_activity_at = utcnow()
    return opp


def compute_quote_totals(items: List[Dict]) -> Dict[str, Decimal]:
    subtotal = Decimal("0")
    vat = Decimal("0")
    clean = []
    for it in items:
        qty = Decimal(str(it.get("quantity") or 0))
        price = Decimal(str(it.get("unit_price") or 0))
        rate = Decimal(str(it.get("vat_rate") if it.get("vat_rate") is not None else 20))
        line = (qty * price).quantize(Decimal("0.01"))
        subtotal += line
        vat += (line * rate / Decimal(100)).quantize(Decimal("0.01"))
        clean.append({"description": str(it.get("description") or "")[:500], "quantity": float(qty),
                      "unit": str(it.get("unit") or "Adet")[:20], "unit_price": float(price), "vat_rate": float(rate),
                      "line_total": float(line)})
    return {"items": clean, "subtotal": subtotal, "vat_total": vat, "total": subtotal + vat}


def next_quote_number(db: Session) -> str:
    year = dt.date.today().year
    prefix = f"TKL-{year}-"
    count = db.scalar(select(func.count(Quote.id)).where(Quote.number.like(prefix + "%"))) or 0
    n = count + 1
    while db.scalar(select(Quote.id).where(Quote.number == f"{prefix}{n:05d}")):
        n += 1
    return f"{prefix}{n:05d}"


def due_reminders(db: Session, until: dt.date, user_id: Optional[int] = None) -> List[Dict]:
    out: List[Dict] = []
    q = (select(Activity, Business.trade_name).join(Business, Business.id == Activity.business_id)
         .where(Activity.follow_up_date.is_not(None), Activity.follow_up_date <= until,
                Activity.follow_up_done.is_(False), Business.is_active.is_(True)))
    if user_id:
        q = q.where(Activity.user_id == user_id)
    for a, name in db.execute(q.order_by(Activity.follow_up_date)).all():
        out.append({"kind": "activity", "id": a.id, "business_id": a.business_id, "business": name,
                    "date": a.follow_up_date.isoformat(), "text": a.content[:200], "overdue": a.follow_up_date < dt.date.today()})
    q2 = (select(Opportunity, Business.trade_name).join(Business, Business.id == Opportunity.business_id)
          .where(Opportunity.next_action_date.is_not(None), Opportunity.next_action_date <= until,
                 Opportunity.stage.not_in(["kazanildi", "olumsuz"]), Business.is_active.is_(True)))
    if user_id:
        q2 = q2.where(Opportunity.owner_id == user_id)
    for o, name in db.execute(q2.order_by(Opportunity.next_action_date)).all():
        out.append({"kind": "opportunity", "id": o.id, "business_id": o.business_id, "business": name,
                    "service_line": o.service_line, "date": o.next_action_date.isoformat(),
                    "text": o.next_action or "Sonraki aksiyon", "overdue": o.next_action_date < dt.date.today()})
    return sorted(out, key=lambda r: r["date"])
