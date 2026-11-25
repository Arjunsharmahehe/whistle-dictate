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

WORKER_TIMEOUT = 90  # first run downloads the .cact; afterwards transcription takes seconds
POLL_INTERVAL = 0.1  # result-file / process-liveness poll cadence
REAP_ROUNDS = 40     # overlay grace period: 40 x 0.1s to show its final card


def _read_pid(pidfile) -> int | None:
    """Parse a pidfile. None when missing or garbage (file removed)."""
    try:
        return int(pidfile.read_text().strip())
    except Exception:
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def is_recording() -> int | None:
    """PID of the running record worker, or None."""
    pid = _read_pid(state.pid_path())
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
        return pid
    except ProcessLookupError:
        state.safe_unlink(state.pid_path())
        return None
    except PermissionError:
        return pid


def _kill_pidfile(pidfile, sig=signal.SIGTERM) -> None:
    pid = _read_pid(pidfile)
    if pid is not None:
        try:
            os.kill(pid, sig)
        except Exception:
            pass
    state.safe_unlink(pidfile)


def _spawn_detached(argv: list, env=None) -> int:
    """Launch a detached child (stdio to null). Returns its pid."""
    p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=env)
    return p.pid


def spawn_overlay() -> None:
    """Start the GTK card (instant feedback). Runs on system python (gi+cairo)."""
    try:
        from pathlib import Path as _P
        _root = str(_P(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env["PYTHONPATH"] = _root + (os.pathsep + env["PYTHONPATH"]
                                     if env.get("PYTHONPATH") else "")
        pid = _spawn_detached(["/usr/bin/python3", "-m", "whistle_dictate.gtk_overlay"],
                              env=env)
        state.osd_pid_path().write_text(str(pid))
    except Exception:
        pass


def spawn_worker() -> int:
    """Start the detached `_record` worker. Returns its pid."""
    pid = _spawn_detached([sys.executable, "-m", "whistle_dictate.cli", "_record"])
    state.pid_path().write_text(str(pid))
    return pid


def request_stop() -> None:
    state.stop_path().touch(exist_ok=True)


def wait_result(timeout: float = WORKER_TIMEOUT) -> dict | None:
    """Wait for the worker's result file. Returns the dict, or None on timeout."""
    result = None
    for _ in range(int(timeout / POLL_INTERVAL)):
        try:
            if state.result_path().exists():
                result = json.loads(state.result_path().read_text(encoding="utf-8"))
                break
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return result


def reap_overlay() -> None:
    """Let the card show its final state, then make sure it exits."""
    for _ in range(REAP_ROUNDS):
        pid = _read_pid(state.osd_pid_path())
        if pid is None:
            break
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        except PermissionError:
            pass
        time.sleep(POLL_INTERVAL)
    _kill_pidfile(state.osd_pid_path())
    state.safe_unlink(state.osd_path())


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
    state.safe_unlink(state.pid_path(), state.result_path())
    if result is None:
        return ("timeout", None)
    return ("ok", result)


def kill_overlay() -> None:
    """Kill the card immediately (cancel path — no final state to show)."""
    _kill_pidfile(state.osd_pid_path())
    state.safe_unlink(state.osd_path())


def cancel() -> bool:
    """Discard a running session. Returns True if one was running."""
    pid = is_recording()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    kill_overlay()
    state.safe_unlink(state.pid_path(), state.stop_path(), state.result_path())
    return pid is not None
