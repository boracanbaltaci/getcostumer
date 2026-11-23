"""Test yapılandırması.

Not: Testlerdeki işletme adları ve numaralar TAMAMEN KURGUSALDIR; yalnızca ayrıştırma ve iş
kurallarını doğrulamak için kullanılır, gerçek bir kayıt olarak sunulmaz.
"""
from __future__ import annotations

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="radar-test-")
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["INBOX_DIR"] = os.path.join(_tmp, "inbox")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["ENRICHMENT_ENABLED"] = "false"
os.environ["LLM_PROVIDER"] = "none"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789abcdef"
os.makedirs(os.environ["INBOX_DIR"], exist_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.sources.registry import seed_sources  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_sources(db)
        db.add_all([
            User(email="admin@test.local", full_name="Admin", role="admin", password_hash=hash_password("Admin12345!")),
            User(email="sales@test.local", full_name="Satış", role="sales", password_hash=hash_password("Sales12345!")),
            User(email="viewer@test.local", full_name="İzleyici", role="viewer", password_hash=hash_password("View12345!")),
        ])
        db.commit()
    for f in os.listdir(os.environ["INBOX_DIR"]):
        p = os.path.join(os.environ["INBOX_DIR"], f)
        if os.path.isfile(p):
            os.remove(p)
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_h(client):
    return _login(client, "admin@test.local", "Admin12345!")


@pytest.fixture
def sales_h(client):
    return _login(client, "sales@test.local", "Sales12345!")


@pytest.fixture
def viewer_h(client):
    return _login(client, "viewer@test.local", "View12345!")


SAMPLE_ILAN = """ANKARA TİCARET SİCİLİ MÜDÜRLÜĞÜ
Ticaret Sicil Müdürlüğü : ANKARA
Ticaret Sicil No : 999001
Ticaret Unvanı : KURGUSAL ÖRNEKTEST İNŞAAT TAAHHÜT LİMİTED ŞİRKETİ
MERSİS No : 0999-0000-0000-0001
Adres : Örnek Mah. Deneme Cad. No: 1 İç Kapı No: 2 Etimesgut / Ankara

Yukarıda bilgileri verilen şirketin kuruluşu 03.11.2026 tarihinde tescil edilmiştir.
Şirketin Amaç ve Konusu: Her türlü konut ve altyapı inşaatı, tadilat ve taahhüt işleri.

Sermaye : 500.000,00 TL
"""
