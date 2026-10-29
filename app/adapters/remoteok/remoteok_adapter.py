import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


# Primary tags — strongly indicate IT Support / Help Desk / SysAdmin role
IT_TAGS_PRIMARY = {
    "sysadmin", "linux", "networking", "it", "support", "helpdesk",
    "help-desk", "it-support", "service-desk", "noc", "operations",
    "sys admin", "desktop", "windows", "monitoring", "it operations"
}

# Secondary tags — general tech that could include our target roles
IT_TAGS_SECONDARY = {
    "devops", "cloud", "infra", "infrastructure", "aws", "azure", "gcp",
    "security", "systems", "database", "ops", "python", "bash"
}

IT_TAGS = IT_TAGS_PRIMARY | IT_TAGS_SECONDARY


class RemoteOKAdapter(BaseJobAdapter):
    """
    Adapter for RemoteOK public API — worldwide remote jobs.
    No authentication required. Returns JSON directly.
    API docs: https://remoteok.com/api
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="remoteok.com", name="RemoteOK_Global")
        self.api_url = "https://remoteok.com/api"
        # Max age of jobs to include (14 days)
        self.max_age_days = 14

    async def discover_jobs(
        self,
        query: str = "IT support",
        location: str = "Remote",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request(max_per_hour=6):
            return []

        jobs = []
        cutoff_ts = time.time() - (self.max_age_days * 86400)

        try:
            self.record_access(action_type="SCAN")
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0; personal job search agent)",
                    "Accept": "application/json",
                }
                resp = await client.get(self.api_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # First element is a metadata dict — skip it
                    postings = [item for item in data if isinstance(item, dict) and "id" in item]

                    # Build search keywords from query
                    query_words = set(query.lower().replace("-", " ").split())

                    for posting in postings:
                        # Freshness filter
                        epoch = posting.get("epoch", 0)
                        if epoch and epoch < cutoff_ts:
                            continue

                        # Tag relevance filter — two tier approach
                        tags = set(t.lower() for t in (posting.get("tags") or []))
                        position = (posting.get("position") or "").lower()
                        title_words = set(position.split())

                        has_primary_tag = bool(tags & IT_TAGS_PRIMARY)
                        has_secondary_tag = bool(tags & IT_TAGS_SECONDARY)
                        title_matches_query = any(w in position for w in query_words if len(w) > 3)
                        title_is_support = any(k in position for k in [
                            "support", "sysadmin", "helpdesk", "help desk", "service desk",
                            "desktop", "noc", "operations engineer", "infrastructure", "linux"
                        ])

                        is_relevant = (
                            has_primary_tag or
                            title_is_support or
                            (has_secondary_tag and title_matches_query)
                        )
                        if not is_relevant:
                            continue

                        # Build normalized job
                        pub_date = ""
                        if epoch:
                            pub_date = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")
                        else:
                            pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        ext_id = str(posting.get("id", ""))
                        salary = self._extract_salary(posting)

                        jobs.append(self.normalize_job({
                            "id": f"rok-{ext_id}",
                            "source": "remoteok",
                            "external_id": ext_id,
                            "company": posting.get("company", "Empresa Remota"),
                            "title": posting.get("position", "Remote IT Role"),
                            "location": "100% Remoto / Worldwide",
                            "url": posting.get("url") or f"https://remoteok.com/jobs/{ext_id}",
                            "description": self._clean_html(posting.get("description") or "Vacante remota de TI publicada en RemoteOK."),
                            "requirements": f"Tags: {', '.join(list(tags)[:10])}",
                            "salary": salary,
                            "employment_type": "Remoto Tiempo Completo",
                            "publication_date": pub_date,
                        }))

                        if len(jobs) >= limit:
                            break

        except Exception:
            pass

        return jobs

    def _extract_salary(self, posting: dict) -> str:
        """Extract salary range from RemoteOK posting if present."""
        salary_min = posting.get("salary_min")
        salary_max = posting.get("salary_max")
        if salary_min and salary_max:
            return f"USD ${salary_min:,} - ${salary_max:,} / year"
        elif salary_min:
            return f"USD desde ${salary_min:,} / year"
        return "Salario a convenir (USD)"

    def _clean_html(self, text: str) -> str:
        """Remove basic HTML tags from description."""
        import re
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:800]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "remoteok",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa RemoteOK"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "100% Remoto / Worldwide"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "Salario a convenir (USD)"),
            "employment_type": raw_job.get("employment_type", "Remoto Tiempo Completo"),
            "publication_date": raw_job.get("publication_date", ""),
            "closing_date": raw_job.get("closing_date", ""),
        }
