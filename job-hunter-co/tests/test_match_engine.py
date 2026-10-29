"""test_match_engine — motor de compatibilidad (Módulo 3).

El score es priorización interna; los tests validan reglas y banderas,
no veredictos.
"""

from tests.helpers import make_job


def _job(**overrides):
    payload = dict(
        source="spe",
        external_id="x1",
        company="Acme",
        title="Técnico de Soporte TI",
        url="https://example.com/1",
        location="Valledupar, Cesar",
        description=(
            "Soporte técnico presencial y remoto. Instalación y configuración "
            "de sistemas operativos Windows y Linux, diagnóstico y solución de "
            "fallas de hardware y software, mantenimiento preventivo y "
            "correctivo, impresoras, redes básicas, soporte remoto con AnyDesk."
        ),
        requirements=["Formación técnica", "1 año de experiencia"],
    )
    payload.update(overrides)
    return make_job(**payload)


def test_perfect_job_high_priority(real_matcher):
    result = real_matcher.match(_job())
    assert result.priority == "HIGH"
    assert result.score >= 75
    assert "does_not_meet_required_requirement" not in result.flags
    assert "windows" in result.matched_skills


def test_accepts_dict_input(real_matcher):
    result = real_matcher.match(_job().model_dump())
    assert result.score > 0


def test_score_bounds_and_components(real_matcher):
    result = real_matcher.match(_job())
    assert 0.0 <= result.score <= 100.0
    assert set(result.components) == {
        "skills", "education", "experience", "location", "role_keywords"
    }


def test_senior_title_is_penalized(real_matcher):
    result = real_matcher.match(
        _job(title="Ingeniero Senior de Soporte TI")
    )
    assert "seniority_mismatch" in result.flags
    assert result.priority == "LOW"
    assert "does_not_meet_required_requirement" in result.flags


def test_location_valuedupar_beats_bogota(real_matcher):
    local = real_matcher.match(_job())
    capital = real_matcher.match(_job(location="Bogotá D.C."))
    assert local.score > capital.score
    assert local.components["location"] == 1.0
    assert capital.components["location"] == 0.2


def test_remote_job_location(real_matcher):
    result = real_matcher.match(_job(location="Colombia (remoto)"))
    assert result.components["location"] == 0.9


def test_job_with_no_it_skills_capped_to_review(real_matcher):
    result = real_matcher.match(
        _job(
            title="Auxiliar Administrativo",
            description="Funciones de archivo y correspondencia.",
            requirements=[],
            location="",
        )
    )
    assert "no_skills_detected" in result.flags
    assert result.priority == "REVIEW"


def test_missing_skills_reported(real_matcher):
    result = real_matcher.match(
        _job(
            description=(
                "Experiencia en Active Directory, Windows Server y soporte "
                "técnico a usuarios."
            )
        )
    )
    assert "active_directory" in result.missing_skills
    assert "windows_server" in result.missing_skills
    assert "soporte_tecnico" in result.matched_skills


def test_role_keyword_scoring(real_matcher):
    exact = real_matcher.match(_job())
    partial = real_matcher.match(_job(title="Persona para TI"))
    unrelated = real_matcher.match(_job(title="Vendedor de mostrador"))
    assert exact.components["role_keywords"] == 1.0
    assert partial.components["role_keywords"] == 0.6
    assert unrelated.components["role_keywords"] == 0.1
