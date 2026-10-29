"""Motor de compatibilidad JobMatcher (Módulo 3).

El match_score es un mecanismo INTERNO de priorización: nunca se presenta
como evaluación definitiva. Reglas:
  - score >= high_priority_threshold  -> alta prioridad
  - score >= review_threshold        -> revisión
  - score <  review_threshold        -> no priorizar
  - requisito obligatorio incumplido -> flag does_not_meet_required_requirement
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping

from pydantic import BaseModel, Field

from app.config import Settings
from app.matching.profile import (
    KeywordsData,
    ProfileData,
    normalize_text,
)
from app.schemas import NormalizedJob

logger = logging.getLogger("jobhunter.matching")

HARD_FLAGS = {
    "education_not_met",
    "experience_not_met",
    "certification_not_met",
    "language_not_met",
    "seniority_mismatch",
}
SOFT_CAP_FLAGS = {"certification_mentioned_not_held", "no_skills_detected"}

_EDUCATION_ORDER = ["bachiller", "tecnico", "tecnologo", "profesional"]
_TECHNICIAN_LEVEL = 1  # índice de "técnico" en _EDUCATION_ORDER
_REMOTE_TERMS = [
    "remoto", "teletrabajo", "trabajo desde casa", "home office",
    "100% remota", "virtual",
]
_YEAR_PATTERNS = [
    r"(\d+)\s*\+?\s*anos?\s*(?:de\s*)?experiencia",
    r"minimo\s+(\d+)\s*anos?",
    r"experiencia(?:\s*minima)?(?:\s*de)?\s*(\d+)\s*anos?",
    r"(\d+)\s*anos?\s+en\s+",
]
_HARD_CERT_MARKERS = ("certificaci", "requer", "exig", "obligator", "debe contar")


class MatchResult(BaseModel):
    score: float
    priority: str
    flags: list[str] = Field(default_factory=list)
    components: dict[str, float] = Field(default_factory=dict)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    required_years: int | None = None


class JobMatcher:
    """Computa la compatibilidad de una vacante contra el perfil real."""

    def __init__(
        self, profile: ProfileData, keywords: KeywordsData, settings: Settings
    ) -> None:
        self.profile = profile
        self.keywords = keywords
        self.settings = settings

        self._skill_index = [
            (
                entry.name,
                {normalize_text(a) for a in entry.aliases if a},
                entry.profile,
            )
            for entry in keywords.skill_taxonomy
        ]
        self._cert_index = [
            (
                entry.name,
                {normalize_text(entry.name)} | {normalize_text(a) for a in entry.aliases if a},
                entry.held,
            )
            for entry in keywords.certification_taxonomy
        ]
        self._role_patterns = [
            normalize_text(role) for role in keywords.target_roles if role
        ]
        self._partial_terms = [
            normalize_text(t).strip()
            for t in keywords.partial_title_terms
            if t and t.strip()
        ]
        self._seniority_terms = [
            normalize_text(t) for t in keywords.seniority_exclusions if t
        ]
        self._education_terms = {
            level: {normalize_text(t) for t in terms}
            for level, terms in keywords.education_terms.items()
        }
        self._english_levels = {
            normalize_text(k): v for k, v in keywords.english_levels.items()
        }
        self._profile_english_level = self._detect_profile_english_level()

    # ------------------------------------------------------------------ API

    def match(self, job: NormalizedJob | Mapping[str, Any]) -> MatchResult:
        if isinstance(job, NormalizedJob):
            data: dict[str, Any] = job.model_dump()
        else:
            data = dict(job)

        title = normalize_text(str(data.get("title") or ""))
        location = normalize_text(str(data.get("location") or ""))
        requirements = data.get("requirements") or []
        if isinstance(requirements, str):
            requirements = [requirements]
        req_text = normalize_text(" ".join(str(r) for r in requirements))
        description = normalize_text(str(data.get("description") or ""))
        body = f"{title} {description} {req_text} {location}"

        flags: list[str] = []
        components: dict[str, float] = {}

        components["skills"], matched, missing, skill_flags = self._skills(body)
        flags.extend(skill_flags)

        req_body = f"{description} {req_text} {location}"
        components["education"], edu_flags = self._education(req_body, title)
        flags.extend(edu_flags)

        components["experience"], required_years, exp_flags = self._experience(body)
        flags.extend(exp_flags)

        components["location"] = self._location(location)

        components["role_keywords"] = self._role(title)

        if any(term in title for term in self._seniority_terms):
            flags.append("seniority_mismatch")

        flags.extend(self._certifications(body))
        flags.extend(self._language(body))

        raw = 100.0 * (
            self.settings.skill_weight * components["skills"]
            + self.settings.education_weight * components["education"]
            + self.settings.experience_weight * components["experience"]
            + self.settings.location_weight * components["location"]
            + self.settings.keyword_weight * components["role_keywords"]
        )
        if "seniority_mismatch" in flags:
            raw *= 0.5
        score = round(min(100.0, max(0.0, raw)), 1)

        hard = [f for f in flags if f in HARD_FLAGS]
        if hard and "does_not_meet_required_requirement" not in flags:
            flags.append("does_not_meet_required_requirement")

        soft_capped = any(f in SOFT_CAP_FLAGS for f in flags)
        if hard:
            priority = "LOW"
        elif score >= self.settings.high_priority_threshold and not soft_capped:
            priority = "HIGH"
        elif score >= self.settings.review_threshold:
            priority = "REVIEW"
        else:
            priority = "LOW"

        # El orden de los flags se conserva; does_not... queda al final.
        return MatchResult(
            score=score,
            priority=priority,
            flags=flags,
            components={k: round(v, 3) for k, v in components.items()},
            matched_skills=matched,
            missing_skills=missing,
            required_years=required_years,
        )

    def match_row(self, row: Any) -> MatchResult:
        """Matchea una fila ORM Job (usado por el runner tras el escaneo)."""
        return self.match(
            {
                "title": row.title,
                "description": row.description,
                "requirements": row.requirements or [],
                "location": row.location or "",
                "company": row.company,
            }
        )

    # ------------------------------------------------------------ internals

    def _skills(self, body: str) -> tuple[float, list[str], list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        for name, aliases, held in self._skill_index:
            if name in body or any(a in body for a in aliases):
                matched.append(name) if held else missing.append(name)
        if not matched and not missing:
            return 0.5, [], [], ["no_skills_detected"]
        found = len(matched) + len(missing)
        return len(matched) / found, matched, missing, []

    def _education(self, req_body: str, title: str) -> tuple[float, list[str]]:
        """Nivel educativo exigido (solo en requisitos/descripción).

        El título del cargo "Ingeniero..." implica grado profesional.
        """
        if "ingenier" in title:
            return 0.0, ["education_not_met"]
        mentioned = [
            level
            for level in _EDUCATION_ORDER
            if any(term in req_body for term in self._education_terms.get(level, ()))
        ]
        if not mentioned:
            return 1.0, []
        required_level = min(_EDUCATION_ORDER.index(level) for level in set(mentioned))
        if required_level <= _TECHNICIAN_LEVEL:
            return 1.0, []
        return 0.0, ["education_not_met"]

    def _experience(self, body: str) -> tuple[float, int | None, list[str]]:
        required = None
        for pattern in _YEAR_PATTERNS:
            for match in re.finditer(pattern, body):
                value = int(match.group(1))
                required = value if required is None else max(required, value)
        if required is None:
            return 1.0, None, []
        have = self.profile.experience_years_it
        if required <= have:
            return 1.0, required, []
        score = max(0.0, have / required)
        if required > have + 0.5:
            return score, required, ["experience_not_met"]
        return score, required, []

    def _location(self, location: str) -> float:
        if not location:
            return 0.5
        if "valledupar" in location or "cesar" in location:
            return 1.0
        if any(term in location for term in _REMOTE_TERMS):
            return 0.9
        return 0.2

    def _role(self, title: str) -> float:
        for pattern in self._role_patterns:
            if pattern in title:
                return 1.0
        for term in self._partial_terms:
            if re.search(rf"\b{re.escape(term)}\b", title):
                return 0.6
        return 0.1

    def _certifications(self, body: str) -> list[str]:
        sentences = [s for s in re.split(r"[.;\n|•]", body) if s]
        flags: list[str] = []
        for name, names, held in self._cert_index:
            if held or not any(n in body for n in names):
                continue
            hard = any(
                any(n in sentence for n in names)
                and any(marker in sentence for marker in _HARD_CERT_MARKERS)
                for sentence in sentences
            )
            flags.append("certification_not_met" if hard else "certification_mentioned_not_held")
            _ = name
        return flags

    def _language(self, body: str) -> list[str]:
        match = re.search(r"ingles\s+([a-z0-9]+)", body)
        if not match:
            return []
        required = self._english_levels.get(match.group(1))
        if required is None:
            return []
        if required > self._profile_english_level:
            return ["language_not_met"]
        return []

    def _detect_profile_english_level(self) -> int:
        for language in self.profile.languages:
            if normalize_text(language.language) == "ingles":
                return self._english_levels.get(
                    normalize_text(language.level), 3
                )
        return 0
