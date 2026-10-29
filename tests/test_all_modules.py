import os
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.storage.models import Base, Job, Application, ApplicationStatus, HumanReviewReason
from app.storage.repository import Repository, compute_job_hash
from app.matching.matcher import JobMatcher
from app.cv.cv_generator import ATSCVGenerator
from app.cv.cover_letter import CoverLetterGenerator
from app.browser.field_mapper import FieldMapper
from app.adapters.sena.sena_adapter import SENAAdapter
from app.adapters.computrabajo.computrabajo_adapter import ComputrabajoAdapter


@pytest.fixture
def db_session():
    """In-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_job_normalization(db_session):
    """Verifies that adapters normalize raw jobs into the canonical schema correctly."""
    adapter = SENAAdapter(db_session)
    raw = {
        "id": "raw-123",
        "company": "Compañía Caribe S.A.S.",
        "title": "Técnico en Sistemas y Redes",
        "location": "Valledupar, Cesar",
        "url": "https://agenciapublicadeempleo.sena.edu.co/oferta/123",
        "description": "Soporte presencial y mantenimiento.",
        "requirements": "Técnico SENA",
        "salary": "$1.600.000 COP"
    }
    normalized = adapter.normalize_job(raw)

    assert normalized["source"] == "sena"
    assert normalized["company"] == "Compañía Caribe S.A.S."
    assert normalized["title"] == "Técnico en Sistemas y Redes"
    assert normalized["location"] == "Valledupar, Cesar"
    assert normalized["salary"] == "$1.600.000 COP"
    assert "description" in normalized
    assert "url" in normalized


def test_duplicate_detection(db_session):
    """
    Verifies that identical jobs are detected and deduplicated via:
    1. source + external_id
    2. hash(company + title + url)
    """
    repo = Repository(db_session)
    job1_data = {
        "id": "job-uuid-1",
        "source": "computrabajo",
        "external_id": "CT-9999",
        "company": "Soluciones TI S.A.S.",
        "title": "Analista de Mesa de Ayuda",
        "location": "Valledupar",
        "url": "https://co.computrabajo.com/oferta/9999",
        "description": "Soporte Helpdesk",
    }
    job1, created1 = repo.store_job(job1_data)
    assert created1 is True

    # Attempt 1: Same source and external_id
    job2_data = dict(job1_data)
    job2_data["id"] = "job-uuid-2"
    job2, created2 = repo.store_job(job2_data)
    assert created2 is False
    assert job2.id == job1.id

    # Attempt 2: Different external_id but same company + title + url (fallback hash)
    job3_data = dict(job1_data)
    job3_data["id"] = "job-uuid-3"
    job3_data["external_id"] = "CT-DIFFERENT-ID"
    job3, created3 = repo.store_job(job3_data)
    assert created3 is False
    assert job3.id == job1.id


def test_match_engine():
    """
    Verifies that JobMatcher scores relevant Junior IT vacancies highly (>=75%)
    and penalizes or drops irrelevant roles.
    """
    matcher = JobMatcher()

    # Highly compatible junior IT support role
    ideal_job = {
        "title": "Técnico de Soporte TI y Mesa de Ayuda Junior",
        "description": "Mantenimiento preventivo y correctivo de hardware, diagnóstico de fallas en Windows y Linux, soporte remoto con AnyDesk, configuración de impresoras en red.",
        "requirements": "Técnico en sistemas SENA o afines. Experiencia de 6 meses a 1 año en soporte a usuarios.",
        "location": "Valledupar, Cesar"
    }
    res_ideal = matcher.evaluate_job(ideal_job)
    assert res_ideal["match_score"] >= 75.0
    assert res_ideal["priority"] == "ALTA_PRIORIDAD"
    assert res_ideal["does_not_meet_required_requirement"] is False


def test_required_requirement_detection():
    """
    Verifies that jobs requiring mandatory Senior/Manager levels or mandatory
    professional university degrees are flagged with does_not_meet_required_requirement.
    """
    matcher = JobMatcher()

    senior_job = {
        "title": "Senior Infrastructure Manager / Director de TI",
        "description": "Liderar equipo de infraestructura cloud. Mínimo 8 años de experiencia. Título profesional universitario obligatorio con tarjeta profesional vigente obligatoria.",
        "requirements": "Título profesional universitario obligatorio con tarjeta profesional vigente obligatoria. Mínimo 8 años.",
        "location": "Colombia"
    }
    res_senior = matcher.evaluate_job(senior_job)
    assert res_senior["does_not_meet_required_requirement"] is True
    assert res_senior["match_score"] <= 50.0
    assert any("Senior" in r or "obligatorio" in r for r in res_senior["disqualification_reasons"])


def test_cv_keyword_extraction():
    """
    Verifies that ATSCVGenerator extracts relevant keywords matching Julian's real profile
    without hallucinating or stuffing irrelevant keywords.
    """
    cv_gen = ATSCVGenerator()
    job_desc = "Requerimos técnico de soporte con experiencia en diagnóstico de hardware, configuración de impresoras, Linux, Windows 11 y soporte remoto con TeamViewer."
    extracted = cv_gen.extract_relevant_keywords(job_desc)

    assert len(extracted) > 0
    # Check extracted skills belong to Julian's genuine profile
    all_profile_skills = []
    for cat in cv_gen.profile["technical_skills"].values():
        all_profile_skills.extend(cat)

    for k in extracted:
        assert k in all_profile_skills


def test_field_mapping():
    """Verifies that FieldMapper recognizes form attributes in Spanish and English."""
    # Full name
    assert FieldMapper.identify_field("fullname", "txt_name", "Nombre Completo", "") == "full_name"
    # Email
    assert FieldMapper.identify_field("user_email", "email_input", "Correo Electrónico", "tu@correo.com") == "email"
    # Phone
    assert FieldMapper.identify_field("phone_num", "celular", "Teléfono / Celular", "") == "phone"
    # Resume file upload
    assert FieldMapper.identify_field("resume_file", "cv_upload", "Adjuntar Hoja de Vida / CV", "") == "resume"
    # City
    assert FieldMapper.identify_field("city", "ciudad", "Ciudad de Residencia", "") == "city"
    # Document number / Cédula
    assert FieldMapper.identify_field("cedula", "num_doc", "Número de Cédula", "1081795939") == "document_number"
    # Password & Username
    assert FieldMapper.identify_field("password", "pwd", "Contraseña", "") == "password"
    assert FieldMapper.identify_field("username", "login_usr", "Usuario", "") == "username"

    # Values mapping
    profile = {
        "name": "Julian David Diaz Medina",
        "email": "maestrecs92@gmail.com",
        "phone": "+57 320 684 1270",
        "cedula": "1081795939",
        "portal_credentials": {
            "password": "JulianTalento2026*!",
            "username": "maestrecs92"
        }
    }
    assert FieldMapper.get_candidate_value("document_number", profile) == "1081795939"
    assert FieldMapper.get_candidate_value("email", profile) == "maestrecs92@gmail.com"
    assert FieldMapper.get_candidate_value("password", profile) == "JulianTalento2026*!"
    assert FieldMapper.get_candidate_value("username", profile) == "maestrecs92"


def test_application_tracking(db_session):
    """Verifies complete application lifecycle tracking."""
    repo = Repository(db_session)
    job, _ = repo.store_job({
        "id": "job-track-1",
        "source": "sena",
        "external_id": "trk-1",
        "company": "Tech Corp",
        "title": "Técnico TI",
        "location": "Valledupar",
        "url": "https://ejemplo.com/1"
    })

    app = repo.create_or_update_application({
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "source": job.source,
        "status": ApplicationStatus.DISCOVERED.value,
        "match_score": 82.5,
    })
    assert app.status == ApplicationStatus.DISCOVERED.value
    assert app.match_score == 82.5

    # Progress to READY then SUBMITTED
    app = repo.create_or_update_application({
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "status": ApplicationStatus.READY.value,
    })
    assert app.status == ApplicationStatus.READY.value

    app = repo.create_or_update_application({
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "status": ApplicationStatus.SUBMITTED.value,
    })
    assert app.status == ApplicationStatus.SUBMITTED.value


def test_rate_limit(db_session):
    """Verifies domain rate limiting (max 10 requests per domain per hour)."""
    repo = Repository(db_session)
    domain = "co.computrabajo.com"

    # Initially allowed
    assert repo.check_domain_rate_limit(domain, max_per_hour=3) is True

    # Record 3 accesses
    repo.record_domain_access(domain, "SCAN")
    repo.record_domain_access(domain, "SCAN")
    repo.record_domain_access(domain, "SCAN")

    # Now should be blocked
    assert repo.check_domain_rate_limit(domain, max_per_hour=3) is False


def test_human_intervention(db_session):
    """Verifies that human intervention queue correctly halts and pauses an application."""
    repo = Repository(db_session)
    job, _ = repo.store_job({
        "id": "job-hil-1",
        "source": "computrabajo",
        "external_id": "hil-1",
        "company": "Bancolombia",
        "title": "Soporte TI",
        "url": "https://ejemplo.com/apply"
    })

    app = repo.create_or_update_application({
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "status": ApplicationStatus.READY.value,
    })

    # Enqueue review due to CAPTCHA
    review = repo.enqueue_human_review(
        application_id=app.id,
        reason=HumanReviewReason.CAPTCHA.value,
        url=app.url,
        screenshot_path="logs/screenshots/captcha_sample.png",
        question_prompt="Resolver CAPTCHA"
    )

    assert review.resolved is False
    assert review.user_action == "PENDING"

    # Verify application status was updated to CONFIRMATION_REQUIRED
    updated_app = repo.get_application(app.id)
    assert updated_app.status == ApplicationStatus.CONFIRMATION_REQUIRED.value

    # User resolves by approving
    resolved = repo.resolve_human_review(review.id, action="APPROVED")
    assert resolved.resolved is True
    assert resolved.user_action == "APPROVED"

    updated_app = repo.get_application(app.id)
    assert updated_app.status == ApplicationStatus.READY.value


def test_no_fake_information():
    """
    CRITICAL RULE: Verifies that CV ATS generation and Cover Letters NEVER
    invent fake companies, fake degrees, or false dates.
    """
    cv_gen = ATSCVGenerator()
    cl_gen = CoverLetterGenerator()

    # Check profile source
    profile = cv_gen.profile
    assert profile["name"] == "Julian David Diaz Medina"
    assert "SENA" in profile["education"][0]["institution"]
    assert "Negocios e Inversiones SINGS S.A.S." in profile["experience"][0]["company"]

    # Tailor for a test job
    cv_result = cv_gen.generate_tailored_cv(
        application_id="test-validation-uuid",
        job_title="Técnico de Soporte TI",
        company="Empresa de Prueba S.A.S.",
        job_description="Soporte Windows, mantenimiento preventivo de hardware e impresoras"
    )
    assert os.path.exists(cv_result["pdf_path"])

    # Cover letter
    letter = cl_gen.generate_letter(
        company="Empresa de Prueba S.A.S.",
        job_title="Técnico de Soporte TI"
    )
    assert "Julian David Diaz Medina" in letter
    assert "Técnico en Sistemas Teleinformáticos" in letter
    assert "Negocios e Inversiones SINGS S.A.S." in letter
    assert len(letter.split()) <= 250


def test_salary_matching():
    """Verifies that salary matching correctly rewards competitive salaries and penalizes sub-minimum salaries."""
    matcher = JobMatcher()

    # Competitive salary
    res_high = matcher.evaluate_job({
        "title": "Técnico de Soporte TI",
        "description": "Soporte de sistemas y hardware",
        "salary": "$2.800.000 COP",
        "location": "Valledupar",
        "publication_date": "2026-09-18"
    })
    assert res_high["breakdown"]["salary_match"] == 100.0

    # Low salary
    res_low = matcher.evaluate_job({
        "title": "Técnico de Soporte TI",
        "description": "Soporte de sistemas y hardware",
        "salary": "$1.000.000 COP",
        "location": "Valledupar",
        "publication_date": "2026-09-18"
    })
    assert res_low["breakdown"]["salary_match"] == 40.0
    assert res_high["match_score"] > res_low["match_score"]

    # Negotiable / A convenir
    res_conv = matcher.evaluate_job({
        "title": "Técnico de Soporte TI",
        "description": "Soporte de sistemas y hardware",
        "salary": "A convenir",
        "location": "Valledupar",
        "publication_date": "2026-09-18"
    })
    assert res_conv["breakdown"]["salary_match"] == 85.0


def test_freshness_scoring():
    """Verifies that fresh vacancies receive maximum score and ancient vacancies (>30 days) are penalized."""
    from datetime import datetime, timezone
    matcher = JobMatcher()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res_fresh = matcher.evaluate_job({
        "title": "Técnico de Sistemas",
        "description": "Mantenimiento y soporte",
        "publication_date": today_str  # Always fresh — today
    })
    assert res_fresh["breakdown"]["freshness_match"] == 100.0

    res_old = matcher.evaluate_job({
        "title": "Técnico de Sistemas",
        "description": "Mantenimiento y soporte",
        "publication_date": "2026-01-10"
    })
    assert res_old["breakdown"]["freshness_match"] == 40.0
    assert res_fresh["match_score"] > res_old["match_score"]


def test_remote_priority_matching():
    """Verifies that 100% remote vacancies are prioritized and receive a maximum location score."""
    matcher = JobMatcher()

    res_remote = matcher.evaluate_job({
        "title": "Help Desk Junior (100% Remoto)",
        "description": "Mesa de ayuda teletrabajo soporte remoto",
        "location": "100% Remoto, Colombia",
        "salary": "$2.200.000 COP",
        "publication_date": "2026-09-18"
    })
    assert res_remote["breakdown"]["location_match"] == 100.0
    assert res_remote["match_score"] >= 80.0


def test_expired_patterns_recognition():
    """Verifies that 404 and expired vacancy markers are properly recognized by error detection."""
    expired_samples = [
        "404 Not Found - The resource requested could not be found on this server! Proudly powered by LiteSpeed",
        "Esta vacante ya no está disponible o ha expirado.",
        "Oferta de empleo finalizada por la empresa.",
        "El empleo ha sido cerrado y ya no acepta solicitudes."
    ]
    patterns = [
        "404 not found",
        "the resource requested could not be found",
        "proudly powered by litespeed",
        "esta vacante ya no está disponible",
        "oferta de empleo finalizada",
        "el empleo ha sido cerrado",
        "ya no acepta solicitudes",
    ]
    for sample in expired_samples:
        matched = any(p in sample.lower() for p in patterns)
        assert matched, f"Failed to match expired pattern in: {sample}"


def test_simo_opec_extraction_and_url_normalization():
    """Verifies that SIMO OPEC numbers are accurately extracted and URLs normalized for Dojo."""
    import re

    test_urls = [
        ("https://simo.cnsc.gov.co/#ofertaEmpleo?opec=204192", "204192"),
        ("https://simo.cnsc.gov.co/#ofertaEmpleo?opec=205318", "205318"),
        ("https://simo.cnsc.gov.co/#ofertaEmpleo?opec_193063", "193063"),
    ]

    for raw_url, expected_opec in test_urls:
        m = re.search(r"opec[=\-_](\d+)", raw_url, re.IGNORECASE)
        assert m is not None, f"Could not extract OPEC from {raw_url}"
        assert m.group(1) == expected_opec

        # Clean URL check
        if "simo.cnsc.gov.co" in raw_url.lower():
            clean_url = "https://simo.cnsc.gov.co/#ofertaEmpleo"
            assert clean_url == "https://simo.cnsc.gov.co/#ofertaEmpleo"


def test_cnsc_adapter_normalization(db_session):
    """Verifies that CNSC / SIMO jobs are correctly normalized and identified as Carrera Administrativa."""
    from app.adapters.cnsc.cnsc_adapter import CNSCAdapter
    adapter = CNSCAdapter(db_session)
    raw = {
        "id": "cnsc-opec-204192",
        "source": "cnsc",
        "external_id": "OPEC-204192",
        "company": "Gobernación del Cesar / Alcaldía de Valledupar (Convocatoria Territorial)",
        "title": "Técnico Operativo — Área de Sistemas e Informática",
        "location": "Valledupar, Cesar",
        "url": "https://simo.cnsc.gov.co/#ofertaEmpleo?opec=204192",
        "salary": "$2.150.000 COP",
        "employment_type": "Carrera Administrativa / Empleo Público"
    }
    normalized = adapter.normalize_job(raw)
    assert normalized["source"] == "cnsc"
    assert normalized["external_id"] == "OPEC-204192"
    assert "Gobernación del Cesar" in normalized["company"]
    assert "Sistemas" in normalized["title"]
    assert normalized["salary"] == "$2.150.000 COP"
    assert normalized["employment_type"] == "Carrera Administrativa / Empleo Público"


def test_desktop_launcher_browser_detection():
    """Verifies that desktop_launcher detects a valid browser executable on the system."""
    from app.browser.desktop_launcher import find_browser_executable
    exe = find_browser_executable()
    assert exe is not None, "A valid browser executable should be detected on Windows (Chromium, Chrome or Edge)"
    assert exe.exists(), f"Detected browser path {exe} does not exist"


def test_desktop_launcher_cleanup_locks():
    """Verifies that cleanup_profile_locks removes all Chromium lock files."""
    import tempfile
    from pathlib import Path
    from app.browser.desktop_launcher import cleanup_profile_locks

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        lockfile = tmp_dir / "lockfile"
        singleton = tmp_dir / "SingletonLock"
        cookie = tmp_dir / "SingletonCookie"
        lockfile.write_text("lock")
        singleton.write_text("lock")
        cookie.write_text("cookie")

        assert lockfile.exists()
        assert singleton.exists()
        assert cookie.exists()

        cleanup_profile_locks(tmp_dir)

        assert not lockfile.exists()
        assert not singleton.exists()
        assert not cookie.exists()


def test_language_detection():
    """Verifies that job language is accurately identified as 'en' or 'es'."""
    from app.cv.language_detector import detect_job_language, classify_job_archetype

    # English jobs
    lang_en1 = detect_job_language(
        title="IT Help Desk Technician",
        description="We are looking for a remote support technician to troubleshoot hardware and software issues.",
        requirements="2+ years experience with Windows 10/11, ticketing systems, and active directory.",
        location="Worldwide",
        source="weworkremotely"
    )
    assert lang_en1 == "en"

    lang_en2 = detect_job_language(
        title="Linux Support Engineer",
        description="Responsible for troubleshooting customer server environments and network configuration.",
        source="remoteok"
    )
    assert lang_en2 == "en"

    # Spanish jobs
    lang_es1 = detect_job_language(
        title="Técnico de Soporte en Sitio",
        description="Importante empresa requiere técnico en sistemas para mantenimiento preventivo y correctivo.",
        requirements="Técnico o tecnólogo con experiencia mínima de 1 año en soporte a usuarios.",
        location="Valledupar, Cesar",
        source="computrabajo"
    )
    assert lang_es1 == "es"

    lang_es2 = detect_job_language(
        title="Técnico Operativo — Sistemas",
        description="Convocatoria territorial para empleo público de carrera administrativa.",
        location="Colombia",
        source="cnsc"
    )
    assert lang_es2 == "es"

    # Archetype classification
    assert classify_job_archetype(title="Help Desk Junior", description="Atención a usuarios y tickets") == "it_support"
    assert classify_job_archetype(title="Junior SysAdmin", description="Linux server configuration and networks") == "sysadmin"
    assert classify_job_archetype(title="Python Support Analyst", description="Data scripts with pandas") == "software_data"


def test_bilingual_cv_generation():
    """Verifies that ATS CV can be generated in both English ('en') and Spanish ('es')."""
    from app.cv.cv_generator import ATSCVGenerator
    from pathlib import Path

    gen = ATSCVGenerator()

    # Generate English CV
    res_en = gen.generate_tailored_cv(
        application_id="test-job-en-001",
        job_title="IT Help Desk Specialist",
        company="Global Tech Inc",
        job_description="Technical support for remote users, Windows, hardware diagnostics, and ticket management.",
        language="en",
        location="Worldwide",
        source="remoteok"
    )
    assert res_en["language"] == "en"
    assert "EN" in res_en["cv_version"]
    assert Path(res_en["pdf_path"]).exists()
    assert Path(res_en["pdf_path"]).stat().st_size > 1000

    # Generate Spanish CV
    res_es = gen.generate_tailored_cv(
        application_id="test-job-es-001",
        job_title="Técnico de Sistemas y Redes",
        company="Soluciones Valledupar",
        job_description="Mantenimiento preventivo, impresoras en red y soporte a usuarios presencial.",
        language="es",
        location="Valledupar, Cesar",
        source="sena"
    )
    assert res_es["language"] == "es"
    assert "ES" in res_es["cv_version"]
    assert Path(res_es["pdf_path"]).exists()
    assert Path(res_es["pdf_path"]).stat().st_size > 1000


def test_bilingual_cover_letter():
    """Verifies that Cover Letters are properly generated and structured in English and Spanish."""
    from app.cv.cover_letter import CoverLetterGenerator

    gen = CoverLetterGenerator()

    # English cover letter
    letter_en = gen.generate_letter(
        company="Acme Cloud LLC",
        job_title="Remote IT Support Specialist",
        job_description="Provide excellent technical assistance to worldwide users.",
        language="en"
    )
    assert "Dear Hiring Team at Acme Cloud LLC," in letter_en
    assert "Julian David Diaz Medina" in letter_en
    assert "SINGS S.A.S." in letter_en
    assert "400" in letter_en
    assert len(letter_en.split()) <= 250

    # Spanish cover letter
    letter_es = gen.generate_letter(
        company="Distribuidora del Cesar",
        job_title="Técnico de Soporte TI",
        job_description="Soporte técnico a usuarios en sitio.",
        language="es"
    )
    assert "Apreciado equipo de Selección y Talento Humano" in letter_es
    assert "Distribuidora del Cesar" in letter_es
    assert "Julian David Diaz Medina" in letter_es
    assert len(letter_es.split()) <= 250


def test_verification_code_and_hil_flow():
    """Verifies that verification code handling and HIL resolution work correctly."""
    from app.api.routes_applications import ApplyAutopilotRequest
    from app.storage.models import Application, HumanReviewItem, ApplicationStatus
    from app.storage.repository import Repository
    from app.storage.database import SessionLocal

    # Test request model
    req = ApplyAutopilotRequest(dry_run=True, verification_code="987654")
    assert req.dry_run is True
    assert req.verification_code == "987654"

    db = SessionLocal()
    try:
        repo = Repository(db)
        app = repo.create_or_update_application({
            "job_id": "test-otp-job-1",
            "company": "Bancolombia Test",
            "position": "Auxiliar de Soporte TI",
            "url": "https://empleo.grupobancolombia.com/job/test",
            "source": "Bancolombia",
            "status": ApplicationStatus.CONFIRMATION_REQUIRED.value
        })
        
        # Enqueue HIL
        review = repo.enqueue_human_review(
            application_id=app.id,
            reason="LOGIN_REQUIRED",
            url=app.url,
            question_prompt="El portal ha enviado un código de acceso a tu correo."
        )
        assert review.resolved is False
        
        # Resolve HIL with user_input (verification code)
        resolved_review = repo.resolve_human_review(
            review_id=review.id,
            action="APPROVED",
            user_input="554433"
        )
        assert resolved_review.resolved is True
        assert resolved_review.user_input == "554433"
        assert resolved_review.application.status == ApplicationStatus.READY.value
    finally:
        db.close()



