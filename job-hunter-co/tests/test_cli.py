from app.main import main


def _isolate_env(monkeypatch, tmp_path):
    """Aísla los paths del CLI hacia tmp_path (no toca el proyecto)."""
    base = tmp_path / "jhc"
    monkeypatch.setenv("JHC_DATA_DIR", str(base / "data"))
    monkeypatch.setenv("JHC_DB_PATH", str(base / "data/applications.db"))
    monkeypatch.setenv("JHC_LOGS_DIR", str(base / "logs"))
    monkeypatch.setenv("JHC_BROWSER_PROFILE_DIR", str(base / "data/bp"))
    monkeypatch.setenv("JHC_SCREENSHOTS_DIR", str(base / "data/shots"))
    monkeypatch.setenv("JHC_CV_DIR", str(base / "cv"))
    monkeypatch.setenv("JHC_CV_VARIANTS_DIR", str(base / "cv/variants"))


def test_cli_scan_returns_zero(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    assert main(["scan"]) == 0


def test_cli_autopilot_blocked_without_confirmation(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JHC_AUTOPILOT_ENABLED", "true")
    assert main(["autopilot"]) == 2


def test_cli_autopilot_blocked_when_disabled(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JHC_AUTOPILOT_ENABLED", "false")
    assert main(["autopilot", "--i-confirm-autopilot"]) == 2


def test_cli_autopilot_confirmed(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JHC_AUTOPILOT_ENABLED", "true")
    assert main(["autopilot", "--i-confirm-autopilot"]) == 0


def test_cli_export_creates_csv(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    out = tmp_path / "export.csv"
    assert main(["export", "--out", str(out)]) == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8-sig")
    assert "company" in content
    assert "status" in content
