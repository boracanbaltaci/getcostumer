"""TTSG gazete / ilan PDF'lerinden metin çıkarma.

Yalnızca kullanıcının hukuka uygun biçimde edindiği PDF'ler (satın alınan günlük elektronik
gazete, veri aboneliği kapsamında gelen PDF, üyelikle görüntülenip indirilen ilan) içindir.
Taranmış (resim) PDF'lerde metin katmanı yoksa OCR gerekir; bu durumda kayıt üretilmez
ve kullanıcıya bildirilir.
"""
from __future__ import annotations

import io
import re
from typing import Dict, Iterator, List, Optional, Tuple

from pypdf import PdfReader

from app.services import ttsg_parser
from app.services.normalize import parse_date

_RE_GAZ_NO = re.compile(r"Say[ıi]\s*[:：]?\s*(\d{4,6})", re.I)
_RE_GAZ_DATE = re.compile(r"(\d{1,2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4})|(\d{2}[./]\d{2}[./]\d{4})", re.I)
_MONTHS = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
           "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}


def extract_pages(data: bytes) -> List[str]:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # bozuk sayfa
            pages.append("")
    return pages


def _parse_tr_long_date(s: str):
    import datetime as dt
    parts = s.split()
    try:
        return dt.date(int(parts[2]), _MONTHS[parts[1].lower().replace("I", "ı")], int(parts[0]))
    except (KeyError, ValueError, IndexError):
        return None


def detect_gazette_meta(first_page: str) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {"gazette_no": None, "gazette_date": None}
    head = first_page[:1500]
    m = _RE_GAZ_NO.search(head)
    if m:
        meta["gazette_no"] = m.group(1)
    m = _RE_GAZ_DATE.search(head)
    if m:
        d = _parse_tr_long_date(m.group(1)) if m.group(1) else parse_date(m.group(2).replace("/", "."))
        meta["gazette_date"] = d.isoformat() if d else None
    return meta


def iter_announcements(data: bytes, gazette_date: Optional[str] = None, gazette_no: Optional[str] = None
                       ) -> Iterator[Tuple[int, Dict, str, List[str]]]:
    """(sayfa_no, kanonik_kayit, ham_metin, uyarilar) üretir."""
    pages = extract_pages(data)
    if not any(p.strip() for p in pages):
        raise ValueError("PDF'de metin katmanı yok (taranmış görüntü olabilir). OCR'lı PDF yükleyin.")
    meta = detect_gazette_meta(pages[0]) if pages else {}
    gdate = gazette_date or meta.get("gazette_date")
    gno = gazette_no or meta.get("gazette_no")
    for page_no, text in enumerate(pages, start=1):
        for block in ttsg_parser.split_gazette_text(text):
            p = ttsg_parser.parse_announcement_text(block)
            if not (p.trade_name or p.registry_no or p.mersis_no):
                continue
            rec = p.as_record()
            rec.update({"gazette_date": gdate, "gazette_no": gno, "gazette_page": str(page_no)})
            yield page_no, rec, block, p.warnings
