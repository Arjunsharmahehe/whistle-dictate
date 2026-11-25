"""sounddevice audio source: current Linux implementation.

Thin wrapper around the existing `audio.py` helpers so behavior on
Hyprland is byte-identical — this module only re-exports it behind the
AudioSource protocol for the factory to pick.
"""
from __future__ import annotations
from pathlib import Path

from .. import audio as _audio


class SounddeviceSource:
    name = "sounddevice"
    sample_rate = _audio.TARGET_SR

    def resolve_mic(self, mic_cfg):
        return _audio.resolve_mic(mic_cfg)

    def list_sources(self) -> str:
        return _audio.list_sources()

    def record_blocking(self, duration_s=None, sample_rate: int = _audio.TARGET_SR):
        return _audio.record_blocking(duration_s=duration_s, sample_rate=sample_rate)

    def load_wav_mono16k(self, path: Path):
        return _audio.load_wav_mono16k(path)
