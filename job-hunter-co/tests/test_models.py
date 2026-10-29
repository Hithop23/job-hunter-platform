import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Application,
    ApplicationStatus,
    Job,
    ReviewItem,
    ReviewReason,
    ReviewStatus,
    RunLog,
)
from app.utils import compute_dedup_hash


def _job(**kw):
    defaults = dict(
        source="spe",
        external_id="e1",
        dedup_hash=compute_dedup_hash("Acme", "Técnico", "https://x/1"),
        company="Acme",
        title="Técnico de Soporte TI",
        url="https://x/1",
    )
    defaults.update(kw)
    return Job(**defaults)


def test_job_roundtrip(session):
    session.add(_job())
    session.commit()
    loaded = session.query(Job).one()
    assert loaded.company == "Acme"
    assert loaded.title == "Técnico de Soporte TI"
    assert loaded.discovered_at is not None


def test_unique_source_external_id(session):
    session.add(_job())
    session.commit()
    session.add(
        _job(company="Otra", dedup_hash="x2", url="https://x/2", title="Otro cargo")
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_application_and_review_roundtrip(session):
    job = _job()
    session.add(job)
    session.flush()

    app = Application(
        job_id=job.id, status=ApplicationStatus.MATCHED, source="spe"
    )
    session.add(app)
    session.flush()

    review = ReviewItem(
        application_id=app.id,
        reason=ReviewReason.CAPTCHA,
        url="https://x/apply",
        status=ReviewStatus.PENDING,
    )
    session.add(review)
    session.commit()

    stored = session.query(Application).one()
    assert stored.status == ApplicationStatus.MATCHED
    assert stored.job.title == "Técnico de Soporte TI"

    pending = session.query(ReviewItem).one()
    assert pending.reason == ReviewReason.CAPTCHA
    assert pending.status == ReviewStatus.PENDING


def test_runlog_roundtrip(session):
    session.add(
        RunLog(
            source="sena",
            company="Acme",
            job="Técnico de Sistemas",
            action="DISCOVERED",
            result="STORED",
        )
    )
    session.commit()
    row = session.query(RunLog).one()
    assert row.result == "STORED"
    assert row.timestamp is not None
