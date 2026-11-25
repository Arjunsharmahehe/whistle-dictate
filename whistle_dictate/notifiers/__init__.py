"""Notifier factory: config -> backend.

Default is Noctalia-on-Hyprland, NoOp elsewhere. `notifier = "noop"`
forces silence (tests/servers). Unknown names raise visibly.
"""
from __future__ import annotations

from .base import NotifierBackend
from .. import platform as _platform

_AVAILABLE = ("auto", "noctalia", "noop", "none")


def available() -> tuple[str, ...]:
    return _AVAILABLE


def create(name: str | None = None) -> NotifierBackend:
    from .noctalia import NoctaliaBackend, NoopBackend
    kind = (name or "auto").lower() if isinstance(name, str) else "auto"
    if kind in ("noop", "none"):
        return NoopBackend()
    if kind == "noctalia":
        return NoctaliaBackend()
    if kind == "auto":
        if _platform.is_hyprland() or _platform.have("noctalia"):
            return NoctaliaBackend()
        return NoopBackend()
    raise ValueError(f"unknown notifier {name!r} (available: {', '.join(_AVAILABLE)})")


def get_backend(cfg: dict | None = None) -> NotifierBackend:
    return create((cfg or {}).get("notifier", "auto") or "auto")


__all__ = ["NotifierBackend", "available", "create", "get_backend"]
