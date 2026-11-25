"""Config + paths. Mirrors Hex's layout (XDG) but Python-simple."""
from __future__ import annotations
import os
import sys
from pathlib import Path
import tomllib

APP = "whistle-dictate"

def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP

def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP

def state_dir() -> Path:
    # pidfile + result/state files live in the runtime dir (fresh per login)
    base = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(base) / APP

DEFAULTS = {
    "language": None,          # None = auto-detect; else en/de/fr/es/it/nl/pl
    "keywords": [],            # vocabulary biasing, e.g. ["Siobhan", "Krzysztof"]
    "paste_method": "auto",    # auto | wtype | clipboard | hyprland | stdout
    "transcriber": "whistle",  # transcription engine; only "whistle" today
    "audio_source": "sounddevice",  # mic backend; only "sounddevice" today
    "notifier": "auto",        # auto | noctalia | noop (short OSD feedback)
    "sample_rate": 16000,
    "channels": 1,
    "mic": None,               # None = system default; else sounddevice index or name substring
    "sensitivity": 1.0,        # spectrum gate: >1 opens easier, <1 stricter (0.3..3)
    "overlay": True,           # true = auto card (gtk on Linux); false/"noop" = headless
}

def load_config() -> dict:
    cfg = dict(DEFAULTS)
    p = config_dir() / "config.toml"
    if p.exists():
        try:
            with p.open("rb") as f:
                user = tomllib.load(f)
            for k, v in user.items():
                if k in cfg:
                    cfg[k] = v
                else:
                    print(f"whistle-dictate: ignoring unknown config key {k!r} in {p}",
                          file=sys.stderr, flush=True)
        except Exception:
            pass
    _validate(cfg, p)
    return cfg


SENSITIVITY_MIN, SENSITIVITY_MAX = 0.3, 3.0


def _validate(cfg: dict, path) -> None:
    """Clamp/coerce known keys so a bad value degrades visibly, not silently."""
    try:
        s = float(cfg.get("sensitivity", 1.0))
    except (TypeError, ValueError):
        print(f"whistle-dictate: bad sensitivity {cfg.get('sensitivity')!r} in {path}; using 1.0",
              file=sys.stderr, flush=True)
        s = 1.0
    if not SENSITIVITY_MIN <= s <= SENSITIVITY_MAX:
        print(f"whistle-dictate: sensitivity {s} out of range "
              f"{SENSITIVITY_MIN}..{SENSITIVITY_MAX}; clamping",
              file=sys.stderr, flush=True)
        s = max(SENSITIVITY_MIN, min(SENSITIVITY_MAX, s))
    cfg["sensitivity"] = s
    ov = cfg.get("overlay", True)
    if not isinstance(ov, (bool, str)):
        print(f"whistle-dictate: overlay must be true/false or a backend name in {path}; using true",
              file=sys.stderr, flush=True)
        cfg["overlay"] = True
    for key in ("transcriber", "audio_source", "notifier", "paste_method"):
        v = cfg.get(key)
        if v is not None and not isinstance(v, str):
            print(f"whistle-dictate: {key} must be a string in {path}; using default",
                  file=sys.stderr, flush=True)
            cfg[key] = DEFAULTS[key]


def sample_rate(cfg: dict) -> int:
    """Validated sample rate (single home for the 16000 default)."""
    return int(cfg.get("sample_rate", 16000))


def paste_method(cfg: dict) -> str:
    """Validated paste method (single home for the 'auto' default)."""
    return cfg.get("paste_method", "auto") or "auto"


def transcriber_name(cfg: dict) -> str:
    """Validated transcriber name (single home for the 'whistle' default)."""
    return cfg.get("transcriber", "whistle") or "whistle"


def audio_source_name(cfg: dict) -> str:
    """Validated audio source name (single home for 'sounddevice')."""
    return cfg.get("audio_source", "sounddevice") or "sounddevice"


def notifier_name(cfg: dict) -> str:
    """Validated notifier name (single home for the 'auto' default)."""
    return cfg.get("notifier", "auto") or "auto"


def sensitivity(cfg: dict) -> float:
    """Validated gate sensitivity (already clamped by _validate)."""
    return float(cfg.get("sensitivity", 1.0))

def ensure_dirs() -> tuple[Path, Path, Path]:
    c, d, s = config_dir(), data_dir(), state_dir()
    c.mkdir(parents=True, exist_ok=True)
    d.mkdir(parents=True, exist_ok=True)
    s.mkdir(parents=True, exist_ok=True)
    # seed example config if missing
    example = c / "config.toml"
    if not example.exists():
        example.write_text(
            '# None = auto-detect. Whistle langs: en, de, fr, es, it, nl, pl\n'
            '# language = "en"\n'
            '# vocabulary biasing (Hex calls this Vocabulary)\n'
            '# keywords = ["Siobhan", "Krzysztof"]\n'
            '# paste_method = "auto"  # auto | wtype | clipboard | hyprland | stdout\n'
            '# transcriber = "whistle"  # transcription engine (only "whistle" today)\n'
            '# audio_source = "sounddevice"  # mic backend (only "sounddevice" today)\n'
            '# notifier = "auto"  # auto | noctalia | noop\n'
            '# mic = null  # pin input: sounddevice index or name substring (see `whistle-dictate devices`)\n'
            '# sensitivity = 1.0  # spectrum gate strictness for noisy rooms\n'
            '# overlay = true  # floating card (gtk on Linux); false = headless\n'
        )
    return c, d, s
