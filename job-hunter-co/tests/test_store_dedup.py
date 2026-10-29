"""test_duplicate_detection — deduplicación de vacantes (Módulo 2)."""

from app.models import Job
from tests.helpers import DummyAdapter, make_job


def test_store_new_job(ctx, session):
    adapter = DummyAdapter(ctx)
    result = adapter.store_job(make_job())
    assert result.duplicate is False
    assert result.job_id
    assert session.query(Job).count() == 1


def test_dedup_by_source_external_id(ctx, session):
    adapter = DummyAdapter(ctx)
    first = adapter.store_job(make_job())
    second = adapter.store_job(make_job())  # misma vacante de nuevo
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.job_id == first.job_id
    assert session.query(Job).count() == 1


def test_dedup_by_hash_fallback(ctx, session):
    """Distinto external_id pero misma empresa+título+URL → duplicado."""
    adapter = DummyAdapter(ctx)
    adapter.store_job(make_job())
    result = adapter.store_job(make_job(external_id="job-2"))
    assert result.duplicate is True
    assert session.query(Job).count() == 1


def test_different_jobs_are_not_duplicates(ctx, session):
    adapter = DummyAdapter(ctx)
    adapter.store_job(make_job())
    result = adapter.store_job(
        make_job(
            external_id="job-9",
            url="https://example.com/jobs/9",
            title="Analista de Mesa de Ayuda",
        )
    )
    assert result.duplicate is False
    assert session.query(Job).count() == 2


def test_dummy_adapter_discovers(ctx, session):
    adapter = DummyAdapter(ctx, [make_job(), make_job(external_id="job-2", url="u2")])
    discovered = list(adapter.discover_jobs())
    assert len(discovered) == 2
    assert all(j.source == "dummy" for j in discovered)
