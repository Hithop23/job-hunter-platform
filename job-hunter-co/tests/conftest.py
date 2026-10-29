from __future__ import annotations

import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters import clear_registry
from app.adapters.base import AdapterContext
from app.config import PROJECT_ROOT, Settings
from app.db import init_db


@pytest.fixture(autouse=True)
def _reset_adapter_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data/applications.db",
        logs_dir=tmp_path / "logs",
        browser_profile_dir=tmp_path / "data/browser_profile",
        screenshots_dir=tmp_path / "data/screenshots",
        cv_dir=tmp_path / "cv",
        cv_variants_dir=tmp_path / "cv/variants",
    )


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    yield db
    db.close()


@pytest.fixture
def ctx(session, settings):
    return AdapterContext(session=session, settings=settings)


@pytest.fixture
def settings_with_data(settings):
    """Settings con los archivos reales de data/ copiados a tmp."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("profile.json", "keywords.json", "companies.json"):
        shutil.copy(PROJECT_ROOT / "data" / name, settings.data_dir / name)
    return settings


@pytest.fixture
def real_matcher(settings_with_data):
    from app.matching.engine import JobMatcher
    from app.matching.profile import load_keywords, load_profile

    return JobMatcher(
        load_profile(settings_with_data.data_dir / "profile.json"),
        load_keywords(settings_with_data.data_dir / "keywords.json"),
        settings_with_data,
    )
