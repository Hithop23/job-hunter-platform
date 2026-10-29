from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Hora UTC actual sin zona ni microsegundos (formato estable para SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def compute_dedup_hash(company: str, title: str, url: str) -> str:
    """Hash de respaldo para deduplicación: company + title + url (Módulo 2)."""
    payload = "|".join(
        part.strip().lower() for part in (company or "", title or "", url or "")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
