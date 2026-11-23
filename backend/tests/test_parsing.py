import datetime as dt

from app.services import ttsg_parser as P
from app.services.normalize import (
    clean_mersis, clean_nace, detect_company_type, detect_district, distinctive_tokens, normalize_phone,
    normalize_trade_name, parse_date, parse_decimal,
)
from tests.conftest import SAMPLE_ILAN


def test_district_detection():
    assert detect_district("Kızılay Mah. Atatürk Bulvarı No:5 Çankaya/ANKARA") == "Çankaya"
    assert detect_district("OSTİM OSB 1234. Cad. YENİMAHALLE / ANKARA") == "Yenimahalle"
    assert detect_district("Saray Mah. KAZAN / ANKARA") == "Kahramankazan"
    assert detect_district("Bağdat Cad. Kadıköy / İstanbul") is None


def test_company_type():
    assert detect_company_type("ABC YAZILIM ANONİM ŞİRKETİ") == "AS"
    assert detect_company_type("ABC Gıda Ltd. Şti.") == "LTD"
    assert detect_company_type("Mehmet Yılmaz - Yılmaz Ticaret") == "SAHIS"
    assert detect_company_type("ÖRNEK KONUT YAPI KOOPERATİFİ") == "KOOP"


def test_identifier_cleaning():
    assert clean_mersis("0999-0000-0000-0001") == "0999000000000001"
    assert clean_mersis("12345") is None
    assert clean_nace("43.39.01") == "43.39.01"
    assert clean_nace("4339") == "43.39"
    assert normalize_phone("0 (312) 555 12 34") == "+903125551234"
    assert normalize_phone("+90 532 000 00 00") == "+905320000000"
    assert normalize_phone("123") is None
    assert parse_date("03.11.2026") == dt.date(2026, 11, 3)
    assert parse_decimal("1.250.000,50") == parse_decimal("1250000.50")


def test_trade_name_normalization():
    assert normalize_trade_name("ABC Yazılım A.Ş.") == normalize_trade_name("ABC YAZILIM AŞ")
    assert distinctive_tokens("ÖRNEKTEST YAZILIM BİLİŞİM ANONİM ŞİRKETİ") == ["ornektest"]


def test_classification_types():
    assert P.classify_announcement("Kuruluş")[0] == P.ESTABLISHMENT
    assert P.classify_announcement("Şube Açılışı")[0] == P.EXCLUDED
    assert P.classify_announcement("Şube Kuruluşu")[0] == P.EXCLUDED
    assert P.classify_announcement("Adres Değişikliği")[0] == P.EXCLUDED
    assert P.classify_announcement("Unvan Değişikliği")[0] == P.EXCLUDED
    assert P.classify_announcement("Sermaye Artırımı")[0] == P.EXCLUDED
    assert P.classify_announcement("Merkez Nakli")[0] == P.EXCLUDED
    assert P.classify_announcement("Genel Kurul")[0] == P.EXCLUDED


def test_classification_text():
    assert P.classify_announcement(None, SAMPLE_ILAN)[0] == P.ESTABLISHMENT
    assert P.classify_announcement(None, "Şirketin adres değişikliği tescil edilmiştir")[0] == P.EXCLUDED
    assert P.classify_announcement(None, "Şirketin sermayesinin 100.000 TL artırılması")[0] == P.EXCLUDED
    assert P.classify_announcement(None, "Genel bir metin")[0] == P.UNKNOWN


def test_parse_announcement():
    p = P.parse_announcement_text(SAMPLE_ILAN)
    assert p.trade_name == "KURGUSAL ÖRNEKTEST İNŞAAT TAAHHÜT LİMİTED ŞİRKETİ"
    assert p.registry_no == "999001"
    assert p.mersis_no == "0999000000000001"
    assert p.district == "Etimesgut"
    assert p.registration_date == "2026-11-03"
    assert "inşaat" in (p.activity_text or "").lower()
    assert p.capital == "500000.00"
    assert p.registry_office and p.registry_office.lower().startswith("ankara")


def test_split_gazette():
    other = SAMPLE_ILAN.replace("999001", "999002").replace("ÖRNEKTEST", "DİĞERTEST")
    blocks = P.split_gazette_text(SAMPLE_ILAN + "\n" + other)
    assert len(blocks) == 2


def test_target_office():
    assert P.is_target_office("Ankara", None)[0] is True
    assert P.is_target_office("İstanbul", "Kadıköy / İstanbul")[0] is False
    assert P.is_target_office("Polatlı", "Polatlı / Ankara")[0] is True
    assert P.is_target_office("Gölbaşı", "Gölbaşı / Adıyaman")[0] is False
    assert P.is_target_office(None, None)[0] is None
