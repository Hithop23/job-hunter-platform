import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


class ElempleoAdapter(BaseJobAdapter):
    """
    Adapter for El Empleo Colombia (elempleo.com/co).
    Extracts structured offers directly from elempleo.com.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="elempleo.com", name="ElEmpleo_CO")
        self.base_url = "https://www.elempleo.com"

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CO,es;q=0.9"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
        except Exception:
            pass
        return ""

    async def discover_jobs(
        self,
        query: str = "tecnico sistemas",
        location: str = "Valledupar",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request():
            return []

        jobs = []
        try:
            self.record_access(action_type="SCAN")
            clean_query = query.strip().lower().replace(" ", "-")

            search_urls = [
                f"{self.base_url}/co/ofertas-empleo/trabajo-{clean_query}",
                f"{self.base_url}/co/ofertas-empleo/trabajo-soporte-tecnico",
                f"{self.base_url}/co/ofertas-empleo/trabajo-mesa-de-ayuda",
                f"{self.base_url}/co/ofertas-empleo/trabajo-sistemas",
                f"{self.base_url}/co/ofertas-empleo/trabajo-auxiliar-sistemas"
            ]

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for url in search_urls:
                html = await self._fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".result-item")
                for it in items:
                    area_div = it.select_one(".js-area-bind[data-ga4-offerdata]")
                    if not area_div:
                        continue

                    raw_data = area_div.get("data-ga4-offerdata", "")
                    rel_url = area_div.get("data-url", "")
                    if not raw_data:
                        continue

                    try:
                        info = json.loads(raw_data)
                    except Exception:
                        continue

                    ext_id = str(info.get("id", ""))
                    job_title = info.get("title", "").strip()
                    job_comp = info.get("company", "Empresa en El Empleo").strip()
                    job_loc = info.get("location", location).strip()
                    job_sal = info.get("salary", "A convenir").strip()

                    if not ext_id or not job_title:
                        continue

                    full_url = rel_url if rel_url.startswith("http") else f"{self.base_url}{rel_url}"
                    job_id = f"ee-{ext_id}"

                    if any(j["id"] == job_id for j in jobs):
                        continue

                    jobs.append(self.normalize_job({
                        "id": job_id,
                        "source": "elempleo",
                        "external_id": ext_id,
                        "company": job_comp,
                        "title": job_title,
                        "location": job_loc,
                        "url": full_url,
                        "description": f"Oferta en El Empleo: {job_title}. Ubicación: {job_loc}. Salario: {job_sal}.",
                        "requirements": "Técnico o tecnólogo en sistemas, soporte de infraestructura o telecomunicaciones.",
                        "salary": job_sal,
                        "employment_type": "Tiempo Completo",
                        "publication_date": today_str
                    }))

                    if len(jobs) >= limit:
                        break

                if len(jobs) >= limit:
                    break
        except Exception:
            pass

        return jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "elempleo",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa en El Empleo"),
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
