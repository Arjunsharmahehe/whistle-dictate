"""Paste into the focused app on Hyprland/Wayland.

Strategy (same as Hex on Linux):
1. wtype if installed (virtual-keyboard protocol, wlroots/Hyprland) — types directly.
2. else wl-copy + hyprctl sendshortcut CTRL+V (clipboard paste), restoring old clipboard after.

Each Hyprland dispatch syntax lives behind its own adapter (modern Lua-0.57
vs legacy dispatch) behind one seam, and every strategy returns a
PasteResult — so callers can tell "pasted" apart from "clipboard set but the
keystroke never landed" without reading the debug log.
"""
from __future__ import annotations
import shutil
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PasteResult:
    """Outcome of a paste attempt. `delivered` = text is in the focused app."""

    method: str  # wtype | clipboard | clipboard-only | stdout | empty
    delivered: bool
    detail: str = ""


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def type_via_wtype(text: str) -> bool:
    if not have("wtype"):
        return False
    try:
        subprocess.run(["wtype", "--", text], check=True, timeout=15)
        return True
    except Exception:
        return False


def paste_via_wtype(text: str) -> PasteResult:
    """Virtual-keyboard typing adapter."""
    if type_via_wtype(text):
        return PasteResult("wtype", True)
    return PasteResult("wtype", False,
                       "wtype missing or failed" if not have("wtype")
                       else "wtype exited non-zero")


def _wl_copy_set(text: str) -> bool:
    """Set clipboard without blocking: wl-copy stays alive to serve it, so don't wait."""
    try:
        subprocess.Popen(["wl-copy", "--", text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except Exception:
        return False


TERMINAL_CLASSES = (
    "kitty", "foot", "footclient", "alacritty", "wezterm", "ghostty",
    "gnome-terminal", "gnome-terminal-server", "konsole", "xterm",
    "tilix", "terminator", "st-", "ptyxis", "blackbox", "warpterminal",
    "rio", "contour", "tabby",
)


def _active_window_class() -> str:
    """Hyprland focused app class, lowercase. '' when unknown."""
    try:
        r = subprocess.run(["hyprctl", "activewindow", "-j"],
                           capture_output=True, timeout=5, text=True)
        if r.returncode == 0:
            import json
            return str(json.loads(r.stdout).get("class", "")).lower()
    except Exception:
        pass
    return ""


def _run(cmd: list) -> tuple[bool, str]:
    """Run a hyprctl probe; ok = exit 0 and 'ok' in output. Returns (ok, log)."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=5, text=True)
        ok = r.returncode == 0 and "ok" in (r.stdout + r.stderr).lower()
        return ok, f"{' '.join(cmd[1:3])} -> rc={r.returncode} out={r.stdout.strip()!r}"
    except Exception as e:
        return False, f"{' '.join(cmd[1:3])} -> EXC {e}"


def send_shortcut_modern(mods: str, key: str) -> tuple[bool, str]:
    """Adapter: Hyprland 0.57+ Lua `hl.dsp.send_shortcut({mods,key,window})`."""
    return _run(["hyprctl", "eval",
                 f'return hl.dsp.send_shortcut({{mods="{mods}", key="{key}", window="activewindow"}})'])


def send_shortcut_legacy(mod: str, key: str, disp: str) -> tuple[bool, str]:
    """Adapter: pre-0.57 `hyprctl dispatch sendshortcut MOD,KEY,activewindow`."""
    return _run(["hyprctl", "dispatch", disp, f"{mod},{key},activewindow"])


def _hypr_paste(terminal: bool = False) -> tuple[bool, list]:
    """Send Ctrl+V (terminals: Ctrl+Shift+V). Returns (delivered, attempts)."""
    attempts: list = []
    mods_list = ("CTRL_SHIFT",) if terminal else ()
    mods_list = mods_list + ("CTRL", "ctrl", "CONTROL")
    for mods in mods_list:
        for key in ("V", "v"):
            ok, log = send_shortcut_modern(mods, key)
            attempts.append(log)
            if ok:
                _debug_log(attempts, True)
                return True, attempts
    for mod, key in (("CTRL", "V"), ("ctrl", "v"), ("CONTROL", "V")):
        for disp in ("sendshortcut", "send_shortcut"):
            ok, log = send_shortcut_legacy(mod, key, disp)
            attempts.append(log)
            if ok:
                _debug_log(attempts, True)
                return True, attempts
    _debug_log(attempts, False)
    return False, attempts


def _debug_log(attempts: list, delivered: bool) -> None:
    try:
        from .config import data_dir
        p = data_dir() / "paste-debug.log"
        with p.open("a", encoding="utf-8") as f:
            import time as _t
            f.write(f"--- {_t.strftime('%H:%M:%S')} delivered={delivered}\n")
            for a in attempts:
                f.write(f"  {a}\n")
    except Exception:
        pass


def paste_via_clipboard(text: str) -> PasteResult:
    """Clipboard adapter: wl-copy + Ctrl+V (terminals get Ctrl+Shift+V)."""
    if not have("wl-copy"):
        return PasteResult("clipboard", False, "wl-copy missing")
    cls = _active_window_class()
    terminal = any(t in cls for t in TERMINAL_CLASSES)
    old = None
    if have("wl-paste"):
        try:
            old = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=3).stdout
        except Exception:
            old = None
    if not _wl_copy_set(text):
        return PasteResult("clipboard", False, "wl-copy failed")
    time.sleep(0.3)  # let wl-copy claim the clipboard
    if not have("hyprctl"):
        _schedule_restore(old)
        return PasteResult("clipboard-only", False, "no hyprctl to send keys")
    delivered, _ = _hypr_paste(terminal=terminal)
    _schedule_restore(old)
    if delivered:
        return PasteResult("clipboard", True)
    return PasteResult("clipboard-only", False, "keystroke not delivered")


def _schedule_restore(old: bytes | None) -> None:
    """Restore the previous clipboard after 0.6s (Hex does ~500ms)."""
    def _restore():
        time.sleep(0.6)
        try:
            if old:
                p = subprocess.Popen(["wl-copy", "--"],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
                try:
                    p.communicate(input=old, timeout=3)
                except Exception:
                    p.kill()
            else:
                subprocess.run(["wl-copy", "--clear"], timeout=5)
        except Exception:
            pass
    import threading
    threading.Thread(target=_restore, daemon=True).start()


def paste_text(text: str, method: str = "auto") -> PasteResult:
    """Paste text via the configured strategy. Never raises for missing tools."""
    if not text:
        return PasteResult("empty", False, "no text")
    if method in ("auto", "wtype"):
        res = paste_via_wtype(text)
        if res.delivered:
            return res
        if method == "wtype":
            print(text, flush=True)
            return PasteResult("stdout", False, res.detail)
    if method in ("auto", "clipboard"):
        return paste_via_clipboard(text)
    print(text, flush=True)
    return PasteResult("stdout", False, "paste disabled by method")
