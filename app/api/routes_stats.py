import json
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.storage.database import get_db
from app.storage.repository import Repository

from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/stats", tags=["Dashboard & Analytics"])


class SearchPreferencesPayload(BaseModel):
    country: Optional[str] = "Colombia"
    region: Optional[str] = "Cesar"
    city: Optional[str] = "Valledupar"
    remote: Optional[bool] = True
    willing_to_relocate: Optional[bool] = True
    keywords: Optional[str] = "soporte TI sistemas"
    min_salary: Optional[float] = 1500000
    desired_salary: Optional[float] = 2200000


@router.get("/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    repo = Repository(db)
    return repo.get_dashboard_stats()


@router.get("/profile")
def get_profile():
    base_dir = Path(__file__).resolve().parent.parent.parent
    with open(base_dir / "data" / "profile.json", "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/preferences")
def get_preferences():
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
        "min_salary": 1500000,
        "desired_salary": 2200000,
        "currency": "COP"
    })
    prefs["min_salary"] = salary_prefs.get("min_salary", 1500000)
    prefs["desired_salary"] = salary_prefs.get("desired_salary", 2200000)
    return prefs


@router.put("/preferences")
def update_preferences(payload: SearchPreferencesPayload):
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

