import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple


class JobMatcher:
    def __init__(self, profile_path: str = None, keywords_path: str = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        if profile_path is None:
            profile_path = base_dir / "data" / "profile.json"
        if keywords_path is None:
            keywords_path = base_dir / "data" / "keywords.json"

        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)

        with open(keywords_path, "r", encoding="utf-8") as f:
            self.keywords_config = json.load(f)

        self._build_candidate_skill_set()

    def _build_candidate_skill_set(self):
        self.candidate_skills = set()
        for cat, skills in self.profile.get("technical_skills", {}).items():
            for s in skills:
                words = re.findall(r"\w+", s.lower())
                self.candidate_skills.update(words)

        # Add target roles words
        for role in self.profile.get("target_roles", []):
            words = re.findall(r"\w+", role.lower())
            self.candidate_skills.update(words)

        # Add education keywords
        self.candidate_education_level = "tecnico"  # Técnico en Sistemas Teleinformáticos SENA

    def evaluate_job(self, job_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a job posting against Julian's verified profile.
        Returns detailed scoring and does_not_meet_required_requirement flag.
        """
        title = (job_dict.get("title") or "").lower()
        description = (job_dict.get("description") or "").lower()
        requirements = (job_dict.get("requirements") or "").lower()
        location = (job_dict.get("location") or "").lower()
        salary_text = str(job_dict.get("salary") or "")
        pub_date_text = str(job_dict.get("publication_date") or "")
        full_text = f"{title} {description} {requirements} {salary_text}"

        # 1. Seniority & Disqualification Check
        disqualified, disqualification_reasons = self._check_disqualification(title, requirements, full_text)

        # 2. Required Skills Match (40%)
        skill_score, matched_skills, missing_skills = self._calculate_skill_match(full_text)

        # 3. Education Match (20%)
        education_score, edu_reason = self._calculate_education_match(full_text)

        # 4. Experience Match (20%)
        experience_score, exp_reason = self._calculate_experience_match(full_text)

        # 5. Location Match (10%)
        location_score, loc_reason = self._calculate_location_match(location, full_text)

        # 6. Keyword Match (10%)
        keyword_score, matched_keywords = self._calculate_keyword_match(title, full_text)

        # 7. Seniority Score (Penalties)
        seniority_score = self._calculate_seniority_score(title, full_text)

        # 8. Salary Match
        salary_score, salary_reason = self._calculate_salary_match(salary_text)

        # 9. Freshness Match
        freshness_score, freshness_reason = self._calculate_freshness_match(pub_date_text)

        # Composite score
        weights = self.keywords_config.get("scoring_weights", {
            "required_skills": 0.40,
            "education": 0.20,
            "experience": 0.20,
            "location": 0.10,
            "keywords": 0.10
        })

        raw_score = (
            (skill_score * weights["required_skills"]) +
            (education_score * weights["education"]) +
            (experience_score * weights["experience"]) +
            (location_score * weights["location"]) +
            (keyword_score * weights["keywords"])
        )

        # Apply seniority multiplier
        composite_score = raw_score * (seniority_score / 100.0)

        # Modifiers: Freshness, Salary, Remote Priority
        if freshness_score >= 95:
            composite_score += 3.0
        elif freshness_score <= 40:
            composite_score -= 10.0

        if salary_score >= 95:
            composite_score += 3.0
        elif salary_score <= 40:
            composite_score -= 10.0

        # Remote priority boost — candidate explicitly prioritizes remote work
        is_remote = any(k in full_text or k in location for k in [
            "remoto", "teletrabajo", "home office", "100% remoto", "virtual",
            "remote", "worldwide", "global", "anywhere", "work from home", "wfh"
        ])
        target_country = (self.profile.get("search_preferences", {}).get("country") or "").lower()
        if is_remote and (target_country == "remoto" or self.profile.get("search_preferences", {}).get("remote", True)):
            composite_score += 10.0  # Stronger bonus for 100% remote (candidate priority)

        # If hard disqualified, force score below threshold and mark flag
        if disqualified:
            composite_score = min(composite_score, 45.0)

        composite_score = max(0.0, min(100.0, composite_score))
        composite_score = round(composite_score, 1)

        # Categorization
        thresholds = self.keywords_config.get("score_thresholds", {"high_priority": 75, "review": 60})
        if composite_score >= thresholds["high_priority"] and not disqualified:
            priority = "ALTA_PRIORIDAD"
            recommended_status = "READY"
        elif composite_score >= thresholds["review"] and not disqualified:
            priority = "REVISION"
            recommended_status = "REVIEW"
        else:
            priority = "NO_PRIORIZAR"
            recommended_status = "DISCOVERED"

        return {
            "match_score": composite_score,
            "priority": priority,
            "recommended_status": recommended_status,
            "does_not_meet_required_requirement": disqualified,
            "disqualification_reasons": disqualification_reasons,
            "breakdown": {
                "required_skill_match": round(skill_score, 1),
                "education_match": round(education_score, 1),
                "experience_match": round(experience_score, 1),
                "location_match": round(location_score, 1),
                "keyword_match": round(keyword_score, 1),
                "seniority_match": round(seniority_score, 1),
                "salary_match": round(salary_score, 1),
                "freshness_match": round(freshness_score, 1),
            },
            "matched_skills": list(matched_skills)[:10],
            "matched_keywords": list(matched_keywords)[:10],
            "details": {
                "education_reason": edu_reason,
                "experience_reason": exp_reason,
                "location_reason": loc_reason,
                "salary_reason": salary_reason,
                "freshness_reason": freshness_reason,
            }
        }

    def _check_disqualification(self, title: str, requirements: str, full_text: str) -> Tuple[bool, List[str]]:
        reasons = []
        disqualifiers = self.keywords_config.get("seniority_penalties", {}).get("disqualifying_keywords", [])

        # Check in title first (very strong indicator)
        for d in ["senior", "sr.", "sr ", "lead", "leader", "manager", "gerente", "director", "head of", "principal", "arquitecto"]:
            if re.search(r"\b" + re.escape(d) + r"\b", title):
                reasons.append(f"Cargo Senior/Lead/Manager en título: '{d}'")

        # Check in requirements or full text for mandatory exclusions
        mandatory_degrees = [
            "título profesional universitario obligatorio",
            "tarjeta profesional vigente obligatoria",
            "ingeniero graduado obligatorio",
            "obligatorio tarjeta copnia",
            "profesional titulado excluyente",
            "mínimo 5 años",
            "mínimo 6 años",
            "mínimo 7 años",
            "mínimo 8 años",
            "mínimo 10 años"
        ]
        for m in mandatory_degrees:
            if m in full_text:
                reasons.append(f"Requisito obligatorio no cumplido: '{m}'")

        return (len(reasons) > 0), reasons

    def _calculate_skill_match(self, full_text: str) -> Tuple[float, set, set]:
        priority_skills = self.keywords_config.get("technical_skills_priority", [])
        matched = set()
        for skill in priority_skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", full_text):
                matched.add(skill)

        # Baseline: if it mentions soporte, sistemas, hardware, windows, redes
        core_count = sum(1 for s in ["soporte", "sistemas", "hardware", "windows", "redes", "help desk", "mesa de ayuda"] if s in matched)
        
        # Calculate ratio
        total_eval = max(len(matched), 1)
        score = min(100.0, (core_count * 20.0) + (len(matched) * 4.0))
        return min(score, 100.0), matched, set()

    def _calculate_education_match(self, full_text: str) -> Tuple[float, str]:
        # Julian has: Técnico en Sistemas Teleinformáticos (SENA), Bachiller
        if re.search(r"\b(t[eé]cnico|tecn[oó]logo|sena|aprendiz|auxiliar|asistencial)\b", full_text):
            return 100.0, "La vacante acepta o solicita perfil técnico/SENA o afín."
        elif re.search(r"\b(estudiante|carrera técnica|semestre)\b", full_text):
            return 90.0, "Acepta estudios técnicos o en curso."
        elif "profesional" in full_text and not ("título profesional obligatorio" in full_text or "excluyente" in full_text):
            # Preferiblemente profesional pero no excluyente
            return 60.0, "Menciona formación profesional pero sin exclusión estricta."
        elif "ingeniero" in full_text:
            return 50.0, "Menciona perfil de ingeniería."
        return 75.0, "Requisitos educativos neutrales o flexibles."

    def _calculate_experience_match(self, full_text: str) -> Tuple[float, str]:
        # Julian has: ~1 year corporate tech support + 2 years computer repair + customer support
        if re.search(r"\b(sin experiencia|primer empleo|junior|jr|aprendiz|etapa productiva)\b", full_text):
            return 100.0, "Vacante junior, aprendiz o sin experiencia previa requerida."
        elif re.search(r"\b(6 meses|1 a[ñn]o|12 meses|un a[ñn]o)\b", full_text):
            return 95.0, "Requiere de 6 meses a 1 año de experiencia (Candidato cumple plenamente)."
        elif re.search(r"\b(2 a[ñn]os|24 meses|dos a[ñn]os)\b", full_text):
            return 80.0, "Requiere 2 años de experiencia (Candidato cumple con experiencia combinada)."
        elif re.search(r"\b(3 a[ñn]os|tres a[ñn]os)\b", full_text):
            return 55.0, "Requiere 3 años de experiencia (En el límite del perfil)."
        elif re.search(r"\b(4 a[ñn]os|5 a[ñn]os|m[aá]s de 3 a[ñn]os)\b", full_text):
            return 30.0, "Excede la experiencia junior del candidato."
        return 80.0, "Experiencia no especificada de forma rígida."

    def _calculate_location_match(self, location: str, full_text: str) -> Tuple[float, str]:
        loc = (location + " " + full_text).lower()
        prefs = self.profile.get("search_preferences", {})
        target_city = (prefs.get("city") or "").strip().lower()
        target_region = (prefs.get("region") or "").strip().lower()
        target_country = (prefs.get("country") or "Colombia").strip().lower()
        allow_remote = prefs.get("remote", True)

        is_remote_job = any(k in loc for k in [
            "remoto", "teletrabajo", "home office", "100% remoto", "virtual",
            "remote", "worldwide", "global", "anywhere", "work from home", "wfh"
        ])

        # Prioritize 100% remote if target country is Remoto or candidate specifies remote
        if target_country == "remoto" or "remoto" in target_city:
            if is_remote_job:
                return 100.0, "Modalidad 100% remota / teletrabajo (prioridad máxima del candidato)."
            elif target_city and target_city not in ["remoto", "cualquier ciudad / remoto"] and target_city in loc:
                return 85.0, f"Ubicación en {target_city.capitalize()} (presencial)."
            else:
                return 65.0, "Vacante presencial (el candidato prioriza modalidades remotas)."

        if is_remote_job and allow_remote:
            return 100.0, "Modalidad remota / teletrabajo aplicable desde cualquier ciudad de Colombia."

        if target_city and target_city not in ["remoto", "cualquier ciudad / remoto", "todas", "nacional"] and (target_city in loc or target_city in location.lower()):
            return 100.0, f"Ubicación local directa en {target_city.capitalize()}."
        elif target_region and target_region not in ["nacional", "toda colombia"] and (target_region in loc or target_region in location.lower()):
            return 90.0, f"Ubicación departamental / regional en {target_region.capitalize()}."
        elif any(k in loc for k in ["híbrido", "hibrido"]):
            return 75.0, "Modalidad híbrida (requiere verificar sede)."
        elif target_country in loc or "nacional" in loc or "colombia" in loc:
            return 85.0, "Vacante a nivel nacional (Colombia)."
        elif any(c in loc for c in ["bogotá", "bogota", "barranquilla", "bucaramanga", "medellín", "medellin", "cali", "cartagena", "santa marta", "valledupar"]):
            return 75.0, "Ciudad principal de Colombia."
        return 70.0, "Ubicación general en Colombia."

    def _calculate_salary_match(self, salary_str: str) -> Tuple[float, str]:
        if not salary_str or not salary_str.strip():
            return 80.0, "Salario no especificado en la oferta."

        s_lower = salary_str.lower()
        if any(k in s_lower for k in ["convenir", "acordar", "confidencial", "competitivo", "a convenir"]):
            return 85.0, "Salario a convenir / confidencial (acorde a perfil)."

        # --- Currency detection and COP conversion ---
        # Approximate exchange rates (monthly refresh not needed for scoring)
        USD_TO_COP = 4200.0   # 1 USD ≈ 4200 COP
        EUR_TO_COP = 4600.0   # 1 EUR ≈ 4600 COP
        GBP_TO_COP = 5400.0   # 1 GBP ≈ 5400 COP

        currency_factor = 1.0  # default: COP
        is_foreign_currency = False

        if "usd" in s_lower or "$" in salary_str and "cop" not in s_lower and "usd" in s_lower:
            currency_factor = USD_TO_COP
            is_foreign_currency = True
        elif "eur" in s_lower or "€" in salary_str:
            currency_factor = EUR_TO_COP
            is_foreign_currency = True
        elif "gbp" in s_lower or "£" in salary_str:
            currency_factor = GBP_TO_COP
            is_foreign_currency = True
        elif "usd" in s_lower:
            currency_factor = USD_TO_COP
            is_foreign_currency = True

        # Is this a yearly or monthly salary?
        is_yearly = any(k in s_lower for k in ["year", "annual", "yearly", "anual", "/yr", "per year"])
        is_monthly = any(k in s_lower for k in ["month", "mensual", "/mo", "/mes"])

        # Extract numeric amounts
        matches = re.findall(r"\d[\d.,]*\d|\d+", salary_str)
        parsed_vals = []
        for m in matches:
            clean_digits = re.sub(r"\D", "", m)
            if not clean_digits:
                continue
            try:
                numeric = float(clean_digits)
                # Convert based on currency and period
                if is_foreign_currency:
                    if is_yearly:
                        numeric_cop = (numeric * currency_factor) / 12  # monthly COP
                    else:
                        # Could be monthly foreign currency
                        numeric_cop = numeric * currency_factor
                    # Only accept reasonable salary values (avoid phone/ext numbers)
                    if 100 <= numeric <= 500000:
                        parsed_vals.append(numeric_cop)
                else:
                    # COP: raw amounts >= 100,000
                    if len(clean_digits) >= 6:
                        parsed_vals.append(numeric)
            except Exception:
                pass

        if parsed_vals:
            val = max(parsed_vals)
            salary_prefs = self.profile.get("salary_preferences", {})
            min_sal = float(salary_prefs.get("min_salary", 1500000))
            des_sal = float(salary_prefs.get("desired_salary", 2200000))

            currency_label = "USD equiv." if is_foreign_currency else "COP"

            if val >= des_sal:
                return 100.0, f"Salario (${val:,.0f} {currency_label}/mes) supera o iguala la expectativa deseada."
            elif val >= min_sal:
                return 90.0, f"Salario (${val:,.0f} {currency_label}/mes) cumple con el mínimo requerido."
            elif val >= 1350000:
                return 70.0, f"Salario (${val:,.0f} {currency_label}/mes) cercano al mínimo legal pero inferior a la expectativa."
            else:
                return 40.0, f"Salario (${val:,.0f} {currency_label}/mes) por debajo del mínimo esperado."

        return 80.0, f"Rango salarial: {salary_str}."

    def _calculate_freshness_match(self, pub_date_str: str) -> Tuple[float, str]:
        if not pub_date_str or not pub_date_str.strip():
            return 80.0, "Fecha de publicación no especificada."

        from datetime import datetime, timezone
        try:
            if "T" in pub_date_str:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).date()
            else:
                pub_date = datetime.strptime(pub_date_str[:10], "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            diff_days = (today - pub_date).days

            if diff_days <= 1:
                return 100.0, "Vacante recién publicada (últimas 24-48 horas)."
            elif diff_days <= 7:
                return 95.0, f"Publicada recientemente (hace {diff_days} días)."
            elif diff_days <= 15:
                return 85.0, f"Publicada hace {diff_days} días."
            elif diff_days <= 30:
                return 70.0, f"Publicada hace {diff_days} días."
            else:
                return 40.0, f"Publicación antigua con más de 30 días ({diff_days} días)."
        except Exception:
            return 80.0, f"Fecha registrada: {pub_date_str}."

    def _calculate_keyword_match(self, title: str, full_text: str) -> Tuple[float, set]:
        target_roles = self.keywords_config.get("target_roles", [])
        matched = set()
        for role in target_roles:
            r_clean = role.lower()
            if r_clean in title or r_clean in full_text:
                matched.add(role)

        score = min(100.0, len(matched) * 35.0 + 30.0)
        return score, matched

    def _calculate_seniority_score(self, title: str, full_text: str) -> float:
        penalties = self.keywords_config.get("seniority_penalties", {})
        caution_words = penalties.get("caution_keywords", [])

        # Check caution words
        for c in caution_words:
            if c in full_text:
                return 65.0

        # Check junior boost
        if re.search(r"\b(junior|jr|auxiliar|asistente|asistencial|soporte|t[eé]cnico|aprendiz)\b", title):
            return 100.0

        return 90.0
