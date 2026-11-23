"""Harici, izinli iletişim bilgisi sağlayıcıları.

* Brave Search API – resmî web arama API'si (anahtar gerekir); yalnızca aday URL üretir,
  her aday site doğrulamasından geçer.
* OpenStreetMap Nominatim – ODbL lisanslı açık veri; kullanım politikası gereği saniyede en
  fazla 1 istek ve tanımlayıcı User-Agent/e-posta ile çağrılır. Varsayılan kapalıdır.
* Google Places API (New) – Google Maps Platform koşulları gereği yalnızca place_id saklanır;
  telefon/web sitesi canlı olarak (saklanmadan) görüntülenir.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from rapidfuzz import fuzz

from app.config import settings
from app.models import Business
from app.services.normalize import distinctive_tokens, fold

_SKIP_HOSTS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "tiktok.com",
    "wikipedia.org", "ticaretsicil.gov.tr", "gov.tr", "sahibinden.com", "trendyol.com", "hepsiburada.com",
    "google.com", "yandex.com", "bing.com", "kariyer.net", "eksisozluk.com", "sikayetvar.com",
)


def _name_match(b: Business, name: str) -> int:
    toks = distinctive_tokens(b.trade_name)
    if not toks:
        return 0
    fn = fold(name)
    if not all(t in fn.split() for t in toks):
        return 0
    return int(fuzz.token_set_ratio(" ".join(toks), fn))


def brave_candidates(b: Business, log) -> List[str]:
    if not settings.BRAVE_SEARCH_API_KEY:
        return []
    q = f"\"{b.trade_name}\" Ankara"
    try:
        r = httpx.get("https://api.search.brave.com/res/v1/web/search",
                      params={"q": q, "country": "tr", "count": 10},
                      headers={"X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY, "Accept": "application/json"},
                      timeout=15)
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
    except Exception as exc:
        log(f"Arama API hatası: {exc}")
        return []
    out = []
    for item in results:
        url = item.get("url") or ""
        host = (urlparse(url).hostname or "").lower()
        if not host or any(host == h or host.endswith("." + h) for h in _SKIP_HOSTS):
            continue
        out.append(f"{urlparse(url).scheme}://{host}")
    log(f"Arama API: {len(out)} aday site")
    return list(dict.fromkeys(out))[:5]


_last_nominatim = [0.0]


def osm_lookup(b: Business, log) -> List[Dict[str, Any]]:
    if not settings.OSM_NOMINATIM_ENABLED:
        return []
    wait = 1.1 - (time.time() - _last_nominatim[0])
    if wait > 0:
        time.sleep(wait)
    _last_nominatim[0] = time.time()
    toks = distinctive_tokens(b.trade_name)
    if not toks:
        return []
    params = {"q": " ".join(toks) + " Ankara", "format": "jsonv2", "extratags": 1, "addressdetails": 1,
              "countrycodes": "tr", "limit": 5}
    if settings.OSM_CONTACT_EMAIL:
        params["email"] = settings.OSM_CONTACT_EMAIL
    try:
        r = httpx.get(settings.OSM_NOMINATIM_URL, params=params,
                      headers={"User-Agent": settings.ENRICHMENT_USER_AGENT}, timeout=15)
        r.raise_for_status()
        items = r.json()
    except Exception as exc:
        log(f"OSM Nominatim hatası: {exc}")
        return []
    out = []
    for it in items:
        name = it.get("name") or it.get("display_name", "")
        sim = _name_match(b, name)
        addr = it.get("address", {})
        in_ankara = fold(addr.get("province") or addr.get("state") or addr.get("city") or "") == "ankara"
        if sim < 85 or not in_ankara:
            continue
        district_ok = bool(b.district) and fold(b.district) in fold(it.get("display_name", ""))
        tags = it.get("extratags") or {}
        osm_url = f"https://www.openstreetmap.org/{it.get('osm_type')}/{it.get('osm_id')}"
        base_conf = 55 + (10 if district_ok else 0)
        rec = {"source_url": osm_url, "confidence": base_conf, "name": name,
               "evidence": f"OSM kaydı '{name}', ad benzerliği %{sim}" + (", ilçe uyumlu" if district_ok else "")}
        rec["phone"] = tags.get("phone") or tags.get("contact:phone")
        rec["website"] = tags.get("website") or tags.get("contact:website")
        rec["email"] = tags.get("email") or tags.get("contact:email")
        out.append(rec)
    log(f"OSM: {len(out)} eşleşme")
    return out[:1]


def google_place_lookup(b: Business, log) -> Optional[Dict[str, Any]]:
    if not settings.GOOGLE_PLACES_API_KEY:
        return None
    try:
        r = httpx.post(
            "https://places.googleapis.com/v1/places:searchText",
            json={"textQuery": f"{b.trade_name} {b.district or ''} Ankara", "languageCode": "tr", "regionCode": "TR"},
            headers={"X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
                     "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"},
            timeout=15,
        )
        r.raise_for_status()
        places = r.json().get("places", [])
    except Exception as exc:
        log(f"Google Places hatası: {exc}")
        return None
    for p in places[:5]:
        name = (p.get("displayName") or {}).get("text", "")
        sim = _name_match(b, name)
        addr = p.get("formattedAddress", "")
        if sim < 85 or "ankara" not in fold(addr):
            continue
        district_ok = bool(b.district) and fold(b.district) in fold(addr)
        log(f"Google Places eşleşmesi: {name} (%{sim})")
        return {"place_id": p["id"], "name": name, "confidence": 60 + (10 if district_ok else 0),
                "evidence": f"Google Places '{name}', ad benzerliği %{sim}" + (", ilçe uyumlu" if district_ok else "")}
    return None


def google_place_live_details(place_id: str) -> Dict[str, Any]:
    """Saklanmadan gösterilecek canlı detaylar (Google Maps Platform koşulları)."""
    if not settings.GOOGLE_PLACES_API_KEY:
        return {"error": "GOOGLE_PLACES_API_KEY tanımlı değil"}
    r = httpx.get(f"https://places.googleapis.com/v1/places/{place_id}",
                  headers={"X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
                           "X-Goog-FieldMask": "displayName,formattedAddress,nationalPhoneNumber,websiteUri,googleMapsUri"},
                  params={"languageCode": "tr"}, timeout=15)
    r.raise_for_status()
    d = r.json()
    return {"name": (d.get("displayName") or {}).get("text"), "address": d.get("formattedAddress"),
            "phone": d.get("nationalPhoneNumber"), "website": d.get("websiteUri"), "maps_url": d.get("googleMapsUri"),
            "attribution": "Google Maps verisi – saklanmaz, canlı gösterilir"}
