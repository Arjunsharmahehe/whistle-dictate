"""Hyprland paste backend: current Wayland implementation.

Delegates to the existing `paste.py` adapters (wtype first, then
wl-copy + hyprctl sendshortcut) so behavior on Hyprland is unchanged.
Future desktop backends live alongside this module.
"""
from __future__ import annotations

from .. import paste as _paste
from ..paste import PasteResult


class HyprlandBackend:
    name = "hyprland"

    def available(self) -> bool:
        return _paste.have("wtype") or _paste.have("wl-copy")

    def paste(self, text: str, method: str | None = None) -> PasteResult:
        return _paste.paste_text(text, method="auto")


class WtypeBackend:
    """Forced wtype-only variant (respects `paste_method = wtype`)."""

    name = "wtype"

    def available(self) -> bool:
        return _paste.have("wtype")

    def paste(self, text: str, method: str | None = None) -> PasteResult:
        return _paste.paste_text(text, method="wtype")


class ClipboardBackend:
    """Forced clipboard-only variant (respects `paste_method = clipboard`)."""

    name = "clipboard"

    def available(self) -> bool:
        return _paste.have("wl-copy")

    def paste(self, text: str, method: str | None = None) -> PasteResult:
        return _paste.paste_text(text, method="clipboard")


class StdoutBackend:
    """Headless fallback: prints instead of pasting (never fails)."""

    name = "stdout"

    def available(self) -> bool:
        return True

    def paste(self, text: str, method: str | None = None) -> PasteResult:
        return _paste.paste_text(text, method="stdout")
