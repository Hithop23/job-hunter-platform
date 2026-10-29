import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.storage.database import init_db
from app.api.routes_jobs import router as jobs_router
from app.api.routes_applications import router as apps_router
from app.api.routes_hil import router as hil_router
from app.api.routes_stats import router as stats_router
from app.api.routes_cv import router as cv_router

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = BASE_DIR / "logs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
VARIANTS_DIR = BASE_DIR / "cv" / "variants"
VARIANTS_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    init_db()
    yield


app = FastAPI(
    title="JOB-HUNTER-CO API",
    description="Agente automatizado de búsqueda, preparación y seguimiento laboral para Colombia (Julian David Diaz Medina)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount endpoints
app.include_router(jobs_router)
app.include_router(apps_router)
app.include_router(hil_router)
app.include_router(stats_router)
app.include_router(cv_router)

# Mount static asset dirs
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")
app.mount("/cv_downloads", StaticFiles(directory=str(VARIANTS_DIR)), name="cv_downloads")


@app.get("/", response_class=HTMLResponse)
def get_dashboard_html():
    """Serves the standalone modern responsive SPA dashboard."""
    html_path = BASE_DIR / "app" / "api" / "dashboard.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>JOB-HUNTER-CO Dashboard</h1>"
