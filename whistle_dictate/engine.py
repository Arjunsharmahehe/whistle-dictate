"""Whistle engine behind a seam.

Previously this was a locked module-global singleton: every caller got the
same object and tests could not substitute a stub without the 17MB model.
Now the engine is a small constructed module — `WhistleEngine(weights)` —
and `get_whistle()` is just the default shared instance for the CLI. Any
caller that accepts `engine=` can run against a fake, which is what makes
the record→transcribe→paste pipeline testable (see pipeline.py).
"""
from __future__ import annotations
import threading

_lock = threading.Lock()
_default = None


class WhistleEngine:
    """Local Whistle transcription engine (16.9 MB .cact, lazy-loaded)."""

    def __init__(self, weights=None):
        import cactus
        self._w = cactus.Whistle() if weights is None else cactus.Whistle(weights)

    def transcribe(self, samples, language=None, keywords=None,
                   word_timestamps=False) -> dict:
        return self._w.transcribe(samples, language=language,
                                  keywords=keywords,
                                  word_timestamps=word_timestamps)


def get_whistle() -> WhistleEngine:
    """Default shared engine for production use (loaded once, then hot)."""
    global _default
    with _lock:
        if _default is None:
            _default = WhistleEngine()
        return _default


def transcribe_audio(samples, language=None, keywords=None,
                     word_timestamps=False, engine=None) -> dict:
    """Transcribe samples. Pass `engine=` (anything with .transcribe) in tests."""
    eng = engine or get_whistle()
    kw = keywords or None
    return eng.transcribe(samples, language=language, keywords=kw,
                          word_timestamps=word_timestamps)
