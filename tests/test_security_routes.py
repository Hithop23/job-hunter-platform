from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routes_cv import router as cv_router
from app.api.routes_hil import router as hil_router, validate_browser_url
from app.api.routes_stats import router as stats_router
from app.security import supabase_auth
from app.security.supabase_auth import get_optional_authenticated_user_id


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(stats_router)
    app.include_router(hil_router)
    app.include_router(cv_router)
    return TestClient(app)


def test_profile_routes_reject_user_ids_without_a_verified_session(api_client):
    profile = api_client.get("/api/stats/profile?user_id=another-user")
    dashboard = api_client.get("/api/stats/dashboard?user_id=another-user")
    preferences = api_client.get("/api/stats/preferences?user_id=another-user")
    save_profile = api_client.post(
        "/api/stats/profile",
        json={
            "user_id": "another-user",
            "email": "candidate@example.com",
            "full_name": "Candidate",
        },
    )
    save_preferences = api_client.put("/api/stats/preferences", json={})
    open_session = api_client.post(
        "/api/hil/open-session",
        json={"url": "https://www.linkedin.com/login"},
    )
    upload_cv = api_client.post(
        "/api/cv/upload",
        data={"user_id": "another-user"},
        files={"file": ("resume.txt", b"Resume content long enough for parsing")},
    )
    generate_cv = api_client.post(
        "/api/cv/generate",
        json={
            "user_id": "another-user",
            "name": "Candidate",
            "email": "candidate@example.com",
        },
    )
    ai_builder = api_client.post(
        "/api/cv/ai-builder",
        json={"user_id": "another-user", "answers": {}},
    )

    assert profile.status_code == 401
    assert dashboard.status_code == 401
    assert preferences.status_code == 401
    assert save_profile.status_code == 401
    assert save_preferences.status_code == 401
    assert open_session.status_code == 401
    assert upload_cv.status_code == 401
    assert generate_cv.status_code == 401
    assert ai_builder.status_code == 401


def test_profile_routes_reject_a_different_authenticated_user(api_client):
    api_client.app.dependency_overrides[get_optional_authenticated_user_id] = (
        lambda: "authenticated-user"
    )
    profile = api_client.get("/api/stats/profile?user_id=another-user")
    dashboard = api_client.get("/api/stats/dashboard?user_id=another-user")

    assert profile.status_code == 403
    assert dashboard.status_code == 403


def test_supabase_access_token_is_verified_and_user_id_is_derived(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_KEY", "public-test-key")
    requested = {}

    class AuthResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "verified-user"}

    def fake_get(url, headers, timeout):
        requested.update(url=url, headers=headers, timeout=timeout)
        return AuthResponse()

    monkeypatch.setattr(supabase_auth.httpx, "get", fake_get)

    assert get_optional_authenticated_user_id("Bearer verified-token") == "verified-user"
    assert requested["url"] == "https://project.supabase.co/auth/v1/user"
    assert requested["headers"]["Authorization"] == "Bearer verified-token"
    assert requested["headers"]["apikey"] == "public-test-key"
    assert requested["timeout"] == 5.0


def test_invalid_supabase_token_is_rejected(monkeypatch):
    class AuthResponse:
        status_code = 401

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "public-test-key")
    monkeypatch.setattr(supabase_auth.httpx, "get", lambda *args, **kwargs: AuthResponse())

    with pytest.raises(HTTPException) as exc_info:
        get_optional_authenticated_user_id("Bearer invalid-token")

    assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/jobs/view/123",
        "https://co.computrabajo.com/ofertas/123",
        "https://jobs.lever.co/company/123",
    ],
)
def test_browser_url_allows_https_job_portals(url):
    assert validate_browser_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://www.linkedin.com/login",
        "https://localhost/",
        "https://127.0.0.1/",
        "https://linkedin.com.attacker.example/",
        "https://user@www.linkedin.com/",
        "https://www.linkedin.com:8443/",
        "file:///C:/Windows/win.ini",
    ],
)
def test_browser_url_rejects_non_https_or_unapproved_destinations(url):
    with pytest.raises(HTTPException) as exc_info:
        validate_browser_url(url)

    assert exc_info.value.status_code == 400


def test_skill_rendering_uses_text_nodes_in_dashboard():
    html_path = Path(__file__).resolve().parents[1] / "app" / "api" / "dashboard.html"
    html = html_path.read_text(encoding="utf-8")

    assert "skillsEl.innerHTML = (skillsList || []).map" not in html
    assert "verifiedContainer.innerHTML = list.slice" not in html
    assert "span.textContent = String(skill);" in html
    assert "span.textContent = skill;" in html
