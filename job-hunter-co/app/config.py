from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuración global de JOB-HUNTER-CO.

    Toda variable de entorno usa el prefijo JHC_ (ver .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="JHC_",
        extra="ignore",
    )

    # --- Rutas (relativas a la raíz del proyecto) -------------------------
    data_dir: Path = Path("data")
    db_path: Path = Path("data/applications.db")
    logs_dir: Path = Path("logs")
    browser_profile_dir: Path = Path("data/browser_profile")
    screenshots_dir: Path = Path("data/screenshots")
    cv_dir: Path = Path("cv")
    cv_variants_dir: Path = Path("cv/variants")

    # --- Control de volumen (Módulo 7) -----------------------------------
    max_concurrent_browsers: int = 2
    max_same_domain_per_hour: int = 10
    max_applications_per_day: int = 50
    same_employer_cooldown_hours: int = 72
    request_min_wait_seconds: float = 8.0
    request_max_wait_seconds: float = 25.0
    retry_backoff_base_seconds: float = 30.0
    retry_backoff_factor: float = 2.0
    max_retries: int = 3

    # --- Motor de compatibilidad (Módulo 3) -------------------------------
    high_priority_threshold: int = 75
    review_threshold: int = 60
    skill_weight: float = 0.40
    education_weight: float = 0.20
    experience_weight: float = 0.20
    location_weight: float = 0.10
    keyword_weight: float = 0.10

    # --- Modo AUTOPILOT (Módulo 15) ---------------------------------------
    autopilot_enabled: bool = False

    # --- Notificaciones (Módulo 17; consola+logs por defecto) -------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email_to: str = ""

    def resolve(self, path: Path | str) -> Path:
        """Devuelve una ruta absoluta (relativas contra la raíz del proyecto)."""
        p = Path(path)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    def ensure_dirs(self) -> None:
        for name in (
            "data_dir",
            "logs_dir",
            "browser_profile_dir",
            "screenshots_dir",
            "cv_dir",
            "cv_variants_dir",
        ):
            self.resolve(getattr(self, name)).mkdir(parents=True, exist_ok=True)
        self.resolve(self.db_path).parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
