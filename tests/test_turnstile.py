from fastapi.testclient import TestClient
from app.api.main import app
from app.security.cloudflare_turnstile import (
    verify_turnstile_token,
    DEFAULT_TEST_SITE_KEY,
    DEFAULT_TEST_SECRET_KEY,
    get_turnstile_site_key,
    get_turnstile_secret_key
)

client = TestClient(app)


def test_turnstile_config_endpoint():
    r = client.get("/api/security/turnstile/config")
    assert r.status_code == 200
    data = r.json()
    assert "site_key" in data
    assert data["provider"] == "Cloudflare Turnstile"
    assert data["status"] == "ACTIVE"


def test_turnstile_verify_testing_token():
    # Cloudflare testing secret allows any token to pass
    res = verify_turnstile_token("TESTING_TOKEN_123")
    assert res.get("success") is True


def test_turnstile_verify_endpoint_success():
    r = client.post("/api/security/turnstile/verify", json={"token": "SAMPLE_PASSED_TOKEN"})
    assert r.status_code == 200
    data = r.json()
    assert data["verified"] is True
    assert data["status"] == "SUCCESS"


def test_turnstile_missing_token_fails():
    res = verify_turnstile_token("")
    assert res.get("success") is False
    assert "missing-input-response" in res.get("error-codes", [])


def test_ai_builder_with_turnstile():
    payload = {
        "answers": {
            "full_name": "Test Turnstile Candidate",
            "email": "turnstile@example.com",
            "target_role": "Analista Cloud"
        },
        "turnstile_token": "VALID_MOCK_TOKEN"
    }
    r = client.post("/api/cv/ai-builder", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCESS"
