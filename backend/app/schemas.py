from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: int = Field(..., ge=100, le=50_000)


WebsiteStatus = Literal["yok", "eski", "erisilemedi"]


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
