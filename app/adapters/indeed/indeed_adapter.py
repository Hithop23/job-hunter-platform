import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


class IndeedAdapter(BaseJobAdapter):
    """
    Adapter for Indeed worldwide (indeed.com) with remote and freshness filters.
    Falls back to co.indeed.com for Colombia-specific searches.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="indeed.com", name="Indeed_Global")
        self.base_url_global = "https://www.indeed.com"
        self.base_url_co = "https://co.indeed.com"

    async def discover_jobs(
        self,
        query: str = "IT support remote",
        location: str = "Remote",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request():
            return []

        jobs = []
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        loc_lower = location.strip().lower()
        is_remote = any(kw in loc_lower for kw in ["remoto", "remote", "worldwide", "mundial"]) or \
                    any(kw in query.lower() for kw in ["remoto", "remote"])

        try:
            self.record_access(action_type="SCAN")
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                headers = {"User-Agent": "Mozilla/5.0"}
                if is_remote:
                    # Global search — no location, remote filter, last 14 days
                    url = f"{self.base_url_global}/jobs?q={query}&remotejob=1&fromage=14"
                else:
                    url = f"{self.base_url_co}/jobs?q={query}&l={location}"

                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select(".job_seen_beacon, .result")
                    for card in cards[:limit]:
                        title_el = card.select_one("h2.jobTitle span")
                        comp_el = card.select_one("[data-testid='company-name']")
                        loc_el = card.select_one("[data-testid='text-location']")
                        link_el = card.select_one("a.jcs-JobTitle")
                        if title_el and link_el:
                            href = link_el.get("href", "")
                            base = self.base_url_global if is_remote else self.base_url_co
                            full_url = href if href.startswith("http") else f"{base}{href}"
                            ext_id = link_el.get("data-jk") or href.split("/")[-1]
                            jobs.append(self.normalize_job({
                                "id": f"indeed-{ext_id}",
                                "source": "indeed",
                                "external_id": ext_id,
                                "company": comp_el.text.strip() if comp_el else "Empresa Destacada",
                                "title": title_el.text.strip(),
                                "location": loc_el.text.strip() if loc_el else ("100% Remoto / Worldwide" if is_remote else location),
                                "url": full_url,
                                "description": "Soporte técnico a usuarios, configuración de estaciones de trabajo e impresoras.",
                                "requirements": "Técnico de sistemas o informática. Experiencia mínima de 6 meses a 1 año.",
                                "salary": "A convenir",
                                "employment_type": "Remoto Tiempo Completo" if is_remote else "Tiempo Completo",
                                "publication_date": today_str
                            }))
        except Exception:
            pass

        return jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "indeed",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa Indeed"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "Colombia"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "A convenir"),
            "employment_type": raw_job.get("employment_type", "Tiempo Completo"),
            "publication_date": raw_job.get("publication_date", ""),
            "closing_date": raw_job.get("closing_date", ""),
        }
