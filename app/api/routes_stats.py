import json
from pathlib import Path
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.storage.database import get_db
from app.storage.repository import Repository

from typing import Optional, Dict, Any, List
from pydantic import BaseModel

router = APIRouter(prefix="/api/stats", tags=["Dashboard & Analytics"])


class SearchPreferencesPayload(BaseModel):
    country: Optional[str] = "Colombia"
    region: Optional[str] = "Cesar"
    city: Optional[str] = "Valledupar"
    remote: Optional[bool] = True
    willing_to_relocate: Optional[bool] = True
    keywords: Optional[str] = "soporte TI sistemas"
    min_salary: Optional[float] = 2500000
    desired_salary: Optional[float] = 3500000


class UserProfilePayload(BaseModel):
    user_id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    city: Optional[str] = "Valledupar"
    department: Optional[str] = "Cesar"
    country: Optional[str] = "Colombia"
    target_role: Optional[str] = "Técnico de Soporte TI / Sistemas"
    headline: Optional[str] = None
    summary: Optional[str] = None
    english_level: Optional[str] = "B2"
    salary_min_cop: Optional[int] = 2500000
    salary_max_cop: Optional[int] = 4000000
    remote_only: Optional[bool] = True
    technical_skills: Optional[Dict[str, Any]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None


@router.get("/dashboard")
def get_dashboard_metrics(user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    repo = Repository(db)
    return repo.get_dashboard_stats(user_id=user_id)


@router.get("/profile")
def get_profile(user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if user_id:
        repo = Repository(db)
        up = repo.get_user_profile(user_id)
        if up:
            def parse_json(val, fallback):
                if not val:
                    return fallback
                if isinstance(val, (dict, list)):
                    return val
                try:
                    return json.loads(val)
                except Exception:
                    return fallback

            return {
                "user_id": up.user_id,
                "email": up.email,
                "name": up.full_name,
                "phone": up.phone or "",
                "city": up.city or "Valledupar",
                "department": up.department or "Cesar",
                "country": up.country or "Colombia",
                "location": f"{up.city or 'Valledupar'}, {up.department or 'Cesar'}, {up.country or 'Colombia'}",
                "target_role": up.target_role or "Técnico en Sistemas Teleinformáticos",
                "headline": up.headline or f"{up.target_role} | Bilingüe B2",
                "summary": up.summary or "",
                "english_level": up.english_level or "B2",
                "salary_min_cop": up.salary_min_cop or 2500000,
                "salary_max_cop": up.salary_max_cop or 4000000,
                "remote_only": up.remote_only,
                "technical_skills": parse_json(up.technical_skills, {}),
                "experience": parse_json(up.experience, []),
                "education": parse_json(up.education, [])
            }

    # Baseline profile.json
    base_dir = Path(__file__).resolve().parent.parent.parent
    p_path = base_dir / "data" / "profile.json"
    if p_path.exists():
        with open(p_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "name": "Candidato",
        "email": "",
        "phone": "",
        "target_role": "Soporte TI / Sistemas",
        "english_level": "B2",
        "salary_min_cop": 2500000
    }


@router.post("/profile")
def save_profile(payload: UserProfilePayload, db: Session = Depends(get_db)):
    repo = Repository(db)
    saved = repo.upsert_user_profile(payload.dict())
    return {
        "status": "SUCCESS",
        "message": f"Perfil de {saved.full_name} guardado correctamente.",
        "user_id": saved.user_id,
        "profile": {
            "name": saved.full_name,
            "email": saved.email,
            "headline": saved.headline,
            "target_role": saved.target_role,
            "english_level": saved.english_level,
            "salary_min_cop": saved.salary_min_cop
        }
    }


@router.get("/preferences")
def get_preferences(user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if user_id:
        repo = Repository(db)
        up = repo.get_user_profile(user_id)
        if up:
            return {
                "country": up.country or "Colombia",
                "region": up.department or "Cesar",
                "city": up.city or "Valledupar",
                "remote": up.remote_only,
                "willing_to_relocate": True,
                "keywords": up.target_role or "soporte TI sistemas",
                "min_salary": up.salary_min_cop or 2500000,
                "desired_salary": up.salary_max_cop or 3500000
            }

    base_dir = Path(__file__).resolve().parent.parent.parent
    with open(base_dir / "data" / "profile.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    prefs = data.get("search_preferences", {
        "country": "Colombia",
        "region": "Cesar",
        "city": "Valledupar",
        "remote": True,
        "willing_to_relocate": True,
        "keywords": "soporte TI sistemas"
    })
    salary_prefs = data.get("salary_preferences", {
        "min_salary": 2500000,
        "desired_salary": 3500000,
        "currency": "COP"
    })
    prefs["min_salary"] = salary_prefs.get("min_salary", 2500000)
    prefs["desired_salary"] = salary_prefs.get("desired_salary", 3500000)
    return prefs


@router.put("/preferences")
def update_preferences(payload: SearchPreferencesPayload, user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if user_id:
        repo = Repository(db)
        repo.upsert_user_profile({
            "user_id": user_id,
            "country": payload.country,
            "department": payload.region,
            "city": payload.city,
            "remote_only": payload.remote,
            "target_role": payload.keywords,
            "salary_min_cop": int(payload.min_salary or 2500000),
            "salary_max_cop": int(payload.desired_salary or 3500000)
        })

    base_dir = Path(__file__).resolve().parent.parent.parent
    p_path = base_dir / "data" / "profile.json"
    with open(p_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    data["search_preferences"] = {
        "country": payload.country,
        "region": payload.region,
        "city": payload.city,
        "remote": payload.remote,
        "willing_to_relocate": payload.willing_to_relocate,
        "keywords": payload.keywords,
    }
    if "salary_preferences" not in data:
        data["salary_preferences"] = {}
    if payload.min_salary is not None:
        data["salary_preferences"]["min_salary"] = payload.min_salary
    if payload.desired_salary is not None:
        data["salary_preferences"]["desired_salary"] = payload.desired_salary
    data["salary_preferences"]["currency"] = "COP"

    if payload.city and payload.region and payload.country:
        data["location"] = f"{payload.city}, {payload.region}, {payload.country}"
    
    with open(p_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return {
        "message": "Preferencias de búsqueda, ubicación y salario guardadas correctamente.",
        "preferences": data["search_preferences"],
        "salary_preferences": data["salary_preferences"]
    }
