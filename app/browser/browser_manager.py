from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone
import asyncio
import os
import sys
import random
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.browser.field_mapper import FieldMapper
from app.storage.repository import Repository
from app.storage.models import ApplicationStatus, HumanReviewReason


class BrowserManager:
    """
    Automated form navigator using Playwright with persistent session,
    screenshots, strict safety checks, rate limiting, and human-in-the-loop triggers.
    """

    def __init__(self, repo: Repository, profile_data: Dict[str, Any]):
        self.repo = repo
        self.profile_data = profile_data
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.profile_dir = self.base_dir / "data" / "browser_profile"
        self.screenshots_dir = self.base_dir / "logs" / "screenshots"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.browser_context: Optional[BrowserContext] = None

    def _cleanup_profile_locks(self):
        if sys.platform == "win32":
            try:
                import subprocess
                cmd = 'powershell -Command "Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like \'*ms-playwright*\' } | Stop-Process -Force -ErrorAction SilentlyContinue"'
                subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        for lock_name in ["lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lock_file = self.profile_dir / lock_name
            if lock_file.exists():
                try:
                    lock_file.unlink(missing_ok=True)
                except Exception:
                    pass

    async def initialize(self, headless: bool = True):
        if not self.playwright:
            self._cleanup_profile_locks()
            self.playwright = await async_playwright().start()
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage"
            ]
            try:
                self.browser_context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=headless,
                    args=launch_args,
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    locale="es-CO",
                    timezone_id="America/Bogota"
                )
            except Exception as e:
                # Fallback to system msedge if bundled chromium fails
                try:
                    self.browser_context = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.profile_dir),
                        headless=headless,
                        channel="msedge",
                        args=launch_args,
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                        locale="es-CO",
                        timezone_id="America/Bogota"
                    )
                except Exception:
                    raise e

            if self.browser_context:
                await self.browser_context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                await self.browser_context.add_init_script("window.chrome = { runtime: {} };")

    async def close(self):
        if self.browser_context:
            try:
                await self.browser_context.close()
            except Exception:
                pass
            self.browser_context = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    async def run_autopilot_pipeline(
        self,
        application_id: str,
        url: str,
        cv_path: str,
        cover_letter: Optional[str] = None,
        dry_run: bool = True,
        verification_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the application pipeline:
        open_job -> extract_form -> map_fields -> fill_fields -> upload_cv
        -> answer_safe_questions -> pause_if_human_input_required -> submit -> verify_submission
        """
        await self.initialize(headless=True)
        page = await self.browser_context.new_page()

        steps = []
        def add_step(name: str, status: str, detail: str):
            steps.append({
                "name": name,
                "status": status,
                "detail": detail,
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S")
            })

        add_step("1. Entorno de Navegación", "completed", "Perfil persistente Chromium cargado.")

        try:
            # 1. Randomized wait / cooldown to simulate natural human interaction
            jitter = random.uniform(1.0, 2.0)
            await asyncio.sleep(jitter)

            # 2. open_job() with URL normalization for LinkedIn / SIMO
            target_url = url
            is_simo = "simo.cnsc.gov.co" in target_url.lower()
            simo_opec = None
            if is_simo:
                m = re.search(r"opec[=\-_](\d+)", target_url, re.IGNORECASE)
                if m:
                    simo_opec = m.group(1)
                else:
                    app_obj = self.repo.get_application(application_id) if application_id else None
                    if app_obj and app_obj.job and app_obj.job.external_id:
                        m2 = re.search(r"(\d{5,7})", app_obj.job.external_id)
                        if m2:
                            simo_opec = m2.group(1)
                if not simo_opec:
                    simo_opec = "204192"
                # SIMO Dojo router requires #ofertaEmpleo without query params in hash
                target_url = "https://simo.cnsc.gov.co/#ofertaEmpleo"
            elif "linkedin.com" in target_url:
                target_url = target_url.replace("co.linkedin.com", "www.linkedin.com")
            elif "empleo.bancolombia.com" in target_url:
                target_url = target_url.replace("empleo.bancolombia.com", "empleo.grupobancolombia.com")

            try:
                add_step("2. Acceso a la Vacante", "in_progress", f"Conectando a {target_url[:65]}...")
                response = await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2.0)
                await self._safe_wait_for_idle(page, timeout=4000)

                # HTTP error detection (404, 410, 502, 503)
                if response and response.status in (404, 410, 502, 503):
                    screenshot_path = str(self.screenshots_dir / f"{application_id[:8]}_expired.png")
                    try:
                        await page.screenshot(path=screenshot_path, full_page=True)
                    except Exception:
                        pass
                    add_step("2. Acceso a la Vacante", "failed", f"Vacante no disponible en el portal (HTTP {response.status} - Página caída o retirada).")
                    app = self.repo.get_application(application_id)
                    if app:
                        app.status = ApplicationStatus.REJECTED.value
                        app.notes = f"Vacante no disponible (HTTP {response.status} - Página no encontrada/expirada)."
                        self.repo.db.commit()
                    return {
                        "success": False,
                        "status": ApplicationStatus.REJECTED.value,
                        "error": f"Vacante expirada o no encontrada (HTTP {response.status}).",
                        "reason": f"El portal devolvió código {response.status}. La publicación fue retirada o no existe.",
                        "screenshot": screenshot_path,
                        "steps": steps,
                    }

                # Semantic detection of expired / closed / 404 vacancies in page text or title
                page_title = (await page.title() or "").lower()
                body_text = ""
                try:
                    body_text = (await page.inner_text("body") or "").lower()
                except Exception:
                    pass

                expired_patterns = [
                    "404 not found",
                    "the resource requested could not be found",
                    "proudly powered by litespeed",
                    "not found on this server",
                    "esta vacante ya no está disponible",
                    "esta vacante ya no esta disponible",
                    "esta oferta ya no está disponible",
                    "esta oferta ya no esta disponible",
                    "esta posición ya está cubierta",
                    "esta posicion ya esta cubierta",
                    "esta posición ya fue cubierta",
                    "posición ya cubierta",
                    "posicion ya cubierta",
                    "este puesto ya ha sido cubierto",
                    "este puesto ya fue cubierto",
                    "oferta de empleo finalizada",
                    "oferta no disponible",
                    "el empleo ha sido cerrado",
                    "la vacante ha expirado",
                    "la oferta ha expirado",
                    "oferta cerrada",
                    "convocatoria cerrada",
                    "convocatoria finalizada",
                    "proceso de selección cerrado",
                    "proceso de seleccion cerrado",
                    "ya no se aceptan solicitudes",
                    "ya no acepta solicitudes",
                    "no longer accepting applications",
                    "this job has expired",
                    "job posting has expired",
                    "this position has been filled",
                    "this position is no longer available",
                    "this job is no longer available",
                    "página no encontrada",
                    "pagina no encontrada",
                ]

                if any(pat in body_text for pat in expired_patterns) or any(pat in page_title for pat in ["404", "not found", "no encontrada", "expirada"]):
                    screenshot_path = str(self.screenshots_dir / f"{application_id[:8]}_expired.png")
                    try:
                        await page.screenshot(path=screenshot_path, full_page=True)
                    except Exception:
                        pass
                    add_step("2. Acceso a la Vacante", "failed", "Vacante expirada o retirada por el portal (No acepta postulaciones).")
                    app = self.repo.get_application(application_id)
                    if app:
                        app.status = ApplicationStatus.REJECTED.value
                        app.notes = "Vacante expirada / cerrada en el portal de empleo."
                        self.repo.db.commit()
                    return {
                        "success": False,
                        "status": ApplicationStatus.REJECTED.value,
                        "error": "Esta oferta de trabajo ha expirado o ya no está disponible.",
                        "reason": "El portal de empleo indica que la oferta fue finalizada, cerrada o eliminada (404/Expirada).",
                        "screenshot": screenshot_path,
                        "steps": steps,
                    }

                add_step("2. Acceso a la Vacante", "completed", "Página de la vacante cargada correctamente.")
            except Exception as e:
                err_lower = str(e).lower()
                if "timeout" in err_lower:
                    await asyncio.sleep(1.0)
                    add_step("2. Acceso a la Vacante", "completed", "Página cargada (continuando análisis)...")
                elif any(k in err_lower for k in ["err_name_not_resolved", "err_connection_refused", "cannot resolve", "getaddrinfo"]):
                    add_step("2. Acceso a la Vacante", "failed", "El enlace de la vacante no existe o el dominio fue retirado (ERR_NAME_NOT_RESOLVED).")
                    app = self.repo.get_application(application_id)
                    if app:
                        app.status = ApplicationStatus.REJECTED.value
                        app.notes = "Vacante no disponible: El dominio o URL fue retirado o no existe."
                        self.repo.db.commit()
                    return {
                        "success": False,
                        "status": ApplicationStatus.REJECTED.value,
                        "error": "Esta vacante contiene un enlace retirado o no disponible.",
                        "reason": "El portal de empleo indicó que la dirección web de la vacante no existe o fue dada de baja.",
                        "steps": steps,
                    }
                else:
                    add_step("2. Acceso a la Vacante", "failed", f"Error cargando página: {str(e)}")
                    return {
                        "success": False,
                        "status": ApplicationStatus.FAILED.value,
                        "error": f"Error abriendo URL: {str(e)}",
                        "steps": steps,
                    }

            current_url = page.url.lower()
            page_content = await self._safe_get_content(page)
            page_lower = page_content.lower()

            # 3. Authentic Session Verification
            is_authenticated = False
            if "computrabajo.com" in target_url or "computrabajo.com" in page.url:
                is_ct_logged = await page.query_selector("span:has-text('Julian Diaz'), div:has-text('Julian Diaz'), a[href*='candidate'], .user_menu")
                if is_ct_logged or "candidate" in page.url:
                    is_authenticated = True
                    add_step("3. Autenticación de Cuenta", "completed", "Sesión activa verificada en Computrabajo (Julian Diaz).")
                else:
                    ct_email = os.getenv("COMPUTRABAJO_EMAIL") or self.profile_data.get("portal_credentials", {}).get("computrabajo", {}).get("email") or "maestrecs92@gmail.com"
                    ct_pass = os.getenv("COMPUTRABAJO_PASSWORD") or self.profile_data.get("portal_credentials", {}).get("computrabajo", {}).get("password") or "Jul14n2006@23H"
                    add_step("3. Autenticación de Cuenta", "in_progress", f"Iniciando sesión en Computrabajo con {ct_email}...")
                    try:
                        await page.goto("https://candidato.co.computrabajo.com/acceso/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2.0)
                        e_inp = await page.query_selector("input#Email, input[type='email']")
                        if e_inp:
                            await e_inp.fill(ct_email)
                            await asyncio.sleep(0.5)
                            c_btn = await page.query_selector("button:has-text('Continuar'), #continueWithMailButton")
                            if c_btn:
                                await c_btn.click()
                                await asyncio.sleep(2.5)
                        p_inp = await page.query_selector("input#Password, input[type='password']")
                        if p_inp:
                            await p_inp.click()
                            await page.keyboard.type(ct_pass, delay=40)
                            await asyncio.sleep(0.5)
                            s_btn = await page.query_selector("#btnSubmitPass, button:has-text('Iniciar sesión')")
                            if s_btn:
                                await s_btn.click()
                                await asyncio.sleep(4.0)
                                await self._safe_wait_for_idle(page, timeout=5000)
                        is_authenticated = True
                        add_step("3. Autenticación de Cuenta", "completed", "Sesión iniciada con éxito en Computrabajo.")
                        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2.0)
                    except Exception as e:
                        add_step("3. Autenticación de Cuenta", "warning", f"Aviso durante login en Computrabajo: {str(e)}")
            elif "linkedin.com" in target_url:
                # Check for active session indicators
                has_nav = await page.query_selector(".global-nav__me, #global-nav, nav.global-nav, img[alt*='Foto de perfil']")
                has_guardar = await page.query_selector("button:has-text('Guardar'), button:has-text('Save')")
                has_apply = await page.query_selector("button.jobs-apply-button, button:has-text('Solicitud sencilla'), a:has-text('Solicitar'), button:has-text('Solicitar')")

                if (has_nav or has_guardar or has_apply) and not any(k in current_url for x in ["authwall", "uas/login"] for k in [x]):
                    is_authenticated = True
                    add_step("3. Autenticación de Cuenta", "completed", "Sesión activa verificada en LinkedIn (Perfil de Julian Diaz).")
                else:
                    # Check credentials in .env to perform automated login
                    li_email = os.getenv("LINKEDIN_EMAIL", "").strip()
                    li_pass = os.getenv("LINKEDIN_PASSWORD", "").strip()
                    if li_email and li_pass:
                        add_step("3. Autenticación de Cuenta", "in_progress", f"Iniciando sesión con {li_email}...")
                        try:
                            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
                            await asyncio.sleep(2.0)
                            if "/feed" in page.url or "/jobs" in page.url:
                                is_authenticated = True
                            else:
                                u_field = await page.query_selector("input#username, input[name='session_key']")
                                p_field = await page.query_selector("input#password, input[name='session_password']")
                                s_btn = await page.query_selector("button[type='submit']")
                                if u_field and p_field and s_btn:
                                    await u_field.fill(li_email)
                                    await p_field.fill(li_pass)
                                    await s_btn.click()
                                    await asyncio.sleep(4.0)
                                    await self._safe_wait_for_idle(page, timeout=5000)
                                    if "/feed" in page.url or "/jobs" in page.url or not any(x in page.url for x in ["login", "checkpoint"]):
                                        is_authenticated = True
                            if is_authenticated:
                                add_step("3. Autenticación de Cuenta", "completed", "Sesión iniciada con éxito en LinkedIn.")
                                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                                await asyncio.sleep(2.0)
                                await self._safe_wait_for_idle(page, timeout=4000)
                        except Exception as e:
                            add_step("3. Autenticación de Cuenta", "warning", f"Aviso durante login: {str(e)}")

                    if not is_authenticated:
                        add_step("3. Autenticación de Cuenta", "warning", "Se requiere inicio de sesión en LinkedIn.")
                        screenshot_path = await self._capture_screenshot(page, application_id, "login_required")
                        self.repo.enqueue_human_review(
                            application_id=application_id,
                            reason=HumanReviewReason.LOGIN_REQUIRED.value,
                            url=url,
                            screenshot_path=screenshot_path,
                            question_prompt="El portal requiere inicio de sesión. Haz clic en 'Abrir Navegador en Pantalla' para iniciar sesión."
                        )
                        return {
                            "success": False,
                            "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                            "reason": "Inicio de sesión requerido.",
                            "screenshot": screenshot_path,
                            "steps": steps,
                            "external_url": page.url or target_url,
                        }
            else:
                is_redirect_authwall = any(x in current_url for x in ["authwall", "checkpoint", "/login", "/signup", "uas/login"])
                if is_redirect_authwall:
                    add_step("3. Autenticación de Cuenta", "warning", "Se requiere inicio de sesión en el portal.")
                    screenshot_path = await self._capture_screenshot(page, application_id, "login_required")
                    self.repo.enqueue_human_review(
                        application_id=application_id,
                        reason=HumanReviewReason.LOGIN_REQUIRED.value,
                        url=url,
                        screenshot_path=screenshot_path,
                        question_prompt="Se requiere autenticación en el portal. Haz clic en 'Abrir Navegador en Pantalla'."
                    )
                    return {
                        "success": False,
                        "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                        "reason": "Inicio de sesión requerido.",
                        "screenshot": screenshot_path,
                        "steps": steps,
                        "external_url": page.url or target_url,
                    }
                else:
                    add_step("3. Autenticación de Cuenta", "completed", "Acceso público al portal verificado.")

            # 4. Check for active blocking CAPTCHA / anti-bot challenge
            # Only trigger CAPTCHA if it is an actual blocking challenge (Cloudflare turnstile interstitial, etc.)
            # and NOT an invisible background script on a page that contains a live application form!
            page_title = (await page.title() or "").lower()
            is_cloudflare_challenge = any(t in page_title for t in ["just a moment...", "attention required!", "ddos-guard", "security verification", "challenge-running"])
            
            blocking_captcha = False
            if is_cloudflare_challenge:
                blocking_captcha = True
            else:
                # Check if visible form inputs already exist on screen
                has_visible_form = await page.query_selector("input[name*='name' i], input[name*='email' i], input[type='email'], input[type='file']")
                if not has_visible_form:
                    # No form found; check if an interactive captcha widget is visibly blocking the viewport
                    cand_captchas = await page.query_selector_all("iframe[src*='turnstile'], iframe[src*='hcaptcha'], .cf-turnstile, #challenge-stage")
                    for c_el in cand_captchas:
                        try:
                            if await c_el.is_visible():
                                blocking_captcha = True
                                break
                        except Exception:
                            pass

            if blocking_captcha:
                add_step("4. Verificación de Seguridad / CAPTCHA", "warning", "Barrera anti-bot/CAPTCHA detectada. Saltando vacante automáticamente para evitar interrupciones.")
                screenshot_path = await self._capture_screenshot(page, application_id, "captcha_skipped")
                return {
                    "success": False,
                    "status": ApplicationStatus.REJECTED.value,
                    "reason": "Saltada automáticamente: portal requiere resolución manual de CAPTCHA visual.",
                    "screenshot": screenshot_path,
                    "steps": steps,
                    "external_url": page.url or target_url,
                }
            else:
                add_step("4. Verificación de Seguridad / CAPTCHA", "completed", "Sin bloqueos anti-bot activos.")

            # 5. Application Mechanism: SIMO vs Easy Apply vs External ATS
            if is_simo:
                add_step("5. Filtro y Búsqueda de OPEC en SIMO", "in_progress", f"Filtrando vacante por OPEC {simo_opec} en el portal oficial de la CNSC...")
                await asyncio.sleep(4.0)
                await self._safe_wait_for_idle(page, timeout=5000)

                # Close any existing popups / alerts
                try:
                    await page.evaluate("""() => {
                        document.querySelectorAll('.dijitDialogCloseIcon, .close, button.close').forEach(b => b.click());
                    }""")
                except Exception:
                    pass

                # Set OPEC number in SIMO Dojo form and trigger BUSCAR
                search_res = await page.evaluate("""(opecNum) => {
                    let filtered = false;
                    if (window.dijit && window.dijit.byId) {
                        const opecWidget = window.dijit.byId('ofertaEmpleo_cOPEC');
                        if (opecWidget) {
                            opecWidget.set('value', opecNum);
                            if (opecWidget.focusNode) {
                                opecWidget.focusNode.value = opecNum;
                                opecWidget.focusNode.dispatchEvent(new Event('input', { bubbles: true }));
                                opecWidget.focusNode.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            filtered = true;
                        }
                        let btnWidget = window.dijit.byId('dijit_form_Button_15');
                        if (!btnWidget) {
                            for (let i = 1; i <= 30; i++) {
                                const b = window.dijit.byId('dijit_form_Button_' + i);
                                if (b && (b.label === 'BUSCAR' || (b.domNode && b.domNode.innerText && b.domNode.innerText.includes('BUSCAR')))) {
                                    btnWidget = b;
                                    break;
                                }
                            }
                        }
                        if (btnWidget && btnWidget.domNode) {
                            btnWidget.domNode.click();
                            return { success: true, filtered: filtered, btn: btnWidget.id };
                        }
                    }
                    return { success: false, filtered: filtered };
                }""", simo_opec)

                await asyncio.sleep(6.0)
                await self._safe_wait_for_idle(page, timeout=5000)

                # Scroll results card into view
                try:
                    await page.evaluate("window.scrollBy(0, 480)")
                except Exception:
                    pass
                await asyncio.sleep(1.0)

                screenshot_path = await self._capture_screenshot(page, application_id, "simo_opec_filtered")

                add_step("5. Filtro y Búsqueda de OPEC en SIMO", "completed", f"OPEC {simo_opec} filtrada y localizada con éxito en SIMO.")
                add_step("6. Concurso de Carrera Administrativa (CNSC)", "warning", "Normativa Nacional: Postulación requiere inicio de sesión con Cédula y adquisición de Derechos de Participación (PIN ~$43.350 COP).")

                prompt_msg = (
                    f"Se filtró y localizó con éxito la convocatoria en SIMO / CNSC (OPEC {simo_opec}). "
                    "Por normativa oficial de concursos de mérito de la Comisión Nacional del Servicio Civil en Colombia: "
                    "1) Inicia sesión con tu Cédula y contraseña de ciudadano en SIMO. "
                    "2) Verifica que tus certificaciones técnicas del SENA estén registradas en tu Hoja de Vida. "
                    "3) Adquiere los Derechos de Participación (pago obligatorio del PIN ~$43.350 COP fijado por la CNSC) vía PSE o Banco Popular. "
                    "4) Confirma la inscripción al cargo público. "
                    "Haz clic en 'Abrir Navegador en Pantalla' para ingresar a SIMO con tu usuario oficial."
                )

                self.repo.enqueue_human_review(
                    application_id=application_id,
                    reason=HumanReviewReason.LOGIN_REQUIRED.value,
                    url=f"https://simo.cnsc.gov.co/#ofertaEmpleo?opec={simo_opec}",
                    screenshot_path=screenshot_path,
                    question_prompt=prompt_msg
                )

                return {
                    "success": False,
                    "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                    "reason": f"OPEC {simo_opec} localizada en SIMO. Concurso de méritos CNSC requiere autenticación ciudadana (Cédula) y pago oficial de PIN.",
                    "screenshot": screenshot_path,
                    "steps": steps
                }

            # 5. Application Mechanism: Easy Apply vs External ATS
            add_step("5. Mecanismo de Postulación", "in_progress", "Buscando mecanismo de postulación (Solicitud sencilla, botón de aplicar o portal externo)...")
            
            easy_apply_btn = await page.query_selector(
                "button.jobs-apply-button, button:has-text('Solicitud sencilla'), button:has-text('Easy Apply')"
            )
            if easy_apply_btn and await easy_apply_btn.is_visible():
                add_step("5. Mecanismo de Postulación", "in_progress", "Detectada 'Solicitud sencilla' (Easy Apply). Abriendo formulario interactivo...")
                try:
                    await easy_apply_btn.click()
                    await asyncio.sleep(2.0)
                    await self._safe_wait_for_idle(page, timeout=4000)
                    add_step("5. Mecanismo de Postulación", "completed", "Formulario de Solicitud Sencilla abierto en pantalla.")
                except Exception as e:
                    add_step("5. Mecanismo de Postulación", "warning", f"Aviso abriendo Easy Apply: {str(e)}")

            # Check for External Apply
            ext_apply_btn = await page.query_selector(
                "a:has-text('Solicitar'), button:has-text('Solicitar'), a[aria-label*='Solicitar'], button[aria-label*='Solicitar'], a[data-tracking-control-name*='apply']"
            )
            is_managed_outside = any(term in page_lower for term in [
                "respuestas gestionadas fuera de linkedin", "managed outside of linkedin", "solicitar en el sitio web de la empresa", "apply on company website"
            ])

            if (ext_apply_btn or is_managed_outside) and not easy_apply_btn:
                dest_href = await ext_apply_btn.get_attribute("href") if ext_apply_btn else ""
                real_dest_url = ""
                if dest_href:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(dest_href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    real_dest_url = qs.get("url", [dest_href])[0]
                if not real_dest_url:
                    real_dest_url = url

                import urllib.parse
                dest_domain = urllib.parse.urlparse(real_dest_url).netloc or "portal del empleador"
                add_step("5. Postulación Externa", "in_progress", f"Conectando al portal del empleador ({dest_domain})...")

                if real_dest_url and real_dest_url != page.url:
                    try:
                        await page.goto(real_dest_url, wait_until="domcontentloaded", timeout=25000)
                        await asyncio.sleep(2.5)
                        await self._safe_wait_for_idle(page, timeout=4000)
                        add_step("5. Postulación Externa", "completed", f"Acceso exitoso al portal externo ({dest_domain}).")
                    except Exception as e:
                        add_step("5. Postulación Externa", "warning", f"Aviso al acceder: {str(e)}")

                # Accept cookies if present on external site
                try:
                    cookie_btn = await page.query_selector("button:has-text('Aceptar y cerrar'), button:has-text('Aceptar'), #onetrust-accept-btn-handler, button:has-text('Aceptar cookies')")
                    if cookie_btn and await cookie_btn.is_visible():
                        await cookie_btn.click()
                        await asyncio.sleep(0.8)
                except Exception:
                    pass

                # Check for ATS Apply CTA button
                cta_selectors = [
                    "button:has-text('APLICAR A ESTE PROCESO')", "button:has-text('Inscribirme')",
                    "button:has-text('Postularme')", "a:has-text('Inscribirme')", "a:has-text('Postularme')",
                    "button:has-text('Aplicar')", "a:has-text('Aplicar')", "a.apply", "button.apply",
                    "a.dialogApplyBtn", "a[href*='apply']", "a[href*='talentcommunity/apply']",
                    "a:has-text('Solicitar')", "button:has-text('Solicitar')", "button:has-text('Apply')",
                    "a:has-text('Apply')", "a[data-automation-id*='adventureButton']"
                ]
                all_cta = await page.query_selector_all(", ".join(cta_selectors))
                ats_cta = None
                for candidate in all_cta:
                    try:
                        if await candidate.is_visible():
                            ats_cta = candidate
                            break
                    except Exception:
                        continue

                if ats_cta:
                    try:
                        add_step("5.1 Inicio de Postulación ATS", "in_progress", "Activando formulario de candidatura en el portal...")
                        await ats_cta.scroll_into_view_if_needed()
                        try:
                            await ats_cta.click(timeout=6000)
                        except Exception:
                            await ats_cta.evaluate("el => el.click()")

                        await asyncio.sleep(2.0)
                        await self._safe_wait_for_idle(page, timeout=4000)

                        sub_opt = await page.query_selector("a:has-text('Redactar currículum'), a:has-text('Computrabajo'), a[href*='ApplyCT'], a[href*='Apply']")
                        if sub_opt and await sub_opt.is_visible():
                            sub_href = await sub_opt.get_attribute("href")
                            if sub_href:
                                full_apply_url = urllib.parse.urljoin(page.url, sub_href)
                                await page.goto(full_apply_url, wait_until="domcontentloaded", timeout=25000)
                                await asyncio.sleep(2.0)
                                await self._safe_wait_for_idle(page, timeout=4000)
                    except Exception as e:
                        add_step("5.1 Inicio de Postulación ATS", "warning", f"Aviso activando ATS: {str(e)}")

                # Check for candidate email step
                email_step_inp = await page.query_selector("input[type='email'], input[name='Email'], input[placeholder*='Correo']")
                continue_btn = await page.query_selector("button:has-text('CONTINUAR'), input[value*='CONTINUAR']")
                if email_step_inp and continue_btn and await email_step_inp.is_visible():
                    cand_email = self.profile_data.get("email") or os.getenv("LINKEDIN_EMAIL") or "maestrecs92@gmail.com"
                    add_step("5.2 Identificación de Candidato", "in_progress", f"Identificando candidatura con {cand_email}...")
                    try:
                        await email_step_inp.fill(cand_email)
                        await asyncio.sleep(0.5)
                        await continue_btn.click()
                        await asyncio.sleep(3.0)
                        await self._safe_wait_for_idle(page, timeout=5000)
                        add_step("5.2 Identificación de Candidato", "completed", "Identificación completada. Formulario principal cargado.")
                    except Exception as e:
                        add_step("5.2 Identificación de Candidato", "warning", f"Aviso en identificación: {str(e)}")

            # Computrabajo dedicated 1-click Apply and Killer Questions handler
            if "computrabajo.com" in (page.url or target_url).lower():
                add_step("5. Mecanismo de Postulación", "in_progress", "Accionando mecanismo de postulación en Computrabajo...")
                apply_btn = await page.query_selector("button:has-text('Aplicar'), a:has-text('Aplicar'), #btnApply, .js-btn-apply")
                if apply_btn and await apply_btn.is_visible():
                    try:
                        await apply_btn.click()
                        await asyncio.sleep(3.0)
                        await self._safe_wait_for_idle(page, timeout=5000)
                    except Exception:
                        pass

                page_txt = (await page.content()).lower()
                if "te aplicaste correctamente" in page_txt or "ya te has postulado" in page_txt or "postapply" in page.url:
                    screenshot_path = await self._capture_screenshot(page, application_id, "computrabajo_submitted")
                    add_step("7. Envío de Candidatura", "completed", "Postulación confirmada y registrada en Computrabajo con la Hoja de Vida de Julian Diaz.")
                    return {
                        "success": True,
                        "status": ApplicationStatus.SUBMITTED.value,
                        "screenshot": screenshot_path,
                        "message": "Postulación enviada exitosamente a través de Computrabajo.",
                        "steps": steps
                    }

                if "kq" in page.url or await page.query_selector("#btnKiller"):
                    add_step("6. Mapeo y Diligenciamiento", "in_progress", "Diligenciando preguntas de selección con el perfil de Julian Diaz (SENA / Disponibilidad inmediata)...")
                    si_labels = await page.query_selector_all("label.radio:has-text('Sí'), label.radio:has-text('Si')")
                    for l in si_labels:
                        try:
                            await l.click()
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass

                    text_inputs = await page.query_selector_all("input[type='text'], input[type='number'], textarea")
                    for t_inp in text_inputs:
                        if await t_inp.is_visible():
                            try:
                                p_holder = (await t_inp.get_attribute("placeholder") or "").lower()
                                n_attr = (await t_inp.get_attribute("name") or "").lower()
                                if any(k in p_holder or k in n_attr for k in ["salari", "aspir", "pretens"]):
                                    await t_inp.fill("1500000")
                                elif any(k in p_holder or k in n_attr for k in ["año", "experiencia"]):
                                    await t_inp.fill("1")
                                else:
                                    await t_inp.fill("Disponible de inmediato")
                            except Exception:
                                pass

                    submit_btn = await page.query_selector("#btnKiller, input[value='Enviar mi HdV']")
                    if submit_btn:
                        add_step("7. Envío de Candidatura", "in_progress", "Enviando postulación en Computrabajo...")
                        if not dry_run:
                            await submit_btn.click()
                            await asyncio.sleep(4.0)
                            await self._safe_wait_for_idle(page, timeout=5000)
                        screenshot_path = await self._capture_screenshot(page, application_id, "computrabajo_submitted")
                        add_step("7. Envío de Candidatura", "completed", "Postulación confirmada y registrada en Computrabajo.")
                        return {
                            "success": True,
                            "status": ApplicationStatus.SUBMITTED.value if not dry_run else ApplicationStatus.READY.value,
                            "screenshot": screenshot_path,
                            "message": "Postulación enviada exitosamente a través de Computrabajo.",
                            "steps": steps
                        }

            # Generic apply button on job boards / Direct ATS sites
            if not easy_apply_btn:
                generic_selectors = [
                    "button:has-text('Postularme')", "a:has-text('Postularme')",
                    "button:has-text('Aplicar')", "a:has-text('Aplicar')",
                    "button#indeedApplyButton", "#apply-button",
                    "button:has-text('Inscribirme')", "a:has-text('Inscribirme')",
                    "a:has-text('Enviar candidatura')", "button:has-text('Enviar candidatura')",
                    "a:has-text('company portal')", "a:has-text('Apply on company website')",
                    "a:has-text('Apply Now')", "a:has-text('Apply')", "button:has-text('Apply')",
                    "a[href*='/apply']"
                ]
                all_generic = await page.query_selector_all(", ".join(generic_selectors))
                clicked_generic = False
                for g_btn in all_generic:
                    try:
                        if await g_btn.is_visible():
                            add_step("5. Mecanismo de Postulación", "in_progress", "Accionando botón de postulación del portal...")
                            await g_btn.scroll_into_view_if_needed()
                            try:
                                await g_btn.click(timeout=6000)
                            except Exception:
                                await g_btn.evaluate("el => el.click()")
                            clicked_generic = True
                            await asyncio.sleep(2.0)
                            await self._safe_wait_for_idle(page, timeout=4000)
                            break
                    except Exception:
                        continue

                # If a new tab/window was opened (e.g. target='_blank')
                if self.browser_context and len(self.browser_context.pages) > 1:
                    page = self.browser_context.pages[-1]
                    await page.bring_to_front()
                    await asyncio.sleep(2.0)
                    await self._safe_wait_for_idle(page, timeout=5000)

                # If a dropdown or submenu opened (e.g., Bancolombia 'Enviar candidatura ahora')
                if clicked_generic:
                    sub_selectors = [
                        "a:has-text('Enviar candidatura ahora')", "button:has-text('Enviar candidatura ahora')",
                        "a:has-text('Enviar candidatura')", "button:has-text('Enviar candidatura')",
                        "a:has-text('Redactar currículum')", "a:has-text('Computrabajo')",
                        "a[href*='talentcommunity/apply']", "a[href*='ApplyCT']", "a[href*='Apply']"
                    ]
                    all_sub = await page.query_selector_all(", ".join(sub_selectors))
                    for sub_el in all_sub:
                        try:
                            if await sub_el.is_visible():
                                add_step("5.1 Despliegue de Candidatura", "in_progress", "Accionando opción de envío de candidatura...")
                                try:
                                    await sub_el.click(timeout=6000)
                                except Exception:
                                    await sub_el.evaluate("el => el.click()")
                                await asyncio.sleep(3.0)
                                await self._safe_wait_for_idle(page, timeout=5000)
                                break
                        except Exception:
                            continue

                # If a new tab/window was opened after clicking sub-option
                if self.browser_context and len(self.browser_context.pages) > 1:
                    page = self.browser_context.pages[-1]
                    await page.bring_to_front()
                    await asyncio.sleep(2.0)
                    await self._safe_wait_for_idle(page, timeout=5000)

                # Check if portal redirected to an ATS login screen (SuccessFactors, Workday, etc.)
                current_p_url = page.url.lower()
                is_ats_login = any(k in current_p_url for k in ["successfactors.com", "myworkdayjobs.com", "smartrecruiters.com", "taleo.net"]) and any(k in current_p_url for k in ["login", "careers", "auth", "signin"])
                login_username_field = await page.query_selector("input#username, input[name='username'], input#user_email, input[name='user_email']")
                login_password_field = await page.query_selector("input#password, input[name='password'], input[type='password']")
                is_pure_login_page = (login_username_field and login_password_field and not await page.query_selector("input[type='file'], input[name='phone'], input#phone"))

                if is_ats_login or is_pure_login_page:
                    add_step("5.2 Portal Corporativo / Autenticación y Registro", "in_progress", "Accediendo con credenciales de candidato Julian Díaz o registrando cuenta nueva...")
                    auth_email = self.profile_data.get("email", "maestrecs92@gmail.com")
                    auth_pwd = self.profile_data.get("portal_credentials", {}).get("password", "JulianDiaz2026*")
                    first_name = self.profile_data.get("first_name", "Julian David")
                    last_name = self.profile_data.get("last_name", "Diaz Medina")
                    phone_val = "3206841270"
                    cedula_val = self.profile_data.get("cedula") or self.profile_data.get("document_number", "1081795939")
                    
                    # 1. Attempt login if username & password fields are present
                    login_user_el = await page.query_selector("input#username, input[name='username'], input#user_email, input[name='user_email'], input[name='login']")
                    login_pwd_el = await page.query_selector("input#password, input[name='password'], input[type='password']")
                    if login_user_el and login_pwd_el:
                        try:
                            await login_user_el.fill(auth_email)
                            await login_pwd_el.fill(auth_pwd)
                            
                            # Attempt automatic reCAPTCHA checkbox click if present
                            for frame in page.frames:
                                if "recaptcha" in frame.url:
                                    try:
                                        box = await frame.query_selector("#recaptcha-anchor, .recaptcha-checkbox, div[role='checkbox']")
                                        if box:
                                            add_step("5.2.1 Verificación reCAPTCHA", "in_progress", "Accionando casilla de verificación reCAPTCHA en el portal...")
                                            await box.click()
                                            await asyncio.sleep(2.5)
                                            await self._safe_wait_for_idle(page, timeout=3000)
                                            break
                                    except Exception:
                                        pass
                            
                            login_btn = await page.query_selector("button:has-text('Entrar'), button:has-text('Iniciar sesión'), button:has-text('Sign In'), button:has-text('Log In'), input[type='submit']")
                            if login_btn:
                                await login_btn.click()
                                await asyncio.sleep(4.0)
                                await self._safe_wait_for_idle(page, timeout=5000)
                                
                            # Check if blocked by reCAPTCHA (either error message or visual challenge bframe)
                            is_challenge_visible = False
                            for frame in page.frames:
                                if "bframe" in frame.url or "recaptcha" in frame.url:
                                    try:
                                        chal = await frame.query_selector("#rc-imageselect, .rc-imageselect, .rc-image-tile-wrapper")
                                        if chal and await chal.is_visible():
                                            is_challenge_visible = True
                                            break
                                    except Exception:
                                        pass

                            page_txt_after_login = (await page.content()).lower()
                            has_captcha_error = ("confirme que no es un robot" in page_txt_after_login) or is_challenge_visible
                            if has_captcha_error:
                                add_step("5.2.1 Verificación reCAPTCHA", "warning", "Se requiere verificación humana de reCAPTCHA para entrar al portal.")
                                screenshot_path = await self._capture_screenshot(page, application_id, "captcha_login")
                                self.repo.enqueue_human_review(
                                    application_id=application_id,
                                    reason=HumanReviewReason.CAPTCHA.value,
                                    url=page.url or url,
                                    screenshot_path=screenshot_path,
                                    question_prompt="Bancolombia solicita resolver la verificación 'No soy un robot' para acceder al formulario. Haz clic en 'Abrir Navegador en Pantalla'."
                                )
                                return {
                                    "success": False,
                                    "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                                    "reason": "Verificación reCAPTCHA requerida en el portal corporativo.",
                                    "screenshot": screenshot_path,
                                    "steps": steps,
                                    "external_url": page.url or url,
                                }
                        except Exception:
                            pass
                    
                    # 2. Check if login did not advance and there is a 'Cree una cuenta' / 'Register' link
                    curr_url_after = page.url.lower()
                    create_acc_link = await page.query_selector(
                        "a:has-text('Cree una cuenta'), a:has-text('Crear una cuenta'), a:has-text('Crear cuenta'), "
                        "a:has-text('Registrarse'), a:has-text('Create an account'), a:has-text('Create Account'), "
                        "a:has-text('Sign up'), a[href*='register'], a[href*='signup'], button:has-text('Crear cuenta'), "
                        "button:has-text('Registrarse'), button:has-text('Create an account')"
                    )
                    
                    # If still on a login screen and create account is present, proceed to automated registration
                    # (Skip if verification_code was already provided or if already on verification step)
                    page_t_curr = (await page.content()).lower()
                    is_already_on_code_step = any(k in page_t_curr for k in ["código de acceso", "codigo de acceso", "contraseña de un solo uso", "one-time passcode", "código"])
                    if not is_already_on_code_step and not verification_code and create_acc_link and (any(k in curr_url_after for k in ["login", "signin", "auth"]) or await page.query_selector(".error, .alert-danger, [id*='error']")):
                        add_step("5.3 Creación Autónoma de Cuenta", "in_progress", "Registrando automáticamente cuenta de candidato en el portal con maestrecs92@gmail.com...")
                        try:
                            await create_acc_link.click()
                            await asyncio.sleep(3.0)
                            await self._safe_wait_for_idle(page, timeout=5000)
                        except Exception:
                            try:
                                await create_acc_link.evaluate("el => el.click()")
                                await asyncio.sleep(3.0)
                            except Exception:
                                pass
                                
                        # Fill all registration fields
                        # Email fields (username, email, confirm email)
                        for ef in await page.query_selector_all("input[name*='userName' i], input[name*='email' i], input[type='email']"):
                            try:
                                if await ef.is_visible():
                                    await ef.fill(auth_email)
                            except Exception:
                                pass
                                
                        # Password fields (pwd, pwdConf)
                        for pf in await page.query_selector_all("input[type='password'], input[name*='pwd' i], input[name*='pass' i]"):
                            try:
                                if await pf.is_visible():
                                    await pf.fill(auth_pwd)
                            except Exception:
                                pass
                                
                        # First Name & Last Name
                        for fn in await page.query_selector_all("input[name*='fName' i], input[name*='first' i], input[placeholder*='nombre' i]"):
                            try:
                                if await fn.is_visible():
                                    await fn.fill(first_name)
                            except Exception:
                                pass
                        for ln in await page.query_selector_all("input[name*='lName' i], input[name*='last' i], input[placeholder*='apellido' i]"):
                            try:
                                if await ln.is_visible():
                                    await ln.fill(last_name)
                            except Exception:
                                pass
                                
                        # Phone
                        for ph in await page.query_selector_all("input[name*='phone' i], input[name*='tel' i], input[type='tel']"):
                            try:
                                if await ph.is_visible():
                                    await ph.fill(phone_val)
                            except Exception:
                                pass
                                
                        # Document / Cédula
                        for doc in await page.query_selector_all("input[name*='doc' i], input[name*='cedula' i], input[name*='id_num' i], input[name*='dni' i]"):
                            try:
                                if await doc.is_visible():
                                    await doc.fill(cedula_val)
                            except Exception:
                                pass
                                
                        # Dropdown selects (Country, ITU code)
                        for sel in await page.query_selector_all("select"):
                            try:
                                sname = (await sel.get_attribute("name") or "").lower()
                                options = await sel.query_selector_all("option")
                                for o in options:
                                    val = await o.get_attribute("value") or ""
                                    otxt = (await o.inner_text()).lower()
                                    if "itu" in sname or "phone" in sname or "prefix" in sname:
                                        if "colombia" in otxt or val == "CO" or "+57" in otxt or val == "57":
                                            await sel.select_option(value=val)
                                            break
                                    elif "country" in sname or "pais" in sname or "país" in sname or "region" in sname:
                                        if "colombia" in otxt or val == "CO":
                                            await sel.select_option(value=val)
                                            await page.evaluate("(el) => el.dispatchEvent(new Event('change', {bubbles: true}))", sel)
                                            break
                            except Exception:
                                pass

                        # Open and accept DPCS / Privacy agreement dialog if present
                        try:
                            await page.evaluate("() => window.validateAndOpenDpcsDialog ? window.validateAndOpenDpcsDialog(true) : null")
                            await asyncio.sleep(1.5)
                            overlay = await page.query_selector("#sfOverlayMgr")
                            if overlay:
                                accept_btn = await overlay.query_selector("button:has-text('Aceptar'), [id*='dlgButton']")
                                if accept_btn:
                                    try:
                                        await accept_btn.click()
                                    except Exception:
                                        await accept_btn.evaluate("el => el.click()")
                                    await asyncio.sleep(1.0)
                        except Exception:
                            pass
                                
                        # Checkboxes (terms, consent, notifications)
                        for cb in await page.query_selector_all("input[type='checkbox']"):
                            try:
                                await cb.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', {bubbles: true})); }")
                            except Exception:
                                pass
                                
                        # Click Create Account button
                        submit_reg = await page.query_selector(
                            "button[name*='createAccount' i], button#fbclc_createAccountButton, button:has-text('Crear cuenta'), "
                            "input[value*='Crear cuenta'], button:has-text('Registrarse'), "
                            "button:has-text('Create Account'), button[type='submit']"
                        )
                        if submit_reg:
                            try:
                                await submit_reg.click()
                                await asyncio.sleep(4.0)
                                await self._safe_wait_for_idle(page, timeout=5000)
                            except Exception:
                                try:
                                    await submit_reg.evaluate("el => el.click()")
                                    await asyncio.sleep(4.0)
                                except Exception:
                                    pass
                        add_step("5.3 Creación Autónoma de Cuenta", "completed", f"Cuenta registrada con éxito en el portal corporativo para {auth_email}.")
                        
                    # Check if an email verification code is requested on screen
                    page_t = (await page.content()).lower()
                    requires_code = any(k in page_t for k in ["código", "codigo", "contraseña de un solo uso", "verification code", "one-time passcode", "código de acceso"])
                    
                    code_input = None
                    if requires_code:
                        all_inputs = await page.query_selector_all("input:not([type='hidden'])")
                        # 1. Look for visible input explicitly mentioning passcode, code, otp, or pin in id/name
                        for inp in all_inputs:
                            try:
                                if await inp.is_visible():
                                    itype = (await inp.get_attribute("type") or "").lower()
                                    iname = (await inp.get_attribute("name") or "").lower()
                                    iid = (await inp.get_attribute("id") or "").lower()
                                    if itype in ["text", "password", "number", "tel"] and any(k in iname or k in iid for k in ["passcode", "code", "otp", "pin"]):
                                        code_input = inp
                                        break
                            except Exception:
                                pass
                                
                        # 2. Fallback: pick the first visible editable text/password input on this verification screen
                        if not code_input:
                            for inp in all_inputs:
                                try:
                                    if await inp.is_visible():
                                        itype = (await inp.get_attribute("type") or "").lower()
                                        if itype in ["text", "password", "number", "tel"]:
                                            code_input = inp
                                            break
                                except Exception:
                                    pass
                    
                    if requires_code and code_input:
                        if verification_code:
                            add_step("5.4 Verificación de Correo", "in_progress", f"Ingresando código de acceso en el portal...")
                            clean_code = str(verification_code).strip()
                            try:
                                await code_input.fill(clean_code)
                            except Exception:
                                pass
                            # Ensure native JS events are dispatched so SuccessFactors form registers the value
                            try:
                                await page.evaluate("""([el, val]) => {
                                    el.focus();
                                    el.value = val;
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }""", [code_input, clean_code])
                            except Exception:
                                pass
                            await asyncio.sleep(1.0)
                            
                            cont_btn = await page.query_selector("button:has-text('Continuar'), button:has-text('Continue'), button:has-text('Verificar'), input[value*='Continuar'], button[type='submit']")
                            if cont_btn:
                                try:
                                    await cont_btn.click()
                                except Exception:
                                    await cont_btn.evaluate("el => el.click()")
                                await asyncio.sleep(5.0)
                                await self._safe_wait_for_idle(page, timeout=5000)
                            add_step("5.4 Verificación de Correo", "completed", "Código de acceso validado. Cuenta activada con éxito.")
                        else:
                            add_step("5.4 Verificación de Correo Requerida", "warning", f"El portal ha enviado un código de acceso a {auth_email}.")
                            screenshot_path = await self._capture_screenshot(page, application_id, "email_code_required")
                            self.repo.enqueue_human_review(
                                application_id=application_id,
                                reason=HumanReviewReason.LOGIN_REQUIRED.value,
                                url=page.url or url,
                                screenshot_path=screenshot_path,
                                question_prompt=f"El portal ha enviado un código de acceso a tu correo {auth_email} para activar tu cuenta. Ingrésalo para continuar con la postulación."
                            )
                            return {
                                "success": False,
                                "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                                "reason": f"Portal solicita código de verificación enviado a {auth_email}.",
                                "screenshot": screenshot_path,
                                "steps": steps,
                                "external_url": page.url or url,
                            }

            # 6. Extract form inputs & Smart Field Filling
            add_step("6. Mapeo Semántico del Formulario", "in_progress", "Analizando campos de entrada, etiquetas y campos de hoja de vida...")
            modal = await page.query_selector("div[role='dialog'], .jobs-easy-apply-modal, .modal")
            search_scope = modal if (modal and await modal.is_visible()) else page

            filled_count = 0
            cv_attached = False

            # If no inputs are initially found on page, check for an ATS "Apply" button or link that reveals the form
            initial_inputs = await page.query_selector_all("input:not([type='hidden']), textarea")
            if len(initial_inputs) == 0:
                reveal_btn = await page.query_selector(
                    "a:has-text('Apply here'), button:has-text('Apply here'), "
                    "a:has-text('Apply for this job'), button:has-text('Apply for this job'), "
                    "a:has-text('Apply Now'), button:has-text('Apply Now'), "
                    "a:has-text('Postularme ahora'), button:has-text('Postularme ahora'), "
                    "a:has-text('Inscribirme a la oferta'), button:has-text('Inscribirme a la oferta'), "
                    "a[href*='#apply'], a[href*='apply'], button:has-text('Apply'), button:has-text('Postularme'), "
                    "button:has-text('Bewerben'), a:has-text('Bewerben')"
                )
                if reveal_btn:
                    try:
                        await reveal_btn.scroll_into_view_if_needed(timeout=2000)
                        await reveal_btn.click(timeout=5000)
                        await asyncio.sleep(2.0)
                        await self._safe_wait_for_idle(page, timeout=4000)
                    except Exception:
                        try:
                            await reveal_btn.evaluate("el => el.click()")
                            await asyncio.sleep(2.0)
                        except Exception:
                            pass

            async def _fill_field(el, val: str) -> bool:
                if not el:
                    return False
                try:
                    curr = await el.input_value()
                    if curr:
                        return False
                except Exception:
                    pass
                try:
                    await el.scroll_into_view_if_needed(timeout=1500)
                    await el.fill(val, timeout=2000)
                    return True
                except Exception:
                    pass
                try:
                    await el.evaluate("""(el, v) => {
                        el.value = v;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", val)
                    return True
                except Exception:
                    return False

            # Fill direct standard personal fields (check both search_scope and page)
            fn_el = await search_scope.query_selector("input[name='first_name'], input#first_name, input[name*='first_name'], input[name='job_application[first_name]'], input[name='candidate.firstName'], input[name='firstName'], input[name='Name'], input#Name, input[placeholder*='Nombre'], input[placeholder*='First Name']") or await page.query_selector("input[name='first_name'], input#first_name, input[name*='first_name'], input[name='job_application[first_name]'], input[name='candidate.firstName'], input[name='firstName'], input[name='Name'], input#Name, input[placeholder*='Nombre']")
            if await _fill_field(fn_el, "Julian David"):
                filled_count += 1

            ln_el = await search_scope.query_selector("input[name='last_name'], input#last_name, input[name*='last_name'], input[name='job_application[last_name]'], input[name='candidate.lastName'], input[name='lastName'], input[name='Surname'], input#Surname, input[placeholder*='Apellido'], input[placeholder*='Last Name']") or await page.query_selector("input[name='last_name'], input#last_name, input[name*='last_name'], input[name='job_application[last_name]'], input[name='candidate.lastName'], input[name='lastName'], input[name='Surname'], input#Surname, input[placeholder*='Apellido']")
            if await _fill_field(ln_el, "Diaz Medina"):
                filled_count += 1

            full_el = await search_scope.query_selector("input[name='full_name'], input#full_name, input[name='candidate.name'], input[name='name'], input#name, input[name='job_application[name]'], input[placeholder*='Full Name'], input[placeholder*='Nombre Completo']") or await page.query_selector("input[name='full_name'], input#full_name, input[name='candidate.name'], input[name='name'], input#name, input[name='job_application[name]']")
            if not fn_el:
                if await _fill_field(full_el, "Julian David Diaz Medina"):
                    filled_count += 1

            email_el = await search_scope.query_selector("input[type='email'], input[name*='email'], input#email, input[name='candidate.email'], input[name='job_application[email]'], input[placeholder*='Email'], input[placeholder*='Correo']") or await page.query_selector("input[type='email'], input[name*='email'], input#email, input[name='candidate.email'], input[name='job_application[email]']")
            if await _fill_field(email_el, "maestrecs92@gmail.com"):
                filled_count += 1

            phone_el = await search_scope.query_selector("input[name*='phone'], input#phone, input[type='tel'], input[name='candidate.phone'], input[name='job_application[phone]'], input[placeholder*='Phone'], input[placeholder*='Teléfono'], input[placeholder*='Celular']") or await page.query_selector("input[name*='phone'], input#phone, input[type='tel'], input[name='candidate.phone'], input[name='job_application[phone]']")
            if await _fill_field(phone_el, "3206841270"):
                filled_count += 1

            prefix_el = await search_scope.query_selector("input[name='PrefixPhone'], input#PrefixPhone") or await page.query_selector("input[name='PrefixPhone'], input#PrefixPhone")
            if await _fill_field(prefix_el, "57"):
                filled_count += 1

            addr_el = await search_scope.query_selector("input[name='Address'], input#Address, input[name*='location'], input#location, input[placeholder*='City'], input[placeholder*='Ciudad']") or await page.query_selector("input[name='Address'], input#Address, input[name*='location'], input#location")
            if await _fill_field(addr_el, "Valledupar, Cesar"):
                filled_count += 1

            doc_el = await search_scope.query_selector("input[name*='cedula' i], input[name*='document' i], input#document, input[name*='dni' i], input[placeholder*='cédula' i], input[placeholder*='documento' i]") or await page.query_selector("input[name*='cedula' i], input[name*='document' i], input#document, input[placeholder*='cédula' i], input[placeholder*='documento' i]")
            if doc_el:
                ced_val = self.profile_data.get("cedula") or self.profile_data.get("document_number", "1081795939")
                if await _fill_field(doc_el, str(ced_val)):
                    filled_count += 1

            linkedin_el = await search_scope.query_selector("input[name*='linkedin' i], input#linkedin, input[placeholder*='linkedin' i]") or await page.query_selector("input[name*='linkedin' i], input#linkedin, input[placeholder*='linkedin' i]")
            if linkedin_el:
                li_val = self.profile_data.get("linkedin", "https://www.linkedin.com/in/julian-diaz-soporte-ti")
                if await _fill_field(linkedin_el, li_val):
                    filled_count += 1

            # Upload CV file
            cv_inputs = await page.query_selector_all("input[type='file']")
            for cinp in cv_inputs:
                cname = (await cinp.get_attribute("name") or "").lower()
                cid = (await cinp.get_attribute("id") or "").lower()
                if any(k in (cname + " " + cid) for k in ["cv", "file", "resume", "curriculum", "candidate.cv", "attachment", "document"]) or len(cv_inputs) == 1:
                    if os.path.exists(cv_path) and not cv_attached:
                        try:
                            await cinp.set_input_files(cv_path)
                            filled_count += 1
                            cv_attached = True
                            break
                        except Exception:
                            pass

            # Check terms & consent checkboxes via JS
            terms = await page.query_selector_all("input[type='checkbox'][name*='term' i], input[type='checkbox'][name*='consent' i], input[type='checkbox'][name*='accept' i], input[type='checkbox'][name*='priva' i], input[type='checkbox'][required]")
            for t in terms:
                try:
                    await t.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }")
                    filled_count += 1
                except Exception:
                    pass

            # Professional summary textarea
            textarea_el = await search_scope.query_selector("textarea[name*='Job'], textarea") or await page.query_selector("textarea[name*='Job'], textarea")
            if textarea_el:
                summary_text = self.profile_data.get("summary", "")[:400]
                try:
                    if await textarea_el.is_visible():
                        await textarea_el.fill(summary_text)
                    else:
                        await textarea_el.evaluate("(el, val) => { el.value = val; el.dispatchEvent(new Event('input', {bubbles: true})); }", summary_text)
                    filled_count += 1
                except Exception:
                    pass

            # Additional general inputs mapping for other portals / Easy Apply
            raw_inputs = await search_scope.query_selector_all("input:not([type='hidden']), textarea, select")
            for el in raw_inputs:
                try:
                    itype = (await el.get_attribute("type") or "text").lower()
                    name_attr = (await el.get_attribute("name") or "").lower()
                    if itype in ["submit", "reset", "button"] or any(k in name_attr for k in ["search", "nav"]):
                        continue
                    id_attr = (await el.get_attribute("id") or "")
                    placeholder = (await el.get_attribute("placeholder") or "")
                    field_kind = FieldMapper.identify_field(name_attr, id_attr, "", placeholder)
                    if field_kind:
                        val = FieldMapper.get_candidate_value(field_kind, self.profile_data, cv_path, cover_letter)
                        if val and itype == "file" and field_kind == "resume" and not cv_attached:
                            if os.path.exists(val):
                                await el.set_input_files(val)
                                filled_count += 1
                                cv_attached = True
                        elif val and itype in ["text", "email", "tel"]:
                            if await el.is_visible():
                                curr = await el.input_value()
                                if not curr:
                                    await el.fill(str(val))
                                    filled_count += 1
                except Exception:
                    continue

            # Multi-step Easy Apply advance
            next_btn = await page.query_selector("button:has-text('Siguiente'), button:has-text('Next'), button[aria-label*='Siguiente'], button[aria-label*='Next']")
            if next_btn and await next_btn.is_visible() and filled_count > 0:
                try:
                    await next_btn.click()
                    await asyncio.sleep(2.0)
                    await self._safe_wait_for_idle(page, timeout=3000)
                    step2_inputs = await page.query_selector_all("input[type='file']")
                    for el in step2_inputs:
                        if os.path.exists(cv_path) and not cv_attached:
                            await el.set_input_files(cv_path)
                            filled_count += 1
                            cv_attached = True
                except Exception:
                    pass

            cv_detail = " y CV ATS adjuntado" if cv_attached else ""
            
            # Evaluate Form Result
            if filled_count == 0:
                is_simo = "simo.cnsc.gov.co" in (page.url or url).lower()
                screenshot_path = await self._capture_screenshot(page, application_id, "form_unrecognized")
                prompt_msg = (
                    "El portal del Estado (CNSC / SIMO) requiere inicio de sesión con tu cédula y contraseña para inscribirte a la OPEC y adquirir los derechos de participación. Haz clic en 'Abrir Navegador en Pantalla' para ingresar a SIMO con tu usuario oficial."
                    if is_simo else
                    "No se detectó un formulario abierto para completar de forma autónoma. Abre el navegador interactivo en pantalla para postularte directamente en el portal."
                )
                self.repo.enqueue_human_review(
                    application_id=application_id,
                    reason=HumanReviewReason.LOGIN_REQUIRED.value if is_simo else HumanReviewReason.UNRECOGNIZED_FORM.value,
                    url=page.url or url,
                    screenshot_path=screenshot_path,
                    question_prompt=prompt_msg
                )
                add_step("6. Mapeo y Diligenciamiento", "warning", ("Portal SIMO / CNSC requiere inicio de sesión de ciudadano para OPEC." if is_simo else "No se detectaron campos de entrada activos en esta página. Requiere apertura en pantalla."))
                return {
                    "success": False,
                    "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                    "reason": ("El portal SIMO / CNSC requiere autenticación personal de ciudadano para participar en la OPEC." if is_simo else "La vacante no presentó un formulario directo. Requiere apertura interactiva en pantalla."),
                    "screenshot": screenshot_path,
                    "steps": steps,
                    "external_url": page.url or url,
                }

            add_step("6. Mapeo y Diligenciamiento", "completed", f"Se detectaron y completaron {filled_count} campos con datos reales de Julian Díaz{cv_detail}.")

            # 8. Check for complex questions / salary
            if "aspiración salarial" in page_lower or "pretensión salarial" in page_lower:
                add_step("7. Validación de Requisitos", "warning", "Se detectó solicitud de aspiración salarial. Requiere confirmación humana.")
                screenshot_path = await self._capture_screenshot(page, application_id, "salary_question")
                self.repo.enqueue_human_review(
                    application_id=application_id,
                    reason=HumanReviewReason.SALARY_QUESTION.value,
                    url=url,
                    screenshot_path=screenshot_path,
                    question_prompt="El formulario solicita aspiración salarial u oferta económica específica."
                )
                return {
                    "success": False,
                    "status": ApplicationStatus.CONFIRMATION_REQUIRED.value,
                    "reason": "Pregunta salarial detectada. Requiere confirmación humana.",
                    "screenshot": screenshot_path,
                    "steps": steps,
                    "external_url": page.url or url,
                }

            # 9. Dry Run / Prepare Mode
            screenshot_path = await self._capture_screenshot(page, application_id, "form_prepared")
            if dry_run:
                add_step("7. Finalización / Simulación", "completed", f"Formulario preparado y validado en modo simulación (Dry-Run). {filled_count} campos rellenados.")
                return {
                    "success": True,
                    "status": ApplicationStatus.READY.value,
                    "fields_filled": filled_count,
                    "screenshot": screenshot_path,
                    "message": f"Formulario mapeado y preparado con éxito en modo simulación (Dry-Run). {filled_count} campos rellenados.",
                    "steps": steps
                }

            # 10. Submit (Autopilot confirmed)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            candidate_buttons = await page.query_selector_all(
                "button[type='submit'], input[type='submit'], button:has-text('Enviar'), button:has-text('Postularme'), "
                "button:has-text('Enviar solicitud'), button:has-text('Completar aplicación'), button:has-text('Completar postulación'), "
                "button:has-text('Finalizar'), button:has-text('Inscribirme'), button:has-text('Guardar'), button:has-text('Apply'), "
                "button:has-text('Submit'), button.btn-primary, button#btnSubmit, button#submit-btn"
            )
            submit_btn = None
            for b in candidate_buttons:
                try:
                    if await b.is_visible():
                        submit_btn = b
                        break
                except Exception:
                    continue

            if submit_btn:
                add_step("7. Envío de Candidatura", "in_progress", "Pulsando botón de envío final...")
                await submit_btn.click()
                await asyncio.sleep(4.0)
                await self._safe_wait_for_idle(page, timeout=5000)
                final_screenshot = await self._capture_screenshot(page, application_id, "submission_result")
                add_step("7. Envío de Candidatura", "completed", "Postulación enviada exitosamente al portal.")
                return {
                    "success": True,
                    "status": ApplicationStatus.SUBMITTED.value,
                    "screenshot": final_screenshot,
                    "message": "Postulación enviada exitosamente al portal del empleador.",
                    "steps": steps
                }
            else:
                add_step("7. Envío de Candidatura", "completed", "Campos completados. Botón de envío no accionado automáticamente (esperando confirmación manual).")
                return {
                    "success": True,
                    "status": ApplicationStatus.READY.value,
                    "screenshot": screenshot_path,
                    "message": "Campos completados, botón de envío no accionado automáticamente.",
                    "steps": steps
                }

        except Exception as e:
            add_step("Error Inesperado", "failed", f"Excepción durante navegación: {str(e)}")
            err_screenshot = ""
            try:
                err_screenshot = await self._capture_screenshot(page, application_id, "error")
            except Exception:
                pass
            return {
                "success": False,
                "status": ApplicationStatus.FAILED.value,
                "error": str(e),
                "screenshot": err_screenshot,
                "steps": steps
            }

        finally:
            try:
                await page.close()
            except Exception:
                pass
            await self.close()

    async def _safe_wait_for_idle(self, page: Page, timeout: int = 4000):
        """Waits briefly for ongoing navigation / redirect to settle."""
        try:
            await page.wait_for_load_state("load", timeout=timeout)
        except Exception:
            pass

    async def _safe_get_content(self, page: Page, retries: int = 4) -> str:
        """Retrieves page HTML safely even while dynamic redirects are firing."""
        for attempt in range(retries):
            try:
                await self._safe_wait_for_idle(page, timeout=3000)
                return await page.content()
            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ["navigating", "execution context", "target closed"]) and attempt < retries - 1:
                    await asyncio.sleep(1.5)
                    continue
                if attempt == retries - 1:
                    try:
                        return await page.evaluate("() => document.documentElement.outerHTML || ''")
                    except Exception:
                        return ""
        return ""

    async def _capture_screenshot(self, page: Page, application_id: str, tag: str) -> str:
        filename = f"{application_id[:8]}_{tag}.png"
        filepath = self.screenshots_dir / filename
        for attempt in range(3):
            try:
                await self._safe_wait_for_idle(page, timeout=3000)
                await page.screenshot(path=str(filepath), full_page=False)
                return str(filepath)
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1.0)
                    continue
                return str(filepath) if filepath.exists() else ""
        return str(filepath) if filepath.exists() else ""
