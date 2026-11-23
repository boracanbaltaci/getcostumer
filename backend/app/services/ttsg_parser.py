"""Türkiye Ticaret Sicili Gazetesi ilanları için sınıflandırma ve alan ayrıştırma.

ÖNEMLİ: Bu modül yalnızca kullanıcının hukuka uygun biçimde edindiği içerikleri
(veri aboneliği, satın alınan elektronik gazete, üyelik ile görüntülenip indirilen ilan)
işler. Siteye otomatik giriş yapmaz, CAPTCHA çözmez.

Ayrıştırma kuralları yaygın ilan kalıplarına göre yazılmıştır; gerçek gazete örnekleriyle
kalibre edilmelidir (bkz. docs/VERI_KAYNAKLARI_RAPORU.md). Emin olunamayan kayıtlar
'needs_review' olarak işaretlenir, tahminle doldurulmaz.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.constants import ANKARA_DISTRICTS
from app.services.normalize import (
    clean_mersis, clean_nace, clean_registry_no, detect_district, fold, parse_date, parse_decimal,
)

ESTABLISHMENT = "establishment"
EXCLUDED = "excluded"
UNKNOWN = "unknown"

# İlan türü içinde geçtiğinde kaydı DIŞARIDA bırakan ifadeler (katlanmış/ascii)
_EXCLUDE_TYPE_TERMS = [
    "sube", "nakil", "nakli", "degisiklik", "artirim", "arttirim", "azaltim", "tasfiye", "terkin", "birlesme",
    "bolunme", "tur degis", "genel kurul", "temsil", "ortak", "pay devri", "hisse devri", "adres", "unvan",
    "sermaye", "mudur", "yonetim kurulu", "kapanis", "iflas", "konkordato", "sicilden silin", "faaliyet konusu deg",
    "ek ilan", "duzeltme", "yeniden", "ihya", "devir", "satis",
]
# Kuruluşa işaret eden ifadeler
_ESTABLISH_TYPE_TERMS = ["kurulus", "yeni kayit", "ilk kayit", "ticari isletme tescil", "kurulus tescil"]

# Metin içi sinyaller
_TEXT_ESTABLISH = [
    r"kurulus(?:u|unun)? tescil", r"sirketin kurulusu", r"kurulus islemi", r"kurulmus olup",
    r"yeni kurulan", r"kurulus ilan", r"esas sozlesme(?:si)? tescil", r"ticari isletme(?:nin)? tescil",
    r"isletmenin tescil", r"kurulusu .{0,40} tescil edil",
]
_TEXT_EXCLUDE = [
    r"sube(?:si)? (?:acil|tescil|kurulus)", r"merkez nakl", r"adres degisikli", r"unvan degisikli",
    r"sermaye artir", r"sermaye\w* .{0,40}?artir", r"tur degisikli", r"nevi degisikli", r"birlesme",
    r"tasfiye", r"terkin",
]


def classify_announcement(ann_type: Optional[str], text: Optional[str] = None) -> Tuple[str, str]:
    """İlanı 'yeni kuruluş' / 'dışarıda' / 'belirsiz' olarak sınıflandırır."""
    t = fold(ann_type)
    if t:
        for term in _EXCLUDE_TYPE_TERMS:
            if term in t:
                return EXCLUDED, f"İlan türü kuruluş dışı: '{ann_type}'"
        for term in _ESTABLISH_TYPE_TERMS:
            if term in t:
                return ESTABLISHMENT, f"İlan türü: '{ann_type}'"
        if t not in {"diger", "ilan"}:
            return EXCLUDED, f"İlan türü kuruluş değil: '{ann_type}'"
    body = fold(text)
    if not body:
        return UNKNOWN, "İlan türü ve metni yok"
    head = body[:1500]
    for pat in _TEXT_EXCLUDE:
        if re.search(pat, head):
            return EXCLUDED, f"Metinde kuruluş dışı işlem ifadesi: /{pat}/"
    for pat in _TEXT_ESTABLISH:
        if re.search(pat, body):
            return ESTABLISHMENT, f"Metinde kuruluş ifadesi: /{pat}/"
    return UNKNOWN, "Kuruluş ilanı olduğu metinden doğrulanamadı"


@dataclass
class ParsedAnnouncement:
    trade_name: Optional[str] = None
    registry_office: Optional[str] = None
    registry_no: Optional[str] = None
    mersis_no: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    activity_text: Optional[str] = None
    nace_code: Optional[str] = None
    capital: Optional[str] = None
    registration_date: Optional[str] = None
    announcement_type: Optional[str] = None
    raw_text: str = ""
    warnings: List[str] = field(default_factory=list)

    def as_record(self) -> Dict[str, Optional[str]]:
        return {
            "trade_name": self.trade_name, "registry_office": self.registry_office, "registry_no": self.registry_no,
            "mersis_no": self.mersis_no, "address": self.address, "district": self.district,
            "activity_text": self.activity_text, "nace_code": self.nace_code, "capital": self.capital,
            "establishment_date": self.registration_date, "announcement_type": self.announcement_type,
        }


_UP = "A-ZÇĞİÖŞÜ"
_RE_OFFICE = re.compile(rf"([{_UP}][{_UP}\s]{{1,40}}?)\s+T[İI]CARET\s+S[İI]C[İI]L[İI]?\s+M[ÜU]D[ÜU]RL[ÜU][ĞG][ÜU]")
_RE_OFFICE_LABEL = re.compile(r"Ticaret\s+Sicil(?:i)?\s+M[üu]d[üu]rl[üu][ğg][üu]\s*[:：]\s*([^\n]+)", re.I)
_RE_MERSIS = re.compile(r"MERS[İI]S\s*(?:No|Numaras[ıi])?\s*[:：]?\s*([0-9][0-9\s\-]{14,24}[0-9])", re.I)
_RE_SICIL = re.compile(r"(?:Ticaret\s+)?Sicil\s*(?:No|Numaras[ıi])\s*[:：]?\s*([0-9][0-9\-/]*)", re.I)
_RE_UNVAN = re.compile(
    r"(?:Ticaret\s+)?Unvan[ıi]?\s*[:：]\s*(.+?)(?=\n\s*\n|\n\s*(?:Ticaret\s+Sicil|Sicil\s*No|MERS[İI]S|Adres|Tescil)|$)",
    re.I | re.S,
)
_RE_ADRES = re.compile(
    r"(?:İşletme\s+|Şirket\s+|Merkez\s+)?Adres(?:i)?\s*[:：]\s*(.+?)(?=\n\s*\n|\n\s*[A-ZÇĞİÖŞÜ][\wçğıöşü\s]{1,30}\s*[:：]|$)",
    re.I | re.S,
)
_RE_KONU = re.compile(
    r"(?:Amaç\s+ve\s+Konu(?:su)?|Şirketin\s+Amaç\s+ve\s+Konusu|Faaliyet\s+Konusu|İşletme\s+Konusu|İştigal\s+Konusu)\s*[:：]?\s*(.+?)"
    r"(?=\n\s*\n|\n\s*(?:Sermaye|SERMAYE|Ortak|ORTAK|Yönetim|Müdür|Temsil|Madde\s*\d|MADDE\s*\d)|$)",
    re.I | re.S,
)
_RE_NACE = re.compile(r"NACE\s*(?:Kodu|Kod)?\s*[:：]?\s*(\d{2}[.\s]?\d{2}(?:[.\s]?\d{2})?)", re.I)
_RE_SERMAYE = re.compile(r"Sermaye(?:si)?\s*(?:Miktarı)?\s*[:：]?\s*([\d\.\,]{3,})\s*(?:TL|Türk\s+Lira|₺)", re.I)
_RE_TESCIL_TARIHI = re.compile(
    r"(?:Tescil\s+Tarihi\s*[:：]?\s*(\d{2}[./]\d{2}[./]\d{4}))|(?:(\d{2}[./]\d{2}[./]\d{4})\s+tarihinde\s+(?:.{0,40}?)tescil)",
    re.I | re.S,
)
_RE_INLINE_TITLE = re.compile(
    rf"\b([{_UP}0-9][{_UP}0-9\.\-&'\s]{{3,200}}?(?:ANON[İI]M\s+Ş[İI]RKET[İI]|L[İI]M[İI]TED\s+Ş[İI]RKET[İI]|KOOPERAT[İI]F[İI]))"
)


def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" :;,-\t")
    return s or None


def parse_announcement_text(text: str, ann_type: Optional[str] = None) -> ParsedAnnouncement:
    p = ParsedAnnouncement(raw_text=text, announcement_type=ann_type)
    if not text:
        return p
    m = _RE_OFFICE_LABEL.search(text)
    if m:
        p.registry_office = _clean(m.group(1))
    else:
        m = _RE_OFFICE.search(text)
        if m:
            p.registry_office = _clean(m.group(1))
    if p.registry_office:
        p.registry_office = p.registry_office.title().replace("İ", "İ")
    m = _RE_MERSIS.search(text)
    if m:
        p.mersis_no = clean_mersis(m.group(1))
        if not p.mersis_no:
            p.warnings.append("MERSİS numarası 16 haneli değil")
    m = _RE_SICIL.search(text)
    if m:
        p.registry_no = clean_registry_no(m.group(1))
    m = _RE_UNVAN.search(text)
    if m:
        p.trade_name = _clean(m.group(1))
    else:
        m = _RE_INLINE_TITLE.search(text)
        if m:
            p.trade_name = _clean(m.group(1))
            p.warnings.append("Unvan etiketsiz metinden çıkarıldı")
    if p.trade_name and len(p.trade_name) > 300:
        p.warnings.append("Unvan beklenenden uzun; kontrol edin")
        p.trade_name = p.trade_name[:300]
    m = _RE_ADRES.search(text)
    if m:
        p.address = _clean(m.group(1))
        p.district = detect_district(p.address)
    m = _RE_KONU.search(text)
    if m:
        p.activity_text = _clean(m.group(1))[:4000] if _clean(m.group(1)) else None
    m = _RE_NACE.search(text)
    if m:
        p.nace_code = clean_nace(m.group(1))
    m = _RE_SERMAYE.search(text)
    if m:
        dec = parse_decimal(m.group(1))
        p.capital = str(dec) if dec is not None else None
    m = _RE_TESCIL_TARIHI.search(text)
    if m:
        d = parse_date((m.group(1) or m.group(2) or "").replace("/", "."))
        p.registration_date = d.isoformat() if d else None
    return p


_SPLIT_RE = re.compile(
    rf"(?=^\s*[{_UP}][{_UP}\s]{{1,40}}\s+T[İI]CARET\s+S[İI]C[İI]L[İI]?\s+M[ÜU]D[ÜU]RL[ÜU][ĞG][ÜU]\s*$)"
    r"|(?=^\s*Ticaret\s+Sicil(?:i)?\s+M[üu]d[üu]rl[üu][ğg][üu]\s*[:：])",
    re.M,
)


def split_gazette_text(text: str) -> List[str]:
    """Gazete sayfası metnini ilan bloklarına böler."""
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p and p.strip()]
    return [p for p in parts if len(p) > 40]


def is_target_office(office: Optional[str], address: Optional[str], province: str = "ANKARA") -> Tuple[Optional[bool], str]:
    """Kaydın hedef ile ait olup olmadığını belirler. None = belirsiz."""
    fo = fold(office)
    fa = fold(address)
    fp = fold(province)
    if fo:
        if fo == fp or fo.startswith(fp + " "):
            return True, "Sicil müdürlüğü: " + (office or "")
        districts = {fold(d) for d in ANKARA_DISTRICTS} if fp == "ankara" else set()
        if fo in districts:
            if fa and fp in fa:
                return True, f"İlçe sicil müdürlüğü ({office}) ve adres {province}"
            if not fa:
                return None, f"İlçe adıyla sicil müdürlüğü ({office}); adres yok, doğrulanmalı"
            return False, f"Sicil müdürlüğü {office}, adres {province} dışında"
        if fa and re.search(rf"\b{fp}\b\s*$", fa):
            return None, f"Sicil müdürlüğü {office}, ancak adres {province}; doğrulanmalı"
        return False, f"Sicil müdürlüğü hedef il dışında: {office}"
    if fa:
        if re.search(rf"\b{fp}\b", fa):
            return True, f"Adres {province} içeriyor"
        return False, f"Adres {province} içermiyor"
    return None, "Sicil müdürlüğü ve adres bilgisi yok"
