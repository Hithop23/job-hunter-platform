from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ApplicationStatus


class NormalizedJob(BaseModel):
    """Vacante normalizada producida por un adapter (Módulo 2)."""

    source: str
    external_id: str
    company: str
    title: str
    url: str
    location: str | None = None
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    salary: str | None = None
    employment_type: str | None = None
    publication_date: datetime | None = None
    closing_date: datetime | None = None
    raw: dict = Field(default_factory=dict)


class StoreResult(BaseModel):
    job_id: str | None = None
    duplicate: bool = False
    error: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    external_id: str
    company: str
    title: str
    location: str | None = None
    url: str
    description: str
    requirements: list[str] | None = None
    salary: str | None = None
    employment_type: str | None = None
    publication_date: datetime | None = None
    closing_date: datetime | None = None
    discovered_at: datetime
    match_score: float | None = None
    match_flags: list[str] | None = None
    priority: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    status: ApplicationStatus
    cv_version: str | None = None
    keywords_used: list[str] | None = None
    cover_letter_path: str | None = None
    submitted_at: datetime | None = None
    source: str | None = None
    notes: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str | None = None
    reason: str
    url: str | None = None
    screenshot_path: str | None = None
    detail: dict | None = None
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


class RunSummary(BaseModel):
    mode: str
    started_at: datetime
    finished_at: datetime | None = None
    sources_run: list[str] = Field(default_factory=list)
    jobs_discovered: int = 0
    duplicates: int = 0
    errors: int = 0
    matched_high: int = 0
    matched_review: int = 0
    matched_low: int = 0
    flagged: int = 0
    message: str = ""
