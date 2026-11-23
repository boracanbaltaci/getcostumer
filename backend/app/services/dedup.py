"""Mükerrer kayıt tespiti ve işletme birleştirme."""
from __future__ import annotations

from typing import Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Activity, Business, Opportunity, Quote, RawRecord
from app.services.normalize import normalize_trade_name, registry_key


def find_existing(db: Session, *, mersis_no: Optional[str], registry_office: Optional[str],
                  registry_no: Optional[str], trade_name: Optional[str], province: Optional[str]) -> Optional[Business]:
    """Kesin anahtarlara göre mevcut işletmeyi bulur. Benzer isim tek başına eşleşme sayılmaz."""
    if mersis_no:
        b = db.scalar(select(Business).where(Business.mersis_no == mersis_no))
        if b:
            return _resolve_merged(db, b)
    rk = registry_key(registry_office, registry_no)
    if rk:
        b = db.scalar(select(Business).where(Business.registry_key == rk))
        if b:
            return _resolve_merged(db, b)
    if trade_name:
        nn = normalize_trade_name(trade_name)
        q = select(Business).where(Business.name_normalized == nn)
        if province:
            q = q.where(Business.province == province)
        matches = list(db.scalars(q).all())
        # Aynı tam unvan + aynı il: Türk hukukunda aynı sicilde aynı unvan tescil edilemez.
        # Yine de kesin anahtarlar çelişiyorsa (farklı MERSİS) eşleştirme yapılmaz.
        for b in matches:
            if mersis_no and b.mersis_no and b.mersis_no != mersis_no:
                continue
            if registry_no and b.registry_no and b.registry_no != registry_no:
                continue
            return _resolve_merged(db, b)
    return None


def _resolve_merged(db: Session, b: Business) -> Business:
    seen = set()
    while b.merged_into_id and b.id not in seen:
        seen.add(b.id)
        nxt = db.get(Business, b.merged_into_id)
        if not nxt:
            break
        b = nxt
    return b


def find_merge_candidates(db: Session, threshold: int = 90, limit: int = 200) -> List[Dict]:
    """Benzer unvanlı aktif işletme çiftleri (manuel inceleme için)."""
    rows = db.execute(
        select(Business.id, Business.trade_name, Business.name_normalized, Business.mersis_no,
               Business.registry_no, Business.district)
        .where(Business.is_active.is_(True))
    ).all()
    out: List[Dict] = []
    # Basit bloklama: ilk 3 karakter
    blocks: Dict[str, list] = {}
    for r in rows:
        blocks.setdefault((r.name_normalized or "")[:3], []).append(r)
    for items in blocks.values():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.mersis_no and b.mersis_no and a.mersis_no != b.mersis_no:
                    continue
                if a.registry_no and b.registry_no and a.registry_no != b.registry_no:
                    continue
                score = fuzz.token_set_ratio(a.name_normalized, b.name_normalized)
                if score >= threshold:
                    out.append({
                        "a": {"id": a.id, "trade_name": a.trade_name, "district": a.district, "mersis_no": a.mersis_no},
                        "b": {"id": b.id, "trade_name": b.trade_name, "district": b.district, "mersis_no": b.mersis_no},
                        "similarity": int(score),
                    })
                    if len(out) >= limit:
                        return sorted(out, key=lambda x: -x["similarity"])
    return sorted(out, key=lambda x: -x["similarity"])


_MERGE_FIELDS = [
    "establishment_date", "registry_office", "registry_no", "mersis_no", "tax_no", "province", "district",
    "address", "activity_text", "nace_code", "nace_description", "company_type", "capital", "announcement_url",
    "gazette_date", "gazette_no", "gazette_page", "source_reference",
]


def merge_businesses(db: Session, source_id: int, target_id: int) -> Business:
    """source işletmesini target içine birleştirir. source pasifleştirilir (silinmez)."""
    if source_id == target_id:
        raise ValueError("Aynı kayıt birleştirilemez")
    src = db.get(Business, source_id)
    tgt = db.get(Business, target_id)
    if not src or not tgt:
        raise ValueError("İşletme bulunamadı")
    if src.mersis_no and tgt.mersis_no and src.mersis_no != tgt.mersis_no:
        raise ValueError("Farklı MERSİS numaralı kayıtlar birleştirilemez")

    # Benzersiz anahtarları önce kaynaktan boşalt, sonra hedefe taşı
    src_mersis, src_rk = src.mersis_no, src.registry_key
    src.mersis_no = None
    src.registry_key = None
    db.flush()
    for f in _MERGE_FIELDS:
        if getattr(tgt, f) in (None, "") and getattr(src, f) not in (None, ""):
            setattr(tgt, f, getattr(src, f))
    if not tgt.mersis_no and src_mersis:
        tgt.mersis_no = src_mersis
    if not tgt.registry_key and src_rk:
        tgt.registry_key = src_rk

    existing_contacts = {(c.type, c.normalized_value) for c in tgt.contacts}
    for c in list(src.contacts):
        if (c.type, c.normalized_value) in existing_contacts:
            db.delete(c)
        else:
            c.business_id = tgt.id
    tgt_opps = {o.service_line: o for o in tgt.opportunities}
    for o in list(src.opportunities):
        if o.service_line in tgt_opps:
            keep = tgt_opps[o.service_line]
            db.execute(update(Activity).where(Activity.opportunity_id == o.id).values(opportunity_id=keep.id))
            db.execute(update(Quote).where(Quote.opportunity_id == o.id).values(opportunity_id=keep.id, business_id=tgt.id))
            db.delete(o)
        else:
            o.business_id = tgt.id
    db.execute(update(Activity).where(Activity.business_id == src.id).values(business_id=tgt.id))
    db.execute(update(Quote).where(Quote.business_id == src.id).values(business_id=tgt.id))
    db.execute(update(RawRecord).where(RawRecord.business_id == src.id).values(business_id=tgt.id))
    src.merged_into_id = tgt.id
    src.is_active = False
    tgt.do_not_contact = tgt.do_not_contact or src.do_not_contact
    if src.iys_status == "ret":
        tgt.iys_status = "ret"
    db.flush()
    db.expire(tgt)
    return tgt
