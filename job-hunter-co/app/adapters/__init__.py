"""Registry global de adapters de fuentes (Módulo 2 y 8)."""

from __future__ import annotations

from app.adapters.base import AdapterContext, BaseJobAdapter

_REGISTRY: dict[str, type[BaseJobAdapter]] = {}


def register(cls: type[BaseJobAdapter]) -> type[BaseJobAdapter]:
    """Inscribe un adapter en el registro (usar como decorador o helper)."""
    _REGISTRY[cls.source] = cls
    return cls


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


def build_adapters(
    ctx: AdapterContext, sources: list[str] | None = None
) -> list[BaseJobAdapter]:
    """Instancia los adapters solicitados (o todos los registrados)."""
    names = list(sources) if sources else available_sources()
    return [_REGISTRY[name](ctx) for name in names if name in _REGISTRY]


def clear_registry() -> None:
    """Solo para pruebas."""
    _REGISTRY.clear()
