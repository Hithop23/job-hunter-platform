import re
from typing import Tuple

# English indicator words common in job postings
ENGLISH_KEYWORDS = {
    "requirements", "responsibilities", "experience", "we are looking for",
    "must have", "nice to have", "support", "skills", "troubleshooting",
    "customer", "team", "engineer", "remote", "full-time", "benefits",
    "qualifications", "developer", "administrator", "communication",
    "years of experience", "competitive salary", "working hours",
    "about the role", "what you will do", "what we offer", "key responsibilities",
    "specialist", "position", "applicant", "work from home", "contractor"
}

# Spanish indicator words common in job postings
SPANISH_KEYWORDS = {
    "requisitos", "funciones", "experiencia", "conocimientos", "responsabilidades",
    "buscamos", "empresa", "salario", "tiempo completo", "técnico", "tecnico",
    "sistemas", "soporte", "carrera administrativa", "prestaciones de ley",
    "perfil requerido", "horario de trabajo", "postularse", "contrato",
    "bachiller", "sena", "convocatoria", "auxilio", "mantenimiento", "redes",
    "aprendiz", "mesa de ayuda", "vacante", "oferta", "atención", "atencion",
    "computador", "equipos", "impresoras", "teleinformático", "teleinformatico"
}

# Sources that are strictly English/Global by default
GLOBAL_SOURCES = {"remoteok", "weworkremotely", "arbeitnow"}

# Sources that are strictly Spanish/Colombian by default
COLOMBIAN_SOURCES = {"sena", "cnsc", "spe", "computrabajo"}


def detect_job_language(
    title: str = "",
    description: str = "",
    requirements: str = "",
    location: str = "",
    source: str = ""
) -> str:
    """
    Detects if the vacancy is in English ('en') or Spanish ('es').
    Uses source defaults, location cues, and token frequency analysis.
    """
    source_lower = (source or "").lower()
    full_text = f"{title} {description} {requirements}".lower()
    loc_lower = (location or "").lower()

    # 1. Check source origin baseline
    if source_lower in COLOMBIAN_SOURCES:
        return "es"

    # 2. Definitive Colombian / Latin American indicators
    if any(k in loc_lower for k in ["colombia", "valledupar", "bogota", "bogotá", "medellin", "medellín", "cesar", "cali"]):
        if not ("bilingual" in full_text or "english b2" in full_text or "bilingüe" in full_text):
            return "es"

    # 3. Check for Colombian business suffixes in text (S.A.S., SAS, LTDA)
    if re.search(r"\b(s\.?a\.?s\.?|ltda)\b", full_text):
        return "es"

    # 4. Characteristic Spanish accented vowels and ñ
    spanish_accents_count = len(re.findall(r"[áéíóúñ¿¡]", full_text))

    # 5. Frequency count of linguistic keywords
    en_count = sum(1 for kw in ENGLISH_KEYWORDS if kw in full_text)
    es_count = sum(1 for kw in SPANISH_KEYWORDS if kw in full_text) + (spanish_accents_count * 2)

    # 6. Global source baseline
    if source_lower in GLOBAL_SOURCES:
        if es_count > en_count + 3:
            return "es"
        return "en"

    # 7. Location cues for US / UK / Worldwide
    if any(k in loc_lower for k in ["worldwide", "united states", "usa", "uk", "remote / global", "europe", "canada"]):
        return "en"

    # 8. Token score comparison
    if es_count > en_count:
        return "es"
    elif en_count > es_count:
        return "en"

    # Default to Spanish if in Colombia context or unknown local context, English if global keywords
    if "remote" in loc_lower or "worldwide" in loc_lower:
        return "en"

    return "es"


def classify_job_archetype(title: str = "", description: str = "") -> str:
    """
    Classifies job into an archetype to prioritize matching skills in the CV.
    Returns:
    - 'it_support': Help Desk, Service Desk, Desktop Support, PC technician.
    - 'sysadmin': Linux, Network, Infrastructure, Cloud, DevOps, Endpoint Security.
    - 'software_data': Python, Java, Automation, Data analysis.
    - 'general': General IT support.
    """
    text = f"{title} {description}".lower()

    if any(k in text for k in ["python", "pandas", "data analyst", "developer", "backend", "software", "programador"]):
        return "software_data"

    if any(k in text for k in ["sysadmin", "system administrator", "linux", "devops", "cloud", "infra", "redes", "network"]):
        return "sysadmin"

    if any(k in text for k in ["help desk", "helpdesk", "service desk", "soporte", "support", "desktop", "mesas de ayuda", "tecnico"]):
        return "it_support"

    return "general"
