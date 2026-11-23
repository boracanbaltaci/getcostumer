"""İşletme web sitesinin 'güncel mi eski mi' sezgisel analizi.

Ana sayfa HTML'indeki teknik sinyaller puanlanır: HTTPS yokluğu, mobil uyum
meta etiketinin olmaması, eski doctype, terk edilmiş etiketler (font, marquee,
frameset), Flash, eski CMS üreticisi, eski jQuery, telif yılı gibi.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)

# Bu puan ve üzeri "eski görünümlü" sayılır.
OLD_THRESHOLD = 4

# Park edilmiş / satılık alan adı sayfaları: işletmenin gerçek sitesi değildir.
PARKED_MARKERS = (
    "domain for sale", "this domain is for sale", "buy this domain",
    "alan adı satılık", "bu alan adı satılık", "domain satılık",
    "sedoparking", "parkingcrew", "godaddy", "afternic", "dan.com",
    "hugedomains", "namecheap", "bodis.com", "sedo.com",
)

DEPRECATED_TAGS = ("font", "center", "marquee", "big", "tt", "strike", "applet", "blink")
OLD_GENERATORS = (
    "frontpage", "microsoft word", "golive", "netobjects", "publisher",
    "joomla! 1.0", "joomla! 1.5", "wordpress 2.", "wordpress 3.",
)
OLD_CHARSETS = ("windows-1254", "iso-8859-9", "iso-8859-1", "windows-1252")
JQUERY_OLD_RE = re.compile(r"jquery[-.]?([12])\.", re.I)
COPYRIGHT_RE = re.compile(r"(?:©|&copy;|copyright|telif)\D{0,15}(19|20)(\d{2})", re.I)


@dataclass
class SiteVerdict:
    status: str                       # "eski" | "erisilemedi" | "modern"
    score: int = 0
    notes: list[str] = field(default_factory=list)
    final_url: str = ""


def _fetch(url: str) -> Tuple[Optional[str], str, str]:
    """(html, final_url, hata_notu) döner; hata varsa html None olur."""
    try:
        resp = httpx.get(
            url,
            timeout=settings.WEBSITE_CHECK_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": settings.WEBSITE_USER_AGENT, "Accept-Language": "tr,en;q=0.8"},
            verify=False,
        )
    except httpx.HTTPError as exc:
        return None, url, f"siteye ulaşılamadı ({exc.__class__.__name__})"
    if resp.status_code >= 400:
        return None, str(resp.url), f"HTTP {resp.status_code}"
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        return None, str(resp.url), f"HTML olmayan içerik ({ctype.split(';')[0] or 'bilinmiyor'})"
    return resp.text, str(resp.url), ""


def _doctype_is_modern(html: str) -> bool:
    head = html[:500].lstrip().lower()
    return head.startswith("<!doctype html>")


def analyze_html(html: str, final_url: str, now_year: int) -> Tuple[int, list[str]]:
    """HTML içindeki eski teknoloji sinyallerini puanlar."""
    score = 0
    notes: list[str] = []
    low = html.lower()
    soup = BeautifulSoup(html, "html.parser")

    if urlparse(final_url).scheme == "http":
        score += 2
        notes.append("HTTPS kullanmıyor")
    if not soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}):
        score += 2
        notes.append("mobil uyum (viewport) etiketi yok")
    if not _doctype_is_modern(html):
        score += 2
        notes.append("eski doctype")
    if soup.find("frameset") or soup.find("frame"):
        score += 3
        notes.append("frame/frameset kullanıyor")
    deprecated = [t for t in DEPRECATED_TAGS if soup.find(t)]
    if deprecated:
        score += 2
        notes.append(f"terk edilmiş etiketler: {', '.join(deprecated[:4])}")
    if soup.find("object") or soup.find("embed") or ".swf" in low:
        score += 3
        notes.append("Flash/embedded nesne içeriyor")
    gen = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    gen_val = (gen.get("content") or "").lower() if gen else ""
    if any(g in gen_val for g in OLD_GENERATORS):
        score += 3
        notes.append(f"eski site aracı: {gen.get('content', '').strip()[:40]}")
    if any(f"charset={c}" in low or f'charset="{c}"' in low for c in OLD_CHARSETS):
        score += 1
        notes.append("eski karakter kodlaması")
    if soup.find("meta", attrs={"http-equiv": re.compile(r"^x-ua-compatible$", re.I)}):
        score += 1
        notes.append("eski IE uyumluluk etiketi")
    if JQUERY_OLD_RE.search(low):
        score += 1
        notes.append("eski jQuery sürümü")
    tables = len(soup.find_all("table"))
    if tables >= 4 and not soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}):
        score += 1
        notes.append("tablo tabanlı yerleşim")
    year_matches = [int(y1 + y2) for y1, y2 in COPYRIGHT_RE.findall(html)]
    if year_matches and max(year_matches) <= now_year - 6:
        score += 1
        notes.append(f"telif yılı eski ({max(year_matches)})")
    return score, notes


def check_website(url: str, now_year: int) -> SiteVerdict:
    """Siteyi indirir ve modern/eski kararı verir."""
    html, final_url, err = _fetch(url)
    if html is None:
        return SiteVerdict(status="erisilemedi", notes=[err], final_url=final_url)
    low = html.lower()
    if any(m in low for m in PARKED_MARKERS):
        return SiteVerdict(status="erisilemedi", notes=["park/satılık alan adı sayfası"],
                         final_url=final_url)
    score, notes = analyze_html(html, final_url, now_year)
    status = "eski" if score >= OLD_THRESHOLD else "modern"
    return SiteVerdict(status=status, score=score, notes=notes, final_url=final_url)
