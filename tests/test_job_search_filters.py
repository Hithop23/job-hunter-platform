import asyncio
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_jobs
from app.adapters.computrabajo.computrabajo_adapter import ComputrabajoAdapter
from app.adapters.linkedin import linkedin_adapter
from app.storage import database
from app.storage.models import Base
from app.storage.repository import Repository


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _job(external_id, title, location):
    return {
        "source": "test",
        "external_id": external_id,
        "company": "Empresa de prueba",
        "title": title,
        "location": location,
        "url": f"https://example.test/jobs/{external_id}",
        "description": "Vacante de prueba",
        "requirements": "",
    }


@pytest.mark.parametrize(
    ("job_location", "requested_location", "include_remote", "expected"),
    [
        ("Bogotá D.C., Colombia", "Bogota", False, True),
        ("Cali, Colombia", "Bogotá", False, False),
        ("100% Remoto / Worldwide", "Bogotá", True, True),
        ("100% Remoto / Worldwide", "Bogotá", False, False),
        ("Cali, Colombia", "", False, True),
    ],
)
def test_location_matching(job_location, requested_location, include_remote, expected):
    assert routes_jobs._matches_location(job_location, requested_location, include_remote) is expected


def test_list_jobs_filters_by_location_and_blank_keyword_returns_all_city_jobs(db_session):
    repo = Repository(db_session)
    repo.store_job(_job("bogota-1", "Analista", "Bogotá D.C., Colombia"))
    repo.store_job(_job("bogota-2", "Diseñador", "Bogotá, Colombia"))
    repo.store_job(_job("cali-1", "Analista", "Cali, Colombia"))
    repo.store_job(_job("remote-1", "Remote Analyst", "100% Remoto / Worldwide"))

    jobs = repo.list_jobs(location="Bogotá", search="")
    jobs_with_remote = repo.list_jobs(location="Bogotá", search="", remote=True)

    assert {job.external_id for job in jobs} == {"bogota-1", "bogota-2"}
    assert {job.external_id for job in jobs_with_remote} == {
        "bogota-1",
        "bogota-2",
        "remote-1",
    }


def test_computrabajo_uses_city_wide_search_when_query_is_blank(db_session, monkeypatch):
    adapter = ComputrabajoAdapter(db_session)
    requested_urls = []
    monkeypatch.setattr(adapter, "can_request", lambda: True)
    monkeypatch.setattr(adapter, "record_access", lambda **_kwargs: None)

    async def fetch_html(url):
        requested_urls.append(url)
        return ""

    monkeypatch.setattr(adapter, "_fetch_html", fetch_html)

    asyncio.run(adapter.discover_jobs(query="", location="Valledupar"))

    assert requested_urls == [f"{adapter.base_url}/empleos-en-valledupar"]


def test_linkedin_does_not_replace_empty_results_with_sample_jobs(db_session, monkeypatch):
    class Response:
        status_code = 503
        text = ""

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    adapter = linkedin_adapter.LinkedInAdapter(db_session)
    monkeypatch.setattr(adapter, "can_request", lambda **_kwargs: True)
    monkeypatch.setattr(adapter, "record_access", lambda **_kwargs: None)
    monkeypatch.setattr(linkedin_adapter.httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(adapter.discover_jobs(query="", location="Valledupar")) == []


def test_jobs_api_applies_city_filter(db_session):
    repo = Repository(db_session)
    repo.store_job(_job("bogota-api", "Analista", "Bogotá D.C., Colombia"))
    repo.store_job(_job("cali-api", "Analista", "Cali, Colombia"))

    app = FastAPI()
    app.include_router(routes_jobs.router)
    app.dependency_overrides[routes_jobs.get_db] = lambda: db_session

    with TestClient(app) as client:
        response = client.get("/api/jobs/?location=Bogota&search=")

    assert response.status_code == 200
    assert {job["location"] for job in response.json()["jobs"]} == {"Bogotá D.C., Colombia"}


def test_user_scans_create_separate_filtered_applications(db_session):
    repo = Repository(db_session)
    job, _ = repo.store_job(_job("shared-job", "Analista", "Bogotá"))
    user_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    app_data = {
        "job_id": job.id,
        "company": job.company,
        "position": job.title,
        "url": job.url,
        "source": job.source,
    }

    applications = [
        repo.create_or_update_application({**app_data, "user_id": user_id})
        for user_id in user_ids
    ]

    assert applications[0].id != applications[1].id
    assert [app.id for app in repo.list_applications(user_id=user_ids[0], location="Bogota")] == [
        applications[0].id
    ]
    assert repo.list_applications(user_id=user_ids[1], location="Cali") == []


def test_postgres_psycopg_engine_disables_server_side_prepare(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    database.build_engine("postgresql+psycopg://localhost/jobs")

    assert captured["connect_args"] == {"prepare_threshold": None}


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg2://localhost/jobs",
        "sqlite:///jobs.db",
    ],
)
def test_other_database_drivers_do_not_receive_psycopg_options(monkeypatch, url):
    captured = {}

    def fake_create_engine(engine_url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    database.build_engine(url)

    assert captured["connect_args"] == {}


def test_empty_scan_query_and_location_are_preserved(monkeypatch):
    captured = {}

    async def fake_discovery(_db, mode, query, location, country, region, remote, user_id=None):
        captured.update(query=query, location=location)
        return {
            "total_discovered": 0,
            "total_matched": 0,
            "location": location,
            "source_errors": [],
        }

    monkeypatch.setattr(routes_jobs, "run_discovery_task", fake_discovery)
    app = FastAPI()
    app.include_router(routes_jobs.router)
    app.dependency_overrides[routes_jobs.get_db] = lambda: None

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/scan?query=&city=&location=&is_async=false"
        )

    assert response.status_code == 200
    assert captured == {"query": "", "location": ""}


def test_failed_adapter_rolls_back_and_scan_continues(db_session, monkeypatch):
    called = []

    class FailingAdapter:
        name = "failing-source"

        def __init__(self, _db):
            pass

        async def discover_jobs(self, **_kwargs):
            raise RuntimeError("source unavailable")

    class EmptyAdapter:
        name = "empty-source"

        def __init__(self, _db):
            pass

        async def discover_jobs(self, **_kwargs):
            called.append(self.name)
            return []

    for name in (
        "SENAAdapter",
        "SPEAdapter",
        "CompanyDirectoryAdapter",
        "ComputrabajoAdapter",
        "IndeedAdapter",
        "LinkedInAdapter",
        "RemoteOKAdapter",
        "ArbeitnowAdapter",
        "WeWorkRemotelyAdapter",
    ):
        monkeypatch.setattr(
            routes_jobs,
            name,
            FailingAdapter if name == "SENAAdapter" else EmptyAdapter,
        )

    rollback_calls = []
    original_rollback = db_session.rollback

    def tracked_rollback():
        rollback_calls.append(True)
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", tracked_rollback)

    result = asyncio.run(
        routes_jobs.run_discovery_task(
            db_session,
            mode="SCAN",
            query="",
            location="Bogotá",
            country="Colombia",
            region="Bogotá D.C.",
            remote=False,
        )
    )

    assert called == ["empty-source"] * 5
    assert rollback_calls
    assert result["total_discovered"] == 0
    assert result["source_errors"] == [
        {"source": "failing-source", "message": "No se pudo consultar esta fuente."}
    ]
