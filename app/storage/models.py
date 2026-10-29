import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    Enum as SqlEnum,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's native UUID type, otherwise uses String(64) for SQLite.
    Safely binds non-UUID strings to nil UUID on PostgreSQL to avoid syntax crashes.
    """
    impl = String(64)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(String(64))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            try:
                return str(uuid.UUID(str(value)))
            except (ValueError, TypeError, AttributeError):
                return '00000000-0000-0000-0000-000000000000'
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)


class ApplicationStatus(str, enum.Enum):
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


class HumanReviewReason(str, enum.Enum):
    LOGIN_REQUIRED = "INICIAR_SESION"
    CAPTCHA = "CAPTCHA"
    TWO_FACTOR_AUTH = "2FA"
    AMBIGUOUS_QUESTION = "PREGUNTA_AMBIGUA"
    LEGAL_QUESTION = "PREGUNTA_LEGAL"
    SALARY_QUESTION = "PREGUNTA_SALARIAL_COMPLEJA"
    TECHNICAL_TEST = "PRUEBA_TECNICA"
    CONSENT = "DECLARACION_O_CONSENTIMIENTO"
    UNRECOGNIZED_FORM = "FORMULARIO_NO_RECONOCIDO"
    EXTERNAL_APPLICATION = "POSTULACION_EXTERNA"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    external_id = Column(String(128), nullable=False, index=True)
    company = Column(String(150), nullable=False, index=True)
    title = Column(String(200), nullable=False, index=True)
    location = Column(String(150), nullable=True)
    url = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    salary = Column(String(100), nullable=True)
    employment_type = Column(String(50), nullable=True)
    publication_date = Column(String(50), nullable=True)
    closing_date = Column(String(50), nullable=True)
    discovered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deduplication_hash = Column(String(64), unique=True, index=True, nullable=False)

    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_source_external_id", "source", "external_id", unique=True),
    )


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(GUID, nullable=True, index=True)  # Multi-tenant isolation (UUID in PostgreSQL, String in SQLite)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=False, index=True)
    company = Column(String(150), nullable=False, index=True)
    position = Column(String(200), nullable=False)
    url = Column(Text, nullable=False)
    status = Column(String(40), default=ApplicationStatus.DISCOVERED.value, nullable=False, index=True)
    
    # Matching details
    match_score = Column(Float, default=0.0, nullable=False, index=True)
    required_skill_match = Column(Float, default=0.0)
    education_match = Column(Float, default=0.0)
    experience_match = Column(Float, default=0.0)
    location_match = Column(Float, default=0.0)
    keyword_match = Column(Float, default=0.0)
    seniority_match = Column(Float, default=0.0)
    does_not_meet_required_requirement = Column(Boolean, default=False, nullable=False)
    match_reasons = Column(Text, nullable=True)

    # ATS CV & Cover letter
    cv_version = Column(String(64), nullable=True)
    cv_path = Column(Text, nullable=True)
    cover_letter = Column(Text, nullable=True)
    keywords_used = Column(Text, nullable=True)

    # Submission & tracking
    submitted_at = Column(DateTime, nullable=True)
    source = Column(String(50), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    job = relationship("Job", back_populates="applications")
    human_reviews = relationship("HumanReviewItem", back_populates="application", cascade="all, delete-orphan")


class HumanReviewItem(Base):
    __tablename__ = "human_reviews"

    id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False, index=True)
    reason = Column(String(50), nullable=False, index=True)
    url = Column(Text, nullable=False)
    screenshot_path = Column(Text, nullable=True)
    field_name = Column(String(100), nullable=True)
    question_prompt = Column(Text, nullable=True)
    user_action = Column(String(30), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED, EDITED, SKIPPED
    user_input = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="human_reviews")


class DomainRateRecord(Base):
    __tablename__ = "domain_rate_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(150), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # SCAN, APPLY


class SystemAuditLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    source = Column(String(50), nullable=False)
    company = Column(String(150), nullable=True)
    job_title = Column(String(200), nullable=True)
    action = Column(String(50), nullable=False)
    result = Column(String(50), nullable=False)
    score = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)
    error = Column(Text, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String(64), primary_key=True, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    country = Column(String(100), default="Colombia", nullable=False)
    
    # Career & Targeting
    target_role = Column(String(150), nullable=True)
    headline = Column(String(250), nullable=True)
    summary = Column(Text, nullable=True)
    english_level = Column(String(20), default="B2", nullable=False)
    salary_min_cop = Column(Integer, default=2500000)
    salary_max_cop = Column(Integer, default=4000000)
    
    # Remote readiness
    remote_only = Column(Boolean, default=True)
    has_computer = Column(Boolean, default=True)
    has_internet = Column(Boolean, default=True)
    immediate_availability = Column(Boolean, default=True)
    
    # Serialized structures for ATS generation
    technical_skills_json = Column(Text, nullable=True)
    experience_json = Column(Text, nullable=True)
    education_json = Column(Text, nullable=True)
    certifications_json = Column(Text, nullable=True)
    languages_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PortalCredential(Base):
    __tablename__ = "portal_credentials"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(GUID, nullable=False, index=True)
    portal_name = Column(String(50), nullable=False, index=True)  # computrabajo, linkedin, magneto, elempleo
    username = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)
    session_cookies_json = Column(Text, nullable=True)  # Serialized Playwright storage_state for session reuse
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
