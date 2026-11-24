"""Google Places API (New) — seçilen konum çevresindeki işletmeleri listeler.

Nearby Search çağrı başına en fazla 20 sonuç döndüğü için mahalledeki KOBİ
yoğunluğunu yakalamak amacıyla yaygın işletme türleri ayrı çağrılarla taranır;
aynı yer (place_id) tekil sayılır.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.nationalPhoneNumber,places.internationalPhoneNumber,places.websiteUri,"
    "places.businessStatus,places.primaryType"
)
TIMEOUT = 20.0

# Google Places (New) — Table A işletme türleri; her liste tek API çağrısıdır.
TYPE_GROUPS: list[list[str]] = [
    ["restaurant", "cafe", "coffee_shop", "bakery", "meal_takeaway", "meal_delivery", "bar"],
    ["beauty_salon", "hair_care", "barber_shop", "spa", "nail_salon"],
    ["car_repair", "car_wash", "car_dealer", "car_rental", "auto_parts_store"],
    ["doctor", "dentist", "pharmacy", "physiotherapist", "hospital"],
    ["lawyer", "accounting", "real_estate_agency", "insurance_agency", "travel_agency"],
    ["supermarket", "convenience_store", "clothing_store",
     "shoe_store", "jewelry_store", "furniture_store", "hardware_store",
     "electronics_store", "book_store", "florist", "pet_store"],
    ["laundry", "locksmith", "moving_company", "plumber", "electrician", "painter",
     "roofing_contractor"],
    ["gym", "fitness_center", "hotel", "motel", "lodging"],
]


def _post(client: httpx.Client, body: Dict[str, Any]) -> Dict[str, Any]:
    resp = client.post(
        NEARBY_URL,
        json=body,
        headers={
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    resp.raise_for_status()
    return resp.json()


def _normalize(place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if place.get("businessStatus") == "CLOSED_PERMANENTLY":
        return None
    loc = place.get("location") or {}
    name = (place.get("displayName") or {}).get("text") or ""
    if not place.get("id") or not name:
        return None
    return {
        "place_id": place["id"],
        "name": name.strip(),
        "address": place.get("formattedAddress") or "",
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or "",
        "website": place.get("websiteUri"),
        "primary_type": place.get("primaryType"),
    }


def search_nearby(lat: float, lng: float, radius_m: int) -> tuple[List[Dict[str, Any]], List[str]]:
    """Konum çevresindeki işletmeleri döndürür; grup bazlı hatalar uyarı olarak birikir."""
    circle = {"center": {"latitude": lat, "longitude": lng}, "radius": float(radius_m)}
    requests: list[Dict[str, Any]] = [
        # Tür filtresiz çağrı: listeye girmeyen işletme türlerini de yakalar.
        {"maxResultCount": 20, "locationRestriction": {"circle": circle},
         "rankPreference": "DISTANCE", "languageCode": "tr"},
    ]
    for group in TYPE_GROUPS[: max(0, settings.PLACES_MAX_CALLS - 1)]:
        requests.append({"includedTypes": group, "maxResultCount": 20,
                         "locationRestriction": {"circle": circle}, "languageCode": "tr"})

    found: dict[str, Dict[str, Any]] = {}
    warnings: list[str] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for body in requests:
            label = ",".join(body.get("includedTypes", [])[:3]) or "tum-turler"
            try:
                data = _post(client, body)
            except httpx.HTTPStatusError as exc:
                detail = ""
                try:
                    detail = exc.response.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                msg = f"Places çağrısı başarısız ({label}): HTTP {exc.response.status_code} {detail}".strip()
                logger.warning(msg)
                warnings.append(msg)
                continue
            except httpx.HTTPError as exc:
                msg = f"Places çağrısı başarısız ({label}): {exc}"
                logger.warning(msg)
                warnings.append(msg)
                continue
            for raw in data.get("places") or []:
                rec = _normalize(raw)
                if rec:
                    found.setdefault(rec["place_id"], rec)
    return list(found.values()), warnings
