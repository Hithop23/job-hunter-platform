import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter


class BaseATSAdapter:
    """Interface for specific ATS parser."""
    def __init__(self, company_name: str, careers_url: str):
        self.company_name = company_name
        self.careers_url = careers_url

    async def fetch_jobs(self) -> List[Dict[str, Any]]:
        return []


class BancolombiaSuccessFactorsAdapter(BaseATSAdapter):
    """
    Adapter for Bancolombia's official SAP SuccessFactors (Jobs2Web) career portal.
    Portal URL: https://empleo.grupobancolombia.com/
    Search Endpoint: https://empleo.grupobancolombia.com/search/?q={query}&locationsearch={location}
    """
    def __init__(self):
        super().__init__(company_name="Bancolombia", careers_url="https://empleo.grupobancolombia.com/")

    async def fetch_jobs(self, query: str = "soporte", location: str = "Colombia") -> List[Dict[str, Any]]:
        jobs = []
        base_domain = "https://empleo.grupobancolombia.com"
        search_terms = ["soporte", "sistemas", "ti", "aprendiz"]
        
        # Build search query
        q_term = query if query and query != "soporte TI sistemas help desk" else "sistemas"
        search_url = f"{base_domain}/search/?q={q_term}&locationsearch={location}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        }

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    rows = soup.find_all("tr", class_=lambda c: c and "data-row" in str(c).lower())

                    for row in rows:
                        title_tag = row.find("a", class_=lambda c: c and "jobtitle" in str(c).lower())
                        loc_tag = row.find(class_=lambda c: c and "location" in str(c).lower())
                        date_tag = row.find(class_=lambda c: c and "date" in str(c).lower())

                        if title_tag:
                            title_text = title_tag.get_text(strip=True)
                            href = title_tag.get("href", "")
                            full_url = f"{base_domain}{href}" if href.startswith("/") else href

                            loc_text = loc_tag.get_text(strip=True) if loc_tag else "Colombia"
                            date_text = date_tag.get_text(strip=True) if date_tag else None

                            # Filter only IT / Technology / Systems / Support / Aprendiz roles
                            t_lower = title_text.lower()
                            # Avoid non-tech false positives
                            if any(k in t_lower for k in ["derecho", "abogado", "medico", "enfermer", "psicolog", "cajero", "agronomo"]):
                                continue
                            it_keywords = ["software", "sistemas", "soporte", "ciberseguridad", "redes", "datos", "infraestructura", "desarrollador", "developer", "helpdesk", "teleinform", "tecnolog"]
                            has_it_kw = any(k in t_lower for k in it_keywords)
                            has_ti_token = any(token in t_lower.split() for token in ["ti", "it"]) or "(ti)" in t_lower or "/ti" in t_lower or "-ti" in t_lower
                            if not (has_it_kw or has_ti_token):
                                continue

                            # Quick check: verify position is not covered/closed
                            try:
                                check_r = await client.get(full_url, timeout=5.0)
                                if "ya está cubierta" in check_r.text or "ya esta cubierta" in check_r.text or check_r.status_code != 200:
                                    continue
                            except Exception:
                                pass

                            # Extract job ID from URL
                            parts = full_url.strip("/").split("/")
                            job_ext_id = parts[-1] if parts else "bancolombia"

                            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                            jobs.append({
                                "id": f"comp-bancolombia-{job_ext_id}",
                                "source": "company_direct",
                                "external_id": f"bancolombia-{job_ext_id}",
                                "company": "Bancolombia",
                                "title": title_text,
                                "location": loc_text,
                                "url": full_url,
                                "description": f"Vacante activa oficial en Bancolombia: {title_text}. Consulta requisitos y funciones en el portal de empleo de Bancolombia.",
                                "requirements": "Técnico o tecnólogo en sistemas teleinformáticos, soporte TI o carreras afines. Postulación directa en portal Bancolombia.",
                                "salary": "Salario según escala salarial Bancolombia + beneficios extralegales",
                                "employment_type": "Término Indefinido / Prácticas",
                                "publication_date": date_text or today_str
                            })
        except Exception:
            pass

        return jobs


class CompanyDirectoryAdapter(BaseJobAdapter):
    """
    Adapter that iterates through enabled Colombian companies in companies.json
    and discovers IT support & infrastructure vacancies.
    Includes live SuccessFactors scraping for Bancolombia.
    """

    def __init__(self, db: Session, companies_file: str = None):
        super().__init__(db, domain="grupobancolombia.com", name="Big_Companies_CO")
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        if companies_file is None:
            companies_file = base_dir / "data" / "companies.json"

        with open(companies_file, "r", encoding="utf-8") as f:
            self.companies = json.load(f)

        self.bancolombia_adapter = BancolombiaSuccessFactorsAdapter()

    async def discover_jobs(
        self,
        query: str = "soporte",
        location: str = "Colombia",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        jobs = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Fetch live jobs from Bancolombia's official career portal
        try:
            bancolombia_jobs = await self.bancolombia_adapter.fetch_jobs(query=query, location=location)
            if not bancolombia_jobs and location and location.lower() not in ["colombia", "col"]:
                bancolombia_jobs = await self.bancolombia_adapter.fetch_jobs(query="sistemas", location="Colombia")
            for bj in bancolombia_jobs:
                jobs.append(self.normalize_job(bj))
        except Exception:
            pass

        # Only genuine live postings
        return jobs[:limit]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw_job.get("id"),
            "source": raw_job.get("source", "company_direct"),
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Gran Empresa Colombia"),
            "title": raw_job.get("title", ""),
            "location": raw_job.get("location", "Colombia"),
            "url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "salary": raw_job.get("salary", "A convenir"),
            "employment_type": raw_job.get("employment_type", "Tiempo Completo"),
            "publication_date": raw_job.get("publication_date")
        }
