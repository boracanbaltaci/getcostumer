from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import SERVICE_LINES
from app.database import get_db
from app.deps import audit, get_current_user, require_role
from app.models import Activity, Business, Opportunity, Quote, User, utcnow
from app.schemas import ActivityCreate, ActivityUpdate, OpportunityUpdate, QuoteCreate, QuoteUpdate
from app.serializers import activity_out, opportunity_out, quote_out
from app.services import crm, exports
from app.services.reports import today_tr

router = APIRouter(tags=["crm"])


@router.patch("/opportunities/{oid}")
def update_opportunity(oid: int, body: OpportunityUpdate, db: Session = Depends(get_db),
                       user: User = Depends(require_role("sales"))):
    o = db.get(Opportunity, oid)
    if not o:
        raise HTTPException(404, "Fırsat bulunamadı")
    data = body.model_dump(exclude_unset=True)
    if body.stage and body.stage != o.stage:
        if body.stage in ("ilk_gorusme", "ilgileniyor", "teklif_gonderildi", "kazanildi") and o.business.do_not_contact:
            raise HTTPException(400, "İşletme 'iletişime geçme' olarak işaretli")
        crm.change_stage(db, o, body.stage, user.id, body.lost_reason)
    for k in ("owner_id", "estimated_value", "next_action", "next_action_date", "lost_reason"):
        if k in data and k != "stage":
            setattr(o, k, data[k])
    if body.clear_next_action:
        o.next_action, o.next_action_date = None, None
    o.business.last_activity_at = utcnow()
    audit(db, user, "opportunity_update", "opportunity", oid, {k: str(v) for k, v in data.items()})
    db.commit()
    db.refresh(o)
    return opportunity_out(o)


@router.get("/opportunities/{oid}/history")
def opportunity_history(oid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models import StageHistory
    rows = db.scalars(select(StageHistory).where(StageHistory.opportunity_id == oid).order_by(StageHistory.changed_at)).all()
    return [{"from": r.from_stage, "to": r.to_stage, "changed_by": r.changed_by, "changed_at": r.changed_at} for r in rows]


@router.post("/businesses/{bid}/activities")
def add_activity(bid: int, body: ActivityCreate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    b = db.get(Business, bid)
    if not b:
        raise HTTPException(404, "İşletme bulunamadı")
    if body.opportunity_id:
        o = db.get(Opportunity, body.opportunity_id)
        if not o or o.business_id != bid:
            raise HTTPException(400, "Fırsat bu işletmeye ait değil")
    a = Activity(business_id=bid, opportunity_id=body.opportunity_id, user_id=user.id, type=body.type,
                 content=body.content, occurred_at=body.occurred_at or utcnow(), follow_up_date=body.follow_up_date)
    db.add(a)
    b.last_activity_at = utcnow()
    audit(db, user, "activity_add", "business", bid, {"type": body.type})
    db.commit()
    db.refresh(a)
    return activity_out(a)


@router.patch("/activities/{aid}")
def update_activity(aid: int, body: ActivityUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    a = db.get(Activity, aid)
    if not a:
        raise HTTPException(404, "Kayıt bulunamadı")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return activity_out(a)


@router.get("/reminders")
def reminders(days: int = 7, mine: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crm.due_reminders(db, today_tr() + dt.timedelta(days=days), user.id if mine else None)


@router.post("/opportunities/{oid}/quotes")
def create_quote(oid: int, body: QuoteCreate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    o = db.get(Opportunity, oid)
    if not o:
        raise HTTPException(404, "Fırsat bulunamadı")
    t = crm.compute_quote_totals([i.model_dump() for i in body.items])
    q = Quote(number=crm.next_quote_number(db), opportunity_id=o.id, business_id=o.business_id, title=body.title,
              items=t["items"], subtotal=t["subtotal"], vat_total=t["vat_total"], total=t["total"],
              currency=body.currency, valid_until=body.valid_until or (today_tr() + dt.timedelta(days=30)),
              notes=body.notes, created_by=user.id)
    db.add(q)
    if o.estimated_value is None:
        o.estimated_value = t["subtotal"]
    audit(db, user, "quote_create", "opportunity", oid)
    db.commit()
    db.refresh(q)
    return quote_out(q)


@router.get("/quotes")
def list_quotes(status: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Quote, Business.trade_name).join(Business, Business.id == Quote.business_id).order_by(Quote.created_at.desc())
    if status:
        stmt = stmt.where(Quote.status == status)
    return [dict(quote_out(q), business=name) for q, name in db.execute(stmt.limit(500)).all()]


@router.patch("/quotes/{qid}")
def update_quote(qid: int, body: QuoteUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    q = db.get(Quote, qid)
    if not q:
        raise HTTPException(404, "Teklif bulunamadı")
    data = body.model_dump(exclude_unset=True)
    if "items" in data and data["items"] is not None:
        t = crm.compute_quote_totals(data.pop("items"))
        q.items, q.subtotal, q.vat_total, q.total = t["items"], t["subtotal"], t["vat_total"], t["total"]
    for k, v in data.items():
        setattr(q, k, v)
    o = db.get(Opportunity, q.opportunity_id)
    if body.status == "gonderildi" and o and o.stage not in ("teklif_gonderildi", "kazanildi"):
        crm.change_stage(db, o, "teklif_gonderildi", user.id)
    if body.status == "kabul" and o:
        crm.change_stage(db, o, "kazanildi", user.id)
        if o.estimated_value is None:
            o.estimated_value = q.subtotal
    audit(db, user, "quote_update", "quote", qid, {k: str(v) for k, v in data.items()})
    db.commit()
    db.refresh(q)
    return quote_out(q)


@router.get("/quotes/{qid}/pdf")
def quote_pdf(qid: int, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    q = db.get(Quote, qid)
    if not q:
        raise HTTPException(404, "Teklif bulunamadı")
    b = db.get(Business, q.business_id)
    o = db.get(Opportunity, q.opportunity_id)
    pdf = exports.quote_pdf(q, b, SERVICE_LINES.get(o.service_line if o else "", ""))
    audit(db, user, "quote_pdf", "quote", qid)
    db.commit()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{q.number}.pdf"'})
