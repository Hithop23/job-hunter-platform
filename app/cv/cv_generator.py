import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.cv.language_detector import detect_job_language, classify_job_archetype


# ---------------------------------------------------------------------------
# Archetype-specific dynamic content tables
# ---------------------------------------------------------------------------

# Each archetype entry defines:
#   headline_roles  – up to 3 role titles that form the dynamic headline
#   summary_opener  – opening clause of the professional summary
#   summary_focus   – what the summary emphasises for this archetype
#   top_bullets_idx – per experience index, which achievement indices matter most
#                     (0-based; listed first; rest appended in order)
ARCHETYPE_CONTENT = {
    "en": {
        "sysadmin": {
            "headline_roles": ["Junior Systems Administrator", "IT Infrastructure Technician", "Linux & Windows Support"],
            "summary_opener": "IT Systems Support Technician with solid infrastructure and systems administration experience.",
            "summary_focus": (
                "Proven hands-on expertise in deploying, configuring, and maintaining Windows and Linux environments, "
                "managing enterprise workstations, network connectivity, and delivering end-to-end technical solutions "
                "that keep critical systems operational. Skilled in OS deployment, network troubleshooting, endpoint "
                "hardening, and scripting for maintenance automation."
            ),
        },
        "software_data": {
            "headline_roles": ["Junior Technical Support Analyst", "IT Support & Automation Specialist", "Python & Systems Technician"],
            "summary_opener": "IT Support Technician with a strong foundation in software troubleshooting, automation scripting, and data tools.",
            "summary_focus": (
                "Experienced in diagnosing application and software issues in corporate environments, developing "
                "batch and Python automation scripts to streamline IT operations, and applying data-analysis skills "
                "with Pandas and NumPy. Familiar with Cisco endpoint security, generative AI tooling, and modern "
                "cloud productivity platforms."
            ),
        },
        "it_support": {
            "headline_roles": ["IT Support Technician", "Help Desk Analyst", "Technical Support Specialist"],
            "summary_opener": "Motivated IT & Systems Support Technician with corporate help-desk and end-user support experience.",
            "summary_focus": (
                "Proven expertise in diagnosing and resolving hardware, software, and connectivity issues, managing "
                "ticket lifecycles (400+ tickets resolved), configuring network peripherals, and delivering both "
                "on-site and remote technical assistance via AnyDesk and TeamViewer. Strong user-facing "
                "communication skills with English B2 proficiency."
            ),
        },
        "general": {
            "headline_roles": ["IT Support Technician", "Systems & Network Support", "Help Desk Junior"],
            "summary_opener": "IT & Systems Support Technician with hands-on corporate IT support experience.",
            "summary_focus": (
                "Proven expertise in diagnosing and troubleshooting hardware and software issues, installing and "
                "configuring Windows and Linux operating systems, managing network peripherals and printers, "
                "performing preventive and corrective maintenance, and delivering both on-site and remote technical "
                "assistance (AnyDesk, TeamViewer). Complementary training in Endpoint Security (Cisco), Python data "
                "analysis, and generative AI. English proficiency: B2 (Professional Working)."
            ),
        },
    },
    "es": {
        "sysadmin": {
            "headline_roles": ["Técnico Administrador de Sistemas Junior", "Soporte de Infraestructura TI", "Linux & Windows"],
            "summary_opener": "Técnico en Sistemas con experiencia en administración de infraestructura y soporte técnico empresarial.",
            "summary_focus": (
                "Habilidades comprobadas en despliegue, configuración y mantenimiento de entornos Windows y Linux, "
                "administración de estaciones de trabajo corporativas, conectividad de red y soluciones técnicas "
                "integrales. Conocimiento en endurecimiento de endpoints, scripting de automatización y gestión "
                "de activos TI."
            ),
        },
        "software_data": {
            "headline_roles": ["Analista de Soporte Técnico Junior", "Especialista en Automatización TI", "Técnico en Sistemas y Python"],
            "summary_opener": "Técnico en Sistemas con base sólida en resolución de fallas de software, scripting y herramientas de datos.",
            "summary_focus": (
                "Experiencia en diagnóstico de fallas de aplicaciones en entornos corporativos, desarrollo de scripts "
                "de automatización en Python y batch, y análisis de datos con Pandas y NumPy. Formación en seguridad "
                "de endpoints Cisco, IA generativa y plataformas cloud de productividad."
            ),
        },
        "it_support": {
            "headline_roles": ["Técnico en Soporte TI", "Analista Help Desk", "Especialista en Soporte Técnico"],
            "summary_opener": "Técnico en Sistemas con experiencia en soporte al usuario final y help desk corporativo.",
            "summary_focus": (
                "Habilidades en diagnóstico y resolución de incidentes de hardware, software y conectividad, "
                "gestión del ciclo de vida de tickets (más de 400 tickets resueltos), configuración de periféricos "
                "de red y asistencia técnica remota (AnyDesk, TeamViewer). Comunicación efectiva con usuarios, "
                "nivel de inglés B2."
            ),
        },
        "general": {
            "headline_roles": ["Técnico en Soporte TI", "Soporte Sistemas y Redes", "Help Desk Junior"],
            "summary_opener": "Técnico en Sistemas con experiencia en soporte TI corporativo y mantenimiento de equipos.",
            "summary_focus": (
                "Experiencia comprobada en diagnóstico y resolución de fallas de hardware y software, instalación y "
                "configuración de sistemas operativos Windows y Linux, gestión de periféricos de red e impresoras, "
                "mantenimiento preventivo y correctivo, y asistencia técnica remota. Formación complementaria en "
                "Seguridad de Endpoints (Cisco), análisis de datos en Python e IA generativa. Inglés: B2."
            ),
        },
    },
}

# Achievement bullet priority per archetype (index into experience[i].achievements list)
# Structure: { archetype: { exp_index: [priority_achievement_indices...] } }
ARCHETYPE_BULLET_PRIORITY = {
    "sysadmin": {
        0: [1, 0, 3, 2, 4],   # OS deployment first, then support, then docs, then diagnostics, then tickets
        1: [0, 2, 1],          # hardware first, then automation, then backup
        2: [0, 1],
    },
    "software_data": {
        0: [3, 0, 2, 1, 4],   # docs/automation first
        1: [2, 0, 1],          # automation scripts first
        2: [0, 1],
    },
    "it_support": {
        0: [4, 0, 2, 1, 3],   # ticket count first, then support, then maintenance
        1: [0, 1, 2],
        2: [0, 1],
    },
    "general": {
        0: [0, 1, 2, 3, 4],
        1: [0, 1, 2],
        2: [0, 1],
    },
}


def _reorder_bullets(achievements: list, archetype: str, exp_index: int) -> list:
    """Return achievements reordered by archetype priority."""
    priority = ARCHETYPE_BULLET_PRIORITY.get(archetype, {}).get(exp_index, list(range(len(achievements))))
    seen = set()
    ordered = []
    for i in priority:
        if i < len(achievements):
            ordered.append(achievements[i])
            seen.add(i)
    for i, a in enumerate(achievements):
        if i not in seen:
            ordered.append(a)
    return ordered


def _build_dynamic_summary(
    archetype: str,
    language: str,
    job_title: str,
    company: str,
    keywords: List[str],
) -> str:
    """Builds a 2–3 sentence professional summary tailored to the specific job."""
    content = ARCHETYPE_CONTENT.get(language, ARCHETYPE_CONTENT["en"]).get(
        archetype, ARCHETYPE_CONTENT[language]["general"]
    )
    opener = content["summary_opener"]
    focus = content["summary_focus"]

    # Inject top matched keywords into the opener naturally
    top_kw = keywords[:3]
    if top_kw and language == "en":
        kw_str = ", ".join(top_kw)
        opener = opener.rstrip(".") + f", with demonstrated competency in {kw_str}."
    elif top_kw and language == "es":
        kw_str = ", ".join(top_kw)
        opener = opener.rstrip(".") + f", con competencias demostradas en {kw_str}."

    return f"{opener} {focus}"


def _build_dynamic_headline(archetype: str, language: str, job_title: str) -> str:
    """Returns a pipe-separated headline that matches the target role's archetype."""
    content = ARCHETYPE_CONTENT.get(language, ARCHETYPE_CONTENT["en"]).get(
        archetype, ARCHETYPE_CONTENT[language]["general"]
    )
    roles = content["headline_roles"]
    # If job_title is specific and not already in list, prepend it (truncated)
    if job_title and len(job_title) <= 40:
        clean = job_title.title()
        if clean not in roles:
            roles = [clean] + roles[:2]
    return " | ".join(roles[:3])


class ATSCVGenerator:
    """
    Multilingual, ATS-optimized CV generator for Julian David Diaz Medina.
    Produces clean, highly readable single or two-page PDFs formatted for ATS parsers
    in both English ('en') and Spanish ('es'), fully tailored per target role:

    Dynamic features per application:
    - Headline changes to match job archetype & title
    - Professional summary is generated from archetype + top matched keywords
    - Experience bullet points reordered to front-load the most relevant achievements
    - Skill categories reordered by archetype relevance
    - Matched keywords visually highlighted (bold) in skills section
    """

    def __init__(self, profile_path: str = None, profile_en_path: str = None, user_profile: dict = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.base_dir = base_dir

        if user_profile is not None:
            self.profile_es = user_profile
            self.profile_en = user_profile.get("en", user_profile)
            self.profile = self.profile_es
        else:
            self.profile_es_path = Path(profile_path) if profile_path else base_dir / "data" / "profile.json"
            self.profile_en_path = Path(profile_en_path) if profile_en_path else base_dir / "data" / "profile_en.json"

            with open(self.profile_es_path, "r", encoding="utf-8") as f:
                self.profile_es = json.load(f)

            if self.profile_en_path.exists():
                with open(self.profile_en_path, "r", encoding="utf-8") as f:
                    self.profile_en = json.load(f)
            else:
                self.profile_en = self.profile_es

            # Default profile alias for backward compatibility
            self.profile = self.profile_es

        self.variants_dir = base_dir / "cv" / "variants"
        self.variants_dir.mkdir(parents=True, exist_ok=True)

    def extract_relevant_keywords(self, job_description: str, profile: dict = None) -> List[str]:
        """Extracts keywords from job description that naturally match Julian's real skills."""
        if profile is None:
            profile = self.profile
        desc_lower = job_description.lower()
        matched = []
        for cat, skills in profile.get("technical_skills", {}).items():
            for skill in skills:
                terms = [w for w in re.findall(r"\w+", skill.lower()) if len(w) > 3]
                if any(t in desc_lower for t in terms):
                    if skill not in matched:
                        matched.append(skill)
        return matched

    def _prioritize_skill_categories(self, skills_dict: dict, archetype: str) -> List[tuple]:
        """Reorders technical skill categories to place the most relevant for the role first."""
        order_preferences = {
            "sysadmin": [
                "networking", "operating_systems", "sistemas_operativos", "redes",
                "cybersecurity", "ciberseguridad", "it_support_helpdesk", "soporte_ti"
            ],
            "software_data": [
                "programming_automation", "datos_programacion", "operating_systems",
                "sistemas_operativos", "it_support_helpdesk", "soporte_ti"
            ],
            "it_support": [
                "it_support_helpdesk", "soporte_ti", "operating_systems", "sistemas_operativos",
                "hardware_peripherals", "hardware_perifericos", "remote_tools_office",
                "herramientas_remotas_ofimatica", "networking", "redes"
            ],
            "general": [
                "it_support_helpdesk", "soporte_ti", "hardware_peripherals", "hardware_perifericos",
                "operating_systems", "sistemas_operativos", "networking", "redes"
            ]
        }

        favored = order_preferences.get(archetype, order_preferences["general"])

        def sort_key(item):
            cat_key = item[0].lower()
            try:
                return favored.index(cat_key)
            except ValueError:
                return 99

        return sorted(skills_dict.items(), key=sort_key)

    def _highlight_skills(self, skill_list: List[str], matched_keywords: List[str]) -> List[str]:
        """Returns skill strings with matched skills wrapped in <b> tags."""
        highlighted = []
        matched_lower = {k.lower() for k in matched_keywords}
        for skill in skill_list:
            terms = [w for w in re.findall(r"\w+", skill.lower()) if len(w) > 3]
            if any(t in " ".join(matched_lower) for t in terms):
                highlighted.append(f"<b>{skill}</b>")
            else:
                highlighted.append(skill)
        return highlighted

    def generate_tailored_cv(
        self,
        application_id: str,
        job_title: str,
        company: str,
        job_description: str,
        language: Optional[str] = None,
        location: str = "",
        source: str = ""
    ) -> Dict[str, Any]:
        """
        Generates an ATS-compliant PDF tailored for the vacancy in English or Spanish.
        Strictly preserves truthful information while prioritizing the most relevant
        real skills and achievements of Julian David Diaz Medina.

        Dynamic per-application content:
        - Headline: matched to archetype + job title
        - Summary: generated from archetype template + top matched keywords
        - Skills: reordered by archetype; matched skills bolded
        - Experience bullets: reordered per archetype to front-load relevant achievements
        """
        # 1. Detect language if not provided
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

        # 2. Select profile
        profile = self.profile_en if language == "en" else self.profile_es

        # 3. Classify archetype and extract keywords
        archetype = classify_job_archetype(title=job_title, description=job_description)
        relevant_keywords = self.extract_relevant_keywords(job_description, profile)

        # 4. Build dynamic content
        dynamic_headline = _build_dynamic_headline(archetype, language, job_title)
        dynamic_summary = _build_dynamic_summary(archetype, language, job_title, company, relevant_keywords)

        # 5. File naming with language tag
        comp_clean = re.sub(r"[^\w]", "_", company[:10].strip())
        cv_version = f"ATS-JulianDiaz-{language.upper()}-{comp_clean}-{application_id[:8]}"
        pdf_path = self.variants_dir / f"{cv_version}.pdf"

        # 6. Internationalized Section Titles
        if language == "en":
            labels = {
                "summary": "PROFESSIONAL SUMMARY",
                "skills": "TECHNICAL SKILLS",
                "experience": "PROFESSIONAL EXPERIENCE",
                "education": "EDUCATION",
                "certifications": "CERTIFICATIONS & TRAINING",
                "languages": "LANGUAGES"
            }
        else:
            labels = {
                "summary": "PERFIL PROFESIONAL",
                "skills": "COMPETENCIAS TÉCNICAS",
                "experience": "EXPERIENCIA PROFESIONAL",
                "education": "EDUCACIÓN",
                "certifications": "CERTIFICACIONES Y FORMACIÓN COMPLEMENTARIA",
                "languages": "IDIOMAS"
            }

        # 7. ReportLab Document Setup
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "NameTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A2B4C"),
            fontName="Helvetica-Bold",
            alignment=1,  # Center
            spaceAfter=3,
        )
        subtitle_style = ParagraphStyle(
            "SubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#334155"),
            fontName="Helvetica-Bold",
            alignment=1,
            spaceAfter=4,
        )
        contact_style = ParagraphStyle(
            "Contact",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#475569"),
            alignment=1,
            spaceAfter=8,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#1A2B4C"),
            fontName="Helvetica-Bold",
            spaceBefore=6,
            spaceAfter=3,
        )
        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=3,
        )
        bullet_style = ParagraphStyle(
            "BulletPoint",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            leftIndent=12,
            firstLineIndent=-8,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=2,
        )

        story = []

        # --- HEADER & CONTACT (dynamic headline) ---
        story.append(Paragraph(profile["name"].upper(), title_style))
        story.append(Paragraph(dynamic_headline, subtitle_style))
        contact_line = (
            f"{profile['location']} &bull; {profile['phone']} &bull; "
            f"{profile['email']} &bull; {profile['linkedin']}"
        )
        story.append(Paragraph(contact_line, contact_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=5))

        # --- PROFESSIONAL SUMMARY (dynamic per job) ---
        story.append(Paragraph(labels["summary"], section_style))
        story.append(Paragraph(dynamic_summary, body_style))
        story.append(Spacer(1, 3))

        # --- TECHNICAL SKILLS (reordered + matched skills bolded) ---
        story.append(Paragraph(labels["skills"], section_style))
        skills_dict = profile.get("technical_skills", {})
        sorted_categories = self._prioritize_skill_categories(skills_dict, archetype)

        for cat_name, skill_list in sorted_categories:
            cat_display = cat_name.replace("_", " ").title()
            highlighted = self._highlight_skills(skill_list, relevant_keywords)
            items_str = "; ".join(highlighted)
            story.append(Paragraph(f"<b>{cat_display}:</b> {items_str}", body_style))
        story.append(Spacer(1, 3))

        # --- PROFESSIONAL EXPERIENCE (bullets reordered by archetype) ---
        story.append(Paragraph(labels["experience"], section_style))
        for exp_idx, exp in enumerate(profile.get("experience", [])):
            role_header = f"<b>{exp['role']}</b> | {exp['company']} ({exp['period']}) — {exp['location']}"
            story.append(Paragraph(role_header, body_style))
            ordered_bullets = _reorder_bullets(exp.get("achievements", []), archetype, exp_idx)
            for ach in ordered_bullets:
                story.append(Paragraph(f"&bull; {ach}", bullet_style))
            story.append(Spacer(1, 3))

        # --- EDUCATION ---
        story.append(Paragraph(labels["education"], section_style))
        for edu in profile.get("education", []):
            edu_line = f"<b>{edu['degree']}</b> | {edu['institution']} ({edu['period']}) — {edu['location']}"
            story.append(Paragraph(edu_line, body_style))
            if "focus" in edu:
                focus_prefix = "Focus:" if language == "en" else "Enfoque:"
                story.append(Paragraph(f"&bull; {focus_prefix} {edu['focus']}", bullet_style))
        story.append(Spacer(1, 3))

        # --- CERTIFICATIONS ---
        story.append(Paragraph(labels["certifications"], section_style))
        cert_items = []
        for c in profile.get("certifications", []):
            cert_items.append(f"&bull; <b>{c['title']}</b> ({c['issuer']}, {c['date']})")
        story.append(Paragraph("<br/>".join(cert_items), body_style))
        story.append(Spacer(1, 3))

        # --- LANGUAGES ---
        story.append(Paragraph(labels["languages"], section_style))
        lang_str = " | ".join([f"<b>{l['language']}:</b> {l['level']}" for l in profile.get("languages", [])])
        story.append(Paragraph(lang_str, body_style))

        # Build document
        doc.build(story)

        return {
            "application_id": application_id,
            "cv_version": cv_version,
            "pdf_path": str(pdf_path),
            "language": language,
            "archetype": archetype,
            "keywords_used": relevant_keywords,
            "dynamic_headline": dynamic_headline,
            "dynamic_summary": dynamic_summary[:120] + "...",
        }
