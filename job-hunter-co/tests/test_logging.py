from app.logging_config import LOGGER_NAME, redact, setup_logging


def test_redact_basic():
    assert redact("token=abc123") == "token=[REDACTED]"
    assert redact("password: hunter2") == "password: [REDACTED]"
    assert redact("sin secretos aqui") == "sin secretos aqui"
    assert redact("") == ""


def test_no_secrets_in_logfile(tmp_path):
    logger = setup_logging(tmp_path)
    logger.warning("login falló token=abc123 password=hunter2")

    for handler in logger.handlers:
        handler.flush()

    files = list(tmp_path.glob("*.jsonl"))
    assert files, "debe existir el archivo de log JSONL"
    content = files[0].read_text(encoding="utf-8")
    assert "abc123" not in content
    assert "hunter2" not in content
    assert "[REDACTED]" in content
    assert LOGGER_NAME
