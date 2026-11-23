"""İletişim bilgisi araştırma akışı."""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Business, utcnow
from app.services.contacts import add_contact
from app.services.enrichment import providers, website


def enrich_business(db: Session, b: Business) -> List[str]:
    log: List[str] = []
    say = log.append
    if b.do_not_contact or b.anonymized_at:
        say("İletişim araştırması yapılmadı: işletme 'iletişime geçme' / anonimleştirilmiş olarak işaretli")
        b.enrichment_status = "atlandi"
        b.enrichment_log = log
        return log
    if not settings.ENRICHMENT_ENABLED:
        say("İletişim araştırması kapalı (ENRICHMENT_ENABLED=false)")
        b.enrichment_status = "atlandi"
        b.enrichment_log = log
        return log

    found = 0
    # 1) Mevcut (ör. içe aktarımla gelen) web sitesini doğrula
    candidates: List[str] = [c.value for c in b.contacts if c.type == "website" and c.status != "reddedildi"]
    # 2) Arama API'si
    candidates += providers.brave_candidates(b, say)
    # 3) Unvandan alan adı tahmini
    if settings.ENRICHMENT_DOMAIN_PROBE:
        candidates += website.candidate_domains(b)
    best = None
    for url in list(dict.fromkeys(candidates))[:8]:
        v = website.verify_and_extract(b, url, say)
        if v and (best is None or v.score > best.score):
            best = v
        if best and best.score >= 85:
            break
    if best and best.score >= website.ACCEPT_THRESHOLD:
        ev = "; ".join(best.evidence)
        add_contact(db, b, "website", best.url, source_name="Web sitesi doğrulaması", source_url=best.pages[0],
                    confidence=best.score, evidence=ev)
        found += 1
        for e, page in best.emails[:3]:
            cp, why = add_contact(db, b, "email", e, source_name="İşletmenin web sitesi", source_url=page,
                                  confidence=min(95, best.score), evidence=f"Doğrulanmış sitede yayımlanan adres. {ev}")
            found += 1 if cp else 0
            if why:
                say(f"E-posta {e}: {why}")
        for p, page in best.phones[:3]:
            cp, why = add_contact(db, b, "phone", p, source_name="İşletmenin web sitesi", source_url=page,
                                  confidence=min(90, best.score - 5), evidence=f"Doğrulanmış sitede yayımlanan numara. {ev}")
            found += 1 if cp else 0
            if why:
                say(f"Telefon {p}: {why}")
    elif best:
        say(f"En iyi aday site eşik altında kaldı ({best.score} < {website.ACCEPT_THRESHOLD}); kaydedilmedi")

    # 4) OpenStreetMap
    for rec in providers.osm_lookup(b, say):
        for ctype in ("phone", "website", "email"):
            if rec.get(ctype):
                cp, why = add_contact(db, b, ctype, rec[ctype], source_name="OpenStreetMap (ODbL)",
                                      source_url=rec["source_url"], confidence=rec["confidence"], evidence=rec["evidence"])
                found += 1 if cp else 0
                if why:
                    say(f"OSM {ctype}: {why}")
        add_contact(db, b, "map_profile", rec["source_url"], source_name="OpenStreetMap (ODbL)",
                    source_url=rec["source_url"], confidence=rec["confidence"], evidence=rec["evidence"])

    # 5) Google Places – yalnızca place_id saklanır
    gp = providers.google_place_lookup(b, say)
    if gp:
        url = f"https://www.google.com/maps/place/?q=place_id:{gp['place_id']}"
        add_contact(db, b, "map_profile", url, source_name="Google Places (place_id)", source_url=url,
                    confidence=gp["confidence"], evidence=gp["evidence"] + ". Telefon/web canlı görüntülenir, saklanmaz.")
        found += 1

    has_any = any(c.status != "reddedildi" for c in b.contacts)
    b.enrichment_status = "tamamlandi" if has_any else "bulunamadi"
    if not has_any:
        say("Doğrulanabilir kurumsal iletişim bilgisi bulunamadı")
    b.enriched_at = utcnow()
    b.enrichment_log = log[-60:]
    return log
