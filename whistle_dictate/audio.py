"""Audio recording. 16 kHz mono float32 — exactly what Whistle wants."""
from __future__ import annotations
from pathlib import Path

TARGET_SR = 16000
NBANDS = 24
_FFT_N = 2048

class Spectrum:
    """Speech-reactive spectrum with adaptive noise floor + gate.

    Per-frame self-normalization makes even silence look loud; instead we
    track each band's noise floor (follows down fast, up very slowly) and a
    loud reference, then scale relative to the floor. A broadband gate fades
    everything to flat when the input sits near the floor (fan/room tone).
    """

    def __init__(self, nbands: int = NBANDS, sensitivity: float = 1.0):
        self.n = nbands
        self.sens = max(0.3, min(3.0, float(sensitivity)))
        self.floor = None
        self.floor_broad = None
        self.ref = 1e-6
        self.gate_sm = 0.0
        # FFT plan, built lazily on first analyze so `import audio` stays
        # light (no numpy at import time). Reused every frame after that.
        self._ready = False

    def _ensure_tables(self):
        if self._ready:
            return
        import numpy as np
        self._win = np.hanning(_FFT_N).astype(np.float32)
        self._freqs = np.fft.rfftfreq(_FFT_N, 1.0 / TARGET_SR)
        edges = np.logspace(np.log10(100), np.log10(7500), self.n + 1)
        self._masks = [((self._freqs >= lo) & (self._freqs < hi))
                       for lo, hi in zip(edges[:-1], edges[1:])]
        self._ready = True

    def analyze(self, samples_16k) -> list[float]:
        import numpy as np
        self._ensure_tables()
        x = np.asarray(samples_16k, dtype=np.float32)
        n = _FFT_N
        if len(x) < 256:
            return [0.0] * self.n
        if len(x) >= n:
            seg = x[-n:] * self._win
        else:
            seg = np.zeros(n, dtype=np.float32)
            seg[-(len(x)):] = x
            seg *= self._win
        mag = np.abs(np.fft.rfft(seg))
        bands = np.array([
            float(mag[m].mean() or 0.0) for m in self._masks
        ])
        broad = float(bands.max())
        if self.floor is None:
            self.floor = bands.copy()
            self.floor_broad = broad
            return [0.0] * self.n
        up = np.where(bands > self.floor, 0.005, 0.15)
        self.floor += (bands - self.floor) * up
        self.floor_broad += (broad - self.floor_broad) * (
            0.005 if broad > self.floor_broad else 0.15)
        self.ref = max(self.ref * 0.995, broad)
        raw = (broad - self.floor_broad * (0.8 + 0.4 / self.sens)) / (
            self.floor_broad * (1.0 + 1.0 / self.sens) + 1e-9)
        raw = max(0.0, min(1.0, raw))
        # open fast, close slow: no flicker on ambient swells
        k = 0.4 if raw > self.gate_sm else 0.08
        self.gate_sm += (raw - self.gate_sm) * k
        gate = self.gate_sm
        denom = max(self.ref - float(self.floor.mean()) * 1.5, 1e-9)
        out = np.clip((bands - self.floor * 1.6) / denom, 0.0, 1.0) ** 0.7 * gate
        return [float(max(0.0, min(1.0, v))) for v in out]


def resolve_mic(mic_cfg) -> int | str | None:
    """Turn config `mic` (None | index | name substring) into a sounddevice device."""
    if mic_cfg is None:
        return None
    import sounddevice as sd
    if isinstance(mic_cfg, int):
        return mic_cfg
    name = str(mic_cfg).lower()
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and name in d["name"].lower():
            return i
    raise RuntimeError(f"no input device matches {mic_cfg!r} (see `whistle-dictate devices`)")

def list_sources() -> str:
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        lines = []
        for i, d in enumerate(devs):
            if d["max_input_channels"] > 0:
                star = " *" if d.get("is_default_input") else ""
                lines.append(f"{i}: {d['name']} ({d['max_input_channels']}ch, {int(d['default_samplerate'])}Hz){star}")
        return "\n".join(lines) or "no input devices found"
    except Exception as e:
        return f"audio unavailable: {e}"

def record_blocking(duration_s: float | None = None, sample_rate: int = TARGET_SR):
    """Record for duration_s (or until Ctrl-C) and return float32 mono samples."""
    import numpy as np
    import sounddevice as sd
    import time
    frames: list = []
    def cb(indata, nframes, t, status):
        frames.append(indata.copy())
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", callback=cb):
        if duration_s is None:
            print("recording… Ctrl-C to stop", flush=True)
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
        else:
            time.sleep(duration_s)
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(frames, axis=0).reshape(-1).astype(np.float32)

def load_wav_mono16k(path: Path):
    """Load any wav via soundfile + resample to 16k mono float32."""
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), always_2d=True)
    mono = data.mean(axis=1).astype(np.float32)
    if sr == TARGET_SR:
        return mono
    # resample with soxr if available (cactus-compute[mic] brings it), else linear
    try:
        import soxr
        return soxr.resample(mono, sr, TARGET_SR).astype(np.float32)
    except Exception:
        idx = (np.arange(int(len(mono) * TARGET_SR / sr))).astype(int)
        idx = np.clip((np.arange(len(idx)) * len(mono) // len(idx)), 0, len(mono) - 1)
        return mono[idx]
