from app.models import Business, NaceHazard
from app.services import ingestion
from app.services.contacts import add_contact
from app.services.enrichment import fetch as fetcher
from app.services.enrichment import website
from app.services.enrichment.orchestrator import enrich_business
from app.services.scoring import llm
from app.services.scoring.engine import analyze_business
from app.services.sources.registry import get_source


def _biz(db, **kw):
    src = get_source(db, "manual_import")
    rec = {"trade_name": "KURGU TEST LİMİTED ŞİRKETİ", "registry_office": "Ankara", "announcement_type": "Kuruluş",
           "address": "Test Mah. Sincan / Ankara", "gazette_date": "2026-11-04"}
    rec.update(kw)
    r = ingestion.ingest_record(db, src, rec)
    db.commit()
    return db.get(Business, r.business_id)


def test_construction_scores_higher_isg_than_consulting(db):
    insaat = _biz(db, trade_name="KURGU KAYA İNŞAAT TAAHHÜT LTD. ŞTİ.", activity_text="Bina inşaatı ve tadilat")
    danis = _biz(db, trade_name="KURGU MAVİ DANIŞMANLIK LTD. ŞTİ.", activity_text="Yönetim danışmanlığı", registry_no="2")
    a1 = analyze_business(db, insaat, use_llm=False)
    a2 = analyze_business(db, danis, use_llm=False)
    assert insaat.sector == "insaat" and insaat.sector_basis == "metin_tahmini"
    assert insaat.isg_score > danis.isg_score
    assert danis.software_score >= 1
    # açıklanabilirlik: her faktörün dayanağı var, uyarı metni mevcut
    for f in a1["isg"]["factors"] + a2["software"]["factors"]:
        assert f["basis"] in ("dogrulanmis", "tahmini")
    assert "kanıtlamaz" in a1["isg"]["caveat"]
    assert 0 <= insaat.isg_score <= 100 and insaat.priority in ("A", "B", "C")


def test_official_hazard_list_is_verified(db):
    db.add(NaceHazard(code="43.39.01", hazard_class="cok_tehlikeli", description="test"))
    db.commit()
    b = _biz(db, trade_name="KURGU NACE YAPI LTD. ŞTİ.", nace_code="43.39.01", nace_verified=True)
    a = analyze_business(db, b, use_llm=False)
    assert b.hazard_class == "cok_tehlikeli" and b.hazard_basis == "resmi_liste"
    assert a["isg"]["factors"][0]["basis"] == "dogrulanmis"


def test_llm_adjustment_is_bounded_and_labeled(db):
    class Fake:
        name = "fake"

        def analyze(self, prompt):
            assert "KURGU" in prompt
            return {"summary": "x", "likely_activity": "y", "isg_adjustment": {"points": 50, "reason": "abartı"},
                    "software_adjustment": {"points": -3, "reason": "z"}, "talking_points": [], "open_questions": []}
    llm.set_provider(Fake())
    try:
        b = _biz(db, trade_name="KURGU LLM GIDA LTD. ŞTİ.", activity_text="Restoran")
        base = analyze_business(db, b, use_llm=False)["isg"]["score"]
        a = analyze_business(db, b, use_llm=True)
        assert a["isg"]["score"] == min(100, base + 10)  # en fazla +10
        ai = [f for f in a["isg"]["factors"] if f["label"] == "Yapay zekâ değerlendirmesi"]
        assert ai and ai[0]["basis"] == "tahmini"
        assert b.analysis_method == "kural+llm"
    finally:
        llm.set_provider(None)


SITE_OK = """<html><body><h1>Kurgu Örnektest İnşaat</h1><p>KURGU ÖRNEKTEST İNŞAAT TAAHHÜT LİMİTED ŞİRKETİ</p>
<p>MERSİS No: 0999000000000001</p><p>Etimesgut / Ankara</p>
<a href="mailto:info@ornektestinsaat.com.tr">info@ornektestinsaat.com.tr</a> Tel: 0312 555 11 22
<p>Kişisel: ahmet@gmail.com, 0532 111 22 33</p></body></html>"""
SITE_OTHER = """<html><body><h1>Örnektest Mimarlık</h1><p>İstanbul, Kadıköy</p>
<a href="mailto:info@ornektestmimarlik.com">x</a></body></html>"""


def test_website_verification_and_privacy(db, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", True)
    b = _biz(db, trade_name="KURGU ÖRNEKTEST İNŞAAT TAAHHÜT LİMİTED ŞİRKETİ", mersis_no="0999000000000001",
             address="Örnek Mah. Etimesgut / Ankara")
    pages = {"https://www.ornektestinsaat.com.tr": SITE_OK, "https://www.ornektest.com.tr": SITE_OTHER}

    def fake_fetch(url):
        key = url.rstrip("/")
        if key in pages:
            return pages[key], key, "ok"
        return None, None, "http_404"
    monkeypatch.setattr(fetcher, "fetch", fake_fetch)
    monkeypatch.setattr(website, "candidate_domains",
                        lambda b: ["https://www.ornektest.com.tr", "https://www.ornektestinsaat.com.tr"])
    enrich_business(db, b)
    db.commit()
    by_type = {c.type: c for c in b.contacts}
    assert by_type["website"].normalized_value == "ornektestinsaat.com.tr"
    assert by_type["website"].confidence >= 75 and by_type["website"].confidence_level == "yuksek"
    assert by_type["email"].value == "info@ornektestinsaat.com.tr"
    assert by_type["phone"].value == "0312 555 11 22"
    values = {c.value for c in b.contacts}
    assert "ahmet@gmail.com" not in values and not any("532" in v for v in values)
    assert all(c.source_url for c in b.contacts)
    assert b.enrichment_status == "tamamlandi"


def test_unrelated_site_rejected(db, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", True)
    b = _biz(db, trade_name="KURGU ÖRNEKTEST İNŞAAT TAAHHÜT LİMİTED ŞİRKETİ", registry_no="77")
    monkeypatch.setattr(fetcher, "fetch", lambda url: (SITE_OTHER, url, "ok"))
    monkeypatch.setattr(website, "candidate_domains", lambda b: ["https://www.ornektest.com.tr"])
    enrich_business(db, b)
    db.commit()
    assert b.contacts == []
    assert b.enrichment_status == "bulunamadi"


def test_do_not_contact_blocks_contact_storage(db):
    b = _biz(db, trade_name="KURGU DNC LTD. ŞTİ.")
    b.do_not_contact = True
    cp, why = add_contact(db, b, "phone", "0312 555 00 00", source_name="x", source_url=None, confidence=90)
    assert cp is None and "kapalı" in why
