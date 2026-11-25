"""Whistle transcriber: the default local engine (16.9 MB .cact).

Only module in the project that imports `cactus`. Everything else talks
to the `Transcriber` protocol, so Windows/macOS engines can be added
alongside this one without touching the pipeline.
"""
from __future__ import annotations

from .base import TranscriptionResult


class WhistleTranscriber:
    """Local Whistle transcription engine, lazy-loaded."""

    name = "whistle"
    sample_rate = 16000

    def __init__(self, weights=None):
        import cactus
        self._w = cactus.Whistle() if weights is None else cactus.Whistle(weights)

    def transcribe(self, samples, language=None, keywords=None,
                   word_timestamps=False) -> TranscriptionResult:
        res = self._w.transcribe(samples, language=language,
                                 keywords=keywords,
                                 word_timestamps=word_timestamps)
        if isinstance(res, TranscriptionResult):
            return res
        return TranscriptionResult.from_dict(res if isinstance(res, dict) else {})


# Back-compat alias: the old class name used across docs/tests.
WhistleEngine = WhistleTranscriber
