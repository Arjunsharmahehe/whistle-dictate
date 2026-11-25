"""GTK overlay backend: current Hyprland card (unchanged behavior)."""
from __future__ import annotations

from .. import session as _session


class GtkBackend:
    name = "gtk"

    def available(self) -> bool:
        try:
            import gi  # noqa: F401
            return True
        except Exception:
            # system python has gi even when the venv doesn't; spawning
            # still works, so report available and let spawn fail softly.
            return True

    def spawn(self) -> None:
        _session.spawn_overlay()

    def reap(self) -> None:
        _session.reap_overlay()


class NoopBackend:
    """Headless: no card process (saves ~65MB, used by overlay=false)."""

    name = "noop"

    def available(self) -> bool:
        return True

    def spawn(self) -> None:
        return None

    def reap(self) -> None:
        try:
            _session.reap_overlay()
        except Exception:
            pass
