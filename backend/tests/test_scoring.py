"""scoring birim testleri — Places kaydı + site durumundan fırsat puanı."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import scoring


def _rec(**kw):
    return {"name": "Deneme İşletme", "phone": "", "primary_type": None,
            "website": None, **kw}


def test_site_yok_perakende_a_onceligi():
    s = scoring.score_business(_rec(primary_type="clothing_store",
                                    phone="0312 000 00 00"), "yok")
    assert s["score"] == 50  # 30 + 15 + 5
    assert s["priority"] == "A"
    assert "Kurumsal web sitesi" in s["services"]
    assert "E-ticaret sitesi" in s["services"]


def test_eski_site_randevu_sektoru():
    s = scoring.score_business(_rec(primary_type="dentist"), "eski")
    assert s["score"] == 35  # 20 + 15
    assert s["priority"] == "B"
    assert "Online randevu / rezervasyon sistemi" in s["services"]
    assert "Web sitesi yenileme" in s["services"]


def test_erisilemedi_bare_minimum():
    s = scoring.score_business(_rec(), "erisilemedi")
    assert s["score"] == 15
    assert s["priority"] == "C"


def test_bilisim_firmasi_ceza_alir():
    s = scoring.score_business(_rec(name="Piksel Yazılım Ltd"), "yok")
    # 30 - 10 + 5 (Ltd) = 25
    assert s["score"] == 25
    assert s["priority"] == "C"
    assert any(f["points"] == -10 for f in s["factors"])


def test_sirket_unvani_puan_verir():
    s = scoring.score_business(_rec(name="Yıldız Gıda A.Ş."), "yok")
    assert s["score"] == 35  # 30 + 5
    assert any(f["label"].startswith("Şirket unvanı") for f in s["factors"])


def test_software_company_type_penalty():
    s = scoring.score_business(_rec(name="X", primary_type="software_company"), "yok")
    assert s["score"] == 20  # 30 - 10


def test_faktorler_basis_tasir():
    s = scoring.score_business(_rec(primary_type="restaurant"), "yok")
    assert all(f["basis"] in ("dogrulanmis", "tahmini") for f in s["factors"])
    status_factor = s["factors"][0]
    assert status_factor["basis"] == "tahmini"  # site yokluğu kanıt değildir


def test_servisler_tekil():
    s = scoring.score_business(_rec(primary_type="restaurant"), "yok")
    assert len(s["services"]) == len(set(s["services"]))


# ---- /api/scan uçtan uca: puan alanları + puana göre sıralama ----


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "test-key")
    with TestClient(app) as c:
        yield c


def test_scan_endpoint_puanlar_ve_siralar(client, monkeypatch):
    from app.services import places, sitescan

    recs = [
        _rec(place_id="p1", name="Sitesiz Esnaf", address="", lat=41.0, lng=29.0),
        _rec(place_id="p2", name="Eski Site Ltd", address="", lat=41.0, lng=29.0,
             phone="0312 000 00 00", website="https://eski-ornek.com",
             primary_type="dentist"),
    ]
    monkeypatch.setattr(places, "search_nearby", lambda *a, **k: (recs, []))
    monkeypatch.setattr(sitescan, "check_website", lambda url, year:
                        sitescan.SiteVerdict(status="eski", score=5, notes=["eski doctype"]))

    client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    r = client.post("/api/scan", json={"lat": 41, "lng": 29, "radius_m": 500})
    assert r.status_code == 200
    rows = r.json()["businesses"]
    assert [b["place_id"] for b in rows] == ["p2", "p1"]  # 45 > 30
    p2, p1 = rows
    assert p2["score"] == 45 and p2["priority"] == "B"  # 20 eski + 15 sektör + 5 tel + 5 Ltd
    assert "Web sitesi yenileme" in p2["recommended_services"]
    assert p2["score_factors"][0]["label"] == "Web sitesi eski görünümlü"
    assert p1["score"] == 30 and p1["priority"] == "B"
    # Kayıt snapshot'ında puan saklanır
    rec = client.get("/api/scans").json()[0]
    saved = client.get(f"/api/scans/{rec['id']}").json()["businesses"][0]
    assert saved["place_id"] == "p2" and saved["score"] == 45
