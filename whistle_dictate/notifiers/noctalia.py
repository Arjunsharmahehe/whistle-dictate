"""Noctalia notifier: current Hyprland OSD (unchanged behavior)."""
from __future__ import annotations

from .. import osd as _osd


class NoctaliaBackend:
    name = "noctalia"

    def available(self) -> bool:
        return _osd.available()

    def notify(self, msg: str) -> None:
        _osd.notify(msg)


class NoopBackend:
    name = "noop"

    def available(self) -> bool:
        return True

    def notify(self, msg: str) -> None:
        return None
