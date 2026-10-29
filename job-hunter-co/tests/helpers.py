"""Utilidades compartidas entre los tests (mock jobs y adapter dummy)."""

from __future__ import annotations

from app.adapters.base import AdapterContext, BaseJobAdapter
from app.schemas import NormalizedJob


class DummyAdapter(BaseJobAdapter):
    """Adapter de prueba: devuelve una lista fija de vacantes."""

    source = "dummy"

    def __init__(self, ctx: AdapterContext, jobs=None):
        super().__init__(ctx)
        self._jobs = list(jobs) if jobs is not None else []

    def discover_jobs(self):
        yield from self._jobs


def make_job(**overrides) -> NormalizedJob:
    payload = dict(
        source="dummy",
        external_id="job-1",
        company="Acme Ltda",
        title="Técnico de Soporte TI",
        url="https://example.com/jobs/1",
        location="Valledupar, Cesar",
        description="Soporte técnico presencial y remoto.",
        requirements=["Windows", "Impresoras"],
    )
    payload.update(overrides)
    return NormalizedJob(**payload)
