"""Paste backend factory.

`get_backend(cfg)` maps `paste_method` ("auto" | "wtype" | "clipboard" |
"stdout") to a backend object. "auto" keeps today's Hyprland behavior
(wtype, else clipboard). Platform-specific backends (darwin/windows)
register here later; unknown names raise visibly.
"""
from __future__ import annotations

from .base import PasteBackend
from ..paste import PasteResult

_AVAILABLE = ("auto", "hyprland", "wtype", "clipboard", "stdout")


def available() -> tuple[str, ...]:
    return _AVAILABLE


def create(name: str | None = None) -> PasteBackend:
    from .hyprland import ClipboardBackend, HyprlandBackend, StdoutBackend, WtypeBackend
    kind = (name or "auto").lower()
    if kind in ("auto", "hyprland"):
        return HyprlandBackend()
    if kind == "wtype":
        return WtypeBackend()
    if kind == "clipboard":
        return ClipboardBackend()
    if kind == "stdout":
        return StdoutBackend()
    raise ValueError(f"unknown paste backend {name!r} (available: {', '.join(_AVAILABLE)})")


def get_backend(cfg: dict | None = None) -> PasteBackend:
    return create((cfg or {}).get("paste_method", "auto") or "auto")


def paste_with(text: str, backend: PasteBackend | None = None,
               cfg: dict | None = None) -> PasteResult:
    be = backend or get_backend(cfg)
    return be.paste(text)


__all__ = ["PasteBackend", "available", "create", "get_backend", "paste_with"]
