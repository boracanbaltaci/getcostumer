"""Auth, kullanıcı izolasyonu ve favoriler — geçici DB'de uçtan uca."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import auth, store

_STATS = {"found": 1, "shown": 1, "without_website": 1, "outdated_website": 0,
          "unreachable_website": 0, "filtered_modern": 0}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _login(c: TestClient, username="admin", password="admin"):
    return c.post("/api/auth/login", json={"username": username, "password": password})


def _uid(c: TestClient) -> str:
    return store.get_user_by_username(c.get("/api/auth/me").json()["username"])["id"]


def _scan(user_id: str) -> str:
    return store.insert_scan(user_id, 41.0, 29.0, 1000, _STATS, [])["id"]


def test_ilk_acilis_admin_olusturur(client):
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert client.get("/api/auth/me").json()["username"] == "admin"


def test_korumali_uclar_oturum_ister(client):
    with TestClient(app) as anon:
        assert anon.get("/api/scans").status_code == 401
        assert anon.get("/api/favorites").status_code == 401
        assert anon.get("/api/auth/me").status_code == 401
        assert anon.post("/api/scan", json={"lat": 41, "lng": 29, "radius_m": 1000}).status_code == 401
        assert anon.get("/api/health").status_code == 200


def test_yanlis_parola_401(client):
    assert _login(client, password="yanlis").status_code == 401


def test_logout(client):
    _login(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_kullanicilar_birbirinin_taramasini_gormez(client):
    _login(client)
    sid = _scan(_uid(client))

    store.create_user("ayse", auth.hash_password("gizli-sifre"))
    with TestClient(app) as c2:
        _login(c2, username="ayse", password="gizli-sifre")
        assert c2.get("/api/scans").json() == []
        assert c2.get(f"/api/scans/{sid}").status_code == 404
        assert c2.delete(f"/api/scans/{sid}").status_code == 404

    assert sid in [s["id"] for s in client.get("/api/scans").json()]


def test_favoriler_ekle_listele_kaldir(client):
    _login(client)
    sid = _scan(_uid(client))

    assert client.put(f"/api/favorites/{sid}").status_code == 204
    favs = client.get("/api/favorites").json()
    assert [f["id"] for f in favs] == [sid]
    assert favs[0]["is_favorite"] is True
    assert client.get("/api/scans").json()[0]["is_favorite"] is True

    assert client.delete(f"/api/favorites/{sid}").status_code == 204
    assert client.get("/api/favorites").json() == []


def test_favori_baskasinin_taramasina_404(client):
    _login(client)
    sid = _scan(_uid(client))
    store.create_user("veli", auth.hash_password("gizli-sifre"))
    with TestClient(app) as c2:
        _login(c2, username="veli", password="gizli-sifre")
        assert c2.put(f"/api/favorites/{sid}").status_code == 404
        assert c2.delete(f"/api/favorites/{sid}").status_code == 404


def test_tarama_silince_favorisi_de_gider(client):
    _login(client)
    sid = _scan(_uid(client))
    client.put(f"/api/favorites/{sid}")
    assert client.delete(f"/api/scans/{sid}").status_code == 204
    assert client.get("/api/favorites").json() == []


_BIZ = {"place_id": "plc-1", "name": "Bakkal Ahmet", "address": "Cadde 1",
        "lat": 41.0, "lng": 29.0, "phone": "", "website": None,
        "website_status": "yok", "website_notes": []}


def test_isletme_favorileri(client):
    _login(client)
    assert client.get("/api/business-favorites").json() == []

    assert client.put("/api/business-favorites/plc-1",
                      json={"business": _BIZ}).status_code == 204
    favs = client.get("/api/business-favorites").json()
    assert [f["place_id"] for f in favs] == ["plc-1"]
    assert favs[0]["business"]["name"] == "Bakkal Ahmet"

    assert client.delete("/api/business-favorites/plc-1").status_code == 204
    assert client.get("/api/business-favorites").json() == []
    assert client.delete("/api/business-favorites/plc-1").status_code == 404


def test_isletme_favorileri_kullanici_bazli(client):
    _login(client)
    client.put("/api/business-favorites/plc-1", json={"business": _BIZ})
    store.create_user("veli", auth.hash_password("gizli-sifre"))
    with TestClient(app) as c2:
        _login(c2, username="veli", password="gizli-sifre")
        assert c2.get("/api/business-favorites").json() == []
        c2.put("/api/business-favorites/plc-1", json={"business": _BIZ})
        assert len(c2.get("/api/business-favorites").json()) == 1
    assert len(client.get("/api/business-favorites").json()) == 1


def test_hizli_mesajlar_ekle_listele_sil(client):
    _login(client)
    assert client.get("/api/quick-messages").json() == []

    r = client.post("/api/quick-messages", json={"text": "Merhaba, sitenizi yenileyebiliriz."})
    assert r.status_code == 201
    mid = r.json()["id"]
    assert [m["id"] for m in client.get("/api/quick-messages").json()] == [mid]

    assert client.delete(f"/api/quick-messages/{mid}").status_code == 204
    assert client.get("/api/quick-messages").json() == []
    assert client.delete(f"/api/quick-messages/{mid}").status_code == 404


def test_hizli_mesaj_duzenle(client):
    _login(client)
    mid = client.post("/api/quick-messages", json={"text": "eski"}).json()["id"]

    assert client.put(f"/api/quick-messages/{mid}",
                      json={"text": "  yeni metin  "}).status_code == 204
    msgs = client.get("/api/quick-messages").json()
    assert msgs[0]["text"] == "yeni metin"

    assert client.put("/api/quick-messages/yok", json={"text": "x"}).status_code == 404


def test_hizli_mesajlar_kullanici_bazli(client):
    _login(client)
    mid = client.post("/api/quick-messages", json={"text": "taslak"}).json()["id"]
    store.create_user("veli", auth.hash_password("gizli-sifre"))
    with TestClient(app) as c2:
        _login(c2, username="veli", password="gizli-sifre")
        assert c2.get("/api/quick-messages").json() == []
        assert c2.delete(f"/api/quick-messages/{mid}").status_code == 404
    assert len(client.get("/api/quick-messages").json()) == 1
