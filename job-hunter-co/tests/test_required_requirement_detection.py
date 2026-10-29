"""test_required_requirement_detection — requisitos obligatorios (Módulo 3).

Si el candidato no cumple un requisito obligatorio, la vacante queda
marcada does_not_meet_required_requirement y NO se prioriza.
"""

from tests.helpers import make_job


def _job(**overrides):
    payload = dict(
        source="sena",
        external_id="r1",
        company="Beta S.A.S.",
        title="Técnico de Soporte TI",
        url="https://example.com/r1",
        location="Valledupar, Cesar",
        description="Soporte técnico a usuarios, Windows, impresoras, redes.",
        requirements=[],
    )
    payload.update(overrides)
    return make_job(**payload)


def test_professional_degree_required(real_matcher):
    result = real_matcher.match(
        _job(
            description=(
                "Se requiere título profesional en ingeniería de sistemas. "
                "Soporte a usuarios, Windows, impresoras."
            )
        )
    )
    assert "education_not_met" in result.flags
    assert "does_not_meet_required_requirement" in result.flags
    assert result.priority == "LOW"


def test_engineer_title_implies_degree(real_matcher):
    result = real_matcher.match(_job(title="Ingeniero de Soporte"))
    assert "education_not_met" in result.flags
    assert result.priority == "LOW"


def test_technologist_required_not_met(real_matcher):
    result = real_matcher.match(
        _job(requirements=["Tecnólogo en sistemas o afines"])
    )
    assert "education_not_met" in result.flags
    assert result.priority == "LOW"


def test_technician_or_technologist_accepted(real_matcher):
    result = real_matcher.match(
        _job(requirements=["Formación técnica o tecnológica en sistemas"])
    )
    assert "education_not_met" not in result.flags
    assert result.priority == "HIGH"


def test_experience_years_required(real_matcher):
    too_senior = real_matcher.match(
        _job(requirements=["Mínimo 5 años de experiencia en soporte TI"])
    )
    assert "experience_not_met" in too_senior.flags
    assert too_senior.required_years == 5
    assert too_senior.priority == "LOW"

    reachable = real_matcher.match(
        _job(requirements=["1 año de experiencia en soporte TI"])
    )
    assert "experience_not_met" not in reachable.flags
    assert reachable.priority == "HIGH"


def test_hard_certification_required(real_matcher):
    result = real_matcher.match(
        _job(
            description=(
                "Soporte técnico, Windows, impresoras. Certificación CCNA "
                "requerida para el cargo."
            )
        )
    )
    assert "certification_not_met" in result.flags
    assert result.priority == "LOW"


def test_soft_certification_capped_to_review(real_matcher):
    result = real_matcher.match(
        _job(
            description=(
                "Soporte técnico, Windows, impresoras, redes. "
                "Conocimientos de redes y CCNA se valoran."
            )
        )
    )
    assert "certification_mentioned_not_held" in result.flags
    assert "certification_not_met" not in result.flags
    assert result.priority == "REVIEW"


def test_english_level_required(real_matcher):
    c1 = real_matcher.match(
        _job(description="Soporte técnico, Windows. Se requiere inglés C1.")
    )
    assert "language_not_met" in c1.flags
    assert c1.priority == "LOW"

    b2 = real_matcher.match(
        _job(description="Soporte técnico, Windows. Se requiere inglés B2.")
    )
    assert "language_not_met" not in b2.flags
    assert b2.priority == "HIGH"


def test_held_certification_not_flagged(real_matcher):
    result = real_matcher.match(
        _job(
            description=(
                "Soporte técnico, Windows, impresoras. Formación en "
                "endpoint security será valorada."
            )
        )
    )
    assert not any("certification" in f for f in result.flags)
