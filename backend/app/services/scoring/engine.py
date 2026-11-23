"""Açıklanabilir İSG ve Yazılım fırsat puanlama motoru.

Her puan, kanıt türü belirtilmiş faktörlerin toplamıdır:
  * 'dogrulanmis' – resmî kaynak veya doğrulanmış iletişim bilgisine dayanır
  * 'tahmini'     – çıkarım/varsayım; satış ekibine kesin bilgi olarak sunulmaz
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Business, utcnow
from app.services.contacts import best_contacts
from app.services.normalize import fold
from app.services.scoring import sectors as S

ISG_CAVEAT = ("Şirketin yeni kurulmuş olması çalışan istihdam ettiğini veya İSG hizmeti almadığını kanıtlamaz. "
              "6331 sayılı Kanun kapsamındaki yükümlülükler çalışan çalıştırılmasıyla doğar; çalışan sayısı ve mevcut "
              "hizmet durumu görüşmede teyit edilmelidir. Mevzuat değerlendirmesi güncel düzenlemelere göre yapılmalıdır.")
SW_CAVEAT = ("Dijital görünürlük yalnızca sistemin bulabildiği kamuya açık kaynaklara göre değerlendirilmiştir; "
             "'web sitesi bulunamadı' ifadesi sitenin olmadığını kanıtlamaz.")


def _f(points: int, label: str, basis: str, detail: Optional[str] = None) -> Dict:
    return {"points": points, "label": label, "basis": basis, "detail": detail}


def _age_days(b: Business) -> Optional[int]:
    ref = b.establishment_date or b.gazette_date
    if not ref:
        return None
    return (dt.date.today() - ref).days


def _capital_factor(b: Business, big: int, mid: int, small: int) -> Optional[Dict]:
    if b.capital is None:
        return None
    c = Decimal(b.capital)
    if c >= 5_000_000:
        return _f(big, f"Sermaye {int(c):,} TL".replace(",", "."), "dogrulanmis", "Yüksek sermaye ölçek göstergesi")
    if c >= 1_000_000:
        return _f(mid, f"Sermaye {int(c):,} TL".replace(",", "."), "dogrulanmis")
    if c >= 250_000:
        return _f(small, f"Sermaye {int(c):,} TL".replace(",", "."), "dogrulanmis")
    return None


def classify(db: Session, b: Business) -> Dict:
    sec_nace = S.sector_from_nace(b.nace_code)
    if sec_nace:
        sector, basis = sec_nace, "nace_dogrulanmis" if b.nace_verified else "nace_tahmini"
        evidence = [f"NACE {b.nace_code}"]
    else:
        sector, evidence = S.sector_from_text(b.trade_name, b.activity_text)
        basis = "metin_tahmini"
    hazard, hazard_basis, hazard_note = S.hazard_for(db, b.nace_code, b.nace_verified, sector)
    return {"sector": sector, "sector_label": S.SECTORS[sector]["label"], "sector_basis": basis,
            "sector_evidence": evidence, "hazard_class": hazard, "hazard_basis": hazard_basis, "hazard_note": hazard_note}


def isg_score(b: Business, cls: Dict, contacts: Dict) -> Dict:
    factors: List[Dict] = []
    hz = cls["hazard_class"]
    hz_basis = "dogrulanmis" if cls["hazard_basis"] == "resmi_liste" else "tahmini"
    base = {"cok_tehlikeli": 45, "tehlikeli": 32, "az_tehlikeli": 15}.get(hz or "", 15)
    factors.append(_f(base, f"Tehlike sınıfı: {S.HAZARD_LABELS.get(hz, 'belirlenemedi')}", hz_basis, cls["hazard_note"]))
    boosts = {"insaat": 15, "madencilik": 15, "imalat": 12, "enerji": 10, "otomotiv": 10, "lojistik_depo": 10,
              "saglik": 10, "yeme_icme": 8, "temizlik_tesis": 6, "tarim": 6, "guvenlik": 5, "turizm_konaklama": 4,
              "egitim": 3}
    sec = cls["sector"]
    if boosts.get(sec):
        sb = "dogrulanmis" if cls["sector_basis"] == "nace_dogrulanmis" else "tahmini"
        factors.append(_f(boosts[sec], f"Sektör: {cls['sector_label']}", sb,
                          "Saha riski / ekipman / kimyasal maruziyeti olan sektörlerde İSG ihtiyacı yüksektir"))
    ct = b.company_type
    if ct == "AS":
        factors.append(_f(8, "Anonim şirket", "dogrulanmis", "Genellikle daha büyük ölçek ve kurumsal süreçler"))
    elif ct == "LTD":
        factors.append(_f(5, "Limited şirket", "dogrulanmis"))
    elif ct == "KOOP":
        factors.append(_f(3, "Kooperatif", "dogrulanmis"))
    cf = _capital_factor(b, 8, 5, 2)
    if cf:
        factors.append(cf)
    addr = fold(b.address)
    if re.search(r"\bosb\b|organize sanayi|sanayi sitesi|sanayi bolgesi|kucuk sanayi|ostim|ivedik|siteler", addr):
        factors.append(_f(8, "Adres sanayi bölgesinde", "dogrulanmis", "OSB / sanayi sitesi adresi"))
    age = _age_days(b)
    if age is not None and age <= 30:
        factors.append(_f(8, f"Yeni kuruluş ({age} gün)", "tahmini",
                          "İşe başlama aşamasında İSG hizmeti seçimi henüz yapılmamış olabilir (doğrulanmadı)"))
    if contacts.get("phone") or contacts.get("email"):
        factors.append(_f(6, "Ulaşılabilir kurumsal iletişim bilgisi", "dogrulanmis"
                          if any(c and c.status == "dogrulandi" for c in (contacts.get("phone"), contacts.get("email")))
                          else "tahmini"))
    if b.nace_verified:
        factors.append(_f(4, "NACE kodu resmî kaynaktan", "dogrulanmis"))
    score = max(0, min(100, sum(f["points"] for f in factors)))
    services = ["Risk değerlendirmesi", "Acil durum planı", "Temel İSG eğitimleri"]
    if hz in ("tehlikeli", "cok_tehlikeli"):
        services = ["OSGB hizmeti (iş güvenliği uzmanı + işyeri hekimi)"] + services
    else:
        services += ["İş güvenliği uzmanlığı ve işyeri hekimliği hizmeti"]
    services.append("İSG mevzuatına uyum danışmanlığı")
    return {"score": score, "factors": factors, "recommended_services": services, "caveat": ISG_CAVEAT}


def software_score(b: Business, cls: Dict, contacts: Dict) -> Dict:
    factors: List[Dict] = []
    sec = cls["sector"]
    sb = "dogrulanmis" if cls["sector_basis"] == "nace_dogrulanmis" else "tahmini"
    services: List[str] = []
    web = contacts.get("website")
    if b.enrichment_status in ("tamamlandi", "bulunamadi"):
        if web:
            factors.append(_f(5, "Web sitesi mevcut", "dogrulanmis" if web.status == "dogrulandi" else "tahmini",
                              "Yenileme, entegrasyon veya dijital pazarlama potansiyeli"))
        else:
            factors.append(_f(25, "Kurumsal web sitesi bulunamadı", "tahmini",
                              "Araştırmada doğrulanabilir web sitesi bulunamadı; site ihtiyacı olabilir"))
            services.append("Kurumsal web sitesi")
    else:
        factors.append(_f(0, "Dijital görünürlük araştırması bekliyor", "tahmini"))
    ecommerce = {"e_ticaret": 20, "perakende_toptan": 15, "imalat": 8, "tarim": 6}
    booking = {"saglik": 15, "guzellik_bakim": 15, "turizm_konaklama": 15, "egitim": 12, "spor": 12,
               "yeme_icme": 10, "otomotiv": 8}
    crm = {"danismanlik_ofis": 12, "emlak": 12, "egitim": 8, "otomotiv": 6, "perakende_toptan": 6, "insaat": 6,
           "finans": 8, "saglik": 6}
    automation = {"lojistik_depo": 15, "imalat": 12, "insaat": 6, "saglik": 6, "yeme_icme": 5, "enerji": 6}
    if ecommerce.get(sec):
        factors.append(_f(ecommerce[sec], "E-ticaret uygunluğu", sb, f"{cls['sector_label']} için online satış kanalı"))
        services.append("E-ticaret sitesi" if sec != "imalat" else "B2B ürün kataloğu / bayi portalı")
    if booking.get(sec):
        factors.append(_f(booking[sec], "Online randevu / rezervasyon uygunluğu", sb))
        services.append("Online randevu / rezervasyon sistemi")
    if crm.get(sec):
        factors.append(_f(crm[sec], "Müşteri takip (CRM) ihtiyacı olası", sb))
        services.append("CRM sistemi")
    if automation.get(sec):
        factors.append(_f(automation[sec], "Operasyonel otomasyon fırsatı", sb,
                          "Üretim / stok / sevkiyat / saha süreçleri"))
        services.append("ERP / süreç otomasyonu")
    if b.company_type == "AS":
        factors.append(_f(8, "Anonim şirket – kurumsal yazılım ihtimali", "dogrulanmis"))
    cf = _capital_factor(b, 10, 5, 2)
    if cf:
        factors.append(cf)
        if cf["points"] >= 5:
            services.append("Özel yazılım geliştirme")
    act = fold(b.activity_text)
    if re.search(r"internet|e ticaret|online|dijital|mobil uygulama|yapay zeka", act):
        factors.append(_f(8, "Faaliyet konusunda dijital kanal ifadesi", "dogrulanmis", "Amaç-konu metninde geçiyor"))
    if sec == "bilisim":
        factors.append(_f(-10, "Bilişim firması (kendi yazılımını geliştirebilir)", sb))
        services.append("Yapay zekâ entegrasyonu / iş ortaklığı")
    age = _age_days(b)
    if age is not None and age <= 30:
        factors.append(_f(6, f"Yeni kuruluş ({age} gün)", "tahmini", "Dijital altyapı kurulum aşamasında olabilir"))
    if contacts.get("phone") or contacts.get("email"):
        factors.append(_f(5, "Ulaşılabilir kurumsal iletişim bilgisi", "tahmini"))
    score = max(0, min(100, sum(f["points"] for f in factors)))
    if not services:
        services = ["Kurumsal web sitesi", "İş süreçleri otomasyonu"]
    services = list(dict.fromkeys(services))
    return {"score": score, "factors": factors, "recommended_services": services, "caveat": SW_CAVEAT}


def priority_for(total: int) -> str:
    return "A" if total >= 70 else ("B" if total >= 50 else "C")


def analyze_business(db: Session, b: Business, use_llm: bool = True) -> Dict:
    contacts = best_contacts(b)
    cls = classify(db, b)
    isg = isg_score(b, cls, contacts)
    sw = software_score(b, cls, contacts)
    method = "kural"
    llm_result = None
    if use_llm:
        from app.services.scoring import llm
        llm_result = llm.refine(b, cls, isg, sw)
        if llm_result:
            method = "kural+llm"
            for target, key in ((isg, "isg_adjustment"), (sw, "software_adjustment")):
                adj = llm_result.get(key) or {}
                pts = max(-10, min(10, int(adj.get("points", 0) or 0)))
                if pts:
                    target["factors"].append(_f(pts, "Yapay zekâ değerlendirmesi", "tahmini", adj.get("reason")))
                    target["score"] = max(0, min(100, target["score"] + pts))
    hi, lo = max(isg["score"], sw["score"]), min(isg["score"], sw["score"])
    total = round(hi * 0.65 + lo * 0.35)
    b.sector = cls["sector"]
    b.sector_basis = cls["sector_basis"]
    b.hazard_class = cls["hazard_class"]
    b.hazard_basis = cls["hazard_basis"]
    b.isg_score = isg["score"]
    b.software_score = sw["score"]
    b.total_score = total
    b.priority = priority_for(total)
    b.analysis = {"classification": cls, "isg": isg, "software": sw, "llm": llm_result,
                  "total_formula": "toplam = 0,65 × yüksek puan + 0,35 × düşük puan"}
    b.analysis_method = method
    b.analyzed_at = utcnow()
    return b.analysis
