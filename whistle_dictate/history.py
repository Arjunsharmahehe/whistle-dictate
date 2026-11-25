"""History: JSONL log of dictations, like Hex's 7-day History."""
from __future__ import annotations
import json
import time
from pathlib import Path
from .config import data_dir

def history_path() -> Path:
    return data_dir() / "history.jsonl"

def append(entry: dict) -> None:
    p = history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), **entry}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def read(limit: int = 20) -> list[dict]:
    p = history_path()
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(out))

def last_text() -> str | None:
    items = read(1)
    return items[0].get("text") if items else None

def clear() -> None:
    p = history_path()
    if p.exists():
        p.unlink()
