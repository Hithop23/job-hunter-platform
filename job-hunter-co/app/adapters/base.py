from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Optional

from sqlalchemy.orm import Session

from app.logging_config import redact
from app.models import Job, RunLog
from app.schemas import NormalizedJob, StoreResult
from app.utils import compute_dedup_hash

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger("jobhunter.adapters")


@dataclass
class AdapterContext:
    """Dependencias compartidas que recibe cada adapter."""

    session: Session
    settings: "Settings"


class BaseJobAdapter(ABC):
    """Contrato común de todas las fuentes de vacantes (Módulo 2).

    Cada fuente implementa:
      - discover_jobs(): itera las vacantes descubiertas
      - get_job_details(): obtiene el detalle de una vacante (opcional)
      - normalize_job(): convierte un payload crudo en NormalizedJob
      - store_job(): persiste con deduplicación
        (source + external_id, fallback hash(company + title + url))
    """

    source: str = "base"
    enabled_by_default: bool = True

    def __init__(self, ctx: AdapterContext) -> None:
        self.ctx = ctx
        self.session = ctx.session
        self.settings = ctx.settings

    @abstractmethod
    def discover_jobs(self) -> Iterator[NormalizedJob]:
        """Itera las vacantes descubiertas en la fuente."""

    def get_job_details(self, external_id: str) -> Optional[NormalizedJob]:
        """Detalle completo de una vacante; None si la fuente no lo soporta."""
        return None

    def normalize_job(self, raw: dict) -> NormalizedJob:
        """Convierte un payload crudo de la fuente al esquema normalizado."""
        raise NotImplementedError(
            f"{type(self).__name__} no implementa normalize_job"
        )

    def store_job(self, job: NormalizedJob) -> StoreResult:
        """Persiste la vacante aplicando deduplicación (Módulo 2)."""
        try:
            existing = (
                self.session.query(Job)
                .filter(
                    Job.source == job.source,
                    Job.external_id == job.external_id,
                )
                .first()
            )
            if existing is not None:
                return StoreResult(job_id=existing.id, duplicate=True)

            dedup = compute_dedup_hash(job.company, job.title, job.url)
            clash = self.session.query(Job).filter(Job.dedup_hash == dedup).first()
            if clash is not None:
                return StoreResult(job_id=clash.id, duplicate=True)

            row = Job(
                source=job.source,
                external_id=job.external_id,
                dedup_hash=dedup,
                company=job.company,
                title=job.title,
                location=job.location,
                url=job.url,
                description=job.description or "",
                requirements=job.requirements,
                salary=job.salary,
                employment_type=job.employment_type,
                publication_date=job.publication_date,
                closing_date=job.closing_date,
                raw=job.raw or None,
            )
            self.session.add(row)
            self.session.commit()
            self.log(row.company, row.title, "DISCOVERED", "STORED")
            return StoreResult(job_id=row.id, duplicate=False)
        except Exception as exc:
            self.session.rollback()
            error = redact(str(exc))
            logger.exception(
                "store_job falló para %s/%s", job.source, job.external_id
            )
            self.log(job.company, job.title, "DISCOVERED", "ERROR", error)
            return StoreResult(error=error)

    def log(
        self,
        company: Optional[str],
        job_title: Optional[str],
        action: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Registra la acción en run_logs y en el logger (Módulo 13)."""
        try:
            self.session.add(
                RunLog(
                    source=self.source,
                    company=company,
                    job=job_title,
                    action=action,
                    result=result,
                    error=redact(error) if error else None,
                )
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.exception("No se pudo escribir en run_logs")
        logger.info(
            "%s | %s | %s | %s | %s",
            self.source,
            company or "-",
            job_title or "-",
            action,
            result or (f"ERROR: {error}" if error else "-"),
        )
