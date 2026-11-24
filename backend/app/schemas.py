from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: int = Field(..., ge=100, le=50_000)


WebsiteStatus = Literal["yok", "eski", "erisilemedi"]
Priority = Literal["A", "B", "C"]


class ScoreFactor(BaseModel):
    points: int
    label: str
    basis: Literal["dogrulanmis", "tahmini"] = "tahmini"


class BusinessOut(BaseModel):
    place_id: str
    name: str
    address: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    phone: str = ""
    website: Optional[str] = None
    website_status: WebsiteStatus
    website_notes: list[str] = Field(default_factory=list)
    score: int = 0
    priority: Priority = "C"
    score_factors: list[ScoreFactor] = Field(default_factory=list)
    recommended_services: list[str] = Field(default_factory=list)


class ScanStats(BaseModel):
    found: int = 0               # Places'tan dönen toplam işletme
    shown: int = 0               # tabloda listelenen
    without_website: int = 0
    outdated_website: int = 0
    unreachable_website: int = 0
    filtered_modern: int = 0     # modern sitesi olduğu için elenen


class ScanResponse(BaseModel):
    businesses: list[BusinessOut]
    stats: ScanStats
    warnings: list[str] = Field(default_factory=list)


class ConfigOut(BaseModel):
    google_places_configured: bool


class ScanSummaryOut(BaseModel):
    """Geçmiş listesi satırı — işletme detayı içermez."""
    id: str
    scanned_at: str
    lat: float
    lng: float
    radius_m: int
    stats: ScanStats
    is_favorite: bool = False


class ScanRecordOut(ScanSummaryOut):
    """Tek tarama kaydı — işletme listesi dahil."""
    businesses: list[BusinessOut] = Field(default_factory=list)


class FavoriteBusinessIn(BaseModel):
    """İşletme favorileme gövdesi — snapshot + geldiği tarama (opsiyonel)."""
    business: BusinessOut
    scan_id: Optional[str] = None


class BusinessFavoriteOut(BaseModel):
    place_id: str
    added_at: str
    business: BusinessOut


class QuickMessageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class QuickMessageOut(BaseModel):
    id: str
    text: str
    created_at: str


# ---- Auth ----


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    username: str
