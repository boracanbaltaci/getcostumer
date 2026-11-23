from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.constants import ACTIVITY_TYPES, CONTACT_TYPES, IYS_STATUSES, ROLES, STAGE_KEYS


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "sales"

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("Geçersiz rol")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("Geçersiz e-posta")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class BusinessUpdate(BaseModel):
    trade_name: Optional[str] = None
    establishment_date: Optional[dt.date] = None
    registry_office: Optional[str] = None
    registry_no: Optional[str] = None
    mersis_no: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    activity_text: Optional[str] = None
    nace_code: Optional[str] = None
    nace_verified: Optional[bool] = None
    company_type: Optional[str] = None
    capital: Optional[Decimal] = None
    announcement_url: Optional[str] = None
    owner_id: Optional[int] = None
    verification_status: Optional[str] = None


class ComplianceUpdate(BaseModel):
    iys_status: Optional[str] = None
    do_not_contact: Optional[bool] = None
    note: Optional[str] = None

    @field_validator("iys_status")
    @classmethod
    def _iys(cls, v):
        if v is not None and v not in IYS_STATUSES:
            raise ValueError("Geçersiz İYS durumu")
        return v


class ContactCreate(BaseModel):
    type: str
    value: str
    source_url: Optional[str] = None
    source_name: str = "Manuel giriş"
    note: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _t(cls, v):
        if v not in CONTACT_TYPES:
            raise ValueError("Geçersiz iletişim türü")
        return v


class ContactUpdate(BaseModel):
    status: str  # dogrulandi | reddedildi | aday

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v not in ("dogrulandi", "reddedildi", "aday"):
            raise ValueError("Geçersiz durum")
        return v


class OpportunityUpdate(BaseModel):
    stage: Optional[str] = None
    owner_id: Optional[int] = None
    estimated_value: Optional[Decimal] = None
    next_action: Optional[str] = None
    next_action_date: Optional[dt.date] = None
    lost_reason: Optional[str] = None
    clear_next_action: bool = False

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in STAGE_KEYS:
            raise ValueError("Geçersiz aşama")
        return v


class ActivityCreate(BaseModel):
    type: str = "note"
    content: str = Field(min_length=1, max_length=10000)
    opportunity_id: Optional[int] = None
    occurred_at: Optional[dt.datetime] = None
    follow_up_date: Optional[dt.date] = None

    @field_validator("type")
    @classmethod
    def _t(cls, v):
        if v not in ACTIVITY_TYPES:
            raise ValueError("Geçersiz görüşme türü")
        return v


class ActivityUpdate(BaseModel):
    follow_up_done: Optional[bool] = None
    follow_up_date: Optional[dt.date] = None
    content: Optional[str] = None


class QuoteItem(BaseModel):
    description: str
    quantity: float = 1
    unit: str = "Adet"
    unit_price: float = 0
    vat_rate: float = 20


class QuoteCreate(BaseModel):
    title: str
    items: List[QuoteItem]
    valid_until: Optional[dt.date] = None
    notes: Optional[str] = None
    currency: str = "TRY"


class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    items: Optional[List[QuoteItem]] = None
    valid_until: Optional[dt.date] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in ("taslak", "gonderildi", "kabul", "red"):
            raise ValueError("Geçersiz teklif durumu")
        return v


class MergeIn(BaseModel):
    source_id: int
    target_id: int


class ReviewApprove(BaseModel):
    fields: Dict[str, Any] = {}


class SourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
