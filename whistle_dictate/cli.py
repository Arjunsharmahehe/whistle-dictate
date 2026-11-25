"""CLI mirroring `hex dictation start|stop|toggle`, `hex transcribe`, `hex status`.

Hyprland (Lua, 0.57): one toggle bind is all you need —
  hl.bind("ALT + Space", hl.dsp.exec_cmd(".../whistle-dictate toggle"))

Model stays hot: the `start` worker preloads Whistle's 16.9 MB .cact *while*
you speak, so the stop press transcribes immediately. `warm` (autostart)
pre-downloads it at login.

This module is a thin adapter: argparse in, user-facing messages out. The
session lifecycle lives in session.py, the overlay protocol in state.py,
and the transcribe→history→paste chain in pipeline.py.
"""
from __future__ import annotations
import argparse
import json
import sys
import time

from .config import load_config, ensure_dirs
from . import history as hist
from . import session
from . import state


def notify(msg: str) -> None:
    """User feedback via Noctalia's top-center OSD card (not a notification)."""
    try:
        from . import osd as _osd
        _osd.show("microphone", " ".join(str(msg).split())[:60])
    except Exception:
        pass


def cmd_start(args) -> int:
    cfg = load_config()
    ensure_dirs()
    if session.is_recording():
        notify("already recording")
        print("already recording", flush=True)
        return 0
    state.stop_path().unlink(missing_ok=True)
    state.result_path().unlink(missing_ok=True)
    state.osd_path().unlink(missing_ok=True)
    state.write(state.Phase.RECORDING, elapsed=0.0)
    # overlay first (instant card), then the worker: both detached.
    # Skipped when overlay=false (headless: saves the ~65MB card process).
    if cfg.get("overlay", True):
        session.spawn_overlay()
    pid = session.spawn_worker()
    print(f"recording started (pid {pid})… speak, then `whistle-dictate stop`", flush=True)
    return 0


def cmd__record(args) -> int:
    """Internal worker: records mic AND preloads Whistle at once, then
    transcribes + pastes + notifies on stop. Do not bind directly."""
    import threading
    ensure_dirs()
    from .config import load_config
    from .engine import get_whistle
    from .paste import paste_text
    from . import history as _hist
    from . import pipeline as _pipeline

    cfg = load_config()
    sr = int(cfg.get("sample_rate", 16000))
    result: dict = {}

    def _write_result():
        try:
            state.result_path().write_text(json.dumps(result, ensure_ascii=False))
        except Exception:
            pass

    def _fail(reason: str, notify_msg: str | None = None) -> int:
        result.update({"ok": False, "error": reason} if notify_msg else
                      {"ok": False, "reason": reason})
        _write_result()
        state.write(state.Phase.ERROR, elapsed=time.time() - t0,
                    reason=reason[:80])
        notify(notify_msg or reason)
        try:
            state.pid_path().unlink(missing_ok=True)
        except Exception:
            pass
        return 1

    t0 = time.time()  # set before _fail can run
    from .audio import resolve_mic
    try:
        mic_dev = resolve_mic(cfg.get("mic"))
    except Exception as e:
        return _fail(str(e))

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
        return _fail(f"mic open failed: {e}", f"mic failed: {e}")

    # Preload the 16.9 MB model WHILE recording — it is hot by stop time.
    loaded: dict = {}

    def _load():
        try:
            loaded["w"] = get_whistle()
        except Exception as e:
            loaded["err"] = e

    loader = threading.Thread(target=_load, daemon=True)
    loader.start()
    # Live spectrum feed for the overlay (20 Hz); overlay lerps to 60fps.
    # Spectrum holds the adaptive noise floor, so one instance per session.
    from .audio import Spectrum
    import numpy as np
    tracker = Spectrum(sensitivity=float(cfg.get("sensitivity", 1.0)))
    roll = np.zeros(0, dtype=np.float32)
    consumed = 0
    spec = [0.0] * 24
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
            result = {"ok": False, "reason": "discarded: no audio"}
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
                result = {"ok": False, "error": f"model load failed: {loaded['err']}"}
            else:
                engine = loaded.get("w") or get_whistle()
                result = _pipeline.complete(
                    samples, sample_rate=sr, cfg=cfg, engine=engine,
                    remember=_hist.append, paste=paste_text)
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
    try:
        state.pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    try:
        stopfile.unlink(missing_ok=True)
    except Exception:
        pass
    return 0 if result.get("ok") else 1


def _finish(paste: bool, print_text: bool) -> int:
    status, result = session.stop_and_wait()
    if status == "not-recording":
        print("not recording", flush=True)
        return 1
    if status == "timeout" or result is None:
        msg = "timed out waiting for transcription"
        notify(msg)
        print(msg, flush=True)
        return 1
    # let the overlay flash its done/error card, then make sure it exits
    session.reap_overlay()
    if not result.get("ok"):
        print(result.get("reason") or result.get("error", "failed"), flush=True)
        return 1
    if print_text or not paste:
        print(result["text"], flush=True)
    else:
        print(f"pasted via {result.get('method')}: {result['text']}", flush=True)
    return 0


def cmd_stop(args) -> int:
    ensure_dirs()
    return _finish(paste=not args.no_paste, print_text=args.print)


def cmd_toggle(args) -> int:
    ensure_dirs()
    if session.is_recording():
        return _finish(paste=not args.no_paste, print_text=args.print)
    return cmd_start(args)


def cmd_cancel(args) -> int:
    ensure_dirs()
    session.cancel()
    notify("dictation cancelled")
    print("cancelled", flush=True)
    return 0


def cmd_warm(args) -> int:
    """Pre-download + load Whistle so the first dictation is instant. For autostart."""
    ensure_dirs()
    from .engine import get_whistle
    try:
        get_whistle()
    except Exception as e:
        print(f"warm failed: {e}", file=sys.stderr, flush=True)
        return 1
    print("whistle ready (16.9 MB, resident in this process only)", flush=True)
    return 0


def cmd_listen(args) -> int:
    """Blocking record-until-Ctrl-C, then transcribe+paste. For testing."""
    from .audio import record_blocking
    from .engine import get_whistle
    from .paste import paste_text
    from .pipeline import complete
    ensure_dirs()
    cfg = load_config()
    sr = int(cfg.get("sample_rate", 16000))
    samples = record_blocking(duration_s=args.duration, sample_rate=sr)
    res = complete(samples, sample_rate=sr, cfg=cfg, engine=get_whistle(),
                   remember=hist.append, paste=paste_text)
    if not res.get("ok"):
        print(res.get("reason") or res.get("error", "failed"), flush=True)
        return 1
    if args.print or args.no_paste:
        print(res["text"], flush=True)
    else:
        notify(f"{res['text'][:120]}")
        print(f"pasted via {res.get('method')}: {res['text']}", flush=True)
    return 0


def cmd_transcribe(args) -> int:
    from pathlib import Path as P
    from .audio import load_wav_mono16k
    from .engine import transcribe_audio
    ensure_dirs()
    cfg = load_config()
    p = P(args.file)
    if not p.exists():
        print(f"no such file: {p}", file=sys.stderr)
        return 2
    samples = load_wav_mono16k(p)
    lang = args.language or cfg.get("language")
    res = transcribe_audio(samples, language=lang, keywords=cfg.get("keywords") or None,
                           word_timestamps=args.words)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(res.get("text", ""))
        if args.words and res.get("words"):
            for w in res["words"][:50]:
                print(f"  {w}")
    return 0


def cmd_status(args) -> int:
    from .paste import have
    cfg = load_config()
    pid = session.is_recording()
    try:
        import cactus
        engine = "cactus-compute " + getattr(cactus, "__version__", "?")
    except Exception:
        engine = "not installed"
    st = {
        "app": "whistle-dictate",
        "recording": pid is not None,
        "pid": pid,
        "engine": engine,
        "model": {"id": "whistle.cact", "size": "16.9 MB",
                   "languages": ["en", "de", "fr", "es", "it", "nl", "pl"]},
        "language": cfg.get("language") or "auto-detect",
        "paste": {
            "wtype": have("wtype"), "wl-copy": have("wl-copy"),
            "hyprctl": have("hyprctl"), "method": cfg.get("paste_method"),
        },
    }
    print(json.dumps(st, indent=2 if not args.json else None, ensure_ascii=False))
    return 0


def cmd_history(args) -> int:
    ensure_dirs()
    if args.clear:
        hist.clear()
        print("history cleared", flush=True)
        return 0
    items = hist.read(limit=args.limit)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    if not items:
        print("(empty)", flush=True)
        return 0
    for it in items:
        import datetime
        ts = datetime.datetime.fromtimestamp(it.get("ts", 0)).strftime("%m-%d %H:%M")
        print(f"[{ts}] ({it.get('language', '?')}) {it.get('text', '')}", flush=True)
    return 0


def cmd_paste_last(args) -> int:
    from .paste import paste_text
    ensure_dirs()
    cfg = load_config()
    t = hist.last_text()
    if not t:
        print("no dictations yet", flush=True)
        return 1
    m = paste_text(t, method=cfg.get("paste_method", "auto"))
    print(f"pasted via {m.method} (delivered={m.delivered}): {t}", flush=True)
    return 0


def cmd_devices(args) -> int:
    from .audio import list_sources
    print(list_sources(), flush=True)
    return 0


def cmd_mic_test(args) -> int:
    """Live input level meter — speak and watch the bars move."""
    import time
    import numpy as np
    import sounddevice as sd
    from .audio import resolve_mic
    ensure_dirs()
    cfg = load_config()
    try:
        mic_dev = resolve_mic(cfg.get("mic"))
    except Exception as e:
        print(str(e), flush=True)
        return 2
    sr = int(cfg.get("sample_rate", 16000))
    print(f"mic device: {mic_dev or 'system default'} — speak now (6s)…", flush=True)
    peak_hold = 0.0
    try:
        with sd.InputStream(samplerate=sr, channels=1, dtype="float32", device=mic_dev) as stream:
            for _ in range(60):
                data, _ = stream.read(int(sr * 0.1))
                peak = float(np.abs(data).max()) if len(data) else 0.0
                peak_hold = max(peak_hold * 0.9, peak)
                bars = int(min(peak, 1.0) * 40)
                print(f"\r|{'#' * bars:<40}| {peak:.3f}", end="", flush=True)
                time.sleep(0.02)
    except Exception as e:
        print(f"\nmic open failed: {e}", flush=True)
        return 1
    print(f"\nmax peak: {peak_hold:.3f} — {'HEARS YOU' if peak_hold > 0.02 else 'SILENT: wrong mic or muted (wpctl status)'}", flush=True)
    return 0 if peak_hold > 0.02 else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="whistle-dictate", description="Hex-like dictation with Cactus Whistle (local, 16.9 MB)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="start recording"); s.set_defaults(fn=cmd_start)
    p = sub.add_parser("stop", help="stop + transcribe + paste")
    p.add_argument("--no-paste", action="store_true"); p.add_argument("--print", action="store_true")
    p.set_defaults(fn=cmd_stop)
    t = sub.add_parser("toggle", help="one key: start, then stop+paste")
    t.add_argument("--no-paste", action="store_true"); t.add_argument("--print", action="store_true")
    t.set_defaults(fn=cmd_toggle)
    c = sub.add_parser("cancel", help="discard current recording"); c.set_defaults(fn=cmd_cancel)
    w = sub.add_parser("warm", help="pre-download/load Whistle (autostart)"); w.set_defaults(fn=cmd_warm)
    l = sub.add_parser("listen", help="blocking record-until-Ctrl-C (testing)")
    l.add_argument("--duration", type=float, default=None); l.add_argument("--no-paste", action="store_true")
    l.add_argument("--print", action="store_true"); l.set_defaults(fn=cmd_listen)
    tr = sub.add_parser("transcribe", help="transcribe an audio file (like `hex transcribe`)")
    tr.add_argument("file"); tr.add_argument("--language", default=None)
    tr.add_argument("--words", action="store_true"); tr.add_argument("--json", action="store_true")
    tr.set_defaults(fn=cmd_transcribe)
    st = sub.add_parser("status", help="what whistle-dictate is doing")
    st.add_argument("--json", action="store_true"); st.set_defaults(fn=cmd_status)
    h = sub.add_parser("history", help="past dictations")
    h.add_argument("--limit", type=int, default=20); h.add_argument("--clear", action="store_true")
    h.add_argument("--json", action="store_true"); h.set_defaults(fn=cmd_history)
    pl = sub.add_parser("paste-last", help="paste last dictation again"); pl.set_defaults(fn=cmd_paste_last)
    dv = sub.add_parser("devices", help="list mic devices"); dv.set_defaults(fn=cmd_devices)
    mt = sub.add_parser("mic-test", help="live mic level meter (speak to test)"); mt.set_defaults(fn=cmd_mic_test)
    rec = sub.add_parser("_record", help=argparse.SUPPRESS); rec.set_defaults(fn=cmd__record)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
