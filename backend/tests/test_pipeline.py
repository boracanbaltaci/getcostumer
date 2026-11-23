import datetime as dt
import io
import os

import httpx
from openpyxl import Workbook
from sqlalchemy import func, select

from app.config import settings
from app.models import Business, DataSource, SourceCoverage
from app.services import pipeline
from app.services.coverage import coverage_calendar
from app.services.reports import today_tr
from app.services.sources import registry


def test_no_configured_sources_is_not_reported_as_zero(db):
    job = pipeline.run_daily_pipeline(db, triggered_by="test", notify=False)
    assert job.status == "partial"
    assert job.stats["sources"]["ttsg_ws"]["status"] in ("disabled", "not_configured")
    cal = coverage_calendar(db, today_tr() - dt.timedelta(days=3), today_tr())
    # Taranmamış günler 'not_scanned' olarak döner, yeni işletme sayısı None (sıfır DEĞİL)
    assert all(c["status"] == "not_scanned" and c["new_businesses"] is None for c in cal)
    from app.models import DailyReport
    rep = db.scalar(select(DailyReport).where(DailyReport.report_date == today_tr()))
    assert any("tarama" in w.lower() or "kaynak" in w.lower() for w in rep.content["warnings"])


def _enable_ws(db, monkeypatch, handler):
    monkeypatch.setattr(settings, "TTSG_WS_ENABLED", True)
    monkeypatch.setattr(settings, "TTSG_WS_BASE_URL", "https://ttsg.example.invalid/api")
    monkeypatch.setattr(settings, "TTSG_WS_TOKEN", "x")
    monkeypatch.setattr(settings, "INITIAL_BACKFILL_DAYS", 3)
    src = db.scalar(select(DataSource).where(DataSource.key == "ttsg_ws"))
    src.enabled = True
    db.commit()
    adapter = registry.ADAPTERS["ttsg_ws"]
    monkeypatch.setattr(adapter, "_client", lambda cfg: httpx.Client(
        base_url="https://ttsg.example.invalid/api", transport=httpx.MockTransport(handler)))


def test_webservice_backfill_failures_and_idempotency(db, monkeypatch):
    today = today_tr()
    fail_day = (today - dt.timedelta(days=1)).isoformat()

    def handler(request: httpx.Request):
        day = request.url.params.get("yayinTarihi")
        if day == fail_day:
            return httpx.Response(503, json={"hata": "bakım"})
        items = [
            {"TSM": "ANKARA", "TSMNo": f"8{day[-2:]}01", "Unvan1": f"KURGU WS {day} YAZILIM ANONİM ŞİRKETİ",
             "IlanTuru": "Kuruluş", "YayinTarihi": day, "MersisNo": f"08000000000{day[-2:]}001",
             "Adres": "Test Cad. Çankaya / Ankara", "AnaNaceKodu": "62.01.01", "IlanId": f"{day}-1"},
            {"TSM": "ANKARA", "TSMNo": f"8{day[-2:]}02", "Unvan1": f"KURGU WS {day} GIDA LTD ŞTİ",
             "IlanTuru": "Şube Açılışı", "YayinTarihi": day, "IlanId": f"{day}-2"},
        ]
        return httpx.Response(200, json={"ilanlar": items})

    _enable_ws(db, monkeypatch, handler)
    job = pipeline.run_daily_pipeline(db, triggered_by="test", notify=False)
    ws = job.stats["sources"]["ttsg_ws"]
    assert job.status == "partial"  # bir gün başarısız
    assert fail_day in ws["failed_days"]
    n1 = db.scalar(select(func.count(Business.id)))
    assert n1 == 3  # 4 günden 3'ü başarılı, her gün 1 kuruluş (şube hariç)
    b = db.scalar(select(Business).where(Business.nace_code == "62.01.01"))
    assert b.nace_verified is True and b.sector == "bilisim"
    failed = db.scalar(select(SourceCoverage).where(SourceCoverage.coverage_date == dt.date.fromisoformat(fail_day)))
    assert failed.status == "failed"
    # Tekrar çalıştırma: veri bütünlüğü korunur, başarısız gün tekrar denenir
    monkeypatch.setattr(registry.ADAPTERS["ttsg_ws"], "_client", lambda cfg: httpx.Client(
        base_url="https://ttsg.example.invalid/api",
        transport=httpx.MockTransport(lambda r: handler(r) if r.url.params.get("yayinTarihi") != fail_day else
                                      httpx.Response(200, json={"ilanlar": []}))))
    # son başarılı günden sonrasını tarar; başarısız gün backfill penceresinde olduğundan manuel tekrar:
    src = db.scalar(select(DataSource).where(DataSource.key == "ttsg_ws"))
    res = registry.ADAPTERS["ttsg_ws"].run(db, src, dt.date.fromisoformat(fail_day), today, None)
    db.commit()
    assert db.scalar(select(func.count(Business.id))) == n1
    assert res.days[fail_day] == "covered"


def test_inbox_folder_import(db):
    wb = Workbook()
    ws = wb.active
    ws.append(["TSM", "TSM No", "Ticaret Unvanı", "İlan Türü", "Gazete Tarihi"])
    ws.append(["ANKARA", "700001", "KURGU INBOX LOJİSTİK LTD. ŞTİ.", "Kuruluş", today_tr().strftime("%d.%m.%Y")])
    buf = io.BytesIO()
    wb.save(buf)
    with open(os.path.join(settings.INBOX_DIR, "fihrist.xlsx"), "wb") as fh:
        fh.write(buf.getvalue())
    job = pipeline.run_daily_pipeline(db, triggered_by="test", notify=False)
    assert job.stats["sources"]["ttsg_inbox"]["created"] == 1
    assert os.path.exists(os.path.join(settings.INBOX_DIR, "islenen", "fihrist.xlsx"))
    cal = coverage_calendar(db, today_tr(), today_tr())
    assert cal[0]["status"] == "covered" and cal[0]["new_businesses"] == 1
    # aynı dosya tekrar bırakılırsa mükerrer kayıt oluşmaz
    with open(os.path.join(settings.INBOX_DIR, "fihrist-kopya.xlsx"), "wb") as fh:
        fh.write(buf.getvalue())
    pipeline.run_daily_pipeline(db, triggered_by="test", notify=False)
    assert db.scalar(select(func.count(Business.id))) == 1


def test_concurrent_run_guard(db):
    from app.models import JobRun
    db.add(JobRun(job_type="daily_pipeline", status="running", triggered_by="other"))
    db.commit()
    assert pipeline.run_daily_pipeline(db, triggered_by="test", notify=False) is None
