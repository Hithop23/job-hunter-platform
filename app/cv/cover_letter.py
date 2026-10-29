import json
from pathlib import Path
from typing import Optional

from app.cv.language_detector import detect_job_language


class CoverLetterGenerator:
    """
    Generates tailored, concise cover letters (<250 words) in English ('en')
    or Spanish ('es') tailored strictly to Julian David Diaz Medina's verified background.
    """

    def __init__(self, profile_path: str = None, profile_en_path: str = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.profile_es_path = Path(profile_path) if profile_path else base_dir / "data" / "profile.json"
        self.profile_en_path = Path(profile_en_path) if profile_en_path else base_dir / "data" / "profile_en.json"

        with open(self.profile_es_path, "r", encoding="utf-8") as f:
            self.profile_es = json.load(f)

        if self.profile_en_path.exists():
            with open(self.profile_en_path, "r", encoding="utf-8") as f:
                self.profile_en = json.load(f)
        else:
            self.profile_en = self.profile_es

    def generate_letter(
        self,
        company: str,
        job_title: str,
        job_description: str = "",
        language: Optional[str] = None,
        location: str = "",
        source: str = ""
    ) -> str:
        """
        Generates a professional, targeted cover letter (under 250 words)
        in English ('en') or Spanish ('es').
        """
        if not language:
            language = detect_job_language(
                title=job_title,
                description=job_description,
                location=location,
                source=source
            )
        language = language.lower()
        if language not in ["en", "es"]:
            language = "es"

        profile = self.profile_en if language == "en" else self.profile_es
        name = profile["name"]
        phone = profile["phone"]
        email = profile["email"]
        loc = profile["location"]

        if language == "en":
            letter = f"""Dear Hiring Team at {company},

I am writing to express my strong interest in the {job_title} role at {company}. As an IT Support Technician with hands-on enterprise experience, I specialize in resolving hardware, software, and network issues across Windows and Linux environments.

During my technical tenure at Negocios e Inversiones SINGS S.A.S., I successfully resolved over 400 IT support tickets and configured more than 400 network peripherals and workstations with high user satisfaction. My background includes preventive hardware maintenance, OS standardization, remote assistance (AnyDesk, TeamViewer), Cisco Endpoint Security practices, and basic scripting with Python.

With full professional English proficiency (B2) and availability in the UTC-5 timezone, I am well-positioned to deliver reliable technical support and contribute to {company}'s distributed operational excellence.

Thank you for your time and consideration. I welcome the opportunity to discuss my qualifications in an interview.

Sincerely,

{name}
{phone} | {email}
{loc}"""
        else:
            letter = f"""Apreciado equipo de Selección y Talento Humano
{company}

Asunto: Postulación a la vacante de {job_title}

Me dirijo a ustedes con gran entusiasmo para presentar mi candidatura a la posición de {job_title} en {company}. Como Técnico en Sistemas Teleinformáticos egresado del SENA, cuento con experiencia comprobada en soporte técnico a usuarios, diagnóstico preventivo y correctivo de hardware y software, y administración de entornos operativos Windows y Linux.

En mi trayectoria práctica en Negocios e Inversiones SINGS S.A.S. atendí con éxito más de 400 incidencias técnicas y configuré dispositivos periféricos e impresoras en red, implementando buenas prácticas de documentación y soporte tanto presencial como remoto (AnyDesk, TeamViewer). Asimismo, dispongo de formación complementaria en seguridad de endpoints (Cisco), automatización con Python y sólidas competencias de comunicación y resolución de problemas.

Mi objetivo es aportar a {company} mi vocación de servicio, proactividad y rigor técnico para garantizar la continuidad operativa de sus estaciones de trabajo y sistemas TI, creciendo conjuntamente con su equipo de trabajo.

Agradezco de antemano su atención y quedo a su total disposición para ampliar los detalles de mi perfil en una entrevista.

Atentamente,

{name}
{phone} | {email}
{loc}"""

        # Word count safety guard (must be strictly <= 250 words)
        words = letter.split()
        if len(words) > 250:
            closing = "\n\nSincerely,\n" + name if language == "en" else "\n\nAtentamente,\n" + name
            letter = " ".join(words[:240]) + closing

        return letter
