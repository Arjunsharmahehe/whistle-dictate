"""AudioSource interface: mic + file loading behind one seam.

Today this is `sounddevice` on Linux. Windows/macOS will add their own
sources (or reuse sounddevice — it is cross-platform) without touching
the worker: the worker only calls `resolve_mic`, `list_sources`,
`record_blocking`, and `load_wav_mono16k` through the factory.
"""
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    """Pluggable mic/file backend."""

    name: str
    sample_rate: int

    def resolve_mic(self, mic_cfg) -> int | str | None:
        ...

    def list_sources(self) -> str:
        ...

    def record_blocking(self, duration_s: float | None = None, sample_rate: int = 16000):
        ...

    def load_wav_mono16k(self, path: Path):
        ...
