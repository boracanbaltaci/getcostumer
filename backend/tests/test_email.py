"""E-posta: kazıma (extract/discover), SMTP gönderimi ve /api/email/* uçları."""
from __future__ import annotations

import smtplib
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import emailscan, mailer


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        yield c


# ---- extract_emails (saf) ----


def test_extract_mailto_onceli_ve_tekil():
    html = ('<a href="mailto:info@firma.com?subject=x">mail</a>'
            '<p>yaz: info@firma.com veya satis@firma.com</p>')
    assert emailscan.extract_emails(html) == ["info@firma.com", "satis@firma.com"]


def test_extract_cop_adresleri_eliyor():
    html = '<img src="logo@2x.png"><a href="mailto:a@example.com">x</a> gercek@site.com'
    assert emailscan.extract_emails(html) == ["gercek@site.com"]


def test_extract_bos_html():
    assert emailscan.extract_emails("<p>mail yok</p>") == []


# ---- discover_emails (ağ mock'lu) ----


def test_discover_ana_sayfada_bulunca_iletisime_girmez(monkeypatch):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return '<a href="mailto:info@firma.com">m</a>', url

    monkeypatch.setattr(emailscan, "_fetch", fake_fetch)
    assert emailscan.discover_emails("https://firma.com") == ["info@firma.com"]
    assert calls == ["https://firma.com"]


def test_discover_iletisim_sayfasina_duser(monkeypatch):
    def fake_fetch(url):
        if url.endswith("/iletisim"):
            return "bize ulasin: iletisim@firma.com", url
        return "<p>anasayfa</p>", url

    monkeypatch.setattr(emailscan, "_fetch", fake_fetch)
    assert emailscan.discover_emails("https://firma.com/") == ["iletisim@firma.com"]


def test_discover_hata_bos_liste(monkeypatch):
    monkeypatch.setattr(emailscan, "_fetch", lambda url: (None, url))
    assert emailscan.discover_emails("https://kapali.com") == []


# ---- mailer.send_bulk (SMTP mock'lu) ----


def _smtp_settings(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "u@test")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "sifre")
    monkeypatch.setattr(settings, "SMTP_FROM", "u@test")


def test_send_bulk_kisilestirme_ve_sayim(monkeypatch):
    _smtp_settings(monkeypatch)
    conn = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: conn)

    out = mailer.send_bulk(
        [{"to": "a@x.com", "name": "A Ltd"}, {"to": "b@x.com", "name": "B AŞ"}],
        "Merhaba {firma_adi}", "{firma_adi} için teklif")

    assert out == {"sent": 2, "failed": []}
    assert conn.send_message.call_count == 2
    first = conn.send_message.call_args_list[0].args[0]
    assert first["Subject"] == "Merhaba A Ltd"
    assert "A Ltd için teklif" in first.get_content()


def test_send_bulk_alici_hatasi_digerlerini_durdurmaz(monkeypatch):
    _smtp_settings(monkeypatch)
    conn = MagicMock()
    conn.send_message.side_effect = [smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"no")}),
                                     None]
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: conn)

    out = mailer.send_bulk([{"to": "a@x.com", "name": ""},
                            {"to": "b@x.com", "name": ""}], "k", "m")
    assert out["sent"] == 1
    assert out["failed"][0]["to"] == "a@x.com"


# ---- /api/email/* uçları ----


def test_send_uclar_oturum_ister(client):
    with TestClient(app) as anon:
        assert anon.post("/api/email/send", json={
            "recipients": [{"to": "a@x.com"}], "subject": "s", "body": "b"
        }).status_code == 401
        assert anon.post("/api/email/discover",
                         json={"websites": ["https://x.com"]}).status_code == 401


def test_send_smtp_yoksa_503(client, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_FROM", "")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    r = client.post("/api/email/send", json={
        "recipients": [{"to": "a@x.com", "name": "A"}], "subject": "s", "body": "b"})
    assert r.status_code == 503


def test_send_endpoint_mailer_cagirir(client, monkeypatch):
    _smtp_settings(monkeypatch)
    seen = {}

    def fake_send(recipients, subject, body):
        seen.update(recipients=recipients, subject=subject, body=body)
        return {"sent": len(recipients), "failed": []}

    monkeypatch.setattr(mailer, "send_bulk", fake_send)
    r = client.post("/api/email/send", json={
        "recipients": [{"to": "a@x.com", "name": "A Ltd"}], "subject": "s", "body": "b"})
    assert r.status_code == 200
    assert r.json() == {"sent": 1, "failed": []}
    assert seen["recipients"] == [{"to": "a@x.com", "name": "A Ltd"}]


def test_discover_endpoint_sosyal_siteyi_atlar(client, monkeypatch):
    monkeypatch.setattr(emailscan, "discover_emails",
                        lambda url: ["info@firma.com"])
    r = client.post("/api/email/discover", json={
        "websites": ["https://firma.com", "https://instagram.com/firma"]})
    assert r.status_code == 200
    assert r.json()["results"] == {"https://firma.com": ["info@firma.com"]}
