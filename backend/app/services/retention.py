"""KVKK uyumlu saklama, silme ve anonimleştirme işlemleri."""
from __future__ import annotations

import datetime as dt
from typing import Dict, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Activity, AuditLog, Business, ContactPoint, RawRecord, utcnow


def anonymize_business(db: Session, b: Business, user_id: Optional[int], reason: str) -> None:
    """İşletmeye ait iletişim ve serbest metin verilerini siler; istatistik için iskelet kayıt kalır.

    Tüzel kişi bilgileri KVKK kapsamında değildir; ancak şahıs işletmelerinde unvan ve adres gerçek
    kişiyi tanımlayabildiğinden bu alanlar da maskelenir.
    """
    db.execute(delete(ContactPoint).where(ContactPoint.business_id == b.id))
    db.execute(update(Activity).where(Activity.business_id == b.id).values(content="[silindi – KVKK talebi]"))
    db.execute(update(RawRecord).where(RawRecord.business_id == b.id).values(raw_text=None, payload={}))
    if b.company_type == "SAHIS":
        b.trade_name = f"[Anonimleştirilmiş işletme #{b.id}]"
        b.name_normalized = f"anonim {b.id}"
        b.address = None
        b.tax_no = None
    b.activity_text = None if b.company_type == "SAHIS" else b.activity_text
    b.do_not_contact = True
    b.anonymized_at = utcnow()
    b.enrichment_log = []
    b.analysis = {}
    db.add(AuditLog(user_id=user_id, action="kvkk_anonymize", entity_type="business", entity_id=str(b.id),
                    details={"reason": reason}))


def apply_retention(db: Session, dry_run: bool = False) -> Dict[str, int]:
    """Uzun süre işlem görmeyen adayların iletişim verilerini temizler."""
    now = utcnow()
    cutoff_uncontacted = now - dt.timedelta(days=settings.RETENTION_DAYS_UNCONTACTED)
    cutoff_lost = now - dt.timedelta(days=settings.RETENTION_DAYS_LOST)
    q1 = select(Business).where(Business.anonymized_at.is_(None), Business.sales_status.in_(["yeni", "arastiriliyor", "iletisime_hazir"]),
                                Business.first_seen_at < cutoff_uncontacted,
                                (Business.last_activity_at.is_(None)) | (Business.last_activity_at < cutoff_uncontacted))
    q2 = select(Business).where(Business.anonymized_at.is_(None), Business.sales_status == "olumsuz",
                                (Business.last_activity_at.is_(None)) | (Business.last_activity_at < cutoff_lost))
    stale = list(db.scalars(q1).all())
    lost = list(db.scalars(q2).all())
    if not dry_run:
        for b in stale:
            anonymize_business(db, b, None, f"Saklama süresi doldu ({settings.RETENTION_DAYS_UNCONTACTED} gün, iletişim yok)")
        for b in lost:
            anonymize_business(db, b, None, f"Saklama süresi doldu ({settings.RETENTION_DAYS_LOST} gün, olumsuz sonuç)")
        db.flush()
    return {"uncontacted": len(stale), "lost": len(lost), "dry_run": dry_run}
