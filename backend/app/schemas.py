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
    email: str = ""                     # sitesinden çıkarılan ilk e-posta (yoksa "")
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
    smtp_configured: bool = False


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
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=4000)


class QuickMessageOut(BaseModel):
    id: str
    title: str
    text: str
    created_at: str


# ---- E-posta gönderimi ----


class EmailRecipient(BaseModel):
    to: str = Field(..., min_length=3, max_length=320)
    name: str = Field(default="", max_length=200)   # {firma_adi} için


class SendEmailIn(BaseModel):
    recipients: list[EmailRecipient] = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=8000)


class SendEmailFailure(BaseModel):
    to: str
    error: str


class SendEmailOut(BaseModel):
    sent: int
    failed: list[SendEmailFailure] = Field(default_factory=list)


class EmailDiscoverIn(BaseModel):
    websites: list[str] = Field(..., min_length=1, max_length=100)


class EmailDiscoverOut(BaseModel):
    results: dict[str, list[str]] = Field(default_factory=dict)


# ---- Auth ----


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    username: str
