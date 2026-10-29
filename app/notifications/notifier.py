import logging
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JOB_HUNTER_NOTIFIER")


class Notifier:
    """
    Central notification dispatcher for JOB-HUNTER-CO.
    Dispatches alerts for high-score matches, CAPTCHA human interventions,
    interviews, and public convocatoria deadlines.
    """

    @staticmethod
    def notify_high_priority_job(job: Dict[str, Any], score: float):
        msg = f"[ALERTA VACANTE TOP] ({score}/100) - {job.get('title')} en {job.get('company')} ({job.get('location')})"
        logger.info(msg)

    @staticmethod
    def notify_human_intervention_required(reason: str, application_id: str, url: str):
        msg = f"[HUMAN-IN-THE-LOOP] Se requiere intervención ({reason}) para postulación {application_id} en {url}"
        logger.warning(msg)

    @staticmethod
    def notify_interview_scheduled(company: str, position: str):
        msg = f"[FELICITACIONES - ENTREVISTA] Se ha registrado entrevista para {position} en {company}"
        logger.info(msg)

    @staticmethod
    def notify_public_convocatoria(title: str, entity: str, closing_date: str):
        msg = f"[EMPLEO PÚBLICO - CNSC] Nueva oportunidad técnica en {entity}: {title} (Cierra: {closing_date})"
        logger.info(msg)
