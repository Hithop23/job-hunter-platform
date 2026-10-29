import os
import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, HTTPException, Response, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.storage.database import get_db
from app.storage.repository import Repository
from app.storage.models import Application, ApplicationStatus
from app.matching.matcher import JobMatcher
from app.cv.cv_generator import ATSCVGenerator
from app.cv.cover_letter import CoverLetterGenerator
from app.browser.browser_manager import BrowserManager

router = APIRouter(prefix="/api/applications", tags=["Applications & Tracking"])


@router.get("/")
def list_applications(
    status: Optional[str] = None,
    source: Optional[str] = None,
    company: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    repo = Repository(db)
    apps = repo.list_applications(
        status=status, source=source, company=company, min_score=min_score, limit=limit, offset=offset
    )
    return {
        "total": len(apps),
        "applications": [
            {
                "id": a.id,
                "job_id": a.job_id,
                "company": a.company,
                "position": a.position,
                "url": a.url,
                "source": a.source,
                "status": a.status,
                "match_score": a.match_score,
                "does_not_meet_required_requirement": a.does_not_meet_required_requirement,
                "cv_version": a.cv_version,
                "cv_path": a.cv_path,
                "cover_letter": a.cover_letter,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                "notes": a.notes,
                "salary": a.job.salary if a.job and a.job.salary else "A convenir",
                "location": a.job.location if a.job and a.job.location else "Colombia",
                "publication_date": a.job.publication_date if a.job and a.job.publication_date else None,
            }
            for a in apps
        ]
    }


@router.post("/prepare/{job_id}")
def prepare_application(
    job_id: str,
    language: Optional[str] = Query(None, description="Idioma del CV: 'en' o 'es' (si se omite, se detecta automáticamente)"),
    db: Session = Depends(get_db)
):
    """Tailors CV ATS and generates custom cover letter for a specific job in English or Spanish."""
    repo = Repository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")

    matcher = JobMatcher()
    cv_gen = ATSCVGenerator()
    cl_gen = CoverLetterGenerator()

    eval_res = matcher.evaluate_job({
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "location": job.location,
    })

    cv_res = cv_gen.generate_tailored_cv(
        application_id=job.id,
        job_title=job.title,
        company=job.company,
        job_description=f"{job.description} {job.requirements}",
        language=language,
        location=job.location or "",
        source=job.source or ""
    )

    letter = cl_gen.generate_letter(
        company=job.company,
        job_title=job.title,
        job_description=job.description,
        language=cv_res.get("language"),
        location=job.location or "",
        source=job.source or ""
    )

    app = repo.create_or_update_application({
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "source": job.source,
        "status": ApplicationStatus.READY.value if not eval_res["does_not_meet_required_requirement"] else ApplicationStatus.REVIEW.value,
        "match_score": eval_res["match_score"],
        "required_skill_match": eval_res["breakdown"]["required_skill_match"],
        "education_match": eval_res["breakdown"]["education_match"],
        "experience_match": eval_res["breakdown"]["experience_match"],
        "location_match": eval_res["breakdown"]["location_match"],
        "keyword_match": eval_res["breakdown"]["keyword_match"],
        "seniority_match": eval_res["breakdown"]["seniority_match"],
        "does_not_meet_required_requirement": eval_res["does_not_meet_required_requirement"],
        "match_reasons": json.dumps(eval_res["disqualification_reasons"] if eval_res["does_not_meet_required_requirement"] else eval_res["matched_skills"]),
        "cv_version": cv_res["cv_version"],
        "cv_path": cv_res["pdf_path"],
        "cover_letter": letter,
        "keywords_used": json.dumps(cv_res["keywords_used"]),
    })

    return {
        "status": "prepared",
        "application_id": app.id,
        "cv_path": app.cv_path,
        "cv_version": app.cv_version,
        "language": cv_res.get("language", "es"),
        "match_score": app.match_score,
        "cover_letter": letter
    }


class ApplyAutopilotRequest(BaseModel):
    dry_run: Optional[bool] = False
    verification_code: Optional[str] = None


@router.post("/apply/{application_id}")
async def apply_autopilot(
    application_id: str,
    payload: Optional[ApplyAutopilotRequest] = Body(default=None),
    dry_run: Optional[bool] = Query(None, description="Si es True, ejecuta solo simulación sin envío irreversible"),
    verification_code: Optional[str] = Query(None, description="Código de verificación OTP enviado al correo para completar registro"),
    db: Session = Depends(get_db)
):
    """
    Executes automated form filling via Playwright.
    Enforces daily limit (50/day), domain limit (10/hour), and pauses for human intervention
    if CAPTCHA/2FA or ambiguous questions occur. Supports one-time verification code (OTP).
    """
    repo = Repository(db)
    app = repo.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")

    eff_dry_run = False
    eff_code = None

    if payload:
        if payload.dry_run is not None:
            eff_dry_run = payload.dry_run
        if payload.verification_code:
            eff_code = payload.verification_code

    if dry_run is not None:
        eff_dry_run = dry_run
    if verification_code:
        eff_code = verification_code

    # If verification_code is not passed, check if there is a resolved human review with user_input
    if not eff_code:
        from app.storage.models import HumanReviewItem
        last_review = db.query(HumanReviewItem).filter(
            HumanReviewItem.application_id == app.id,
            HumanReviewItem.resolved == True,
            HumanReviewItem.user_input.isnot(None)
        ).order_by(HumanReviewItem.resolved_at.desc()).first()
        if last_review and last_review.user_input:
            eff_code = last_review.user_input.strip()

    # Safety checks
    if app.does_not_meet_required_requirement:
        raise HTTPException(
            status_code=400,
            detail="No se puede postular automáticamente: El candidato no cumple los requisitos obligatorios de esta vacante."
        )

    if not repo.check_daily_application_limit(max_per_day=50):
        raise HTTPException(
            status_code=429,
            detail="Límite diario de postulaciones alcanzado (50/día). Priorizando calidad sobre volumen."
        )

    # Ensure CV is generated and exists on disk
    if not app.cv_path or not os.path.exists(app.cv_path):
        prep_res = prepare_application(job_id=app.job_id, language=None, db=db)
        app = repo.get_application(application_id)
        if not app.cv_path and prep_res.get("cv_path"):
            app.cv_path = prep_res.get("cv_path")
            repo.db.commit()

    matcher = JobMatcher()
    browser_mgr = BrowserManager(repo=repo, profile_data=matcher.profile)

    try:
        try:
            res = await browser_mgr.run_autopilot_pipeline(
                application_id=app.id,
                url=app.url,
                cv_path=app.cv_path,
                cover_letter=app.cover_letter,
                dry_run=eff_dry_run,
                verification_code=eff_code
            )
        except Exception as e:
            res = {
                "success": False,
                "status": ApplicationStatus.FAILED.value,
                "error": str(e),
                "message": f"Error durante la navegación: {str(e)}",
                "steps": [
                    {
                        "name": "Error Inesperado",
                        "status": "failed",
                        "detail": f"Excepción durante la ejecución: {str(e)}",
                        "time": datetime.now(timezone.utc).strftime("%H:%M:%S")
                    }
                ]
            }
    finally:
        await browser_mgr.close()

    # Update application
    app.status = res.get("status", app.status)
    if res.get("status") == ApplicationStatus.SUBMITTED.value:
        app.submitted_at = datetime.now(timezone.utc)
    repo.db.commit()

    return res


class BatchApplyRequest(BaseModel):
    max_applications: Optional[int] = 5
    limit: Optional[int] = None
    dry_run: Optional[bool] = False


@router.post("/apply-batch")
async def apply_batch_autopilot(
    payload: Optional[BatchApplyRequest] = Body(default=None),
    limit: Optional[int] = Query(None, description="Número máximo de vacantes a postular en este lote"),
    dry_run: Optional[bool] = Query(None, description="Si es True, ejecuta solo simulación sin envío real"),
    db: Session = Depends(get_db)
):
    """
    Executes Autopilot sequentially across top READY applications.
    Applies safety limits, skips disqualified jobs, and returns detailed results.
    """
    repo = Repository(db)
    eff_limit = 5
    eff_dry_run = False

    if payload:
        if payload.limit is not None:
            eff_limit = payload.limit
        elif payload.max_applications is not None:
            eff_limit = payload.max_applications
        if payload.dry_run is not None:
            eff_dry_run = payload.dry_run

    if limit is not None:
        eff_limit = limit
    if dry_run is not None:
        eff_dry_run = dry_run

    ready_apps = db.query(Application).filter(
        Application.status.in_([ApplicationStatus.READY.value, ApplicationStatus.DISCOVERED.value]),
        Application.does_not_meet_required_requirement == False
    ).order_by(Application.match_score.desc()).limit(eff_limit).all()

    if not ready_apps:
        return {
            "status": "EMPTY",
            "success": True,
            "processed": 0,
            "submitted": 0,
            "hil_required": 0,
            "message": "No hay vacantes en cola listas para postulación automática.",
            "results": []
        }

    results = []
    for app in ready_apps:
        if not repo.check_daily_application_limit(max_per_day=50):
            break
        try:
            res = await apply_autopilot(application_id=app.id, dry_run=eff_dry_run, db=db)
            results.append({
                "application_id": app.id,
                "company": app.company,
                "position": app.position,
                "status": res.get("status"),
                "success": res.get("success"),
                "message": res.get("message") or res.get("reason")
            })
        except Exception as exc:
            results.append({
                "application_id": app.id,
                "company": app.company,
                "position": app.position,
                "status": "FAILED",
                "success": False,
                "message": str(exc)
            })

    submitted_count = sum(1 for r in results if r.get("status") == "SUBMITTED")
    hil_count = sum(1 for r in results if r.get("status") in ["REVIEW", "CONFIRMATION_REQUIRED"])

    return {
        "status": "SUCCESS" if submitted_count > 0 or len(results) > 0 else "EMPTY",
        "success": True,
        "processed": len(results),
        "submitted": submitted_count,
        "hil_required": hil_count,
        "dry_run": eff_dry_run,
        "results": results
    }


@router.put("/{application_id}/status")
def update_application_status(
    application_id: str,
    status: str = Query(..., enum=[s.value for s in ApplicationStatus]),
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    repo = Repository(db)
    app = repo.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    app.status = status
    if notes:
        app.notes = notes
    if status == ApplicationStatus.SUBMITTED.value and not app.submitted_at:
        app.submitted_at = datetime.now(timezone.utc)
    repo.db.commit()
    return {"message": "Estado actualizado", "application_id": app.id, "status": app.status}


@router.get("/export/csv")
def export_applications_csv(db: Session = Depends(get_db)):
    """Exports all applications with status, score, dates and links to CSV."""
    repo = Repository(db)
    apps = repo.list_applications(limit=1000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID Postulación",
        "Empresa",
        "Cargo",
        "Fuente",
        "Score Compatibilidad",
        "Estado",
        "Cumple Requisitos Obligatorios",
        "URL Vacante",
        "Versión CV",
        "Fecha Creación",
        "Fecha Envío",
        "Notas"
    ])

    for a in apps:
        writer.writerow([
            a.id,
            a.company,
            a.position,
            a.source,
            a.match_score,
            a.status,
            "SI" if not a.does_not_meet_required_requirement else "NO",
            a.url,
            a.cv_version or "",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
            a.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if a.submitted_at else "",
            a.notes or ""
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=postulaciones_julian_diaz_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"}
    )
