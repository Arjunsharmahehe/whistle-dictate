# Architecture

Same flow everywhere, different backends per OS. The pipeline never branches on
platform — factories pick implementations from config + `platform.py` probes.

```
hotkey → cli.start → session.spawn_worker + overlays.spawn
  → worker: audio_sources.record + transcribers.preload (parallel)
  → stop file → transcribers.transcribe → pipeline.complete
    → history.append → paste_backends.paste → notifiers.notify
  → state.write(DISMISS|DONE|ERROR) → overlays.reap
```

## Seams

| Module | Owns | Must not |
|---|---|---|
| `session.py` | pidfiles, spawn/stop/wait/reap/cancel | parse args, print |
| `state.py` | `rec.osd.json` schema, paths, `safe_unlink` | spawn processes |
| `pipeline.py` | transcribe→history→paste decisions | touch mic/model/Hyprland |
| `config.py` | XDG paths, defaults, validation, accessors | import heavy deps |
| `platform.py` | stdlib OS/desktop/capability probes | import numpy/gi/cactus |
| `transcribers/` | `Transcriber` protocol + `whistle` impl + factory | — |
| `audio_sources/` | `AudioSource` protocol + `sounddevice` impl | — |
| `paste_backends/` | `PasteBackend` protocol + hyprland impls | — |
| `overlays/` | `OverlayBackend` (`gtk` vs `noop`) | render in the worker |
| `notifiers/` | `NotifierBackend` (`noctalia` vs `noop`) | block the pipeline |
| `cli.py` | argparse + messages only | lifecycle logic |
| `worker.py` | detached `_record` program | UI timing decisions |
| `gtk_overlay.py` | system-python card, reads `state` only | own pidfile removal |

## Data shapes

- `TranscriptionResult(text, language, words?, ttft_ms?, decode_tps?, extra?)` —
  engines return it (or a legacy `{"text", ...}` dict, coerced by the pipeline).
- `PasteResult(method, delivered, detail)` — `delivered` means text is in the
  focused app; `clipboard-only` means clipboard set but keystroke not delivered.
- `rec.osd.json` — `{"phase", "elapsed", "spec"[24], "peak", "text", "reason"}`,
  owned by `state.py`, read-only for the overlay.
- CLI result dicts — `{"ok": True, "text", "method", "delivered", "language"}`
  or `{"ok": False, "reason"} / {"ok": False, "error"}` (on-disk shape).

## Conventions

- Factories: `create(name)` builds, `get_backend(cfg)` selects, `available()`
  lists. Unknown names raise `ValueError` (never silent fallback).
- Backends are import-light; heavy imports (`cactus`, `sounddevice`, `gi`)
  happen inside methods so `import whistle_dictate` works anywhere.
- `notify()` / `state.write()` / `safe_unlink()` never raise — UI and cleanup
  must not kill a dictation.
- Tests inject fakes (`engine=`, `remember=`, `paste=`); no real model, mic,
  or subprocess in the suite.
