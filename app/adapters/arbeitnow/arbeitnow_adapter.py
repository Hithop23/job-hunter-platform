import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


# IT-relevant keywords for title/tag filtering
IT_KEYWORDS = {
    "support", "helpdesk", "help desk", "service desk", "it support", "technical support",
    "sysadmin", "system administrator", "network", "infrastructure", "devops", "cloud",
    "linux", "windows", "desktop", "noc", "operations", "monitoring", "backend",
    "soporte", "sistemas", "tecnico", "redes", "infraestructura"
}


class ArbeitnowAdapter(BaseJobAdapter):
    """
    Adapter for Arbeitnow — free worldwide remote jobs API.
    No authentication required. Full JSON API with salary and remote filter.
    API: https://www.arbeitnow.com/api/job-board-api
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="arbeitnow.com", name="Arbeitnow_Global")
        self.api_url = "https://www.arbeitnow.com/api/job-board-api"
        self.max_age_days = 14

    async def discover_jobs(
        self,
        query: str = "IT support",
        location: str = "Remote",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request(max_per_hour=8):
            return []

        jobs = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        try:
            self.record_access(action_type="SCAN")
            query_lower = query.lower()

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0; personal job search)",
                    "Accept": "application/json",
                }

                # Fetch page 1 and page 2 to get more results
                for page in [1, 2]:
                    params = {"page": page}
                    resp = await client.get(self.api_url, headers=headers, params=params)
                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    postings = data.get("data", [])
                    if not postings:
                        break

                    for posting in postings:
                        # Only remote jobs
                        if not posting.get("remote", False):
                            continue

                        # Freshness filter
                        created_at_str = posting.get("created_at", "")
                        try:
                            created_at = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            )
                            if created_at < cutoff:
                                continue
                        except Exception:
                            pass

                        # Relevance filter: Strictly check Title and Tags (not generic description)
                        title = (posting.get("title") or "").lower()
                        tags_list = [t.lower() for t in (posting.get("tags") or [])]
                        tags_str = " ".join(tags_list)
                        title_and_tags = f"{title} {tags_str}"

                        # Exclude obvious non-IT jobs
                        negative_kw = ["marketing", "trainer", "sdr", "recruiter", "hr ", "human resources", "video editor", "influencer", "legal", "accountant", "sales representative"]
                        if any(neg in title for neg in negative_kw):
                            continue

                        is_relevant = any(kw in title_and_tags for kw in IT_KEYWORDS)
                        if not is_relevant:
                            continue

                        # Build normalized job
                        pub_date = ""
                        try:
                            pub_date = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            ).strftime("%Y-%m-%d")
                        except Exception:
                            pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        slug = posting.get("slug", "")
                        ext_id = slug or str(hash(posting.get("title", "") + posting.get("company_name", "")))
                        job_url = posting.get("url") or (f"https://www.arbeitnow.com/jobs/{slug}" if slug else "")

                        salary = self._extract_salary(posting)

                        jobs.append(self.normalize_job({
                            "id": f"arb-{ext_id}",
                            "source": "arbeitnow",
                            "external_id": ext_id,
                            "company": posting.get("company_name", "Empresa Global"),
                            "title": posting.get("title", "Remote IT Role"),
                            "location": posting.get("location") or "100% Remoto / Worldwide",
                            "url": job_url,
                            "description": self._truncate(posting.get("description") or ""),
                            "requirements": f"Tags: {', '.join(tags_list[:8])}",
                            "salary": salary,
                            "employment_type": "Remoto Tiempo Completo",
                            "publication_date": pub_date,
                        }))

                        if len(jobs) >= limit:
                            break

                    if len(jobs) >= limit:
                        break

                    # Respectful delay between pages
                    await asyncio.sleep(0.5)

        except Exception:
            pass

        return jobs

    def _extract_salary(self, posting: dict) -> str:
        """Extract salary info from Arbeitnow posting."""
        salary_from = posting.get("salary_from")
        salary_to = posting.get("salary_to")
        currency = posting.get("salary_currency", "USD")
        if salary_from and salary_to:
            return f"{currency} {salary_from:,} - {salary_to:,} / year"
        elif salary_from:
            return f"{currency} desde {salary_from:,} / year"
        return "Salario a convenir"

    def _truncate(self, text: str, max_len: int = 800) -> str:
        """Clean and truncate description text."""
        import re
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:max_len]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "arbeitnow",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa Arbeitnow"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "100% Remoto / Worldwide"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "Salario a convenir"),
            "employment_type": raw_job.get("employment_type", "Remoto Tiempo Completo"),
            "publication_date": raw_job.get("publication_date", ""),
            "closing_date": raw_job.get("closing_date", ""),
        }
