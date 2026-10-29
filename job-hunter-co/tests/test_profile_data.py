"""Carga y consistencia de los archivos de datos reales (Módulo 1)."""

from app.config import PROJECT_ROOT
from app.matching.profile import (
    load_companies,
    load_keywords,
    load_profile,
    validate_taxonomy_against_profile,
)


def _profile():
    return load_profile(PROJECT_ROOT / "data" / "profile.json")


def _keywords():
    return load_keywords(PROJECT_ROOT / "data" / "keywords.json")


def test_profile_loads_real_data():
    profile = _profile()
    assert profile.name == "Julian David Diaz Medina"
    assert profile.education_level == "técnico"
    assert profile.city == "Valledupar"
    assert profile.experience_years_it == 2.5
    assert len(profile.experience) == 3
    assert len(profile.certifications) == 6
    assert any(
        lang.language == "Inglés" and lang.level == "B2"
        for lang in profile.languages
    )


def test_taxonomy_never_claims_skills_missing_from_profile():
    """Salvaguarda anti-información-falsa (Módulo 4)."""
    violations = validate_taxonomy_against_profile(_keywords(), _profile())
    assert violations == [], f"Skills declaradas sin respaldo en el CV: {violations}"


def test_companies_starts_empty_until_user_adds_real_urls():
    companies = load_companies(PROJECT_ROOT / "data" / "companies.json")
    assert companies == []


def test_weights_from_settings(settings):
    total = (
        settings.skill_weight
        + settings.education_weight
        + settings.experience_weight
        + settings.location_weight
        + settings.keyword_weight
    )
    assert abs(total - 1.0) < 1e-9
