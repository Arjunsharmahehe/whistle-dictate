"""Platform detection: OS + desktop + capability probes.

Stdlib only so every backend (including the system-python overlay) can
import it. This module never imports numpy, sounddevice, gi, or cactus —
it only answers "where am I running" so factories can pick defaults.
"""
from __future__ import annotations
import os
import platform
import shutil


def os_name() -> str:
    """Normalized OS: 'linux' | 'darwin' | 'windows' | other sys.platform."""
    p = platform.system().lower()
    if p.startswith("linux"):
        return "linux"
    if p.startswith("darwin"):
        return "darwin"
    if p.startswith("windows"):
        return "windows"
    return p or "unknown"


def desktop() -> str:
    """Desktop/compositor hint: 'hyprland' | 'wayland' | 'x11' | 'aqua' | ..."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if os.environ.get("HYPRLAND_CMD"):
        return "hyprland"
    wayland = os.environ.get("WAYLAND_DISPLAY")
    display = os.environ.get("DISPLAY")
    session = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
    session_type = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    if "hyprland" in session:
        return "hyprland"
    if wayland or session_type == "wayland":
        return "wayland"
    if display or session_type == "x11":
        return "x11"
    if os_name() == "darwin":
        return "aqua"
    if os_name() == "windows":
        return "windows"
    return "unknown"


def is_hyprland() -> bool:
    return desktop() == "hyprland"


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None
