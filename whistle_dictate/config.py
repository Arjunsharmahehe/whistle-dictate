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
    # pidfile + in-progress wav live in /tmp (or XDG_RUNTIME_DIR)
    base = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(base) / APP

DEFAULTS = {
    "language": None,          # None = auto-detect; else en/de/fr/es/it/nl/pl
    "keywords": [],            # vocabulary biasing, e.g. ["Siobhan", "Krzysztof"]
    "paste_method": "auto",    # auto | wtype | clipboard
    "sample_rate": 16000,
    "channels": 1,
    "mic": None,               # None = system default; else sounddevice index or name substring
    "sensitivity": 1.0,        # spectrum gate: >1 opens easier, <1 stricter (0.3..3)
    "overlay": True,           # floating waveform card; false = headless (saves ~65MB)
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


def _validate(cfg: dict, path) -> None:
    """Clamp/coerce known keys so a bad value degrades visibly, not silently."""
    try:
        s = float(cfg.get("sensitivity", 1.0))
    except (TypeError, ValueError):
        print(f"whistle-dictate: bad sensitivity {cfg.get('sensitivity')!r} in {path}; using 1.0",
              file=sys.stderr, flush=True)
        s = 1.0
    if not 0.3 <= s <= 3.0:
        print(f"whistle-dictate: sensitivity {s} out of range 0.3..3.0; clamping",
              file=sys.stderr, flush=True)
        s = max(0.3, min(3.0, s))
    cfg["sensitivity"] = s
    if not isinstance(cfg.get("overlay", True), bool):
        print(f"whistle-dictate: overlay must be true/false in {path}; using true",
              file=sys.stderr, flush=True)
        cfg["overlay"] = True

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
            '# paste_method = "auto"  # auto | wtype | clipboard\n'
            '# mic = null  # pin input: sounddevice index or name substring (see `whistle-dictate devices`)\n'
            '# sensitivity = 1.0  # spectrum gate strictness for noisy rooms\n'
            '# overlay = true  # floating waveform card; false = headless, saves ~65MB\n'
        )
    return c, d, s
