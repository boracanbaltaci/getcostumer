"""Excel ve PDF dışa aktarma (işletme listesi, teklif, rapor)."""
from __future__ import annotations

import datetime as dt
import io
import os
from typing import Dict, List, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import settings
from app.constants import COMPANY_TYPES, STAGE_LABELS
from app.models import Business, Quote
from app.services.contacts import best_contacts
from app.services.scoring.sectors import SECTORS

_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
_font_ready: Optional[tuple] = None


def _fonts() -> tuple:
    """Türkçe karakter (ş, ğ, ı, İ) destekli TTF yazı tipi kaydeder."""
    global _font_ready
    if _font_ready:
        return _font_ready
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont("TRSans", regular))
            pdfmetrics.registerFont(TTFont("TRSans-Bold", bold if os.path.exists(bold) else regular))
            _font_ready = ("TRSans", "TRSans-Bold")
            return _font_ready
    _font_ready = ("Helvetica", "Helvetica-Bold")
    return _font_ready


def _fmt_date(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def _money(v) -> str:
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


EXPORT_COLUMNS = [
    ("Ticaret Unvanı", lambda b, c: b.trade_name),
    ("Kuruluş/Tescil Tarihi", lambda b, c: _fmt_date(b.establishment_date)),
    ("İlan Tarihi", lambda b, c: _fmt_date(b.gazette_date)),
    ("Sicil Müdürlüğü", lambda b, c: b.registry_office),
    ("Ticaret Sicil No", lambda b, c: b.registry_no),
    ("MERSİS No", lambda b, c: b.mersis_no),
    ("İl", lambda b, c: b.province),
    ("İlçe", lambda b, c: b.district),
    ("Adres", lambda b, c: b.address),
    ("Faaliyet Konusu", lambda b, c: (b.activity_text or "")[:500]),
    ("NACE", lambda b, c: b.nace_code),
    ("NACE Doğrulandı", lambda b, c: "Evet" if b.nace_verified else "Hayır"),
    ("Şirket Türü", lambda b, c: COMPANY_TYPES.get(b.company_type or "", b.company_type)),
    ("Sektör (analiz)", lambda b, c: SECTORS.get(b.sector or "", {}).get("label", "")),
    ("Kurumsal Telefon", lambda b, c: c["phone"].value if c["phone"] else "Bulunamadı"),
    ("Telefon Kaynağı", lambda b, c: c["phone"].source_url or c["phone"].source_name if c["phone"] else ""),
    ("Telefon Güven", lambda b, c: c["phone"].confidence if c["phone"] else ""),
    ("Kurumsal E-posta", lambda b, c: c["email"].value if c["email"] else "Bulunamadı"),
    ("E-posta Kaynağı", lambda b, c: c["email"].source_url or c["email"].source_name if c["email"] else ""),
    ("Web Sitesi", lambda b, c: c["website"].value if c["website"] else "Bulunamadı"),
    ("İSG Puanı", lambda b, c: b.isg_score),
    ("Yazılım Puanı", lambda b, c: b.software_score),
    ("Toplam Potansiyel", lambda b, c: b.total_score),
    ("Öncelik", lambda b, c: b.priority),
    ("Satış Durumu", lambda b, c: STAGE_LABELS.get(b.sales_status, b.sales_status)),
    ("İletişim İzni (İYS)", lambda b, c: {"bilinmiyor": "Kontrol edilmedi", "engel_yok": "Ret kaydı yok", "ret": "RET"}.get(b.iys_status, b.iys_status)),
    ("Kuruluş İlanı", lambda b, c: b.announcement_url or b.source_reference),
    ("Veri Kaynağı", lambda b, c: b.source.name if b.source else ""),
    ("Veri Doğrulama Tarihi", lambda b, c: b.verified_at.strftime("%d.%m.%Y %H:%M") if b.verified_at else ""),
]


def businesses_xlsx(rows: Sequence[Business]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "İşletmeler"
    ws.append([c[0] for c in EXPORT_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for b in rows:
        if b.do_not_contact:
            c = {"phone": None, "email": None, "website": best_contacts(b)["website"]}
        else:
            c = best_contacts(b)
        ws.append([fn(b, c) for _, fn in EXPORT_COLUMNS])
    for i, (title, _) in enumerate(EXPORT_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(60, max(12, len(title) + 4))
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    meta = wb.create_sheet("Bilgi")
    meta.append(["Oluşturulma", dt.datetime.now().strftime("%d.%m.%Y %H:%M")])
    meta.append(["Not", "İletişim bilgileri kamuya açık kurumsal kaynaklardan alınmıştır; 'Bulunamadı' doğrulanamadığını gösterir."])
    meta.append(["KVKK", "Bu dosya kişisel veri içerebilir; yalnızca yetkili satış personeliyle paylaşın ve saklama politikasına uyun."])
    meta.append(["Uyarı", "'İletişim İzni' RET olan veya 'iletişime geçme' işaretli işletmelere ticari ileti gönderilmez."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _styles():
    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName=bold, fontSize=16, leading=20),
        "h": ParagraphStyle("h", parent=ss["Heading2"], fontName=bold, fontSize=11, leading=14),
        "p": ParagraphStyle("p", parent=ss["Normal"], fontName=regular, fontSize=9, leading=12),
        "small": ParagraphStyle("s", parent=ss["Normal"], fontName=regular, fontSize=7.5, leading=9.5),
        "regular": regular, "bold": bold,
    }


def businesses_pdf(rows: Sequence[Business], title: str = "İşletme Listesi") -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=title)
    data = [["Unvan", "İlçe", "Tarih", "Telefon", "E-posta", "Web", "İSG", "Yaz.", "Durum"]]
    for b in rows:
        c = best_contacts(b)
        data.append([
            Paragraph(b.trade_name or "", st["small"]), b.district or "", _fmt_date(b.establishment_date or b.gazette_date),
            c["phone"].value if c["phone"] and not b.do_not_contact else "Bulunamadı",
            Paragraph(c["email"].value if c["email"] and not b.do_not_contact else "Bulunamadı", st["small"]),
            Paragraph(c["website"].value if c["website"] else "Bulunamadı", st["small"]),
            str(b.isg_score if b.isg_score is not None else "-"), str(b.software_score if b.software_score is not None else "-"),
            STAGE_LABELS.get(b.sales_status, b.sales_status),
        ])
    t = Table(data, colWidths=[80 * mm, 25 * mm, 20 * mm, 30 * mm, 45 * mm, 40 * mm, 10 * mm, 10 * mm, 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), st["regular"]), ("FONTNAME", (0, 0), (-1, 0), st["bold"]),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8CED6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F8")]),
    ]))
    doc.build([Paragraph(title, st["title"]),
               Paragraph(f"Oluşturulma: {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} · Kayıt: {len(rows)}", st["p"]),
               Spacer(1, 4 * mm), t])
    return buf.getvalue()


def quote_pdf(q: Quote, b: Business, service_label: str) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=f"Teklif {q.number}")
    story = [Paragraph(settings.COMPANY_NAME_FOR_QUOTES, st["title"])]
    if settings.COMPANY_INFO_FOR_QUOTES:
        story.append(Paragraph(settings.COMPANY_INFO_FOR_QUOTES, st["p"]))
    story += [Spacer(1, 6 * mm), Paragraph(f"FİYAT TEKLİFİ – {q.number}", st["h"]),
              Paragraph(f"Tarih: {_fmt_date(q.created_at.date() if q.created_at else dt.date.today())}"
                        f" · Geçerlilik: {_fmt_date(q.valid_until) or '-'}", st["p"]),
              Spacer(1, 4 * mm), Paragraph("<b>Sayın</b> " + (b.trade_name or ""), st["p"])]
    if b.address:
        story.append(Paragraph(b.address, st["small"]))
    story += [Spacer(1, 4 * mm), Paragraph(f"Konu: {q.title} ({service_label})", st["p"]), Spacer(1, 4 * mm)]
    data = [["#", "Açıklama", "Miktar", "Birim", "Birim Fiyat", "KDV %", "Tutar"]]
    for i, it in enumerate(q.items or [], start=1):
        data.append([str(i), Paragraph(it.get("description", ""), st["small"]), f"{it.get('quantity', 0):g}",
                     it.get("unit", "Adet"), _money(it.get("unit_price")), f"{it.get('vat_rate', 20):g}",
                     _money(it.get("line_total"))])
    data += [["", "", "", "", "", "Ara toplam", _money(q.subtotal)],
             ["", "", "", "", "", "KDV", _money(q.vat_total)],
             ["", "", "", "", "", "GENEL TOPLAM", f"{_money(q.total)} {q.currency}"]]
    t = Table(data, colWidths=[8 * mm, 72 * mm, 15 * mm, 15 * mm, 25 * mm, 18 * mm, 28 * mm], repeatRows=1)
    n = len(data)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), st["regular"]), ("FONTNAME", (0, 0), (-1, 0), st["bold"]),
        ("FONTNAME", (5, n - 1), (-1, n - 1), st["bold"]), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, n - 4), 0.25, colors.HexColor("#C8CED6")), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LINEABOVE", (5, n - 3), (-1, n - 3), 0.5, colors.black),
    ]))
    story.append(t)
    if q.notes:
        story += [Spacer(1, 6 * mm), Paragraph("Notlar", st["h"]), Paragraph(q.notes.replace("\n", "<br/>"), st["p"])]
    doc.build(story)
    return buf.getvalue()


def sales_report_xlsx(report: Dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Özet"
    ws.append(["Dönem", f"{report['period']['start']} – {report['period']['end']}"])
    ws.append(["Tespit edilen işletme", report["detected"]])
    ws.append([])
    ws.append(["Kazanılan", "Adet", "Tutar (TL)"])
    for w in report["won"]:
        ws.append([w["service_line"], w["count"], w["value"]])
    ws.append([])
    ws.append(["Teklif durumu", "Adet", "Toplam (TL)"])
    for qrow in report["quotes"]:
        ws.append([qrow["status"], qrow["count"], qrow["total"]])
    ws2 = wb.create_sheet("Satış Hunisi")
    ws2.append(["Hizmet", "Aşama", "Adet"])
    for p in report["pipeline"]:
        ws2.append([p["service_line"], p["label"], p["count"]])
    ws3 = wb.create_sheet("İlçe-Sektör")
    ws3.append(["İlçe", "Adet"])
    for d in report["by_district"]:
        ws3.append([d["district"], d["count"]])
    ws3.append([])
    ws3.append(["Sektör", "Adet"])
    for s in report["by_sector"]:
        ws3.append([SECTORS.get(s["sector"], {}).get("label", s["sector"]), s["count"]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
