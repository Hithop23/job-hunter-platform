from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.adapters.base import AdapterContext
from app.config import Settings
from app.matching.engine import JobMatcher
from app.matching.profile import load_keywords, load_profile
from app.models import Job, RunLog
from app.schemas import RunSummary
from app.utils import utcnow

logger = logging.getLogger("jobhunter.runner")


class Mode(str, Enum):
    SCAN = "SCAN"
    PREPARE = "PREPARE"
    AUTOPILOT = "AUTOPILOT"


class AutopilotNotConfirmed(RuntimeError):
    """AUTOPILOT jamás se ejecuta sin doble habilitación (Módulo 15)."""


class _Stats:
    def __init__(self) -> None:
        self.discovered = 0
        self.duplicates = 0
        self.errors = 0
        self.sources_run: list[str] = []


def _scan_phase(
    session: Session, settings: Settings, sources: list[str] | None
) -> _Stats:
    stats = _Stats()
    ctx = AdapterContext(session=session, settings=settings)
    adapters = build_adapters(ctx, sources)
    if not adapters:
        logger.warning(
            "No hay fuentes registradas aún (se añaden en F3). Terminando escaneo."
        )
        return stats
    for adapter in adapters:
        stats.sources_run.append(adapter.source)
        logger.info("Escaneando fuente: %s", adapter.source)
        try:
            for job in adapter.discover_jobs():
                result = adapter.store_job(job)
                if result.error:
                    stats.errors += 1
                elif result.duplicate:
                    stats.duplicates += 1
                else:
                    stats.discovered += 1
        except Exception as exc:
            stats.errors += 1
            logger.exception("Fallo del adapter %s: %s", adapter.source, exc)
    return stats


@dataclass
class _MatchStats:
    high: int = 0
    review: int = 0
    low: int = 0
    flagged: int = 0


def _match_phase(session: Session, settings: Settings) -> _MatchStats:
    """Prioriza las vacantes nuevas contra el perfil (Módulos 3 y 16)."""
    stats = _MatchStats()
    profile_path = settings.resolve(settings.data_dir / "profile.json")
    keywords_path = settings.resolve(settings.data_dir / "keywords.json")
    if not profile_path.exists() or not keywords_path.exists():
        logger.warning(
            "profile.json/keywords.json no encontrados; se omite el matching."
        )
        return stats

    matcher = JobMatcher(
        load_profile(profile_path), load_keywords(keywords_path), settings
    )
    rows = session.query(Job).filter(Job.match_score.is_(None)).all()
    for row in rows:
        result = matcher.match_row(row)
        row.match_score = result.score
        row.match_flags = result.flags
        row.priority = result.priority
        if result.priority == "HIGH":
            stats.high += 1
        elif result.priority == "REVIEW":
            stats.review += 1
        else:
            stats.low += 1
        if "does_not_meet_required_requirement" in result.flags:
            stats.flagged += 1
    if rows:
        session.commit()
        session.add(
            RunLog(
                source="matcher",
                action="MATCHED",
                result=(
                    f"high={stats.high} review={stats.review} "
                    f"low={stats.low} flagged={stats.flagged}"
                ),
            )
        )
        session.commit()
    return stats


def run_mode(
    mode: Mode,
    settings: Settings,
    session: Session,
    sources: list[str] | None = None,
    confirm_autopilot: bool = False,
) -> RunSummary:
    """Orquesta un modo de ejecución (Módulo 15)."""
    started_at = utcnow()

    if mode == Mode.AUTOPILOT:
        if not settings.autopilot_enabled:
            raise AutopilotNotConfirmed(
                "AUTOPILOT está deshabilitado. "
                "Establece JHC_AUTOPILOT_ENABLED=true en .env"
            )
        if not confirm_autopilot:
            raise AutopilotNotConfirmed(
                "AUTOPILOT requiere confirmación explícita del usuario: "
                "pasa --i-confirm-autopilot"
            )

    stats = _scan_phase(session, settings, sources)
    match_stats = _match_phase(session, settings)
    message = ""
    if mode == Mode.PREPARE:
        message = "Pipeline PREPARE (matching + CV) se conecta en F4."
    elif mode == Mode.AUTOPILOT:
        message = "Pipeline AUTOPILOT (formularios) se conecta en F5."

    finished_at = utcnow()
    logger.info(
        "[%s] nuevas=%d duplicadas=%d errores=%d fuentes=%s | prioridad alta=%d revisión=%d baja=%d marcadas=%d",
        mode.value,
        stats.discovered,
        stats.duplicates,
        stats.errors,
        ",".join(stats.sources_run) or "ninguna",
        match_stats.high,
        match_stats.review,
        match_stats.low,
        match_stats.flagged,
    )
    return RunSummary(
        mode=mode.value,
        started_at=started_at,
        finished_at=finished_at,
        sources_run=stats.sources_run,
        jobs_discovered=stats.discovered,
        duplicates=stats.duplicates,
        errors=stats.errors,
        matched_high=match_stats.high,
        matched_review=match_stats.review,
        matched_low=match_stats.low,
        flagged=match_stats.flagged,
        message=message,
    )
