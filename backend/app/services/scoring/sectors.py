"""Sektör sınıflandırması ve tehlike sınıfı tespiti.

Öncelik sırası:
 1. Doğrulanmış NACE kodu + resmî tehlike sınıfı listesi (nace_hazard tablosu) → 'dogrulanmis'
 2. NACE kodu var ama resmî liste yüklenmemiş → bölüm düzeyi eşleme → 'tahmini'
 3. NACE yok → unvan ve faaliyet metninden anahtar kelime → 'tahmini'
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import NaceHazard
from app.services.normalize import fold

SECTORS: Dict[str, Dict] = {
    "insaat": {"label": "İnşaat ve yapı", "divisions": [41, 42, 43], "hazard": "cok_tehlikeli",
               "kw": ["insaat", "yapi", "taahhut", "tadilat", "restorasyon", "tesisat", "hafriyat", "iskele",
                      "boya badana", "cati", "yalitim", "prefabrik", "konut", "altyapi", "beton"]},
    "madencilik": {"label": "Madencilik ve taş ocakçılığı", "divisions": [5, 6, 7, 8, 9], "hazard": "cok_tehlikeli",
                   "kw": ["maden", "tas ocag", "kum ocag", "mermer ocag", "agrega"]},
    "enerji": {"label": "Enerji", "divisions": [35], "hazard": "cok_tehlikeli",
               "kw": ["enerji", "elektrik uretim", "gunes enerji", "ges ", "res ", "dogalgaz dagitim", "solar"]},
    "imalat": {"label": "İmalat ve üretim", "divisions": list(range(10, 34)), "hazard": "tehlikeli",
               "kw": ["imalat", "uretim", "fabrika", "atolye", "dokum", "kaynak", "metal", "plastik", "kalip",
                      "matbaa", "ambalaj", "mobilya imal", "tekstil", "konfeksiyon", "cnc", "torna", "makina", "makine"]},
    "otomotiv": {"label": "Otomotiv servis ve ticaret", "divisions": [45], "hazard": "tehlikeli",
                 "kw": ["otomotiv", "oto ", "arac bakim", "kaporta", "lastik", "oto yikama", "galeri", "yedek parca",
                        "oto servis", "motorlu tasit", "rent a car", "arac kiralama"]},
    "lojistik_depo": {"label": "Lojistik, taşımacılık ve depolama", "divisions": [49, 50, 51, 52, 53],
                      "hazard": "tehlikeli",
                      "kw": ["lojistik", "tasimacilik", "nakliye", "nakliyat", "kargo", "depolama", "antrepo", "kurye",
                             "dagitim", "frigorifik", "tir", "ambar"]},
    "saglik": {"label": "Sağlık hizmetleri", "divisions": [86, 87, 88], "hazard": "tehlikeli",
               "kw": ["saglik", "klinik", "poliklinik", "hastane", "tip merkez", "dis hekim", "agiz ve dis", "fizik tedavi",
                      "laboratuvar", "goruntuleme", "bakim merkez", "huzurevi", "medikal", "veteriner", "psikolog",
                      "diyetisyen", "fizyoterapi"]},
    "yeme_icme": {"label": "Restoran, kafe ve yiyecek hizmetleri", "divisions": [56], "hazard": "az_tehlikeli",
                  "kw": ["restoran", "lokanta", "kafe", "cafe", "yemek", "catering", "pastane", "kebap", "doner",
                         "pizza", "burger", "kahve", "bistro", "yiyecek icecek", "unlu mamul"]},
    "turizm_konaklama": {"label": "Turizm ve konaklama", "divisions": [55, 79], "hazard": "az_tehlikeli",
                         "kw": ["otel", "pansiyon", "konaklama", "turizm", "seyahat", "acenta", "apart"]},
    "egitim": {"label": "Eğitim", "divisions": [85], "hazard": "az_tehlikeli",
               "kw": ["egitim", "kurs", "okul", "etut", "anaokul", "kres", "akademi", "dil okulu", "surucu kurs"]},
    "guzellik_bakim": {"label": "Güzellik ve kişisel bakım", "divisions": [], "hazard": "az_tehlikeli",
                       "kw": ["kuafor", "guzellik", "berber", "estetik", "cilt bakim", "spa", "masaj", "tirnak", "epilasyon"]},
    "spor": {"label": "Spor ve eğlence", "divisions": [93], "hazard": "az_tehlikeli",
             "kw": ["spor salon", "fitness", "pilates", "yuzme", "eglence", "oyun salon", "halı saha", "hali saha"]},
    "e_ticaret": {"label": "E-ticaret", "divisions": [], "hazard": "az_tehlikeli",
                  "kw": ["e ticaret", "elektronik ticaret", "internet uzerinden satis", "online satis", "internet satis"]},
    "perakende_toptan": {"label": "Toptan ve perakende ticaret", "divisions": [46, 47], "hazard": "az_tehlikeli",
                         "kw": ["toptan", "perakende", "magaza", "market", "satis", "ticaret", "ithalat", "ihracat",
                                "pazarlama", "bayi"]},
    "bilisim": {"label": "Bilişim ve yazılım", "divisions": [58, 59, 60, 61, 62, 63], "hazard": "az_tehlikeli",
                "kw": ["yazilim", "bilisim", "bilgisayar", "web tasarim", "mobil uygulama", "veri merkez", "siber",
                       "teknoloji", "dijital"]},
    "danismanlik_ofis": {"label": "Danışmanlık ve profesyonel hizmetler", "divisions": [69, 70, 71, 72, 73, 74, 78, 82],
                         "hazard": "az_tehlikeli",
                         "kw": ["danismanlik", "musavirlik", "muhasebe", "hukuk", "avukat", "mimarlik", "muhendislik",
                                "reklam", "organizasyon", "insan kaynak", "tercume", "proje yonetim", "ar ge", "arge"]},
    "emlak": {"label": "Emlak ve gayrimenkul", "divisions": [68], "hazard": "az_tehlikeli",
              "kw": ["emlak", "gayrimenkul", "konut satis", "kiralama"]},
    "temizlik_tesis": {"label": "Temizlik ve tesis hizmetleri", "divisions": [81], "hazard": "tehlikeli",
                       "kw": ["temizlik", "ilaclama", "tesis yonetim", "peyzaj", "bahce bakim"]},
    "guvenlik": {"label": "Özel güvenlik", "divisions": [80], "hazard": "tehlikeli", "kw": ["ozel guvenlik", "guvenlik hizmet"]},
    "tarim": {"label": "Tarım ve hayvancılık", "divisions": [1, 2, 3], "hazard": "tehlikeli",
              "kw": ["tarim", "hayvancilik", "ciftlik", "sera", "tohum", "fide", "su urunleri", "aricilik"]},
    "finans": {"label": "Finans ve sigorta", "divisions": [64, 65, 66], "hazard": "az_tehlikeli",
               "kw": ["sigorta", "finans", "faktoring", "leasing", "yatirim danismanlik"]},
    "diger": {"label": "Diğer / belirlenemedi", "divisions": [], "hazard": None, "kw": []},
}

# NACE Rev.2 bölümlerine göre KABA tehlike sınıfı varsayımı (resmî liste yüklenmediğinde, 'tahmini')
_DIVISION_HAZARD = {}
for _d in [5, 6, 7, 8, 9, 19, 24, 35, 41, 42, 43]:
    _DIVISION_HAZARD[_d] = "cok_tehlikeli"
for _d in list(range(1, 4)) + list(range(10, 19)) + list(range(20, 24)) + list(range(25, 34)) + \
        [36, 37, 38, 39, 45, 49, 50, 51, 52, 53, 80, 81, 86, 87]:
    _DIVISION_HAZARD.setdefault(_d, "tehlikeli")

HAZARD_LABELS = {"az_tehlikeli": "Az tehlikeli", "tehlikeli": "Tehlikeli", "cok_tehlikeli": "Çok tehlikeli"}


def sector_from_nace(nace: Optional[str]) -> Optional[str]:
    if not nace:
        return None
    try:
        div = int(nace[:2])
    except ValueError:
        return None
    if nace.startswith("47.91"):
        return "e_ticaret"
    if nace.startswith("96.02"):
        return "guzellik_bakim"
    for key, s in SECTORS.items():
        if div in s["divisions"]:
            return key
    return None


def sector_from_text(trade_name: Optional[str], activity: Optional[str]) -> Tuple[str, List[str]]:
    name = " " + fold(trade_name) + " "
    act = " " + fold(activity)[:1500] + " "
    scores: Dict[str, float] = {}
    hits: Dict[str, List[str]] = {}
    for key, s in SECTORS.items():
        for kw in s["kw"]:
            pat = r"\b" + re.escape(kw.strip())
            if re.search(pat, name):
                scores[key] = scores.get(key, 0) + 3
                hits.setdefault(key, []).append(f"unvanda '{kw.strip()}'")
            n = len(re.findall(pat, act))
            if n:
                # Amaç-konu metinleri genellikle uzundur; ilk geçişlere daha çok ağırlık
                first = act.find(kw.strip())
                w = 1.5 if 0 <= first < 300 else 1.0
                scores[key] = scores.get(key, 0) + w * min(n, 3)
                hits.setdefault(key, []).append(f"faaliyette '{kw.strip()}'")
    # Genel 'ticaret' kelimesi neredeyse her unvanda var → zayıf sinyal
    if "perakende_toptan" in scores and len(scores) > 1:
        scores["perakende_toptan"] *= 0.5
    if not scores:
        return "diger", []
    best = max(scores, key=scores.get)
    return best, hits.get(best, [])[:5]


def hazard_for(db: Session, nace: Optional[str], nace_verified: bool, sector: Optional[str]) -> Tuple[Optional[str], str, str]:
    """(tehlike_sınıfı, dayanak, açıklama)"""
    if nace:
        row = db.get(NaceHazard, nace) or (db.get(NaceHazard, nace[:5]) if len(nace) > 5 else None)
        if row:
            basis = "resmi_liste" if nace_verified else "resmi_liste_dogrulanmamis_nace"
            note = f"NACE {nace} → {HAZARD_LABELS.get(row.hazard_class, row.hazard_class)} (İşyeri Tehlike Sınıfları listesi)"
            if not nace_verified:
                note += "; NACE kodu resmî kaynaktan doğrulanmadı"
            return row.hazard_class, basis, note
        try:
            div = int(nace[:2])
        except ValueError:
            div = -1
        hc = _DIVISION_HAZARD.get(div, "az_tehlikeli")
        return hc, "nace_bolum_tahmini", (f"NACE bölüm {nace[:2]} için kaba eşleme: {HAZARD_LABELS[hc]} (tahmini; resmî "
                                          "tehlike sınıfı listesini içe aktararak kesinleştirin)")
    if sector and SECTORS.get(sector, {}).get("hazard"):
        hc = SECTORS[sector]["hazard"]
        return hc, "metin_tahmini", f"Faaliyet metninden tahmin edilen sektöre göre: {HAZARD_LABELS[hc]} (tahmini)"
    return None, "bilinmiyor", "Tehlike sınıfı belirlenemedi (NACE kodu ve yeterli faaliyet bilgisi yok)"
