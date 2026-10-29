import hashlib
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from app.storage.models import (
    Job,
    Application,
    ApplicationStatus,
    HumanReviewItem,
    DomainRateRecord,
    SystemAuditLog,
    UserProfile,
)


def compute_job_hash(company: str, title: str, url: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Repository:
    def __init__(self, db: Session):
        self.db = db

    # ------------------ JOBS ------------------
    def store_job(self, job_dict: Dict[str, Any]) -> Tuple[Job, bool]:
        """
        Stores job if not already present.
        Returns (job, created_flag).
        Deduplication rules:
        1. source + external_id
        2. fallback: hash(company + title + url)
        """
        source = job_dict.get("source", "unknown")
        external_id = str(job_dict.get("external_id", ""))
        company = job_dict.get("company", "").strip()
        title = job_dict.get("title", "").strip()
        url = job_dict.get("url", "").strip()

        # 1. Primary check by source + external_id
        existing = (
            self.db.query(Job)
            .filter(Job.source == source, Job.external_id == external_id)
            .first()
        )
        if existing:
            return existing, False

        # 2. Fallback hash check
        dedup_hash = job_dict.get("deduplication_hash") or compute_job_hash(company, title, url)
        existing_hash = self.db.query(Job).filter(Job.deduplication_hash == dedup_hash).first()
        if existing_hash:
            return existing_hash, False

        job_id = job_dict.get("id") or str(uuid.uuid4())
        job = Job(
            id=job_id,
            source=source,
            external_id=external_id,
            company=company,
            title=title,
            location=job_dict.get("location"),
            url=url,
            description=job_dict.get("description", ""),
            requirements=job_dict.get("requirements", ""),
            salary=job_dict.get("salary"),
            employment_type=job_dict.get("employment_type"),
            publication_date=job_dict.get("publication_date"),
            closing_date=job_dict.get("closing_date"),
            discovered_at=datetime.now(timezone.utc),
            deduplication_hash=dedup_hash,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job, True

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == job_id).first()

    def list_jobs(
        self,
        source: Optional[str] = None,
        company: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        q = self.db.query(Job)
        if source:
            q = q.filter(Job.source == source)
        if company:
            q = q.filter(Job.company.ilike(f"%{company}%"))
        if search:
            q = q.filter(
                or_(
                    Job.title.ilike(f"%{search}%"),
                    Job.description.ilike(f"%{search}%"),
                    Job.requirements.ilike(f"%{search}%"),
                )
            )
        return q.order_by(desc(Job.discovered_at)).offset(offset).limit(limit).all()

    # ------------------ APPLICATIONS ------------------
    def create_or_update_application(self, app_data: Dict[str, Any]) -> Application:
        job_id = app_data["job_id"]
        app = self.db.query(Application).filter(Application.job_id == job_id).first()
        if not app:
            app = Application(
                id=app_data.get("id") or str(uuid.uuid4()),
                job_id=job_id,
                company=app_data["company"],
                position=app_data["position"],
                url=app_data["url"],
                source=app_data.get("source", "unknown"),
                status=app_data.get("status", ApplicationStatus.DISCOVERED.value),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(app)

        # Update fields
        for field in [
            "status",
            "match_score",
            "required_skill_match",
            "education_match",
            "experience_match",
            "location_match",
            "keyword_match",
            "seniority_match",
            "does_not_meet_required_requirement",
            "match_reasons",
            "cv_version",
            "cv_path",
            "cover_letter",
            "keywords_used",
            "submitted_at",
            "notes",
            "retry_count",
        ]:
            if field in app_data and app_data[field] is not None:
                # Do not downgrade an already submitted, interviewed or decided application back to discovery states
                if field == "status" and app.status in [
                    ApplicationStatus.SUBMITTED.value,
                    ApplicationStatus.INTERVIEW.value,
                    ApplicationStatus.HIRED.value,
                    ApplicationStatus.REJECTED.value,
                ] and app_data[field] in [
                    ApplicationStatus.DISCOVERED.value,
                    ApplicationStatus.READY.value,
                    ApplicationStatus.REVIEW.value,
                ]:
                    continue
                setattr(app, field, app_data[field])

        app.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(app)
        return app

    def get_application(self, application_id: str) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def list_applications(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        company: Optional[str] = None,
        min_score: Optional[float] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        q = self.db.query(Application)
        if user_id:
            try:
                valid_uuid = str(uuid.UUID(str(user_id)))
                q = q.filter(Application.user_id == valid_uuid)
            except (ValueError, TypeError, AttributeError):
                return []
        if status:
            q = q.filter(Application.status == status)
        if source:
            q = q.filter(Application.source == source)
        if company:
            q = q.filter(Application.company.ilike(f"%{company}%"))
        if min_score is not None:
            q = q.filter(Application.match_score >= min_score)
        return q.order_by(desc(Application.updated_at)).offset(offset).limit(limit).all()

    # ------------------ HUMAN REVIEW QUEUE ------------------
    def enqueue_human_review(
        self,
        application_id: str,
        reason: str,
        url: str,
        screenshot_path: Optional[str] = None,
        field_name: Optional[str] = None,
        question_prompt: Optional[str] = None,
    ) -> HumanReviewItem:
        review = HumanReviewItem(
            id=str(uuid.uuid4()),
            application_id=application_id,
            reason=reason,
            url=url,
            screenshot_path=screenshot_path,
            field_name=field_name,
            question_prompt=question_prompt,
            user_action="PENDING",
            resolved=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(review)

        # Update application status
        app = self.get_application(application_id)
        if app:
            app.status = ApplicationStatus.CONFIRMATION_REQUIRED.value
            app.notes = f"Requiere intervención humana: {reason}"
            app.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(review)
        return review

    def list_pending_reviews(self) -> List[HumanReviewItem]:
        return (
            self.db.query(HumanReviewItem)
            .filter(HumanReviewItem.resolved == False)
            .order_by(desc(HumanReviewItem.created_at))
            .all()
        )

    def resolve_human_review(
        self, review_id: str, action: str, user_input: Optional[str] = None
    ) -> Optional[HumanReviewItem]:
        review = self.db.query(HumanReviewItem).filter(HumanReviewItem.id == review_id).first()
        if not review:
            return None
        review.user_action = action
        review.user_input = user_input
        review.resolved = True
        review.resolved_at = datetime.now(timezone.utc)

        # Update application status based on action
        app = self.get_application(review.application_id)
        if app:
            if action == "APPROVED":
                app.status = ApplicationStatus.READY.value
            elif action == "REJECTED" or action == "DO_NOT_APPLY":
                app.status = ApplicationStatus.REJECTED.value
                app.notes = "Descartado por decisión del usuario en revisión humana."
            elif action == "EDITED":
                app.status = ApplicationStatus.REVIEW.value
            app.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(review)
        return review

    # ------------------ RATE LIMITING & SAFETY ------------------
    def check_domain_rate_limit(self, domain: str, max_per_hour: int = 10) -> bool:
        """Returns True if request is allowed, False if domain rate limit exceeded."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = (
            self.db.query(DomainRateRecord)
            .filter(
                DomainRateRecord.domain == domain,
                DomainRateRecord.timestamp >= one_hour_ago,
            )
            .count()
        )
        return count < max_per_hour

    def record_domain_access(self, domain: str, action_type: str = "SCAN"):
        rec = DomainRateRecord(domain=domain, timestamp=datetime.now(timezone.utc), action_type=action_type)
        self.db.add(rec)
        self.db.commit()

    def check_daily_application_limit(self, max_per_day: int = 50) -> bool:
        """Returns True if allowed to submit, False if daily limit reached."""
        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = (
            self.db.query(Application)
            .filter(
                Application.status == ApplicationStatus.SUBMITTED.value,
                Application.submitted_at >= start_of_day,
            )
            .count()
        )
        return count < max_per_day

    # ------------------ AUDIT LOGS ------------------
    def log_audit(
        self,
        source: str,
        action: str,
        result: str,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        score: Optional[float] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ):
        log = SystemAuditLog(
            timestamp=datetime.now(timezone.utc),
            source=source,
            company=company,
            job_title=job_title,
            action=action,
            result=result,
            score=score,
            status=status,
            error=error,
        )
        self.db.add(log)
        self.db.commit()

    # ------------------ DASHBOARD STATS ------------------
    def get_dashboard_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        total_jobs = self.db.query(Job).count()
        app_q = self.db.query(Application)
        if user_id:
            try:
                valid_uuid = str(uuid.UUID(str(user_id)))
                app_q = app_q.filter(Application.user_id == valid_uuid)
            except (ValueError, TypeError, AttributeError):
                app_q = app_q.filter(Application.user_id.is_(None))
        else:
            app_q = app_q.filter(Application.user_id.is_(None))

        compatible_jobs = (
            app_q.filter(
                Application.match_score >= 60,
                Application.does_not_meet_required_requirement == False,
            )
            .count()
        )
        high_priority_jobs = (
            app_q.filter(
                Application.match_score >= 75,
                Application.does_not_meet_required_requirement == False,
            )
            .count()
        )
        cvs_prepared = app_q.filter(Application.cv_path.isnot(None)).count()
        submitted = (
            app_q.filter(Application.status == ApplicationStatus.SUBMITTED.value)
            .count()
        )
        pending_review = (
            self.db.query(HumanReviewItem).filter(HumanReviewItem.resolved == False).count()
        )
        interviews = (
            app_q.filter(Application.status == ApplicationStatus.INTERVIEW.value)
            .count()
        )
        failed = (
            app_q.filter(Application.status == ApplicationStatus.FAILED.value)
            .count()
        )

        # Source breakdown
        sources_q = (
            self.db.query(Job.source, func.count(Job.id))
            .group_by(Job.source)
            .all()
        )
        source_counts = {src: cnt for src, cnt in sources_q}

        # Status breakdown
        status_q = (
            app_q.with_entities(Application.status, func.count(Application.id))
            .group_by(Application.status)
            .all()
        )
        status_counts = {st: cnt for st, cnt in status_q}

        # Response rate
        response_rate = (interviews / submitted * 100) if submitted > 0 else 0.0

        return {
            "total_jobs_found": total_jobs,
            "compatible_jobs": compatible_jobs,
            "high_priority_jobs": high_priority_jobs,
            "cvs_prepared": cvs_prepared,
            "submitted_applications": submitted,
            "pending_human_interventions": pending_review,
            "interviews_scheduled": interviews,
            "failed_submissions": failed,
            "response_rate_percent": round(response_rate, 1),
            "sources_breakdown": source_counts,
            "status_breakdown": status_counts,
        }

    # ------------------ MULTI-TENANT USER PROFILES ------------------
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    def upsert_user_profile(self, profile_data: Dict[str, Any]) -> UserProfile:
        user_id = profile_data.get("user_id") or str(uuid.uuid4())
        email = (profile_data.get("email") or "").strip().lower()
        profile = self.get_user_profile(user_id)
        if not profile and email:
            profile = self.db.query(UserProfile).filter(UserProfile.email.ilike(email)).first()
            if profile:
                profile.user_id = user_id
        if not profile:
            profile = UserProfile(
                user_id=user_id,
                email=email,
                full_name=profile_data.get("full_name", ""),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(profile)

        # Update profile fields
        for field in [
            "email", "full_name", "phone", "city", "department", "country",
            "target_role", "headline", "summary", "english_level",
            "salary_min_cop", "salary_max_cop", "remote_only",
            "has_computer", "has_internet", "immediate_availability"
        ]:
            if field in profile_data and profile_data[field] is not None:
                setattr(profile, field, profile_data[field])

        # Serialize JSON fields if dicts or lists
        for json_field in ["technical_skills", "experience", "education", "certifications", "languages"]:
            if json_field in profile_data and profile_data[json_field] is not None:
                val = profile_data[json_field]
                if not isinstance(val, str):
                    val = json.dumps(val, ensure_ascii=False)
                setattr(profile, json_field, val)

        profile.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(profile)

        # Claim initial applications for Julian's master account if user_id is a valid UUID
        if profile.email and profile.email.strip().lower() == "maestrecs92@gmail.com":
            try:
                valid_uuid = str(uuid.UUID(str(profile.user_id)))
                self.db.query(Application).filter(Application.user_id.is_(None)).update(
                    {Application.user_id: valid_uuid},
                    synchronize_session=False
                )
                self.db.commit()
            except Exception:
                self.db.rollback()

        return profile
