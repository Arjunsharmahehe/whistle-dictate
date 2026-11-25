"""Overlay factory: config -> backend.

`overlay = true` (default) picks GTK on Linux, NoOp elsewhere.
`overlay = false` always picks NoOp (headless). Unknown string names
raise visibly so future `overlay = "aqua"` fails loudly until added.
"""
from __future__ import annotations

from .base import OverlayBackend
from .. import platform as _platform

_AVAILABLE = ("auto", "gtk", "noop", "none", "false", "true")


def available() -> tuple[str, ...]:
    return _AVAILABLE


def create(name: str | bool | None = None) -> OverlayBackend:
    from .gtk import GtkBackend, NoopBackend
    if name is True or (isinstance(name, str) and name.lower() == "true"):
        name = "auto"
    if name is False or (isinstance(name, str) and name.lower() in ("false", "none", "noop")):
        return NoopBackend()
    kind = (name or "auto")
    kind = kind.lower() if isinstance(kind, str) else "auto"
    if kind == "auto":
        if _platform.os_name() == "linux":
            return GtkBackend()
        return NoopBackend()
    if kind == "gtk":
        return GtkBackend()
    if kind in ("noop", "none"):
        return NoopBackend()
    raise ValueError(f"unknown overlay backend {name!r} (available: {', '.join(_AVAILABLE)})")


def get_backend(cfg: dict | None = None) -> OverlayBackend:
    return create((cfg or {}).get("overlay", True))


__all__ = ["OverlayBackend", "available", "create", "get_backend"]
