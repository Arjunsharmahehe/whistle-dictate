"""Transcriber interface: samples in, structured result out.

This is the main seam for cross-platform growth. Hyprland, Windows, macOS,
and other Linux desktops all share the same contract — only the
implementation behind it changes (Whistle today, Whisper / SAPI / Speech
framework tomorrow).

Contract:
- input: mono float32 samples at `sample_rate` (see `TARGET_SR`), plus
  optional `language` (None = auto-detect) and `keywords` biasing list.
- output: `TranscriptionResult` (never raises for "no speech" — return
  `text=""` and let `pipeline` decide discard vs error).

Implementations must be import-light: `base` imports nothing heavy so
factories, tests, and future platform stubs load anywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TranscriptionResult:
    """Structured transcription outcome (engine-agnostic)."""

    text: str = ""
    language: str | None = None
    words: list | None = None
    ttft_ms: float | None = None
    decode_tps: float | None = None
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict | None) -> "TranscriptionResult":
        d = d or {}
        return cls(
            text=str(d.get("text") or ""),
            language=d.get("language"),
            words=d.get("words"),
            ttft_ms=d.get("ttft_ms"),
            decode_tps=d.get("decode_tps"),
            extra={k: v for k, v in d.items()
                   if k not in ("text", "language", "words", "ttft_ms", "decode_tps")},
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"text": self.text, "language": self.language}
        if self.words is not None:
            out["words"] = self.words
        if self.ttft_ms is not None:
            out["ttft_ms"] = self.ttft_ms
        if self.decode_tps is not None:
            out["decode_tps"] = self.decode_tps
        out.update(self.extra)
        return out


@runtime_checkable
class Transcriber(Protocol):
    """Anything that turns audio samples into a TranscriptionResult."""

    name: str
    sample_rate: int

    def transcribe(self, samples, language: str | None = None,
                   keywords: list[str] | None = None,
                   word_timestamps: bool = False) -> TranscriptionResult | dict:
        ...
