from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env proje kökündedir (backend/ üstü); çalışma dizininden bağımsız bulunur.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_ROOT, ".env")


class Settings(BaseSettings):
    """Uygulama yapılandırması; değerler .env dosyasından okunur."""

    model_config = SettingsConfigDict(env_file=_ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    GOOGLE_PLACES_API_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:3000"

    # Tek taramada yapılacak en fazla Places API çağrısı (maliyet üst sınırı).
    PLACES_MAX_CALLS: int = 9
    # Web sitesi incelenecek en fazla işletme sayısı.
    WEBSITE_CHECK_LIMIT: int = 60
    WEBSITE_CHECK_TIMEOUT: float = 10.0
    WEBSITE_CHECK_WORKERS: int = 10
    WEBSITE_USER_AGENT: str = "Mozilla/5.0 (compatible; IsletmeRadari/1.0)"

    # E-posta gönderimi (SMTP). SMTP_HOST boşsa gönderim uçları 503 döner.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # Gönderen adresi; boşsa SMTP_USERNAME kullanılır.
    SMTP_FROM: str = ""
    # 587 → STARTTLS; 465 verilirse SMTP_SSL kullanılır, bu bayrak yok sayılır.
    SMTP_TLS: bool = True
    SMTP_TIMEOUT: float = 15.0

    # E-posta kazıma (modal açılınca): istek başına en fazla site.
    EMAIL_DISCOVER_MAX_SITES: int = 20
    EMAIL_DISCOVER_WORKERS: int = 5

    # Postgres bağlantı dizesi; doluysa tüm kalıcı veri burada tutulur.
    # Boşsa SQLite dosyası kullanılır (yerel geliştirme + testler).
    DATABASE_URL: str = ""
    # Tarama geçmişinin tutulduğu SQLite dosyası (boş = <proje kökü>/data/scans.db).
    DB_PATH: str = ""

    # Oturum cookie'si geçerlilik süresi (gün).
    SESSION_TTL_DAYS: int = 30

    @property
    def db_path(self) -> str:
        return self.DB_PATH or os.path.join(_ROOT, "data", "scans.db")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def google_configured(self) -> bool:
        return bool(self.GOOGLE_PLACES_API_KEY.strip())

    @property
    def smtp_from(self) -> str:
        return (self.SMTP_FROM or self.SMTP_USERNAME).strip()

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST.strip() and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
