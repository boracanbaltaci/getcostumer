"""Veritabanı modelleri (SQLAlchemy 2.0)."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, JSONType


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="sales")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))


class DataSource(TimestampMixin, Base):
    """Veri kaynağı kaydı: erişim türü, hukuki dayanak ve sağlık durumu."""
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))  # webservice | feed | inbox | manual | reference
    url: Mapped[Optional[str]] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    automated: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_basis: Mapped[Optional[str]] = mapped_column(Text)
    access_notes: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    health: Mapped[str] = mapped_column(String(32), default="unknown")  # ok | error | not_configured | manual | unknown
    last_checked_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class SourceCoverage(Base):
    """Bir kaynağın belirli bir yayın günü için taranıp taranmadığı.

    Taranmamış gün, 'sıfır yeni kuruluş' ile karıştırılmasın diye ayrı tutulur.
    """
    __tablename__ = "source_coverage"
    __table_args__ = (UniqueConstraint("source_id", "coverage_date", name="uq_coverage_source_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    coverage_date: Mapped[dt.date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(16))  # covered | failed | partial
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    new_businesses: Mapped[int] = mapped_column(Integer, default=0)
    job_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"))
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[DataSource] = relationship()


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | success | partial | failed | skipped
    triggered_by: Mapped[str] = mapped_column(String(64), default="schedule")
    run_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    log: Mapped[list] = mapped_column(JSONType, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(32))
    file_sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="processing")
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    errors: Mapped[list] = mapped_column(JSONType, default=list)
    source: Mapped[DataSource] = relationship()


class RawRecord(Base):
    """Kaynaktan gelen ham kayıt (kanıt / izlenebilirlik için saklanır)."""
    __tablename__ = "raw_records"
    __table_args__ = (UniqueConstraint("source_id", "content_hash", name="uq_raw_source_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    import_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"))
    external_id: Mapped[Optional[str]] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64))
    announcement_type: Mapped[Optional[str]] = mapped_column(String(255))
    published_date: Mapped[Optional[dt.date]] = mapped_column(Date, index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(32), default="ingested")
    skip_reason: Mapped[Optional[str]] = mapped_column(String(255))
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        Index("ix_businesses_est_date", "establishment_date"),
        Index("ix_businesses_district", "district"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_name: Mapped[str] = mapped_column(String(500))
    name_normalized: Mapped[str] = mapped_column(String(500), index=True)
    establishment_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    registry_office: Mapped[Optional[str]] = mapped_column(String(128))
    registry_no: Mapped[Optional[str]] = mapped_column(String(64))
    registry_key: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    mersis_no: Mapped[Optional[str]] = mapped_column(String(16), unique=True)
    tax_no: Mapped[Optional[str]] = mapped_column(String(16))
    province: Mapped[Optional[str]] = mapped_column(String(64))
    district: Mapped[Optional[str]] = mapped_column(String(64))
    address: Mapped[Optional[str]] = mapped_column(Text)
    activity_text: Mapped[Optional[str]] = mapped_column(Text)
    nace_code: Mapped[Optional[str]] = mapped_column(String(16))
    nace_description: Mapped[Optional[str]] = mapped_column(String(500))
    nace_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    company_type: Mapped[Optional[str]] = mapped_column(String(16))
    capital: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    announcement_url: Mapped[Optional[str]] = mapped_column(String(1000))
    gazette_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    gazette_no: Mapped[Optional[str]] = mapped_column(String(32))
    gazette_page: Mapped[Optional[str]] = mapped_column(String(32))

    # Kaynak ve doğrulama
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    source_reference: Mapped[Optional[str]] = mapped_column(String(1000))
    verified_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(String(32), default="kaynaktan_otomatik")
    # kaynaktan_otomatik | manuel_dogrulandi | dogrulanmadi | hatali

    # Analiz
    sector: Mapped[Optional[str]] = mapped_column(String(64))
    sector_basis: Mapped[Optional[str]] = mapped_column(String(32))  # nace_dogrulanmis | nace_tahmini | metin_tahmini
    hazard_class: Mapped[Optional[str]] = mapped_column(String(32))
    hazard_basis: Mapped[Optional[str]] = mapped_column(String(32))
    isg_score: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    software_score: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    total_score: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    priority: Mapped[Optional[str]] = mapped_column(String(2))
    analysis: Mapped[dict] = mapped_column(JSONType, default=dict)
    analysis_method: Mapped[Optional[str]] = mapped_column(String(32))
    analyzed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))

    # İletişim araştırma
    enrichment_status: Mapped[str] = mapped_column(String(32), default="bekliyor")
    enriched_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    enrichment_log: Mapped[list] = mapped_column(JSONType, default=list)

    # CRM / KVKK
    sales_status: Mapped[str] = mapped_column(String(32), default="yeni", index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    iys_status: Mapped[str] = mapped_column(String(32), default="bilinmiyor")
    iys_checked_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    merged_into_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    anonymized_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    source: Mapped[Optional[DataSource]] = relationship()
    owner: Mapped[Optional[User]] = relationship(foreign_keys=[owner_id])
    contacts: Mapped[List["ContactPoint"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    opportunities: Mapped[List["Opportunity"]] = relationship(back_populates="business", cascade="all, delete-orphan")


class ContactPoint(Base):
    __tablename__ = "contact_points"
    __table_args__ = (UniqueConstraint("business_id", "type", "normalized_value", name="uq_contact_business_value"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # phone | email | website | map_profile
    value: Mapped[str] = mapped_column(String(500))
    normalized_value: Mapped[str] = mapped_column(String(500))
    source_name: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    confidence_level: Mapped[str] = mapped_column(String(16), default="dusuk")  # yuksek | orta | dusuk
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="aday")  # aday | dogrulandi | reddedildi
    is_corporate: Mapped[bool] = mapped_column(Boolean, default=True)
    personal_data_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    found_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    business: Mapped[Business] = relationship(back_populates="contacts")


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("business_id", "service_line", name="uq_opp_business_line"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    service_line: Mapped[str] = mapped_column(String(16))  # isg | yazilim
    stage: Mapped[str] = mapped_column(String(32), default="yeni", index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    estimated_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="TRY")
    next_action: Mapped[Optional[str]] = mapped_column(String(500))
    next_action_date: Mapped[Optional[dt.date]] = mapped_column(Date, index=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(String(500))
    stage_changed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    won_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    business: Mapped[Business] = relationship(back_populates="opportunities")
    owner: Mapped[Optional[User]] = relationship()


class StageHistory(Base):
    __tablename__ = "stage_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[Optional[str]] = mapped_column(String(32))
    to_stage: Mapped[str] = mapped_column(String(32))
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(16), default="note")
    content: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    follow_up_date: Mapped[Optional[dt.date]] = mapped_column(Date, index=True)
    follow_up_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[Optional[User]] = relationship()


class Quote(TimestampMixin, Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    items: Mapped[list] = mapped_column(JSONType, default=list)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="TRY")
    valid_until: Mapped[Optional[dt.date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="taslak")  # taslak | gonderildi | kabul | red
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class NaceHazard(Base):
    """İşyeri Tehlike Sınıfları Tebliği eki listesi (kullanıcı tarafından resmî listeden içe aktarılır)."""
    __tablename__ = "nace_hazard"
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    hazard_class: Mapped[str] = mapped_column(String(32))  # az_tehlikeli | tehlikeli | cok_tehlikeli
    source: Mapped[Optional[str]] = mapped_column(String(255))
    imported_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyReport(Base):
    __tablename__ = "daily_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[dt.date] = mapped_column(Date, unique=True)
    content: Mapped[dict] = mapped_column(JSONType, default=dict)
    job_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(64))
    entity_id: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[Any] = mapped_column(JSONType, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
