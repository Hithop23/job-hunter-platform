import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("job_hunter.security.turnstile")

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Cloudflare official testing keys:
# Sitekey: 1x00000000000000000000AA (Always passes)
# Secret key: 1x0000000000000000000000000000000AA (Always passes)
DEFAULT_TEST_SITE_KEY = "1x00000000000000000000AA"
DEFAULT_TEST_SECRET_KEY = "1x0000000000000000000000000000000AA"


def get_turnstile_site_key() -> str:
    return (
        os.getenv("CLOUDFLARE_TURNSTILE_SITE_KEY")
        or os.getenv("TURNSTILE_SITE_KEY")
        or DEFAULT_TEST_SITE_KEY
    ).strip()


def get_turnstile_secret_key() -> str:
    return (
        os.getenv("CLOUDFLARE_TURNSTILE_SECRET_KEY")
        or os.getenv("TURNSTILE_SECRET_KEY")
        or DEFAULT_TEST_SECRET_KEY
    ).strip()


def verify_turnstile_token(token: str, remote_ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies Cloudflare Turnstile token against Cloudflare's siteverify API.
    Returns the parsed JSON response with 'success': True/False.
    """
    if not token or not token.strip():
        return {
            "success": False,
            "error-codes": ["missing-input-response"],
            "message": "Token de verificación Turnstile no proporcionado."
        }

    secret = get_turnstile_secret_key()
    post_data = {
        "secret": secret,
        "response": token.strip()
    }
    if remote_ip:
        post_data["remoteip"] = remote_ip

    encoded_data = urllib.parse.urlencode(post_data).encode("utf-8")

    try:
        req = urllib.request.Request(
            TURNSTILE_VERIFY_URL,
            data=encoded_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "JobHunter-Platform/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            logger.info("Cloudflare Turnstile verification response: %s", data.get("success"))
            return data
    except urllib.error.HTTPError as e:
        logger.error("HTTP error verifying Turnstile: %s", e)
        return {"success": False, "error-codes": [f"http-error-{e.code}"]}
    except Exception as e:
        logger.error("Unexpected error verifying Turnstile: %s", e)
        # In case of temporary network glitches with Cloudflare, avoid hard-blocking user if testing
        if secret == DEFAULT_TEST_SECRET_KEY:
            return {"success": True, "warning": "Fallback pass on testing environment"}
        return {"success": False, "error-codes": ["network-timeout"]}


router = APIRouter(prefix="/api/security/turnstile", tags=["Cloudflare Turnstile"])


class TurnstileVerifyPayload(BaseModel):
    token: str


@router.get("/config")
def get_turnstile_config():
    """
    Returns public Turnstile configuration for frontend rendering.
    """
    site_key = get_turnstile_site_key()
    is_test = (site_key == DEFAULT_TEST_SITE_KEY)
    return {
        "site_key": site_key,
        "is_test_mode": is_test,
        "provider": "Cloudflare Turnstile",
        "status": "ACTIVE"
    }


@router.post("/verify")
def verify_turnstile_endpoint(payload: TurnstileVerifyPayload, request: Request):
    """
    Verifies a Turnstile challenge token sent by the browser.
    """
    client_ip = request.client.host if request.client else None
    result = verify_turnstile_token(payload.token, remote_ip=client_ip)

    if not result.get("success"):
        error_codes = result.get("error-codes", [])
        raise HTTPException(
            status_code=400,
            detail=f"Verificación de seguridad Cloudflare fallida: {', '.join(error_codes)}"
        )

    return {
        "status": "SUCCESS",
        "verified": True,
        "message": "Desafío de Cloudflare Turnstile superado correctamente.",
        "challenge_ts": result.get("challenge_ts"),
        "hostname": result.get("hostname")
    }
