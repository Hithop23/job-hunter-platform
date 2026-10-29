import abc
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.storage.repository import Repository, compute_job_hash
from app.storage.models import Job


class BaseJobAdapter(abc.ABC):
    """
    Base contract for all job adapters.
    Each adapter must implement discover_jobs, get_job_details, normalize_job.
    """

    def __init__(self, db: Session, domain: str, name: str):
        self.db = db
        self.repo = Repository(db)
        self.domain = domain
        self.name = name

    @abc.abstractmethod
    async def discover_jobs(
        self,
        query: str = "soporte TI",
        location: str = "Valledupar",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search and retrieve job listings from source."""
        pass

    @abc.abstractmethod
    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch complete description, requirements and closing date if needed."""
        pass

    @abc.abstractmethod
    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize into canonical schema:
        {
            "id": str,
            "source": str,
            "external_id": str,
            "company": str,
            "title": str,
            "location": str,
            "url": str,
            "description": str,
            "requirements": str,
            "salary": str,
            "employment_type": str,
            "publication_date": str,
            "closing_date": str,
        }
        """
        pass

    def store_job(self, normalized_job: Dict[str, Any]) -> Tuple[Job, bool]:
        """Deduplicates and persists normalized job into database."""
        # Ensure deduplication hash is set
        if "deduplication_hash" not in normalized_job or not normalized_job["deduplication_hash"]:
            normalized_job["deduplication_hash"] = compute_job_hash(
                normalized_job.get("company", ""),
                normalized_job.get("title", ""),
                normalized_job.get("url", ""),
            )
        return self.repo.store_job(normalized_job)

    def can_request(self, max_per_hour: int = 10) -> bool:
        """Check domain rate limit."""
        return self.repo.check_domain_rate_limit(self.domain, max_per_hour=max_per_hour)

    def record_access(self, action_type: str = "SCAN"):
        """Record domain access for rate limiting."""
        self.repo.record_domain_access(self.domain, action_type=action_type)
