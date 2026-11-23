"""sitescan birim testleri — ağ çağrısı yapmadan HTML analizini doğrular."""
from __future__ import annotations

import datetime as dt

from app.services.sitescan import OLD_THRESHOLD, analyze_html

YEAR = dt.date.today().year

MODERN_HTML = """<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Modern Site</title></head>
<body><main><h1>Merhaba</h1><p>© {year} Firma</p></main></body></html>
""".format(year=YEAR)

OLD_HTML = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Content-Type" content="text/html; charset=windows-1254">
<meta name="generator" content="Microsoft FrontPage 6.0">
</head><body>
<center><font face="Tahoma" size="2">Hoş geldiniz</font></center>
<marquee>Duyurular</marquee>
<table><tr><td><table><tr><td><table><tr><td><table><tr><td>x</td></tr></table>
</td></tr></table></td></tr></table></td></tr></table>
<script src="/js/jquery-1.4.2.min.js"></script>
<p>Copyright © 2012</p>
</body></html>
"""


def test_modern_site_threshold_altinda():
    score, notes = analyze_html(MODERN_HTML, "https://ornek.com.tr", YEAR)
    assert score < OLD_THRESHOLD, f"modern site eski sayıldı: {score} — {notes}"


def test_eski_site_threshold_ustunde():
    score, notes = analyze_html(OLD_HTML, "http://eski-firma.com.tr", YEAR)
    assert score >= OLD_THRESHOLD
    assert any("HTTPS" in n for n in notes)
    assert any("viewport" in n for n in notes)
    assert any("doctype" in n for n in notes)


def test_frameset_puan_verir():
    html = "<!DOCTYPE html><html><frameset><frame src='a.html'></frameset></html>"
    score, notes = analyze_html(html, "https://x.com", YEAR)
    assert score >= 3
    assert any("frame" in n for n in notes)
