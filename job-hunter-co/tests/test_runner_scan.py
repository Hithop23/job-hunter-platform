from app.adapters import register
from app.adapters.base import BaseJobAdapter
from app.runner import AutopilotNotConfirmed, Mode, run_mode
from tests.helpers import make_job


def test_scan_without_sources(settings, session):
    summary = run_mode(Mode.SCAN, settings, session)
    assert summary.mode == "SCAN"
    assert summary.jobs_discovered == 0
    assert summary.sources_run == []
    assert summary.finished_at >= summary.started_at


def test_scan_discovers_and_dedups(settings, session):
    @register
    class FakeAdapter(BaseJobAdapter):
        source = "fake"

        JOBS = [
            make_job(source="fake", external_id="f1"),
            make_job(
                source="fake",
                external_id="f2",
                url="https://example.com/jobs/2",
                title="Analista de Mesa de Ayuda",
            ),
        ]

        def discover_jobs(self):
            yield from self.JOBS

    first = run_mode(Mode.SCAN, settings, session)
    assert first.jobs_discovered == 2
    assert first.duplicates == 0
    assert first.sources_run == ["fake"]

    second = run_mode(Mode.SCAN, settings, session)
    assert second.jobs_discovered == 0
    assert second.duplicates == 2


def test_scan_with_unknown_source_is_noop(settings, session):
    summary = run_mode(Mode.SCAN, settings, session, sources=["noexiste"])
    assert summary.jobs_discovered == 0
    assert summary.sources_run == []


def test_autopilot_requires_confirmation(settings, session):
    with __import__("pytest").raises(AutopilotNotConfirmed):
        run_mode(Mode.AUTOPILOT, settings, session, confirm_autopilot=False)


def test_autopilot_confirmed_runs_scan(settings, session):
    settings.autopilot_enabled = True
    summary = run_mode(Mode.AUTOPILOT, settings, session, confirm_autopilot=True)
    assert summary.mode == "AUTOPILOT"
    assert "F5" in summary.message


def test_scan_triggers_matching(settings_with_data, session):
    @register
    class FakeAdapter(BaseJobAdapter):
        source = "fake"

        JOBS = [
            make_job(source="fake", external_id="f1"),
            make_job(
                source="fake",
                external_id="f2",
                title="Ingeniero Senior de Soporte TI",
                description="Windows, soporte técnico, impresoras.",
                requirements=["Mínimo 5 años de experiencia"],
            ),
        ]

        def discover_jobs(self):
            yield from self.JOBS

    summary = run_mode(Mode.SCAN, settings_with_data, session)
    assert summary.jobs_discovered == 2

    from app.models import Job

    rows = session.query(Job).order_by(Job.external_id).all()
    assert all(row.match_score is not None for row in rows)
    assert all(row.priority in {"HIGH", "REVIEW", "LOW"} for row in rows)
    priorities = {row.external_id: row.priority for row in rows}
    assert priorities["f1"] == "HIGH"
    assert priorities["f2"] == "LOW"
    assert summary.matched_high == 1
    assert summary.matched_low == 1
    assert summary.flagged == 1
