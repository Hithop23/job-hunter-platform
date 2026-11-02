import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.storage.database import get_db
from app.storage.repository import Repository
from app.storage.models import HumanReviewItem, ApplicationStatus
from app.security.supabase_auth import get_authenticated_user_id

BASE_DIR = Path(__file__).resolve().parent.parent.parent
router = APIRouter(prefix="/api/hil", tags=["Human in the Loop"])


class ResolveActionRequest(BaseModel):
    action: str  # APPROVED, REJECTED, DO_NOT_APPLY, EDITED
    user_input: Optional[str] = None


class OpenSessionRequest(BaseModel):
    url: Optional[str] = "https://www.linkedin.com/login"


ALLOWED_BROWSER_DOMAINS = (
    "linkedin.com",
    "computrabajo.com",
    "elempleo.com",
    "elempleo.com.co",
    "indeed.com",
    "sena.edu.co",
    "remoteok.com",
    "remotive.com",
    "weworkremotely.com",
    "arbeitnow.com",
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "taleo.net",
    "icims.com",
)


def validate_browser_url(target_url: Optional[str]) -> str:
    if not target_url:
        raise HTTPException(status_code=400, detail="Debes proporcionar una URL válida")

    try:
        parsed_url = urlsplit(target_url)
        hostname = (parsed_url.hostname or "").lower()
        port = parsed_url.port
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="URL inválida") from exc

    allowed_domain = any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_BROWSER_DOMAINS
    )
    if (
        parsed_url.scheme.lower() != "https"
        or not hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or port not in (None, 443)
        or not allowed_domain
    ):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten URLs HTTPS de portales de empleo autorizados",
        )

    return target_url


@router.get("/pending")
def list_pending_reviews(db: Session = Depends(get_db)):
    """Returns list of applications requiring human intervention (CAPTCHA, 2FA, questions, login)."""
    repo = Repository(db)
    reviews = repo.list_pending_reviews()
    return {
        "count": len(reviews),
        "items": [
            {
                "id": r.id,
                "application_id": r.application_id,
                "company": r.application.company if r.application else "Desconocida",
                "position": r.application.position if r.application else "Desconocido",
                "reason": r.reason,
                "url": r.url,
                "screenshot_path": r.screenshot_path,
                "question_prompt": r.question_prompt,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]
    }


from app.browser.desktop_launcher import launch_desktop_browser


@router.post("/open-session")
def open_general_browser_session(
    req: Optional[OpenSessionRequest] = None,
    authenticated_user_id: str = Depends(get_authenticated_user_id),
):
    """
    Opens a visible desktop browser window using the persistent profile ('data/browser_profile').
    The user can log in to LinkedIn, Computrabajo, etc.
    All cookies and sessions are permanently saved.
    """
    target_url = (req.url if req and req.url else "https://www.linkedin.com/login")
    target_url = validate_browser_url(target_url)
    res = launch_desktop_browser(target_url)

    return {
        "status": "opened" if res.get("success") else "error",
        "method": res.get("method"),
        "browser": res.get("browser"),
        "message": res.get("message", f"Navegador abierto en pantalla en {target_url}."),
        "url": target_url
    }


@router.post("/{review_id}/open-browser")
def open_browser_for_review(
    review_id: str,
    authenticated_user_id: str = Depends(get_authenticated_user_id),
    db: Session = Depends(get_db),
):
    """
    Opens a visible desktop browser directly at the URL of the paused application,
    allowing the user to solve CAPTCHA, log in, or complete the necessary step on screen.
    """
    repo = Repository(db)
    review = repo.db.query(HumanReviewItem).filter(HumanReviewItem.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Revisión no encontrada")

    target_url = validate_browser_url(review.url)
    res = launch_desktop_browser(target_url)

    return {
        "status": "opened" if res.get("success") else "error",
        "method": res.get("method"),
        "browser": res.get("browser"),
        "message": res.get("message", "Navegador interactivo abierto en tu pantalla para esta vacante."),
        "url": target_url
    }


@router.post("/{review_id}/action")
def resolve_review(
    review_id: str,
    req: ResolveActionRequest,
    db: Session = Depends(get_db)
):
    """User provides decision: [Continuar / Aprobar], [Rechazar / No Aplicar], o [Editar]."""
    repo = Repository(db)
    res = repo.resolve_human_review(review_id, action=req.action, user_input=req.user_input)
    if not res:
        raise HTTPException(status_code=404, detail="Elemento de revisión no encontrado")

    return {
        "message": f"Acción '{req.action}' registrada. La postulación ahora está en estado '{res.application.status if res.application else 'READY'}'.",
        "review_id": res.id,
        "application_id": res.application_id,
        "resolved": res.resolved,
        "action": res.user_action,
    }
