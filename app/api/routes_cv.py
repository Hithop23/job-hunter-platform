import re
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.storage.database import get_db
from app.storage.repository import Repository
from app.cv.cv_transformer import CVTransformer

router = APIRouter(prefix="/api/cv", tags=["CV & ATS Generation"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CV_DIR = BASE_DIR / "cv" / "variants"
CV_DIR.mkdir(parents=True, exist_ok=True)


class GenerateCvPayload(BaseModel):
    user_id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = ""
    city: Optional[str] = "Colombia"
    department: Optional[str] = ""
    country: Optional[str] = "Colombia"
    headline: Optional[str] = "Técnico de Soporte TI"
    target_role: Optional[str] = "Técnico de Soporte TI"
    summary: Optional[str] = ""
    english_level: Optional[str] = "B2"
    linkedin: Optional[str] = ""
    salary_min_cop: Optional[int] = 2500000
    salary_max_cop: Optional[int] = 4000000
    remote_only: Optional[bool] = True
    technical_skills: Optional[Dict[str, Any]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    languages: Optional[List[Dict[str, Any]]] = None


@router.post("/upload")
async def upload_and_transform_cv(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload an existing CV (PDF, Word .docx, TXT), extract all structured sections,
    and immediately convert it into an optimized ATS-Compliant PDF and Word document.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    allowed = [".pdf", ".docx", ".doc", ".txt"]
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no compatible ({ext}). Por favor sube un archivo PDF (.pdf) o Word (.docx)."
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="El archivo subido está vacío.")

    # 1. Extract text and parse
    raw_text = CVTransformer.extract_text(content, file.filename)
    if not raw_text or len(raw_text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer texto legible del documento. Asegúrate de que no sea una imagen escaneada sin texto seleccionable."
        )

    parsed = CVTransformer.parse_resume_text(raw_text)

    # 2. Assign unique ID and generate ATS files
    clean_name = re.sub(r"[^\w]", "_", parsed.get("name", "Candidato")[:12].strip())
    unique_tag = uuid.uuid4().hex[:6]
    pdf_filename = f"ATS-{clean_name}-{unique_tag}.pdf"
    docx_filename = f"ATS-{clean_name}-{unique_tag}.docx"

    pdf_path = CV_DIR / pdf_filename
    docx_path = CV_DIR / docx_filename

    CVTransformer.generate_ats_pdf(parsed, pdf_path)
    CVTransformer.generate_ats_docx(parsed, docx_path)

    # 3. If user is logged in, optionally save/merge into their user_profile
    if user_id:
        repo = Repository(db)
        repo.upsert_user_profile({
            "user_id": user_id,
            "email": parsed.get("email") or "",
            "full_name": parsed.get("name") or "Candidato",
            "phone": parsed.get("phone") or "",
            "city": parsed.get("city") or "Colombia",
            "department": parsed.get("department") or "",
            "country": parsed.get("country") or "Colombia",
            "target_role": parsed.get("target_role") or "Técnico de Soporte TI",
            "headline": parsed.get("headline") or "Técnico de Soporte TI",
            "summary": parsed.get("summary") or "",
            "english_level": parsed.get("english_level") or "B2",
            "salary_min_cop": parsed.get("salary_min_cop") or 2500000,
            "salary_max_cop": parsed.get("salary_max_cop") or 4000000,
            "remote_only": parsed.get("remote_only", True),
            "technical_skills": parsed.get("technical_skills") or {},
            "experience": parsed.get("experience") or [],
            "education": parsed.get("education") or [],
            "certifications": parsed.get("certifications") or [],
            "languages": parsed.get("languages") or []
        })

    return {
        "status": "SUCCESS",
        "message": "Hoja de vida analizada y convertida a estándar ATS con éxito.",
        "parsed_profile": parsed,
        "pdf_filename": pdf_filename,
        "docx_filename": docx_filename,
        "pdf_download_url": f"/api/cv/download/{pdf_filename}",
        "docx_download_url": f"/api/cv/download/{docx_filename}",
        "text_preview": raw_text[:300] + "..." if len(raw_text) > 300 else raw_text
    }


@router.post("/generate")
def generate_custom_ats_cv(payload: GenerateCvPayload, db: Session = Depends(get_db)):
    """
    Generates tailored ATS PDF and DOCX documents from structured form inputs.
    """
    profile_dict = payload.dict()
    clean_name = re.sub(r"[^\w]", "_", profile_dict.get("name", "Candidato")[:12].strip())
    unique_tag = uuid.uuid4().hex[:6]
    pdf_filename = f"ATS-{clean_name}-{unique_tag}.pdf"
    docx_filename = f"ATS-{clean_name}-{unique_tag}.docx"

    pdf_path = CV_DIR / pdf_filename
    docx_path = CV_DIR / docx_filename

    CVTransformer.generate_ats_pdf(profile_dict, pdf_path)
    CVTransformer.generate_ats_docx(profile_dict, docx_path)

    # Save to user profile if user_id is provided
    if payload.user_id:
        repo = Repository(db)
        repo.upsert_user_profile({
            "user_id": payload.user_id,
            "email": payload.email,
            "full_name": payload.name,
            "phone": payload.phone or "",
            "city": payload.city or "Colombia",
            "department": payload.department or "",
            "country": payload.country or "Colombia",
            "target_role": payload.target_role or "Técnico de Soporte TI",
            "headline": payload.headline or payload.target_role,
            "summary": payload.summary or "",
            "english_level": payload.english_level or "B2",
            "salary_min_cop": payload.salary_min_cop or 2500000,
            "salary_max_cop": payload.salary_max_cop or 4000000,
            "remote_only": payload.remote_only if payload.remote_only is not None else True,
            "technical_skills": payload.technical_skills or {},
            "experience": payload.experience or [],
            "education": payload.education or [],
            "certifications": payload.certifications or [],
            "languages": payload.languages or []
        })

    return {
        "status": "SUCCESS",
        "message": "Hoja de vida ATS generada correctamente.",
        "pdf_filename": pdf_filename,
        "docx_filename": docx_filename,
        "pdf_download_url": f"/api/cv/download/{pdf_filename}",
        "docx_download_url": f"/api/cv/download/{docx_filename}"
    }


@router.get("/download/{filename}")
def download_cv_file(filename: str):
    """Securely downloads generated ATS files (PDF or DOCX)."""
    clean_fn = Path(filename).name  # Prevent directory traversal
    target = CV_DIR / clean_fn
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    media_type = "application/pdf" if clean_fn.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(
        path=str(target),
        media_type=media_type,
        filename=clean_fn,
        headers={"Content-Disposition": f'attachment; filename="{clean_fn}"'}
    )
