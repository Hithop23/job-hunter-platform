from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_jobs


def test_async_scan_exposes_its_completion_status(monkeypatch):
    async def complete_scan(scan_id, *_args):
        routes_jobs.scan_runs[scan_id] = {
            "status": "completed",
            "total_discovered": 3,
            "total_matched": 3,
            "location": "Valledupar",
        }

    monkeypatch.setattr(routes_jobs, "_async_discovery_runner", complete_scan)
    app = FastAPI()
    app.include_router(routes_jobs.router)

    with TestClient(app) as client:
        started = client.post("/api/jobs/scan?is_async=true")
        assert started.status_code == 200
        scan_id = started.json()["scan_id"]

        status = client.get(f"/api/jobs/scan/{scan_id}")

    assert status.status_code == 200
    assert status.json() == {
        "status": "completed",
        "total_discovered": 3,
        "total_matched": 3,
        "location": "Valledupar",
    }


def test_unknown_scan_status_returns_not_found():
    app = FastAPI()
    app.include_router(routes_jobs.router)

    with TestClient(app) as client:
        response = client.get("/api/jobs/scan/unknown-scan-id")

    assert response.status_code == 404
