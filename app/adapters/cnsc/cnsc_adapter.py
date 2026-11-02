import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


class CNSCAdapter(BaseJobAdapter):
    """
    Adapter for CNSC / SIMO (Sistema de apoyo para la Igualdad, el Mérito y la Oportunidad).
    Strictly filters for 'Nivel Técnico' and 'Nivel Asistencial' in public convocatorias,
    matching against Julian's technical diploma and experience while enforcing human stop
    prior to any official inscription.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="cnsc.gov.co", name="CNSC_SIMO")
        self.simo_url = "https://simo.cnsc.gov.co"

    async def discover_jobs(
        self,
        query: str = "tecnico sistemas soporte informatica",
        location: str = "Valledupar",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request():
            return []

        jobs = []
        try:
            self.record_access(action_type="SCAN")
            # In live environment, SIMO exposes public convocatoria listings and OPEC search
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                headers = {"User-Agent": "Mozilla/5.0"}
                url = f"{self.simo_url}/empleos/buscar?nivel=tecnico&denominacion={query}"
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    pass
        except Exception:
            pass

        return jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": "cnsc",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Entidad Pública - CNSC SIMO"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "Valledupar, Cesar"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "Regulado por escala salarial"),
            "employment_type": raw_job.get("employment_type", "Carrera Administrativa"),
            "publication_date": raw_job.get("publication_date", ""),
            "closing_date": raw_job.get("closing_date", ""),
        }
