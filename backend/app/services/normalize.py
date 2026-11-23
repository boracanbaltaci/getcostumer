"""Türkçe metin normalizasyonu ve alan ayrıştırma yardımcıları."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List, Optional

from app.constants import ANKARA_DISTRICTS, DISTRICT_ALIASES

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_TR_ASCII = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u",
})


def tr_lower(s: str) -> str:
    return s.translate(_TR_LOWER).lower()


def tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def fold(s: Optional[str]) -> str:
    """Büyük/küçük harf ve Türkçe karakter duyarsız karşılaştırma anahtarı."""
    if not s:
        return ""
    s = tr_lower(s).translate(_TR_ASCII)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Unvandaki şirket türü ve jenerik ekler — eşleştirmede ayırt edici değildir
_LEGAL_SUFFIX_PATTERNS = [
    r"anonim sirketi?", r"\ba ?s\b", r"limited sirketi?", r"\bltd\b", r"\bsti\b", r"\bsirketi?\b",
    r"kollektif", r"komandit", r"kooperatifi?", r"ticaret", r"sanayi", r"\bve\b", r"\btic\b", r"\bsan\b",
    r"\bltd sti\b", r"ithalat", r"ihracat", r"pazarlama", r"\bdis\b", r"\bic\b", r"\bltd\.?\b",
]
GENERIC_TOKENS = {
    "insaat", "gida", "turizm", "danismanlik", "hizmetleri", "hizmet", "yazilim", "bilisim", "teknoloji",
    "teknolojileri", "muhendislik", "otomotiv", "enerji", "lojistik", "tasimacilik", "saglik", "egitim",
    "medikal", "mimarlik", "tekstil", "makina", "makine", "elektrik", "elektronik", "reklam", "organizasyon",
    "uretim", "yatirim", "gayrimenkul", "emlak", "tarim", "hayvancilik", "kimya", "madencilik", "maden",
    "nakliyat", "temizlik", "guvenlik", "restoran", "cafe", "kafe", "mobilya", "dekorasyon", "proje",
    "grup", "group", "holding", "global", "international", "uluslararasi", "ankara", "turkiye", "ve", "anonim",
    "limited", "sirketi", "sirket", "ticaret", "sanayi", "ithalat", "ihracat", "pazarlama", "dis", "ic", "tic",
    "san", "ltd", "sti", "as", "a", "s", "the", "co", "yapi", "malzemeleri", "urunleri", "sistemleri",
}


def normalize_trade_name(name: Optional[str]) -> str:
    """Mükerrer kontrolü için unvan anahtarı (tür ekleri dahil, noktalama hariç)."""
    s = fold(name)
    s = re.sub(r"\ba s\b", "as", s)
    s = re.sub(r"\bltd sti\b", "limited sirketi", s)
    s = re.sub(r"\banonim sirket\b", "anonim sirketi", s)
    return s


def distinctive_tokens(name: Optional[str]) -> List[str]:
    """Unvanın ayırt edici kelimeleri (jenerik sektör ve tür eklerinden arındırılmış)."""
    toks = [t for t in fold(name).split() if t not in GENERIC_TOKENS and len(t) >= 2]
    return toks


def detect_company_type(name: Optional[str], hint: Optional[str] = None) -> str:
    s = fold(" ".join(x for x in [name, hint] if x))
    if re.search(r"anonim sirketi?|\ba s\b|\bas\b$", s):
        return "AS"
    if re.search(r"limited sirketi?|\bltd\b|\bsti\b", s):
        return "LTD"
    if "kooperatif" in s:
        return "KOOP"
    if "kollektif" in s:
        return "KOLL"
    if "komandit" in s:
        return "KOM"
    if hint and re.search(r"gercek kisi|sahis|ticari isletme", fold(hint)):
        return "SAHIS"
    if name and not re.search(r"sirket|kooperatif|birligi|vakfi|dernegi", s):
        return "SAHIS"
    return "DIGER"


_DISTRICT_FOLDED = {fold(d): d for d in ANKARA_DISTRICTS}


def detect_district(text: Optional[str]) -> Optional[str]:
    """Adres metninden Ankara ilçesini bulur. Belirsizse None döner."""
    if not text:
        return None
    f = fold(text)
    # 'X / Ankara' veya 'X/ANKARA' kalıbı en güvenilir sinyal
    m = re.search(r"([a-z]+(?: [a-z]+)?) ankara\b", f)
    candidates = []
    if m:
        tail = m.group(1)
        for key, d in _DISTRICT_FOLDED.items():
            if tail.endswith(key):
                return d
        for alias, d in DISTRICT_ALIASES.items():
            if tail.endswith(alias):
                return d
    for key, d in _DISTRICT_FOLDED.items():
        if re.search(rf"\b{re.escape(key)}\b", f):
            candidates.append(d)
    if not candidates:
        for alias, d in DISTRICT_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", f):
                candidates.append(d)
    uniq = sorted(set(candidates))
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) > 1:
        # Birden çok ilçe adı geçiyorsa (ör. 'Çankaya Cad., Yenimahalle') en sondakini seç
        last = max(uniq, key=lambda d: f.rfind(fold(d)))
        return last
    return None


def mentions_province(text: Optional[str], province: str = "ANKARA") -> bool:
    return bool(text) and fold(province) in fold(text)


def clean_mersis(value: Any) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 16 else None


def clean_registry_no(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = re.sub(r"[^0-9A-Za-z\-/]", "", s)
    return s or None


def registry_key(office: Optional[str], no: Optional[str]) -> Optional[str]:
    if not no:
        return None
    return f"{fold(office or 'ankara').replace(' ', '_')}:{no}"


def clean_nace(value: Any) -> Optional[str]:
    """NACE kodunu 'NN.NN.NN' / 'NN.NN' / 'NN' biçimine getirir."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 2:
        return None
    digits = digits[:6]
    parts = [digits[i:i + 2] for i in range(0, len(digits), 2)]
    return ".".join(parts)


_DATE_PATTERNS = ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%y", "%Y/%m/%d", "%Y%m%d"]


def parse_date(value: Any) -> Optional[dt.date]:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    s = s.split("T")[0].split(" ")[0]
    for p in _DATE_PATTERNS:
        try:
            return dt.datetime.strptime(s, p).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = re.sub(r"[^\d,\.]", "", str(value))
    if not s:
        return None
    # Türkçe biçim: 1.250.000,00
    if "," in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# --- İletişim normalizasyonu ---

FREE_EMAIL_DOMAINS = {
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yandex.com", "yandex.com.tr", "icloud.com",
    "hotmail.com.tr", "windowslive.com", "live.com", "mynet.com", "msn.com", "protonmail.com", "proton.me",
    "outlook.com.tr", "yaani.com", "gmail.com.tr",
}


def normalize_phone(raw: str) -> Optional[str]:
    """Türk telefon numarasını +90XXXXXXXXXX biçimine getirir."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 7 and digits.startswith("444"):
        return digits  # 444 XX XX hatları
    if len(digits) != 10 or digits[0] not in "2345789":
        return None
    return "+90" + digits


def is_mobile(phone_norm: str) -> bool:
    return phone_norm.startswith("+905")


def format_phone(phone_norm: str) -> str:
    if phone_norm.startswith("+90") and len(phone_norm) == 13:
        d = phone_norm[3:]
        return f"0{d[0:3]} {d[3:6]} {d[6:8]} {d[8:10]}"
    if len(phone_norm) == 7:
        return f"{phone_norm[0:3]} {phone_norm[3:5]} {phone_norm[5:7]}"
    return phone_norm


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip()


def registrable_domain(host: str) -> str:
    host = host.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-1] == "tr" and parts[-2] in {"com", "net", "org", "gen", "biz", "web", "info", "av", "dr", "bel", "edu", "gov", "k12", "tsk", "pol"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def content_hash(obj: Any) -> str:
    if isinstance(obj, str):
        data = obj
    else:
        data = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(re.sub(r"\s+", " ", data).strip().encode("utf-8")).hexdigest()


def first_nonempty(*values: Iterable[Any]) -> Any:
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None
