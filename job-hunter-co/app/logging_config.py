from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

LOGGER_NAME = "jobhunter"

# Clave=valor o clave:valor con nombres sensibles → se redactan (Módulo 13).
_KV_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|cookie|authorization|api[_-]?key)"
    r"\b\s*([=:]\s*)[^\s,;]+"
)


def redact(text: str) -> str:
    """Oculta valores de credenciales en texto libre (nunca loguear secretos)."""
    if not text:
        return text or ""
    return _KV_SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    """Formato JSONL para el log persistente (una entrada por línea)."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.name,
            "message": redact(record.getMessage()),
        }
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {record.levelname:<7} | {record.name} | {redact(record.getMessage())}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(logs_dir: Path) -> logging.Logger:
    """Configura el logger raíz de la app: consola + archivo JSONL diario."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        logs_dir / f"jhc_{datetime.now():%Y%m%d}.jsonl", encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
