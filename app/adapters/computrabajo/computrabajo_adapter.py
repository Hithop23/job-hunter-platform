import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.adapters.base import BaseJobAdapter
from playwright.async_api import async_playwright


class ComputrabajoAdapter(BaseJobAdapter):
    """
    Adapter for Computrabajo Colombia (computrabajo.com.co).
    Focuses on Junior TI, Mesa de Ayuda, Soporte en Sitio in Cesar and Colombia.
    Uses stealth Playwright browser if direct HTTP request is blocked by Cloudflare.
    """

    def __init__(self, db: Session):
        super().__init__(db, domain="co.computrabajo.com", name="Computrabajo_CO")
        self.base_url = "https://co.computrabajo.com"

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CO,es;q=0.9,en;q=0.8"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and "challenge-platform" not in resp.text:
                    return resp.text
        except Exception:
            pass

        # Fallback to stealth Playwright
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    locale="es-CO"
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                await context.add_init_script("window.chrome = { runtime: {} };")
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(1.5)
                content = await page.content()
                await browser.close()
                return content
        except Exception:
            return ""

    async def discover_jobs(
        self,
        query: str = "soporte sistemas",
        location: str = "Valledupar",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.can_request():
            return []

        jobs = []
        try:
            self.record_access(action_type="SCAN")
            clean_query = query.strip().lower().replace(" ", "-")
            clean_loc = location.strip().lower().replace(" ", "-").replace(",", "")

            search_urls = []
            if clean_loc and clean_loc not in ["colombia", "nacional", "todo-el-pais", "remoto", ""]:
                search_urls.append(f"{self.base_url}/trabajo-de-{clean_query}-en-{clean_loc}")
            search_urls.append(f"{self.base_url}/trabajo-de-{clean_query}")
            search_urls.append(f"{self.base_url}/trabajo-de-tecnico-sistemas")

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for url in search_urls:
                html = await self._fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.select("article.box_offer, .bClick")
                for art in articles:
                    title_el = art.select_one("h1 a, h2 a, a.js-o-link")
                    company_el = art.select_one("p.fs16, .fc_base")
                    loc_el = art.select_one("p.fs13, .build_location")
                    salary_el = art.select_one("span.tag_base, span.fs13")

                    if title_el:
                        href = title_el.get("href", "")
                        if not href or "oferta-de-trabajo" not in href:
                            continue
                        full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                        ext_id = href.split("/")[-1].replace(".htm", "").split("#")[0]
                        if any(j["id"] == f"ct-{ext_id}" for j in jobs):
                            continue

                        jobs.append(self.normalize_job({
                            "id": f"ct-{ext_id}",
                            "source": "computrabajo",
                            "external_id": ext_id,
                            "company": company_el.text.strip() if company_el else "Empresa Destacada",
                            "title": title_el.text.strip(),
                            "location": loc_el.text.strip() if loc_el else location,
                            "url": full_url,
                            "description": f"Vacante activa en Computrabajo: {title_el.text.strip()}. Soporte técnico a sistemas, hardware, software y redes.",
                            "requirements": "Técnico en sistemas, soporte de infraestructura o telecomunicaciones.",
                            "salary": salary_el.text.strip() if salary_el else "A convenir",
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
            "source": "computrabajo",
            "external_id": str(raw_job.get("external_id", "")),
            "company": raw_job.get("company", "Empresa en Computrabajo"),
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
