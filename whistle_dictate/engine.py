"""Whistle engine behind a seam (back-compat shim).

New code should use `whistle_dictate.transcribers` (the `Transcriber`
protocol + `get_transcriber` factory). This module stays so existing
imports (`engine.get_whistle`, `engine.WhistleEngine`,
`engine.transcribe_audio`) keep working on Hyprland unchanged.
"""
from __future__ import annotations

from .transcribers.base import Transcriber, TranscriptionResult
from .transcribers.whistle import WhistleEngine, WhistleTranscriber
from .transcribers import available, create, get_transcriber, transcribe_audio

get_whistle = get_transcriber

__all__ = ["Transcriber", "TranscriptionResult", "WhistleEngine",
           "WhistleTranscriber", "available", "create", "get_transcriber",
           "get_whistle", "transcribe_audio"]
