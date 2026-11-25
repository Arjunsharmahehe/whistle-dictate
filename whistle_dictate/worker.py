"""The detached record worker: mic + model preload + transcribe + paste.

This is the second program in the project (the first is the CLI adapter):
spawned detached by `session.spawn_worker`, it records until the stop file
appears, then runs the pipeline and exits. It speaks to the outside world
only through seams — `state` (overlay + result files), `pipeline`
(transcribe→history→paste), backends (`transcribers`, `audio_sources`,
`paste_backends`, `notifiers`), and `platform` (OS detection).

Platform behavior today: Hyprland/Linux (sounddevice mic, Whistle engine,
Hyprland paste, Noctalia notify). Other OSes reuse the same flow with
different backends chosen by config + factory defaults.
"""
from __future__ import annotations
import json
import time

from .config import ensure_dirs, load_config, sample_rate, sensitivity as _sensitivity
from .config import audio_source_name, notifier_name, transcriber_name
from . import history as _hist
from . import pipeline as _pipeline
from . import state


def cmd__record(args) -> int:
    """Record mic AND preload the transcriber at once, then transcribe+paste+notify."""
    import threading
    ensure_dirs()

    from .audio import Spectrum
    from .audio_sources import get_source
    from .transcribers import get_transcriber
    from .paste_backends import get_backend as get_paste_backend
    from .notifiers import get_backend as get_notifier

    cfg = load_config()
    sr = sample_rate(cfg)
    audio = get_source({**cfg, "audio_source": audio_source_name(cfg)})
    notifier = get_notifier({**cfg, "notifier": notifier_name(cfg)})
    paste_backend = get_paste_backend(cfg)

    def notify(msg: str) -> None:
        try:
            notifier.notify(msg)
        except Exception:
            pass

    result: dict = {}

    def _write_result():
        try:
            state.result_path().write_text(json.dumps(result, ensure_ascii=False))
        except Exception:
            pass

    t0 = time.time()

    def _fail(reason: str, error: bool = False) -> int:
        if error:
            result.update({"ok": False, "error": reason})
        else:
            result.update(_pipeline.empty_clip(reason))
        _write_result()
        state.write(state.Phase.ERROR, elapsed=time.time() - t0, reason=reason[:80])
        notify(reason)
        state.safe_unlink(state.pid_path())
        return 1

    try:
        mic_dev = audio.resolve_mic(cfg.get("mic"))
    except Exception as e:
        return _fail(str(e), error=True)

    try:
        import sounddevice as sd
        import numpy as np
        frames: list = []
        live = {"peak": 0.0}

        def _cb(data, nframes, t, status):
            frames.append(data.copy())
            try:
                live["peak"] = float(np.abs(data).max())
            except Exception:
                pass

        stream = sd.InputStream(samplerate=sr, channels=1, dtype="float32", device=mic_dev,
                                callback=_cb)
        stream.start()
    except Exception as e:
        return _fail(f"mic open failed: {e}", error=True)

    # Preload the model WHILE recording — it is hot by stop time.
    loaded: dict = {}

    def _load():
        try:
            loaded["w"] = get_transcriber({**cfg, "transcriber": transcriber_name(cfg)})
        except Exception as e:
            loaded["err"] = e

    loader = threading.Thread(target=_load, daemon=True)
    loader.start()
    # Live spectrum feed for the overlay (20 Hz); overlay lerps to 60fps.
    # Spectrum holds the adaptive noise floor, so one instance per session.
    import numpy as np
    tracker = Spectrum(sensitivity=_sensitivity(cfg))
    roll = np.zeros(0, dtype=np.float32)
    consumed = 0
    spec = state.blank_spec()
    last_feed = 0.0
    stopfile = state.stop_path()
    while not stopfile.exists():
        time.sleep(0.05)
        now = time.time()
        if len(frames) > consumed:
            chunk = np.concatenate(frames[consumed:], axis=0).reshape(-1)
            consumed = len(frames)
            roll = np.concatenate([roll, chunk])[-8192:]
        if now - last_feed >= 0.05:
            last_feed = now
            try:
                spec = tracker.analyze(roll[-4096:])
            except Exception:
                pass
            state.write(state.Phase.RECORDING, elapsed=now - t0,
                        spec=spec, peak=float(live.get("peak", 0.0)))
            live["peak"] = 0.0
    state.write(state.Phase.TRANSCRIBING, elapsed=time.time() - t0, spec=spec)
    try:
        stream.stop()
        stream.close()
    except Exception:
        pass
    loader.join(timeout=120)

    try:
        if not frames:
            result = _pipeline.empty_clip("discarded: no audio")
        else:
            import gc
            import numpy as np
            samples = np.concatenate(frames, axis=0).reshape(-1)
            # recording buffers no longer needed — drop them before the
            # model runs so transcribe peaks lower.
            frames.clear()
            del roll, tracker, spec
            gc.collect()
            if "err" in loaded:
                result = _pipeline.load_error(loaded["err"])
            else:
                from .transcribers import get_transcriber as _get
                engine = loaded.get("w") or _get({**cfg, "transcriber": transcriber_name(cfg)})
                result = _pipeline.complete(
                    samples, sample_rate=sr, cfg=cfg, engine=engine,
                    remember=_hist.append, paste=paste_backend.paste)
                if result.get("ok"):
                    if result.get("delivered"):
                        # success: no card — the pasted text is the confirmation
                        state.write(state.Phase.DISMISS, elapsed=time.time() - t0)
                    else:
                        state.write(state.Phase.DONE, elapsed=time.time() - t0,
                                    text=result["text"])
                        notify("in clipboard — press Ctrl+V to paste")
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        state.write(state.Phase.ERROR, elapsed=time.time() - t0, reason=str(e)[:80])
        notify(f"transcription failed: {e}")
    if not result.get("ok"):
        state.write(state.Phase.ERROR, elapsed=time.time() - t0,
                    reason=str(result.get("reason") or result.get("error", "failed"))[:80])
        notify(result.get("reason") or result.get("error", "failed"))
    _write_result()
    state.safe_unlink(state.pid_path(), stopfile)
    return 0 if result.get("ok") else 1
