"""İletişim bilgisi kayıt kuralları (KVKK odaklı).

* Yalnızca kurumsal iletişim bilgisi saklanır.
* Ücretsiz e-posta sağlayıcılarındaki adresler (gmail vb.) kişisel veri olabileceğinden saklanmaz.
* Mobil numaralar varsayılan olarak saklanmaz (STORE_MOBILE_NUMBERS=true ile açılabilir;
  bu durumda 'kişisel veri riski' işaretlenir).
* Her kayıt kaynak bağlantısı ve güven puanı ile tutulur.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Business, ContactPoint, utcnow
from app.services.normalize import FREE_EMAIL_DOMAINS, email_domain, format_phone, is_mobile, normalize_phone

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def confidence_level(score: int) -> str:
    if score >= 75:
        return "yuksek"
    if score >= 50:
        return "orta"
    return "dusuk"


def normalize_contact(ctype: str, value: str) -> Tuple[Optional[str], Optional[str], bool, Optional[str]]:
    """(gösterim değeri, normalize değer, kişisel_veri_riski, red_nedeni)"""
    value = (value or "").strip()
    if not value:
        return None, None, False, "boş"
    if ctype == "phone":
        n = normalize_phone(value)
        if not n:
            return None, None, False, "geçersiz telefon"
        if is_mobile(n):
            if not settings.STORE_MOBILE_NUMBERS:
                return None, None, True, "mobil numara (kişisel veri olabilir) saklanmadı"
            return format_phone(n), n, True, None
        return format_phone(n), n, False, None
    if ctype == "email":
        v = value.lower().removeprefix("mailto:").split("?")[0]
        if not EMAIL_RE.match(v):
            return None, None, False, "geçersiz e-posta"
        if email_domain(v) in FREE_EMAIL_DOMAINS:
            return None, None, True, "ücretsiz sağlayıcı e-postası (kişisel veri olabilir) saklanmadı"
        return v, v, False, None
    if ctype == "website":
        v = value if re.match(r"^https?://", value, re.I) else "https://" + value
        host = urlparse(v).hostname
        if not host or "." not in host:
            return None, None, False, "geçersiz adres"
        host = host.lower()
        norm = host[4:] if host.startswith("www.") else host
        return f"https://{host}", norm, False, None
    if ctype == "map_profile":
        return value, value, False, None
    return None, None, False, "bilinmeyen tür"


def add_contact(db: Session, business: Business, ctype: str, value: str, *, source_name: str,
                source_url: Optional[str], confidence: int, evidence: Optional[str] = None,
                status: str = "aday") -> Tuple[Optional[ContactPoint], Optional[str]]:
    if business.do_not_contact or business.anonymized_at:
        return None, "işletme için iletişim bilgisi işleme kapalı"
    display, norm, personal, reason = normalize_contact(ctype, value)
    if not norm:
        return None, reason
    existing = db.scalar(select(ContactPoint).where(
        ContactPoint.business_id == business.id, ContactPoint.type == ctype, ContactPoint.normalized_value == norm))
    confidence = max(0, min(100, int(confidence)))
    if existing:
        if existing.status == "reddedildi":
            return existing, "daha önce reddedilmiş"
        if confidence > existing.confidence:
            existing.confidence = confidence
            existing.confidence_level = confidence_level(confidence)
            existing.source_name = source_name
            existing.source_url = source_url
            existing.evidence = evidence
        existing.found_at = utcnow()
        return existing, None
    cp = ContactPoint(
        business_id=business.id, type=ctype, value=display, normalized_value=norm, source_name=source_name,
        source_url=source_url, confidence=confidence, confidence_level=confidence_level(confidence),
        evidence=evidence, status=status, is_corporate=not personal, personal_data_risk=personal,
    )
    business.contacts.append(cp)
    db.flush()
    return cp, None


def best_contacts(business: Business) -> dict:
    """Her tür için reddedilmemiş en güvenilir kaydı döndürür; yoksa None ('Bulunamadı')."""
    out = {"phone": None, "email": None, "website": None, "map_profile": None}
    for c in sorted(business.contacts, key=lambda c: (c.status != "dogrulandi", -c.confidence)):
        if c.status == "reddedildi":
            continue
        if out.get(c.type) is None:
            out[c.type] = c
    return out
