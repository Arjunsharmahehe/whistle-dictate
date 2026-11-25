"""Transcriber factory: name -> implementation.

`get_transcriber(cfg)` is the single home for engine selection. Today only
"whistle" exists; unknown names raise with the available list so future
Windows/Mac engines fail visibly instead of silently falling back.
"""
from __future__ import annotations
import threading

from .base import Transcriber, TranscriptionResult

_AVAILABLE = ("whistle",)
_lock = threading.Lock()
_default = None


def available() -> tuple[str, ...]:
    return _AVAILABLE


def create(name: str | None = None, **kwargs) -> Transcriber:
    """Build a transcriber by name (no caching)."""
    kind = (name or "whistle").lower()
    if kind == "whistle":
        from .whistle import WhistleTranscriber
        return WhistleTranscriber(**kwargs) if kwargs else WhistleTranscriber()
    raise ValueError(f"unknown transcriber {name!r} (available: {', '.join(_AVAILABLE)})")


def get_transcriber(cfg: dict | None = None) -> Transcriber:
    """Shared default engine for production (loaded once, then hot)."""
    global _default
    name = (cfg or {}).get("transcriber", "whistle") or "whistle"
    with _lock:
        if _default is None or getattr(_default, "name", "") != name:
            _default = create(name)
        return _default


def transcribe_audio(samples, language=None, keywords=None,
                     word_timestamps=False, engine=None,
                     cfg: dict | None = None) -> dict:
    """Transcribe samples. Pass `engine=` (a Transcriber) in tests."""
    eng = engine or get_transcriber(cfg)
    kw = keywords or None
    res = eng.transcribe(samples, language=language, keywords=kw,
                         word_timestamps=word_timestamps)
    if isinstance(res, TranscriptionResult):
        return res.to_dict()
    return dict(res) if isinstance(res, dict) else {"text": str(res)}


__all__ = ["Transcriber", "TranscriptionResult", "available", "create",
           "get_transcriber", "transcribe_audio"]
