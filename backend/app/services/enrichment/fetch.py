"""Nazik HTTP istemcisi: robots.txt'e uyar, host başına hız sınırı uygular, boyutu sınırlar.

Yalnızca işletmenin KENDİ kamuya açık web sitesi ve resmî API'ler için kullanılır.
Giriş/CAPTCHA arkasındaki sayfalara erişmez; 401/403/429 yanıtlarında geri çekilir.
"""
from __future__ import annotations

import threading
import time
import urllib.robotparser
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import settings

_MAX_BYTES = 1_500_000
_robots_cache: Dict[str, Tuple[float, Optional[urllib.robotparser.RobotFileParser]]] = {}
_last_hit: Dict[str, float] = {}
_lock = threading.Lock()
MIN_INTERVAL = 1.0


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.ENRICHMENT_USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9"},
        timeout=settings.ENRICHMENT_HTTP_TIMEOUT, follow_redirects=True, max_redirects=5,
    )


def _robots(scheme: str, host: str) -> Optional[urllib.robotparser.RobotFileParser]:
    key = f"{scheme}://{host}"
    now = time.time()
    cached = _robots_cache.get(key)
    if cached and now - cached[0] < 3600:
        return cached[1]
    rp: Optional[urllib.robotparser.RobotFileParser] = urllib.robotparser.RobotFileParser()
    try:
        with _client() as c:
            r = c.get(f"{key}/robots.txt")
        if r.status_code in (401, 403):
            rp.disallow_all = True  # type: ignore[attr-defined]
        elif r.status_code >= 400:
            rp.allow_all = True  # type: ignore[attr-defined]
        else:
            rp.parse(r.text.splitlines())
    except httpx.HTTPError:
        rp = None  # robots alınamadı → siteye hiç erişme
    _robots_cache[key] = (now, rp)
    return rp


def allowed(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    rp = _robots(p.scheme, p.hostname)
    if rp is None:
        return False
    return rp.can_fetch(settings.ENRICHMENT_USER_AGENT, url)


def _throttle(host: str) -> None:
    with _lock:
        last = _last_hit.get(host, 0)
        wait = MIN_INTERVAL - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()


def fetch(url: str) -> Tuple[Optional[str], Optional[str], str]:
    """(html, son_url, durum) döndürür. durum: ok | robots | http_<kod> | error | not_html"""
    if not allowed(url):
        return None, None, "robots"
    host = urlparse(url).hostname or ""
    _throttle(host)
    try:
        with _client() as c:
            with c.stream("GET", url) as r:
                if r.status_code >= 400:
                    return None, str(r.url), f"http_{r.status_code}"
                ctype = r.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype:
                    return None, str(r.url), "not_html"
                buf = b""
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > _MAX_BYTES:
                        break
                enc = r.encoding or "utf-8"
                try:
                    text = buf.decode(enc, errors="replace")
                except LookupError:
                    text = buf.decode("utf-8", errors="replace")
                return text, str(r.url), "ok"
    except httpx.HTTPError as exc:
        return None, None, f"error:{type(exc).__name__}"
