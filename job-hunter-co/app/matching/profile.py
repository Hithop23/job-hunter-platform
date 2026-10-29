"""Carga de profile.json, keywords.json y companies.json (Módulos 1, 3 y 8).

Los datos del candidato provienen ÚNICAMENTE de su hoja de vida real.
Nunca se inventa experiencia, títulos, certificaciones ni habilidades.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field


def normalize_text(text: str) -> str:
    """Minúsculas sin tildes: base para comparar términos en español."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


class Contact(BaseModel):
    phone: str = ""
    email: str = ""
    linkedin: str = ""


class EducationEntry(BaseModel):
    degree: str
    institution: str
    dates: str = ""
    location: str = ""
    details: str = ""


class CertificationEntry(BaseModel):
    name: str
    issuer: str = ""
    date: str = ""
    hours: int | None = None


class ExperienceEntry(BaseModel):
    role: str
    company: str
    dates: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class LanguageEntry(BaseModel):
    language: str
    level: str


class ProfileData(BaseModel):
    name: str
    headline: str = ""
    location: str = ""
    city: str = ""
    department: str = ""
    country: str = ""
    contact: Contact = Field(default_factory=Contact)
    professional_summary: str = ""
    education_level: str = ""
    experience_years_it: float = 0.0
    target_roles: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    languages: list[LanguageEntry] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    achieved_metrics: list[str] = Field(default_factory=list)


class SkillEntry(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    profile: bool = False


class CertificationTaxEntry(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    held: bool = False


class Company(BaseModel):
    name: str
    careers_url: str = ""
    ats: str = "custom"
    board: str = ""
    enabled: bool = False


class KeywordsData(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    seniority_exclusions: list[str] = Field(default_factory=list)
    partial_title_terms: list[str] = Field(default_factory=list)
    skill_taxonomy: list[SkillEntry] = Field(default_factory=list)
    certification_taxonomy: list[CertificationTaxEntry] = Field(default_factory=list)
    education_terms: dict[str, list[str]] = Field(default_factory=dict)
    english_levels: dict[str, int] = Field(default_factory=dict)


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Archivo de datos no encontrado: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_profile(path: Path) -> ProfileData:
    data = _read_json(path)
    data.pop("_instrucciones", None)
    return ProfileData.model_validate(data)


def load_keywords(path: Path) -> KeywordsData:
    data = _read_json(path)
    data.pop("_instrucciones", None)
    return KeywordsData.model_validate(data)


def load_companies(path: Path) -> list[Company]:
    data = _read_json(path)
    return [
        Company.model_validate(entry)
        for entry in data.get("companies", [])
        if isinstance(entry, dict) and entry.get("name")
    ]


def profile_text(profile: ProfileData) -> str:
    """Serializa todo el perfil a texto normalizado (para validaciones)."""
    return normalize_text(json.dumps(profile.model_dump(), ensure_ascii=False))


def validate_taxonomy_against_profile(
    keywords: KeywordsData, profile: ProfileData
) -> list[str]:
    """Devuelve habilidades marcadas profile=true que NO constan en el perfil.

    Es la salvaguarda contra información falsa (Módulo 4): si una skill del
    taxonomy dice que el candidato la tiene, debe existir en profile.json.
    """
    text = profile_text(profile)
    violations: list[str] = []
    for skill in keywords.skill_taxonomy:
        if not skill.profile:
            continue
        aliases = [normalize_text(a) for a in skill.aliases]
        if not any(a and a in text for a in aliases):
            violations.append(skill.name)
    return violations
