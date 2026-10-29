import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

logger = logging.getLogger("job_hunter.cv.ai_groq")

SYSTEM_ATS_PROMPT = """Eres un Reclutador Senior y Arquitecto Experto de Hojas de Vida ATS (Applicant Tracking Systems) de clase mundial.
Tu misión es transformar las respuestas del cuestionario de un candidato en un perfil profesional de altísimo impacto, 100% optimizado para superar cualquier filtro ATS corporativo (Workday, Taleo, Greenhouse, Lever, etc.).

Sigue estrictamente estas directrices:
1. Resumen Ejecutivo (Executive Summary): Redacta un párrafo persuasivo de 3 a 4 oraciones. Debe iniciar con el título/rol objetivo, destacar años o nivel de experiencia, mencionar 3-4 competencias clave y sintetizar el valor único que aporta a las empresas.
2. Experiencia Laboral (High-Impact Bullets):
   - Transforma las explicaciones o tareas descritas por el usuario en viñetas estructuradas con la fórmula: [Verbo de Acción fuerte en tiempo pasado o presente] + [Contexto, proceso o herramienta aplicada] + [Resultado tangible o impacto cuantificable estimado en %, horas, precisión o volumen].
   - Evita frases vacías como "responsable de" o "hacía tareas de". Usa verbos de liderazgo técnico o de gestión ("Optimizó", "Implementó", "Lideró", "Coordinó", "Automatizó", "Redujo", "Aumentó").
   - Si el candidato no tiene experiencia laboral formal, enfoca la sección en proyectos académicos, prácticas, voluntariados o proyectos personales con la misma rigurosidad.
3. Habilidades Técnicas y Blandas:
   - Extrae y categoriza las habilidades en: "Herramientas y Tecnologías", "Competencias Técnicas" y "Habilidades Blandas".
   - Enriquece las palabras clave relevantes para el rol objetivo.
4. Título / Titular (Headline): Debe ser conciso, profesional y alineado al cargo deseado.
5. Formato de salida: Devuelve ÚNICAMENTE un objeto JSON válido, sin bloques de markdown adicionales ni texto fuera del JSON, con este esquema exacto:
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "city": "string",
  "country": "string",
  "headline": "string",
  "target_role": "string",
  "summary": "string",
  "english_level": "string",
  "linkedin": "string",
  "technical_skills": {
    "Herramientas y Tecnologías": ["string"],
    "Competencias Técnicas": ["string"],
    "Habilidades Blandas": ["string"]
  },
  "experience": [
    {
      "title": "string",
      "company": "string",
      "period": "string",
      "achievements": [
        "string",
        "string"
      ]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "year": "string"
    }
  ],
  "certifications": ["string"],
  "languages": [
    {"language": "string", "level": "string"}
  ]
}
"""


class GroqAIEngine:
    MODELS = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b"
    ]

    @classmethod
    def get_api_key(cls, user_key: Optional[str] = None) -> Optional[str]:
        if user_key and user_key.strip():
            return user_key.strip()
        env_key = os.getenv("GROQ_API_KEY", "").strip()
        if env_key:
            return env_key
        return None

    @classmethod
    def transform_questionnaire_to_ats(
        cls,
        answers: Dict[str, Any],
        custom_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends raw questionnaire answers to Groq LLM and retrieves structured ATS profile JSON.
        """
        api_key = cls.get_api_key(custom_key)
        if not api_key:
            logger.warning("No Groq API key available; returning heuristic fallback.")
            return cls._heuristic_fallback(answers)

        user_content = json.dumps(answers, ensure_ascii=False, indent=2)

        for model in cls.MODELS:
            try:
                logger.info(f"Invoking Groq API with model {model}...")
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobHunter/1.0"
                    },
                    data=json.dumps({
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_ATS_PROMPT},
                            {"role": "user", "content": f"Por favor procesa y optimiza para ATS las siguientes respuestas del candidato:\n{user_content}"}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }).encode("utf-8")
                )

                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_res = json.loads(resp.read().decode("utf-8"))
                    content_str = raw_res["choices"][0]["message"]["content"]
                    parsed_json = json.loads(content_str)
                    
                    # Ensure basic fields are present
                    parsed_json["name"] = parsed_json.get("name") or answers.get("full_name") or "Candidato Profesional"
                    parsed_json["email"] = parsed_json.get("email") or answers.get("email") or ""
                    parsed_json["phone"] = parsed_json.get("phone") or answers.get("phone") or ""
                    parsed_json["city"] = parsed_json.get("city") or answers.get("city") or "Colombia"
                    parsed_json["country"] = parsed_json.get("country") or answers.get("country") or "Colombia"
                    parsed_json["target_role"] = parsed_json.get("target_role") or answers.get("target_role") or "Profesional"
                    parsed_json["headline"] = parsed_json.get("headline") or parsed_json["target_role"]
                    
                    logger.info(f"Successfully generated ATS profile using model {model}")
                    return parsed_json

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.warning(f"Groq model {model} returned HTTP {e.code}: {err_body}")
                continue
            except Exception as e:
                logger.warning(f"Groq model {model} encountered error: {e}")
                continue

        logger.warning("All Groq models failed or timed out. Using heuristic fallback.")
        return cls._heuristic_fallback(answers)

    @classmethod
    def _heuristic_fallback(cls, answers: Dict[str, Any]) -> Dict[str, Any]:
        """Provides a safe, structured fallback if external AI API is unreachable."""
        target_role = answers.get("target_role") or "Profesional Especializado"
        name = answers.get("full_name") or answers.get("name") or "Candidato Profesional"
        raw_bio = answers.get("raw_bio") or ""
        
        summary = (
            f"Profesional enfocado en {target_role} con sólida orientación al logro, alta capacidad de resolución de problemas "
            f"y optimización de procesos operativos. Demuestra compromiso con la excelencia y adaptabilidad a entornos dinámicos."
        ) if not raw_bio else f"{raw_bio}. Orientado a la entrega de valor y cumplimiento de objetivos estratégicos."

        skills_raw = answers.get("skills_raw", "")
        skills_list = [s.strip() for s in str(skills_raw).split(",") if s.strip()] if isinstance(skills_raw, str) else []
        if not skills_list:
            skills_list = [target_role, "Resolución de problemas", "Trabajo en equipo", "Gestión del tiempo"]

        exp_list = []
        raw_exps = answers.get("experiences") or []
        for exp in raw_exps:
            title = exp.get("title") or target_role
            company = exp.get("company") or "Empresa"
            period = exp.get("period") or "2022 - Presente"
            tasks = exp.get("tasks") or exp.get("achievements") or "Ejecución de actividades operativas y soporte."
            
            achievements = [tasks] if isinstance(tasks, str) else tasks
            exp_list.append({
                "title": title,
                "company": company,
                "period": period,
                "achievements": achievements
            })

        return {
            "name": name,
            "email": answers.get("email") or "",
            "phone": answers.get("phone") or "",
            "city": answers.get("city") or "Colombia",
            "country": answers.get("country") or "Colombia",
            "headline": target_role,
            "target_role": target_role,
            "summary": summary,
            "english_level": answers.get("english_level") or "B1",
            "linkedin": answers.get("linkedin") or "",
            "technical_skills": {
                "Competencias Principales": skills_list,
                "Habilidades Blandas": ["Comunicación asertiva", "Pensamiento crítico", "Adaptabilidad"]
            },
            "experience": exp_list,
            "education": answers.get("education") or [],
            "certifications": answers.get("certifications") or [],
            "languages": answers.get("languages") or [{"language": "Español", "level": "Nativo"}]
        }
