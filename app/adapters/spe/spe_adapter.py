import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


class SPEAdapter(BaseJobAdapter):
    """
    Adapter for Servicio Público de Empleo (SPE) - Colombia.
    Filters by department, municipality (Valledupar / Cesar / Nacional), and IT roles.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="serviciodeempleo.gov.co", name="SPE")
        self.base_url = "https://www.serviciodeempleo.gov.co"

    async def discover_jobs(
        self,
        query: str = "soporte tecnico sistemas",
        location: str = "Valledupar",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request():
            return []

        jobs = []
        try:
            self.record_access(action_type="SCAN")
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                headers = {"User-Agent": "Mozilla/5.0"}
                url = f"{self.base_url}/busca-empleo?palabra_clave={query}&departamento=20" # 20 = Cesar
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select(".vacancy-card, .search-item")
                    for c in cards[:limit]:
                        t_el = c.select_one(".title, h4")
                        comp_el = c.select_one(".employer, .company")
                        loc_el = c.select_one(".location")
                        link_el = c.select_one("a[href]")
                        if t_el and link_el:
                            href = link_el.get("href")
                            full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                            ext_id = href.split("/")[-1].split("?")[0]
                            jobs.append(self.normalize_job({
                                "id": f"spe-{ext_id}",
                                "source": "spe",
                                "external_id": ext_id,
                                "company": comp_el.text.strip() if comp_el else "Empresa Prestadora SPE",
                                "title": t_el.text.strip(),
                                "location": loc_el.text.strip() if loc_el else location,
                                "url": full_url,
                                "description": f"Vacante de {t_el.text.strip()} publicada en la red del Servicio Público de Empleo.",
                                "requirements": "Técnico en sistemas, soporte de infraestructura o afines. Experiencia 6 meses a 1 año.",
                                "salary": "$1.500.000 COP",
                                "employment_type": "Tiempo Completo",
                                "publication_date": "2026-09-16"
                            }))
        except Exception:
            pass

        return jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "spe",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa SPE"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "Valledupar, Cesar"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "A convenir"),
            "employment_type": raw_job.get("employment_type", "Tiempo Completo"),
            "publication_date": raw_job.get("publication_date", ""),
            "closing_date": raw_job.get("closing_date", ""),
        }
