import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


# We Work Remotely RSS feeds relevant to IT Support / Systems / DevOps
WWR_FEEDS = [
    {
        "url": "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "category": "DevOps / SysAdmin"
    },
    {
        "url": "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "category": "Customer & Tech Support"
    },
    {
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "category": "Programming / Systems"
    },
]

IT_KEYWORDS = {
    "support", "helpdesk", "help desk", "service desk", "sysadmin", "linux",
    "network", "infrastructure", "devops", "cloud", "windows", "desktop",
    "noc", "operations", "monitoring", "it support", "technical support",
    "soporte", "sistemas", "tecnico", "redes"
}


class WeWorkRemotelyAdapter(BaseJobAdapter):
    """
    Adapter for We Work Remotely RSS feeds — curated worldwide remote jobs.
    Parses RSS XML from multiple IT/DevOps/Support categories.
    No authentication required. Freshness filter: last 14 days.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="weworkremotely.com", name="WWR_Global")
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
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        query_lower = query.lower()

        try:
            self.record_access(action_type="SCAN")
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0; personal job search)",
                    "Accept": "application/rss+xml, application/xml, text/xml",
                }

                for feed in WWR_FEEDS:
                    if len(jobs) >= limit:
                        break

                    resp = await client.get(feed["url"], headers=headers)
                    if resp.status_code != 200:
                        continue

                    try:
                        root = ET.fromstring(resp.text)
                    except ET.ParseError:
                        continue

                    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
                    channel = root.find("channel")
                    if channel is None:
                        continue

                    items = channel.findall("item")
                    for item in items:
                        if len(jobs) >= limit:
                            break

                        # Freshness filter
                        pub_date_str = item.findtext("pubDate", "")
                        pub_date = ""
                        try:
                            dt = parsedate_to_datetime(pub_date_str)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            if dt < cutoff:
                                continue
                            pub_date = dt.strftime("%Y-%m-%d")
                        except Exception:
                            pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        title = item.findtext("title", "").strip()
                        description_raw = item.findtext("description", "")
                        content_raw = item.find("content:encoded", ns)
                        description = self._clean(
                            content_raw.text if content_raw is not None else description_raw
                        )

                        # Parse title: usually "Company | Job Title" or "Job Title at Company"
                        company, job_title = self._parse_title(title)

                        # Relevance filter
                        search_text = f"{title} {description[:200]}".lower()
                        is_relevant = any(kw in search_text for kw in IT_KEYWORDS)
                        if not is_relevant:
                            is_relevant = any(w in search_text for w in query_lower.split() if len(w) > 3)

                        # For DevOps/SysAdmin feed, all items are relevant
                        if "devops" in feed["url"].lower() or "sysadmin" in feed["url"].lower():
                            is_relevant = True

                        if not is_relevant:
                            continue

                        link = item.findtext("link", "").strip()
                        # Extract ID from GUID or link
                        guid = item.findtext("guid", link)
                        ext_id = guid.split("/")[-1] or guid[-30:]

                        jobs.append(self.normalize_job({
                            "id": f"wwr-{ext_id}",
                            "source": "weworkremotely",
                            "external_id": ext_id,
                            "company": company,
                            "title": job_title,
                            "location": "100% Remoto / Worldwide",
                            "url": link,
                            "description": description,
                            "requirements": f"Categoría: {feed['category']}. Ver descripción completa en el enlace.",
                            "salary": "Salario a convenir (USD/remoto)",
                            "employment_type": "Remoto Tiempo Completo",
                            "publication_date": pub_date,
                        }))

        except Exception:
            pass

        return jobs

    def _parse_title(self, raw_title: str):
        """Extract company and job title from WWR format 'Company: Job Title at Region'."""
        # WWR format: "Company: Job Title"  or "Job Title at Company"
        if ": " in raw_title:
            parts = raw_title.split(": ", 1)
            return parts[0].strip(), parts[1].strip()
        elif " at " in raw_title:
            parts = raw_title.rsplit(" at ", 1)
            return parts[1].strip(), parts[0].strip()
        return "Empresa Remota", raw_title

    def _clean(self, text: str, max_len: int = 800) -> str:
        import re
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"&[a-z]+;", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:max_len]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "weworkremotely",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa WWR"),
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
