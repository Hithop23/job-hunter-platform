from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.config import Settings


def create_app(settings: Settings) -> FastAPI:
    """API local del dashboard (se amplía en F6)."""
    app = FastAPI(title="JOB-HUNTER-CO", version=__version__)
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app


def _module_app() -> FastAPI:
    from app.config import load_settings

    return create_app(load_settings())


app = _module_app()
