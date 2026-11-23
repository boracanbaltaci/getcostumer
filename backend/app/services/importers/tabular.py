"""CSV / Excel içe aktarma: başlıkları kanonik alanlara eşler.

TTSG elektronik gazete fihrist Excel dosyası (sıra no, TSM, TSM no, unvan, ilan türü,
gazete tarihi/sayısı, baş/son sayfa) ve genel firma listeleri desteklenir.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.services.normalize import fold

HEADER_SYNONYMS: Dict[str, List[str]] = {
    "trade_name": ["ticaret unvani", "unvan", "unvani", "firma adi", "sirket adi", "isletme adi", "unvan1",
                   "ticaret unvan", "trade name", "company name", "firma", "sirket unvani", "name"],
    "trade_name_2": ["unvan2"],
    "establishment_date": ["kurulus tarihi", "tescil tarihi", "kayit tarihi", "establishment date",
                           "registration date", "kurulus tescil tarihi"],
    "registry_office": ["ticaret sicil mudurlugu", "ticaret sicili mudurlugu", "sicil mudurlugu", "tsm", "mudurluk"],
    "registry_no": ["ticaret sicil no", "ticaret sicili no", "sicil no", "sicil numarasi", "tsm no",
                    "ticaret sicil numarasi", "registry no"],
    "mersis_no": ["mersis", "mersis no", "mersis numarasi", "mersis number"],
    "tax_no": ["vergi no", "vkn", "vergi numarasi", "vergi kimlik no"],
    "province": ["il", "sehir", "province", "city"],
    "district": ["ilce", "district"],
    "address": ["adres", "isletme adresi", "address", "kurulus adresi", "merkez adresi", "sirket adresi"],
    "activity_text": ["faaliyet konusu", "amac ve konu", "amac konu", "konu", "faaliyet", "isletme konusu",
                      "activity", "istigal konusu", "amac konu tekst metin"],
    "nace_code": ["nace", "nace kodu", "ana nace kodu", "nace code"],
    "nace_description": ["nace aciklamasi", "ana nace konu aciklamasi", "nace konu aciklamasi"],
    "nace_verified": ["nace dogrulandi", "nace dogrulanmis"],
    "company_type": ["sirket turu", "sirket tipi", "company type", "tur", "isletme turu"],
    "capital": ["sermaye", "toplam sermaye", "capital"],
    "announcement_url": ["ilan linki", "ilan baglantisi", "kurulus ilani", "url", "link", "ilan url"],
    "announcement_type": ["ilan turu", "ilan tipi", "ilan turleri", "coklu ilan turu"],
    "gazette_date": ["gazete tarihi", "yayin tarihi", "ilan tarihi"],
    "gazette_no": ["gazete sayisi", "sayi", "sayisi", "gazete no"],
    "gazette_page": ["bas sayfa", "sayfa", "sayfa no"],
    "external_id": ["sira no", "kayit no", "id"],
    "phone": ["telefon", "kurumsal telefon", "tel", "phone"],
    "email": ["e posta", "eposta", "email", "e mail", "kurumsal e posta", "mail"],
    "website": ["web sitesi", "web", "website", "internet sitesi", "site"],
}
_LOOKUP = {syn: canon for canon, syns in HEADER_SYNONYMS.items() for syn in syns}


def map_headers(headers: List[str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    used = set()
    for i, h in enumerate(headers):
        key = fold(str(h or ""))
        canon = _LOOKUP.get(key)
        if canon and canon not in used:
            mapping[i] = canon
            used.add(canon)
    return mapping


def _cell(v: Any) -> Any:
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if v is None:
        return None
    return str(v).strip()


def read_rows(filename: str, data: bytes) -> Tuple[List[str], List[List[Any]]]:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
    elif name.endswith((".csv", ".txt", ".tsv")):
        text = None
        for enc in ("utf-8-sig", "cp1254", "iso-8859-9"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("Dosya kodlaması çözülemedi (UTF-8 / Windows-1254 deneyin)")
        sample = text[:5000]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            delim = dialect.delimiter
        except csv.Error:
            delim = ";" if sample.count(";") > sample.count(",") else ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    else:
        raise ValueError("Desteklenmeyen dosya türü. CSV, XLSX veya PDF yükleyin.")
    # İlk dolu satırı başlık kabul et; başlık satırını ilk 10 satırda ara
    header_idx = 0
    best = -1
    for i, r in enumerate(rows[:10]):
        score = len(map_headers([str(c) if c is not None else "" for c in r]))
        if score > best:
            best, header_idx = score, i
    headers = [str(c) if c is not None else "" for c in rows[header_idx]] if rows else []
    body = [r for r in rows[header_idx + 1:] if any(c not in (None, "") for c in r)]
    return headers, body


def iter_records(filename: str, data: bytes) -> Iterator[Tuple[int, Dict[str, Any]]]:
    headers, body = read_rows(filename, data)
    mapping = map_headers(headers)
    if "trade_name" not in mapping.values():
        raise ValueError(
            "Dosyada ticaret unvanı sütunu bulunamadı. Beklenen başlıklardan biri: "
            "'Ticaret Unvanı', 'Unvan', 'Firma Adı'. Bulunan başlıklar: " + ", ".join(headers)
        )
    for row_no, row in enumerate(body, start=2):
        rec: Dict[str, Any] = {}
        for i, canon in mapping.items():
            if i < len(row):
                rec[canon] = _cell(row[i])
        if rec.get("trade_name_2"):
            rec["trade_name"] = f"{rec.get('trade_name') or ''} {rec.pop('trade_name_2')}".strip()
        else:
            rec.pop("trade_name_2", None)
        nv = rec.get("nace_verified")
        rec["nace_verified"] = fold(str(nv)) in {"evet", "e", "1", "true", "yes", "dogrulandi"} if nv else False
        yield row_no, rec


def mapped_columns(filename: str, data: bytes) -> Dict[str, str]:
    headers, _ = read_rows(filename, data)
    return {headers[i]: canon for i, canon in map_headers(headers).items()}


def extract_contacts(rec: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {k: rec.pop(k, None) for k in ("phone", "email", "website")}
