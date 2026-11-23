"""İşletmenin resmî web sitesini doğrulama ve sitedeki kurumsal iletişim bilgilerini çıkarma.

Yanlış eşleştirmeyi önlemek için site, unvan / MERSİS / sicil no / adres sinyalleriyle puanlanır.
Eşik altındaki siteler kabul edilmez.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models import Business
from app.services.enrichment import fetch as fetcher
from app.services.normalize import (
    FREE_EMAIL_DOMAINS, distinctive_tokens, email_domain, fold, registrable_domain,
)

ACCEPT_THRESHOLD = 60
CONTACT_HINTS = ("iletisim", "contact", "bize-ulasin", "bize ulasin", "hakkimizda", "about", "kunye", "kurumsal")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?90[\s\-\.]?|0)?\(?\s?([2-5]\d{2}|444|850)\s?\)?[\s\-\.]?(\d{3})[\s\-\.]?(\d{2})[\s\-\.]?(\d{2})")


@dataclass
class SiteVerdict:
    url: str
    score: int
    evidence: List[str] = field(default_factory=list)
    emails: List[Tuple[str, str]] = field(default_factory=list)  # (email, sayfa_url)
    phones: List[Tuple[str, str]] = field(default_factory=list)
    pages: List[str] = field(default_factory=list)


def _text(html: str) -> Tuple[str, BeautifulSoup]:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text(" ", strip=True), soup


def score_site(b: Business, text: str, url: str) -> Tuple[int, List[str]]:
    ft = fold(text)
    ev: List[str] = []
    score = 0
    toks = distinctive_tokens(b.trade_name)
    if not toks:
        return 0, ["Unvanda ayırt edici kelime yok; otomatik eşleştirme yapılmadı"]
    present = [t for t in toks if re.search(rf"\b{re.escape(t)}\b", ft)]
    if len(present) < len(toks):
        if not present:
            return 0, ["Unvanın ayırt edici kelimeleri sitede geçmiyor"]
        score += 10
        ev.append(f"Unvan kelimelerinin bir kısmı geçiyor ({', '.join(present)})")
    else:
        score += 25
        ev.append(f"Unvanın ayırt edici kelimeleri geçiyor ({', '.join(present)})")
    core = re.sub(r"\b(anonim|limited)\s+sirketi\b.*$", "", fold(b.trade_name)).strip()
    if core and len(core) > 6 and core in ft:
        score += 20
        ev.append("Ticaret unvanı sitede tam olarak geçiyor")
    if b.mersis_no and b.mersis_no in re.sub(r"\D", "", text):
        score += 60
        ev.append("MERSİS numarası sitede geçiyor")
    if b.registry_no and re.search(rf"sicil\D{{0,25}}{re.escape(b.registry_no)}\b", ft):
        score += 20
        ev.append("Ticaret sicil numarası sitede geçiyor")
    if "ankara" in ft:
        score += 10
        ev.append("'Ankara' ifadesi geçiyor")
    if b.district and fold(b.district) in ft:
        score += 10
        ev.append(f"İlçe ({b.district}) geçiyor")
    host = registrable_domain(urlparse(url).hostname or "")
    if any(t in host.replace("-", "") for t in toks if len(t) >= 4):
        score += 10
        ev.append(f"Alan adı unvanla uyumlu ({host})")
    hard_id = any(e.startswith(("MERSİS", "Ticaret sicil")) for e in ev)
    if not hard_id:
        # Resmî kimlik (MERSİS / sicil no) eşleşmesi yoksa 'yüksek' güven verilmez
        score = min(score, 70)
    return min(score, 100), ev


def extract_contacts(text: str, soup: BeautifulSoup, page_url: str, site_domain: str):
    emails, phones = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            emails.append(href[7:].split("?")[0].strip())
        elif href.lower().startswith("tel:"):
            phones.append(href[4:].strip())
    emails += EMAIL_RE.findall(text)
    phones += ["".join(m) for m in PHONE_RE.findall(text)]
    good_emails = []
    for e in dict.fromkeys(x.lower() for x in emails):
        d = email_domain(e)
        if d in FREE_EMAIL_DOMAINS:
            continue  # kişisel olabilir
        if registrable_domain(d) != site_domain:
            continue  # başka alan adındaki e-posta: işletmeye ait olduğu doğrulanamaz
        if re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", e):
            continue
        good_emails.append((e, page_url))
    return good_emails, [(p, page_url) for p in dict.fromkeys(phones)]


def verify_and_extract(b: Business, url: str, log: Callable[[str], None]) -> Optional[SiteVerdict]:
    html, final_url, status = fetcher.fetch(url)
    if status != "ok" or not html:
        log(f"{url}: erişilemedi ({status})")
        return None
    final_url = final_url or url
    text, soup = _text(html)
    site_domain = registrable_domain(urlparse(final_url).hostname or "")
    verdict = SiteVerdict(url=f"{urlparse(final_url).scheme}://{urlparse(final_url).hostname}", score=0,
                          pages=[final_url])
    combined = text
    em, ph = extract_contacts(text, soup, final_url, site_domain)
    verdict.emails += em
    verdict.phones += ph
    # İletişim / hakkımızda sayfaları (aynı alan adı, en fazla 3)
    links = []
    for a in soup.find_all("a", href=True):
        full = urljoin(final_url, a["href"])
        if registrable_domain(urlparse(full).hostname or "") != site_domain:
            continue
        label = fold(a.get_text(" ") + " " + a["href"])
        if any(h in label for h in CONTACT_HINTS):
            links.append(full.split("#")[0])
    for link in list(dict.fromkeys(links))[:3]:
        h2, f2, s2 = fetcher.fetch(link)
        if s2 != "ok" or not h2:
            continue
        t2, soup2 = _text(h2)
        combined += " " + t2
        verdict.pages.append(f2 or link)
        em, ph = extract_contacts(t2, soup2, f2 or link, site_domain)
        verdict.emails += em
        verdict.phones += ph
    verdict.score, verdict.evidence = score_site(b, combined, final_url)
    log(f"{final_url}: eşleşme puanı {verdict.score} ({'; '.join(verdict.evidence)})")
    return verdict


def candidate_domains(b: Business) -> List[str]:
    """Unvandan olası alan adları. Kısa/jenerik adlar üretilmez."""
    toks = distinctive_tokens(b.trade_name)
    allt = fold(re.sub(r"(?i)\b(anonim|limited)\s+[şs]irketi\b.*$", "", b.trade_name or "")).split()
    labels = []
    if toks:
        labels.append("".join(toks[:2]))
        labels.append("".join(toks))
        if allt:
            labels.append("".join(allt[:3]))
            labels.append("".join(allt))
            labels.append("-".join(allt[:3]))
    out = []
    for lab in dict.fromkeys(labels):
        lab = re.sub(r"[^a-z0-9\-]", "", lab)
        if len(lab.replace("-", "")) < 6 or len(lab) > 40:
            continue
        out += [f"https://www.{lab}.com.tr", f"https://www.{lab}.com"]
    return out[:6]
