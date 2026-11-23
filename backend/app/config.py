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

    # Tarama geçmişinin tutulduğu SQLite dosyası (boş = <proje kökü>/data/scans.db).
    DB_PATH: str = ""

    @property
    def db_path(self) -> str:
        return self.DB_PATH or os.path.join(_ROOT, "data", "scans.db")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def google_configured(self) -> bool:
        return bool(self.GOOGLE_PLACES_API_KEY.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
