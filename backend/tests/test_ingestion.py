import io

from openpyxl import Workbook
from sqlalchemy import func, select

from app.models import Business, Opportunity, RawRecord
from app.services import ingestion
from app.services.dedup import find_merge_candidates, merge_businesses
from app.services.importers.runner import run_import
from app.services.sources.registry import get_source
from tests.conftest import SAMPLE_ILAN


def _rec(**kw):
    base = {"trade_name": "KURGU DENEME GIDA LİMİTED ŞİRKETİ", "registry_office": "Ankara", "registry_no": "900100",
            "mersis_no": "0900000000000100", "address": "Test Mah. Çankaya / Ankara", "announcement_type": "Kuruluş",
            "gazette_date": "2026-11-04", "activity_text": "Restoran ve kafe işletmeciliği"}
    base.update(kw)
    return base


def test_establishment_created_with_two_opportunities(db):
    src = get_source(db, "manual_import")
    r = ingestion.ingest_record(db, src, _rec())
    db.commit()
    assert r.status == "created"
    b = db.get(Business, r.business_id)
    assert b.district == "Çankaya" and b.company_type == "LTD"
    assert {o.service_line for o in b.opportunities} == {"isg", "yazilim"}
    assert b.source_id == src.id and b.verified_at is not None


def test_non_establishments_excluded(db):
    src = get_source(db, "manual_import")
    for t in ("Şube Açılışı", "Adres Değişikliği", "Unvan Değişikliği", "Sermaye Artırımı"):
        r = ingestion.ingest_record(db, src, _rec(announcement_type=t, registry_no=t))
        assert r.status == "skipped_not_establishment", t
    db.commit()
    assert db.scalar(select(func.count(Business.id))) == 0


def test_other_province_skipped(db):
    src = get_source(db, "manual_import")
    r = ingestion.ingest_record(db, src, _rec(registry_office="İstanbul", address="Kadıköy / İstanbul"))
    assert r.status == "skipped_other_province"


def test_idempotent_and_dedup(db):
    src = get_source(db, "manual_import")
    r1 = ingestion.ingest_record(db, src, _rec())
    r2 = ingestion.ingest_record(db, src, _rec())
    assert r2.status == "duplicate_raw"
    # Aynı MERSİS, farklı yazım → aynı işletme
    r3 = ingestion.ingest_record(db, src, _rec(trade_name="Kurgu Deneme Gıda Ltd. Şti.", gazette_no="1"))
    db.commit()
    assert r3.business_id == r1.business_id
    assert db.scalar(select(func.count(Business.id))) == 1
    assert db.scalar(select(func.count(Opportunity.id))) == 2


def test_unknown_goes_to_review(db):
    src = get_source(db, "manual_import")
    r = ingestion.ingest_record(db, src, _rec(announcement_type=None), raw_text="Belirsiz bir ilan metni")
    assert r.status == "needs_review"
    assert db.get(RawRecord, r.raw_record_id).status == "needs_review"


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_import_with_fihrist_columns(db):
    data = _xlsx([
        ["Sıra No", "TSM", "TSM No", "Ticaret Unvanı", "İlan Türü", "Gazete Tarihi", "Sayısı", "Baş Sayfa"],
        [1, "ANKARA", "900201", "KURGU ALFA YAZILIM ANONİM ŞİRKETİ", "Kuruluş", "04.11.2026", "11000", 10],
        [2, "ANKARA", "900202", "KURGU BETA İNŞAAT LTD. ŞTİ.", "Adres Değişikliği", "04.11.2026", "11000", 11],
        [3, "İSTANBUL", "900203", "KURGU GAMA GIDA LTD. ŞTİ.", "Kuruluş", "04.11.2026", "11000", 12],
        [4, "ANKARA", "900204", "KURGU DELTA OTOMOTİV LTD. ŞTİ.", "Şube Açılışı", "04.11.2026", "11000", 13],
    ])
    src = get_source(db, "ttsg_inbox")
    batch = run_import(db, src, "fihrist-2026-11-04.xlsx", data, declared_establishment=False, marks_full_day=True)
    db.commit()
    assert batch.status == "completed"
    assert batch.stats["created"] == 1
    assert batch.stats["skipped_not_establishment"] == 2
    assert batch.stats["skipped_other_province"] == 1
    # tekrar içe aktarma → yeni kayıt yok
    batch2 = run_import(db, src, "fihrist-2026-11-04.xlsx", data, declared_establishment=False)
    db.commit()
    assert batch2.stats.get("created", 0) == 0
    assert db.scalar(select(func.count(Business.id))) == 1


def test_csv_import_with_contacts_and_privacy(db):
    csv_text = ("Ticaret Unvanı;İlçe;Faaliyet Konusu;Kurumsal Telefon;Kurumsal E-posta\n"
                "KURGU EPSİLON DANIŞMANLIK LTD. ŞTİ.;Çankaya;Yönetim danışmanlığı;0312 555 00 00;info@kurgu-epsilon.com.tr\n"
                "KURGU ZETA KUAFÖR;Keçiören;Kuaför;0532 000 00 00;zeta@gmail.com\n")
    src = get_source(db, "manual_import")
    batch = run_import(db, src, "liste.csv", csv_text.encode("utf-8"), declared_establishment=True)
    db.commit()
    assert batch.stats["created"] == 2
    b1 = db.scalar(select(Business).where(Business.trade_name.like("%EPSİLON%")))
    assert {c.type for c in b1.contacts} == {"phone", "email"}
    b2 = db.scalar(select(Business).where(Business.trade_name.like("%ZETA%")))
    # mobil numara ve ücretsiz e-posta (kişisel veri olabilir) saklanmaz
    assert b2.contacts == []


def test_merge(db):
    src = get_source(db, "manual_import")
    a = ingestion.ingest_record(db, src, _rec(trade_name="KURGU OMEGA TEKNOLOJİ A.Ş.", mersis_no=None, registry_no="1"))
    b = ingestion.ingest_record(db, src, _rec(trade_name="KURGU OMEGA TEKNOLOJİ ANONİM ŞİRKETİ AŞ", mersis_no=None,
                                              registry_no=None, gazette_no="x"))
    db.commit()
    assert a.business_id != b.business_id
    cands = find_merge_candidates(db, threshold=85)
    assert cands
    tgt = merge_businesses(db, b.business_id, a.business_id)
    db.commit()
    assert db.get(Business, b.business_id).merged_into_id == tgt.id
    assert len(db.get(Business, a.business_id).opportunities) == 2
