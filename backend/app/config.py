"""Uygulama ayarları. Tüm gizli bilgiler ortam değişkenlerinden okunur."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Genel ---
    APP_NAME: str = "Ankara Business Radar"
    ENVIRONMENT: str = "development"  # development | production | test
    TIMEZONE: str = "Europe/Istanbul"
    TARGET_PROVINCE: str = "ANKARA"

    # --- Güvenlik ---
    SECRET_KEY: str = "change-me-in-production-please-use-64-random-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    CORS_ORIGINS: str = "http://localhost:3000"
    FIRST_ADMIN_EMAIL: Optional[str] = None
    FIRST_ADMIN_PASSWORD: Optional[str] = None

    # --- Veritabanı / kuyruk ---
    DATABASE_URL: str = "postgresql+psycopg://radar:radar@localhost:5432/radar"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # --- Günlük otomasyon ---
    DAILY_SCAN_HOUR: int = 8
    DAILY_SCAN_MINUTE: int = 30
    INITIAL_BACKFILL_DAYS: int = 30
    INBOX_DIR: str = "/data/inbox"  # Satın alınan günlük gazete PDF/fihrist dosyalarının bırakılacağı klasör
    UPLOAD_DIR: str = "/data/uploads"

    # --- TTSG Veri Aboneliği (TOBB) Web Servisi ---
    TTSG_WS_ENABLED: bool = False
    TTSG_WS_BASE_URL: Optional[str] = None
    TTSG_WS_USERNAME: Optional[str] = None
    TTSG_WS_PASSWORD: Optional[str] = None
    TTSG_WS_TOKEN: Optional[str] = None
    TTSG_WS_FIELD_MAP: Optional[str] = None  # JSON; alan adları abonelik dokümanına göre

    # --- Lisanslı / izinli harici veri akışı (ör. ticari veri sağlayıcı) ---
    LICENSED_FEED_ENABLED: bool = False
    LICENSED_FEED_URL: Optional[str] = None
    LICENSED_FEED_API_KEY: Optional[str] = None
    LICENSED_FEED_FORMAT: str = "json"  # json | csv
    LICENSED_FEED_FIELD_MAP: Optional[str] = None

    # --- İletişim bilgisi araştırma ---
    ENRICHMENT_ENABLED: bool = True
    ENRICHMENT_USER_AGENT: str = "AnkaraBusinessRadar/1.0 (+kurumsal iletisim arastirmasi; robots.txt'e uyar)"
    ENRICHMENT_HTTP_TIMEOUT: float = 10.0
    ENRICHMENT_DOMAIN_PROBE: bool = True
    OSM_NOMINATIM_ENABLED: bool = False
    OSM_NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
    OSM_CONTACT_EMAIL: Optional[str] = None
    BRAVE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_PLACES_API_KEY: Optional[str] = None
    STORE_MOBILE_NUMBERS: bool = False  # Mobil numaralar kişisel veri olabilir; varsayılan olarak saklanmaz

    # --- Yapay zekâ ---
    LLM_PROVIDER: str = "none"  # none | anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL: str = "claude-opus-5-5"
    LLM_EFFORT: str = "medium"
    LLM_REFUSAL_FALLBACK: bool = True

    # --- Bildirimler ---
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_USE_TLS: bool = True
    NOTIFY_EMAILS: str = ""
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # --- KVKK ---
    RETENTION_DAYS_UNCONTACTED: int = 365
    RETENTION_DAYS_LOST: int = 730
    COMPANY_NAME_FOR_QUOTES: str = "Firma Adınız"
    COMPANY_INFO_FOR_QUOTES: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _fix_pg_scheme(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql+psycopg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def notify_emails(self) -> List[str]:
        return [e.strip() for e in self.NOTIFY_EMAILS.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
