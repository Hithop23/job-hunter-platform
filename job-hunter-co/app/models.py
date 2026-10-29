from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class ApplicationStatus(str, enum.Enum):
    """Estados de una candidatura (Módulo 11)."""

    DISCOVERED = "DISCOVERED"
    MATCHED = "MATCHED"
    REVIEW = "REVIEW"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    HIRED = "HIRED"


class ReviewReason(str, enum.Enum):
    """Motivos por los que se detiene la automatización (Módulo 14)."""

    CAPTCHA = "CAPTCHA"
    TWO_FACTOR = "TWO_FACTOR"
    AMBIGUOUS_QUESTION = "AMBIGUOUS_QUESTION"
    LEGAL_QUESTION = "LEGAL_QUESTION"
    SALARY_QUESTION = "SALARY_QUESTION"
    TECHNICAL_TEST = "TECHNICAL_TEST"
    MANDATORY_STATEMENT = "MANDATORY_STATEMENT"
    CONSENT = "CONSENT"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    BLOCKED = "BLOCKED"
    OTHER = "OTHER"


class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    dedup_hash: Mapped[str] = mapped_column(String(64))
    company: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    salary: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    applications: Mapped[list["Application"]] = relationship(
        back_populates="job"
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
        Index("ix_jobs_dedup_hash", "dedup_hash"),
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.DISCOVERED
    )
    cv_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keywords_used: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cover_letter_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    job: Mapped[Job] = relationship(back_populates="applications")


class ReviewItem(Base):
    """Cola de intervención humana (Módulo 14)."""

    __tablename__ = "review_queue"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Enum(ReviewReason))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RunLog(Base):
    """Bitácora de ejecución (Módulo 13). Nunca contiene credenciales."""

    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    job: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
