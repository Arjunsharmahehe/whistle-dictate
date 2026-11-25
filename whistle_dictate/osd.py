"""User feedback via Noctalia's own OSD card (the same popup as the
performance/balanced switcher): top-center, no focus steal.

`noctalia msg osd-show <icon> <text...>` renders icon + one text line and
fades after a few idle seconds. Used for short confirmations and errors —
the live recording card is the GTK overlay, which reads shared state.
"""
from __future__ import annotations
import shutil
import subprocess

def available() -> bool:
    return shutil.which("noctalia") is not None

def show(icon: str, text: str) -> bool:
    """Show/replace the OSD card. Returns False when Noctalia is missing."""
    if not available():
        return False
    try:
        r = subprocess.run(["noctalia", "msg", "osd-show", icon, text],
                           capture_output=True, timeout=5, text=True)
        return r.returncode == 0
    except Exception:
        return False


def notify(msg: str) -> None:
    """Short user feedback on Noctalia's card. Never raises."""
    try:
        show("microphone", " ".join(str(msg).split())[:60])
    except Exception:
        pass
