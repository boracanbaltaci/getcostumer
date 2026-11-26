"""İşletme web sitesinden e-posta adresi çıkarma.

`extract_emails` saf fonksiyondur (indirilmiş HTML üzerinde çalışır) —
tarama sırasında sitescan'in zaten getirdiği ana sayfada ek isteksiz
kullanılır. `discover_emails` ise modal açıldığında çağrılır: ana sayfada
adres yoksa yaygın iletişim sayfalarını dener; tek sayfa hatası akışı
durdurmaz.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple
from urllib.parse import urljoin

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAILTO_RE = re.compile(r'href=["\']mailto:([^"\'?]+)', re.I)

# Kazıma çöpleri: resim/ikon dosya adları, şablon yer tutucuları, telemetri.
_JUNK = ("example.", "sentry", "wixpress", "@2x.", "@3x.", ".png", ".jpg",
         ".jpeg", ".gif", ".webp", ".svg", "yourdomain", "domain.com",
         "u003e", "sentry.io")

# Ana sayfada adres yoksa denenecek yaygın iletişim sayfaları (ilk bulguda dur).
_CONTACT_PATHS = ("/iletisim", "/contact", "/contact-us",
                  "/iletisim.html", "/contact.html", "/hakkimizda")

MAX_EMAILS = 5


def _clean(addr: str) -> str:
    return addr.strip().strip(".,;:()[]<>").lower()


def extract_emails(html: str) -> list[str]:
    """HTML'den benzersiz e-posta listesi — mailto: bağlantıları önde gelir."""
    found: list[str] = []
    for raw in MAILTO_RE.findall(html) + EMAIL_RE.findall(html):
        addr = _clean(raw)
        if "@" not in addr or any(j in addr for j in _JUNK):
            continue
        if addr not in found:
            found.append(addr)
        if len(found) >= MAX_EMAILS:
            break
    return found


def _fetch(url: str) -> Tuple[Optional[str], str]:
    """(html, final_url) döner; hatada html None. sitescan._fetch ikizi —
    iki modülün birbirine bağımlı olmaması için ayrı tutulur."""
    try:
        resp = httpx.get(
            url, timeout=settings.WEBSITE_CHECK_TIMEOUT, follow_redirects=True,
            headers={"User-Agent": settings.WEBSITE_USER_AGENT,
                     "Accept-Language": "tr,en;q=0.8"},
            verify=False,
        )
    except httpx.HTTPError:
        return None, url
    if resp.status_code >= 400:
        return None, str(resp.url)
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        return None, str(resp.url)
    return resp.text, str(resp.url)


def discover_emails(url: str) -> list[str]:
    """Siteden e-posta bul: önce ana sayfa, yoksa yaygın iletişim sayfaları."""
    html, final_url = _fetch(url)
    if html is None:
        return []
    emails = extract_emails(html)
    if emails:
        return emails
    for path in _CONTACT_PATHS:
        page, _ = _fetch(urljoin(final_url or url, path))
        if page is None:
            continue
        emails = extract_emails(page)
        if emails:
            return emails
    return []
