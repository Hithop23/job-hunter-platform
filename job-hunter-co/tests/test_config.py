from app.config import Settings


def test_default_volume_limits():
    s = Settings(
        data_dir="data",
        db_path="data/x.db",
        logs_dir="logs",
        browser_profile_dir="data/bp",
        screenshots_dir="data/sh",
        cv_dir="cv",
        cv_variants_dir="cv/v",
    )
    assert s.max_applications_per_day == 50
    assert s.max_same_domain_per_hour == 10
    assert s.max_concurrent_browsers == 2
    assert s.high_priority_threshold == 75
    assert s.review_threshold == 60
    assert s.autopilot_enabled is False


def test_matching_weights_sum_one_hundred():
    s = Settings(
        data_dir="data",
        db_path="data/x.db",
        logs_dir="logs",
        browser_profile_dir="data/bp",
        screenshots_dir="data/sh",
        cv_dir="cv",
        cv_variants_dir="cv/v",
    )
    total = (
        s.skill_weight
        + s.education_weight
        + s.experience_weight
        + s.location_weight
        + s.keyword_weight
    )
    assert abs(total - 1.0) < 1e-9


def test_env_override(monkeypatch):
    monkeypatch.setenv("JHC_MAX_APPLICATIONS_PER_DAY", "7")
    s = Settings()
    assert s.max_applications_per_day == 7


def test_ensure_dirs(tmp_path):
    s = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data/applications.db",
        logs_dir=tmp_path / "logs",
        browser_profile_dir=tmp_path / "data/bp",
        screenshots_dir=tmp_path / "data/shots",
        cv_dir=tmp_path / "cv",
        cv_variants_dir=tmp_path / "cv/variants",
    )
    s.ensure_dirs()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "data/bp").is_dir()
    assert (tmp_path / "cv/variants").is_dir()
