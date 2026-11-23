from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api import auth, businesses, crm, data
from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup()
    yield


app = FastAPI(title="Ankara Business Radar API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

for r in (auth.router, businesses.router, crm.router, data.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    status = {"api": "ok"}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc.__class__.__name__}"
    return status


def startup() -> None:
    if settings.ENVIRONMENT == "production" and settings.SECRET_KEY.startswith("change-me"):
        raise RuntimeError("Üretimde SECRET_KEY değiştirilmelidir")
    try:
        with SessionLocal() as db:
            from app.services.sources.registry import seed_sources
            seed_sources(db)
            if settings.FIRST_ADMIN_EMAIL and settings.FIRST_ADMIN_PASSWORD:
                email = settings.FIRST_ADMIN_EMAIL.strip().lower()
                if not db.scalar(select(User).where(User.email == email)):
                    db.add(User(email=email, full_name="Yönetici", role="admin",
                                password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD)))
            db.commit()
    except Exception as exc:  # migration henüz çalışmadıysa
        logging.getLogger(__name__).warning("Başlangıç verisi yüklenemedi: %s", exc)
