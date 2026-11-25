"""Dictation session lifecycle: the state machine behind start/stop/toggle.

Previously this lived inside cli.py, interleaved with argument parsing,
user-facing messages, and the recording pipeline itself: pidfile checks were
re-implemented per command and the stop→wait→cleanup sequence could only run
by spawning real processes. Now one module owns it all — paths, pidfiles,
worker/overlay spawning, stop-request, result waiting, and cleanup — behind a
narrow interface. cli.py is just the adapter that parses args, calls in, and
prints what comes back.
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time

from . import state

WORKER_TIMEOUT = 90  # first run downloads the .cact; afterwards seconds


def is_recording() -> int | None:
    """PID of the running record worker, or None."""
    pidfile = state.pid_path()
    if not pidfile.exists():
        return None
    try:
        pid = int(pidfile.read_text().strip())
    except Exception:
        pidfile.unlink(missing_ok=True)
        return None
    try:
        os.kill(pid, 0)
        return pid
    except ProcessLookupError:
        pidfile.unlink(missing_ok=True)
        return None
    except PermissionError:
        return pid


def _kill_pidfile(pidfile) -> None:
    try:
        if pidfile.exists():
            os.kill(int(pidfile.read_text().strip()), signal.SIGTERM)
    except Exception:
        pass
    try:
        pidfile.unlink(missing_ok=True)
    except Exception:
        pass


def spawn_overlay() -> None:
    """Start the GTK card (instant feedback). Runs on system python (gi+cairo)."""
    try:
        from pathlib import Path as _P
        _root = str(_P(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env["PYTHONPATH"] = _root + (os.pathsep + env["PYTHONPATH"]
                                     if env.get("PYTHONPATH") else "")
        po = subprocess.Popen(["/usr/bin/python3", "-m", "whistle_dictate.gtk_overlay"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True, env=env)
        state.osd_pid_path().write_text(str(po.pid))
    except Exception:
        pass


def spawn_worker() -> int:
    """Start the detached `_record` worker. Returns its pid."""
    cmd = [sys.executable, "-m", "whistle_dictate.cli", "_record"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    state.pid_path().write_text(str(p.pid))
    return p.pid


def request_stop() -> None:
    state.stop_path().touch(exist_ok=True)


def wait_result(timeout: float = WORKER_TIMEOUT) -> dict | None:
    """Wait for the worker's result file. Returns the dict, or None on timeout."""
    result = None
    for _ in range(int(timeout * 10)):
        try:
            if state.result_path().exists():
                result = json.loads(state.result_path().read_text(encoding="utf-8"))
                break
        except Exception:
            pass
        time.sleep(0.1)
    return result


def reap_overlay() -> None:
    """Let the card show its final state, then make sure it exits."""
    for _ in range(40):
        try:
            os.kill(int(state.osd_pid_path().read_text().strip()), 0)
            alive = True
        except Exception:
            alive = False
            break
        if not alive:
            break
        time.sleep(0.1)
    _kill_pidfile(state.osd_pid_path())
    try:
        state.osd_path().unlink(missing_ok=True)
    except Exception:
        pass


def stop_and_wait(timeout: float = WORKER_TIMEOUT):
    """Stop a running session and wait for transcription.

    Returns (status, result) with status in {"ok", "not-recording", "timeout"}.
    Always cleans up pidfile + result file; overlay reaping is the caller's
    (it owns the UI timing) via reap_overlay().
    """
    if is_recording() is None:
        return ("not-recording", None)
    request_stop()
    result = wait_result(timeout)
    try:
        state.pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    try:
        state.result_path().unlink()
    except Exception:
        pass
    if result is None:
        return ("timeout", None)
    return ("ok", result)


def kill_overlay() -> None:
    """Kill the card immediately (cancel path — no final state to show)."""
    _kill_pidfile(state.osd_pid_path())
    try:
        state.osd_path().unlink(missing_ok=True)
    except Exception:
        pass


def cancel() -> bool:
    """Discard a running session. Returns True if one was running."""
    running = is_recording() is not None
    pid = is_recording()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    kill_overlay()
    try:
        state.pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    try:
        state.stop_path().unlink(missing_ok=True)
    except Exception:
        pass
    try:
        state.result_path().unlink()
    except Exception:
        pass
    return running
