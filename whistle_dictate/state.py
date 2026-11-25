"""Shared overlay-state seam between the record worker and the GTK overlay.

Single owner of the on-disk protocol both processes speak: file names, the
Phase values, the dict keys and their defaults. Previously this lived as
string literals scattered over cli.py (10 write sites) and gtk_overlay.py
(each with its own copy of the path logic) — a rename or missed key failed
silently at runtime. Now there is one module to read and one to test.

Stdlib only, so the system-python overlay can import it too.
"""
from __future__ import annotations
import json
from pathlib import Path

from .config import state_dir

NBANDS = 24

PIDFILE = "rec.pid"
STOPFILE = "rec.stop"
RESULTFILE = "rec.result.json"
OSDFILE = "rec.osd.json"
OSDPIDFILE = "rec.osd.pid"


class Phase:
    """Overlay lifecycle phases. DISMISS = successful paste: fade out, no card."""

    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"
    DISMISS = "dismiss"
    ALL = (RECORDING, TRANSCRIBING, DONE, ERROR, DISMISS)


def _base() -> Path:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def pid_path() -> Path:
    return _base() / PIDFILE


def stop_path() -> Path:
    return _base() / STOPFILE


def result_path() -> Path:
    return _base() / RESULTFILE


def osd_path() -> Path:
    return _base() / OSDFILE


def osd_pid_path() -> Path:
    return _base() / OSDPIDFILE


def blank_spec() -> list[float]:
    return [0.0] * NBANDS


def safe_unlink(*paths: Path) -> None:
    """Best-effort unlink of any number of paths. Never raises."""
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def write(phase: str, elapsed: float = 0.0, spec=None, peak: float = 0.0,
          text: str = "", reason: str = "") -> None:
    """Publish overlay state. Never raises — the worker must not die on UI."""
    try:
        osd_path().write_text(json.dumps({
            "phase": phase,
            "elapsed": elapsed,
            "spec": list(spec) if spec is not None else blank_spec(),
            "peak": peak,
            "text": text,
            "reason": reason,
        }))
    except Exception:
        pass


def read() -> dict:
    """Read overlay state with safe defaults. Never raises."""
    try:
        st = json.loads(osd_path().read_text())
        if not isinstance(st, dict):
            st = {}
    except Exception:
        st = {}
    out = {"phase": Phase.RECORDING, "elapsed": 0.0, "spec": blank_spec(),
           "peak": 0.0, "text": "", "reason": ""}
    for k in out:
        if k in st:
            out[k] = st[k]
    if out["phase"] not in Phase.ALL:
        out["phase"] = Phase.RECORDING
    try:
        out["elapsed"] = float(out.get("elapsed", 0.0))
    except (TypeError, ValueError):
        out["elapsed"] = 0.0
    spec = out.get("spec") or []
    clean = []
    for v in list(spec)[:NBANDS]:
        try:
            clean.append(max(0.0, min(1.0, float(v))))
        except (TypeError, ValueError):
            clean.append(0.0)
    while len(clean) < NBANDS:
        clean.append(0.0)
    out["spec"] = clean
    return out
