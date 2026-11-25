"""PasteBackend interface: text -> focused app, on any OS.

Hyprland today (`wtype` + `wl-copy`+`hyprctl`); Windows/macOS tomorrow
(`pbcopy`+`osascript`, `clip`+`SendKeys`, etc.). Every backend returns a
`PasteResult` so callers can tell "pasted" apart from "clipboard set but
the keystroke never landed" without reading logs.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from ..paste import PasteResult


@runtime_checkable
class PasteBackend(Protocol):
    """Pluggable paste strategy."""

    name: str

    def available(self) -> bool:
        ...

    def paste(self, text: str, method: str | None = None) -> PasteResult:
        """Paste text. `method` is accepted for pipeline compat and ignored
        (the backend was already selected by method at factory time)."""
        ...
