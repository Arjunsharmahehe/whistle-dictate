"""NotifierBackend interface: short user feedback, on any OS.

Hyprland today uses Noctalia's OSD card; everywhere else falls back to
stderr-safe no-op/print so `notify()` never raises and never blocks the
pipeline.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class NotifierBackend(Protocol):
    """Pluggable one-line user feedback."""

    name: str

    def available(self) -> bool:
        ...

    def notify(self, msg: str) -> None:
        ...
