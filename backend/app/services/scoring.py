"""İşletme için yazılım/dijital fırsat puanı (kural tabanlı).

Her faktör {points, label, basis} sözlüğüdür; basis 'dogrulanmis' (Places
kaydından gelen bilgi) ya da 'tahmini' (isimden çıkarım). Puan 0-100'e
kırpılır, A/B/C önceliğiyle döner.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# website_status → (puan, etiket, basis, önerilen hizmet)
STATUS_FIT: Dict[str, Tuple[int, str, str, str]] = {
    "yok": (30, "Web sitesi yok", "tahmini", "Kurumsal web sitesi"),
    "eski": (20, "Web sitesi eski görünümlü", "dogrulanmis", "Web sitesi yenileme"),
    "erisilemedi": (15, "Web sitesine ulaşılamadı", "tahmini", "Site teknik destek / yenileme"),
}

# Google Places primaryType → (puan, sektör etiketi, önerilen hizmet)
TYPE_FIT: Dict[str, Tuple[int, str, str]] = {
    # Randevu / rezervasyon ağırlıklı sektörler
    "doctor": (15, "Sağlık", "Online randevu / rezervasyon sistemi"),
    "dentist": (15, "Sağlık", "Online randevu / rezervasyon sistemi"),
    "physiotherapist": (15, "Sağlık", "Online randevu / rezervasyon sistemi"),
    "hospital": (15, "Sağlık", "Online randevu / rezervasyon sistemi"),
    "beauty_salon": (15, "Güzellik ve bakım", "Online randevu / rezervasyon sistemi"),
    "hair_care": (15, "Güzellik ve bakım", "Online randevu / rezervasyon sistemi"),
    "barber_shop": (15, "Güzellik ve bakım", "Online randevu / rezervasyon sistemi"),
    "spa": (15, "Güzellik ve bakım", "Online randevu / rezervasyon sistemi"),
    "nail_salon": (15, "Güzellik ve bakım", "Online randevu / rezervasyon sistemi"),
    "gym": (15, "Spor", "Online randevu / rezervasyon sistemi"),
    "fitness_center": (15, "Spor", "Online randevu / rezervasyon sistemi"),
    "hotel": (15, "Konaklama", "Online randevu / rezervasyon sistemi"),
    "motel": (15, "Konaklama", "Online randevu / rezervasyon sistemi"),
    "lodging": (15, "Konaklama", "Online randevu / rezervasyon sistemi"),
    "travel_agency": (15, "Turizm", "Online randevu / rezervasyon sistemi"),
    # Perakende → e-ticaret
    "supermarket": (15, "Perakende", "E-ticaret sitesi"),
    "convenience_store": (15, "Perakende", "E-ticaret sitesi"),
    "clothing_store": (15, "Perakende", "E-ticaret sitesi"),
    "shoe_store": (15, "Perakende", "E-ticaret sitesi"),
    "jewelry_store": (15, "Perakende", "E-ticaret sitesi"),
    "furniture_store": (15, "Perakende", "E-ticaret sitesi"),
    "hardware_store": (15, "Perakende", "E-ticaret sitesi"),
    "electronics_store": (15, "Perakende", "E-ticaret sitesi"),
    "book_store": (15, "Perakende", "E-ticaret sitesi"),
    "florist": (15, "Perakende", "E-ticaret sitesi"),
    "pet_store": (15, "Perakende", "E-ticaret sitesi"),
    "pharmacy": (15, "Perakende", "E-ticaret sitesi"),
    "auto_parts_store": (15, "Perakende", "E-ticaret sitesi"),
    "store": (15, "Perakende", "E-ticaret sitesi"),
    # Yeme-içme → online sipariş
    "restaurant": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "cafe": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "coffee_shop": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "bakery": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "meal_takeaway": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "meal_delivery": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    "bar": (10, "Yeme-içme", "Online sipariş / menü sistemi"),
    # Profesyonel ofisler → CRM
    "lawyer": (10, "Profesyonel hizmet", "CRM / müşteri takip sistemi"),
    "accounting": (10, "Profesyonel hizmet", "CRM / müşteri takip sistemi"),
    "real_estate_agency": (10, "Profesyonel hizmet", "CRM / müşteri takip sistemi"),
    "insurance_agency": (10, "Profesyonel hizmet", "CRM / müşteri takip sistemi"),
    # Servis / usta işleri → iş takip
    "car_repair": (8, "Servis", "İş / randevu takip sistemi"),
    "car_wash": (8, "Servis", "İş / randevu takip sistemi"),
    "car_dealer": (8, "Servis", "İş / randevu takip sistemi"),
    "car_rental": (8, "Servis", "İş / randevu takip sistemi"),
    "laundry": (8, "Servis", "İş / randevu takip sistemi"),
    "locksmith": (8, "Servis", "İş / randevu takip sistemi"),
    "moving_company": (8, "Servis", "İş / randevu takip sistemi"),
    "plumber": (8, "Servis", "İş / randevu takip sistemi"),
    "electrician": (8, "Servis", "İş / randevu takip sistemi"),
    "painter": (8, "Servis", "İş / randevu takip sistemi"),
    "roofing_contractor": (8, "Servis", "İş / randevu takip sistemi"),
}

TECH_TYPES = {"software_company"}

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_TR_ASCII = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})

COMPANY_RE = re.compile(r"\b(ltd|limited|sti|sirketi?|anonim|koop)\b|\ba\.?\s?s\b")
TECH_NAME_RE = re.compile(r"yazilim|bilisim|teknoloji|software|bilgisayar")


def _fold(s: str) -> str:
    """Türkçe duyarsız karşılaştırma anahtarı."""
    return s.translate(_TR_LOWER).lower().translate(_TR_ASCII)


def _f(points: int, label: str, basis: str) -> Dict[str, Any]:
    return {"points": points, "label": label, "basis": basis}


def _priority(score: int) -> str:
    return "A" if score >= 50 else "B" if score >= 30 else "C"


def score_business(rec: Dict[str, Any], website_status: str) -> Dict[str, Any]:
    """Places kaydı + site durumundan fırsat puanı üretir; durum yazmaz."""
    factors: List[Dict[str, Any]] = []
    services: List[str] = []

    pts, label, basis, svc = STATUS_FIT.get(website_status, (0, "", "tahmini", ""))
    if pts:
        factors.append(_f(pts, label, basis))
        services.append(svc)

    ptype = rec.get("primary_type")
    fit = TYPE_FIT.get(ptype or "")
    if fit:
        pts, sector, svc = fit
        factors.append(_f(pts, f"Sektör uygunluğu: {sector}", "dogrulanmis"))
        services.append(svc)

    if rec.get("phone"):
        factors.append(_f(5, "Ulaşılabilir telefon", "dogrulanmis"))

    folded = _fold(rec.get("name") or "")
    if COMPANY_RE.search(folded):
        factors.append(_f(5, "Şirket unvanı (Ltd/A.Ş.)", "tahmini"))
    if ptype in TECH_TYPES or TECH_NAME_RE.search(folded):
        factors.append(_f(-10, "Bilişim firması olabilir (kendi yazılımını yapar)", "tahmini"))

    score = max(0, min(100, sum(f["points"] for f in factors)))
    return {"score": score, "priority": _priority(score), "factors": factors,
            "services": list(dict.fromkeys(services))}
