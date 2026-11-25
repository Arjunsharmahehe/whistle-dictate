"""Audio source factory: name -> implementation.

Today only "sounddevice" exists (cross-platform itself, so Windows/Mac
can reuse it initially). Unknown names raise with the available list.
"""
from __future__ import annotations

from .base import AudioSource

_AVAILABLE = ("sounddevice",)


def available() -> tuple[str, ...]:
    return _AVAILABLE


def create(name: str | None = None) -> AudioSource:
    kind = (name or "sounddevice").lower()
    if kind == "sounddevice":
        from .sounddevice_source import SounddeviceSource
        return SounddeviceSource()
    raise ValueError(f"unknown audio source {name!r} (available: {', '.join(_AVAILABLE)})")


def get_source(cfg: dict | None = None) -> AudioSource:
    return create((cfg or {}).get("audio_source", "sounddevice") or "sounddevice")


__all__ = ["AudioSource", "available", "create", "get_source"]
