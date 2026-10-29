import asyncio
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.storage.database import get_db
from app.storage.repository import Repository
from app.storage.models import ApplicationStatus
from app.matching.matcher import JobMatcher
from app.cv.cv_generator import ATSCVGenerator
from app.cv.cover_letter import CoverLetterGenerator
from app.adapters.sena.sena_adapter import SENAAdapter
from app.adapters.spe.spe_adapter import SPEAdapter
from app.adapters.cnsc.cnsc_adapter import CNSCAdapter
from app.adapters.computrabajo.computrabajo_adapter import ComputrabajoAdapter
from app.adapters.indeed.indeed_adapter import IndeedAdapter
from app.adapters.linkedin.linkedin_adapter import LinkedInAdapter
from app.adapters.companies.ats_adapters import CompanyDirectoryAdapter
from app.adapters.remoteok.remoteok_adapter import RemoteOKAdapter
from app.adapters.arbeitnow.arbeitnow_adapter import ArbeitnowAdapter
from app.adapters.weworkremotely.wwr_adapter import WeWorkRemotelyAdapter
from app.notifications.notifier import Notifier

router = APIRouter(prefix="/api/jobs", tags=["Jobs & Discovery"])


async def run_discovery_task(
    db_session: Session,
    mode: str,
    query: str,
    location: str,
    country: str = "Colombia",
    region: str = "Cesar",
    remote: bool = True
):
    repo = Repository(db_session)
    matcher = JobMatcher()
    cv_gen = ATSCVGenerator()
    cl_gen = CoverLetterGenerator()

    adapters = [
        SENAAdapter(db_session),
        SPEAdapter(db_session),
        CNSCAdapter(db_session),
        CompanyDirectoryAdapter(db_session),
        ComputrabajoAdapter(db_session),
        IndeedAdapter(db_session),
        LinkedInAdapter(db_session),
        # 🌍 Global remote adapters — worldwide remote job discovery
        RemoteOKAdapter(db_session),
        ArbeitnowAdapter(db_session),
        WeWorkRemotelyAdapter(db_session),
    ]

    total_discovered = 0
    total_matched = 0

    effective_location = location or region or country

    for adapter in adapters:
        try:
            jobs = await adapter.discover_jobs(query=query, location=effective_location, limit=10)
            for j in jobs:
                job_obj, is_new = repo.store_job(j)
                total_discovered += 1

                # Evaluate with JobMatcher
                eval_res = matcher.evaluate_job(j)
                match_score = eval_res["match_score"]
                priority = eval_res["priority"]
                disqualified = eval_res["does_not_meet_required_requirement"]

                # Create application record
                status = ApplicationStatus.DISCOVERED.value
                if match_score >= 75 and not disqualified:
                    status = ApplicationStatus.READY.value
                    Notifier.notify_high_priority_job(j, match_score)
                elif match_score >= 60 and not disqualified:
                    status = ApplicationStatus.REVIEW.value

                cv_path = None
                cv_ver = None
                cover_let = None
                keywords_used_json = None

                # In PREPARE or AUTOPILOT mode, automatically tailor ATS CV and cover letter for relevant jobs
                if mode in ["PREPARE", "AUTOPILOT"] and match_score >= 60 and not disqualified:
                    cv_res = cv_gen.generate_tailored_cv(
                        application_id=job_obj.id,
                        job_title=job_obj.title,
                        company=job_obj.company,
                        job_description=f"{job_obj.description} {job_obj.requirements}",
                        location=job_obj.location or "",
                        source=job_obj.source or ""
                    )
                    cv_path = cv_res["pdf_path"]
                    cv_ver = cv_res["cv_version"]
                    keywords_used_json = json.dumps(cv_res["keywords_used"])
                    cover_let = cl_gen.generate_letter(
                        company=job_obj.company,
                        job_title=job_obj.title,
                        job_description=job_obj.description,
                        language=cv_res.get("language"),
                        location=job_obj.location or "",
                        source=job_obj.source or ""
                    )

                app_obj = repo.create_or_update_application({
                    "job_id": job_obj.id,
                    "company": job_obj.company,
                    "position": job_obj.title,
                    "url": job_obj.url,
                    "source": job_obj.source,
                    "status": status,
                    "match_score": match_score,
                    "required_skill_match": eval_res["breakdown"]["required_skill_match"],
                    "education_match": eval_res["breakdown"]["education_match"],
                    "experience_match": eval_res["breakdown"]["experience_match"],
                    "location_match": eval_res["breakdown"]["location_match"],
                    "keyword_match": eval_res["breakdown"]["keyword_match"],
                    "seniority_match": eval_res["breakdown"]["seniority_match"],
                    "does_not_meet_required_requirement": disqualified,
                    "match_reasons": json.dumps(eval_res["disqualification_reasons"] if disqualified else eval_res["matched_skills"]),
                    "cv_version": cv_ver,
                    "cv_path": cv_path,
                    "cover_letter": cover_let,
                    "keywords_used": keywords_used_json,
                })
                total_matched += 1

                repo.log_audit(
                    source=job_obj.source,
                    company=job_obj.company,
                    job_title=job_obj.title,
                    action=f"DISCOVERY_{mode}",
                    result="SUCCESS",
                    score=match_score,
                    status=status
                )
        except Exception as e:
            repo.log_audit(
                source=adapter.name,
                action=f"DISCOVERY_{mode}",
                result="ERROR",
                error=str(e)
            )

    return {
        "total_discovered": total_discovered,
        "total_matched": total_matched,
        "location": effective_location
    }


@router.post("/scan")
async def trigger_scan(
    mode: str = Query("SCAN", enum=["SCAN", "PREPARE", "AUTOPILOT"]),
    query: Optional[str] = Query(None, description="Cargos o tecnologías a buscar"),
    country: Optional[str] = Query(None, description="País"),
    region: Optional[str] = Query(None, description="Departamento o Región"),
    city: Optional[str] = Query(None, description="Ciudad o Municipio"),
    remote: Optional[bool] = Query(None, description="Incluir vacantes remotas"),
    location: Optional[str] = Query(None, description="Ubicación consolidada"),
    db: Session = Depends(get_db)
):
    """
    Triggers job discovery across all Colombian adapters with configurable geographic filters.
    Modes:
    - SCAN: Only discovers and scores jobs.
    - PREPARE: Discovers, scores, tailors ATS CV and writes cover letter.
    - AUTOPILOT: Discovers, prepares and queue safe submissions.
    """
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    prefs_file = base_dir / "data" / "profile.json"
    prefs = {}
    if prefs_file.exists():
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                prefs = p_data.get("search_preferences", {})
        except Exception:
            pass

    final_country = country or prefs.get("country") or "Colombia"
    final_region = region or prefs.get("region") or "Cesar"
    final_city = city or prefs.get("city") or "Valledupar"
    final_remote = remote if remote is not None else prefs.get("remote", True)
    final_query = query or prefs.get("keywords") or "soporte TI sistemas"
    final_location = location or final_city or final_region or final_country

    result = await run_discovery_task(
        db,
        mode,
        final_query,
        final_location,
        final_country,
        final_region,
        final_remote
    )
    return {
        "status": "completed",
        "total_discovered": result["total_discovered"],
        "total_matched": result["total_matched"],
        "mode": mode,
        "query": final_query,
        "country": final_country,
        "region": final_region,
        "city": final_city,
        "location": final_location,
        "remote": final_remote,
        "message": f"Escaneo completado: {result['total_discovered']} vacantes evaluadas para {final_location}."
    }


@router.get("/")
def list_jobs(
    source: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    repo = Repository(db)
    jobs = repo.list_jobs(source=source, company=company, search=search, limit=limit, offset=offset)
    return {
        "total": len(jobs),
        "jobs": [
            {
                "id": j.id,
                "source": j.source,
                "company": j.company,
                "title": j.title,
                "location": j.location,
                "url": j.url,
                "salary": j.salary,
                "employment_type": j.employment_type,
                "publication_date": j.publication_date,
                "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    repo = Repository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    return job
