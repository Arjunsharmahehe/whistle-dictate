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

from .config import load_config, ensure_dirs, sample_rate, paste_method
from .config import audio_source_name, notifier_name, transcriber_name
from . import history as hist
from . import session
from . import state
from . import worker
from . import overlays as _overlays
from . import notifiers as _notifiers


def _notify(cfg: dict | None, msg: str) -> None:
    """Short user feedback via the configured notifier. Never raises."""
    try:
        _notifiers.get_backend(cfg or {}).notify(msg)
    except Exception:
        pass


def notify(msg: str) -> None:
    """Back-compat notifier (Hyprland default). Prefer _notify(cfg, msg)."""
    try:
        _notify(load_config(), msg)
    except Exception:
        pass


def cmd_start(args) -> int:
    cfg = load_config()
    ensure_dirs()
    if session.is_recording():
        _notify(cfg, "already recording")
        print("already recording", flush=True)
        return 0
    state.safe_unlink(state.stop_path(), state.result_path(), state.osd_path())
    state.write(state.Phase.RECORDING, elapsed=0.0)
    # overlay first (instant card), then the worker: both detached.
    # overlay=false (or non-Linux default) skips the card process.
    try:
        _overlays.get_backend(cfg).spawn()
    except Exception:
        session.spawn_overlay()
    pid = session.spawn_worker()
    print(f"recording started (pid {pid})… speak, then `whistle-dictate stop`", flush=True)
    return 0


def format_result(result: dict, *, paste: bool, print_text: bool) -> str:
    """Single home for user-visible result rendering (success and failure)."""
    if not result.get("ok"):
        return str(result.get("reason") or result.get("error", "failed"))
    if print_text or not paste:
        return result["text"]
    msg = f"pasted via {result.get('method')}: {result['text']}"
    if "delivered" in result and not result.get("delivered"):
        msg += " (keystroke not delivered — press Ctrl+V)"
    return msg


def _finish(paste: bool, print_text: bool) -> int:
    status, result = session.stop_and_wait()
    if status == "not-recording":
        print("not recording", flush=True)
        return 1
    if status == "timeout" or result is None:
        msg = "timed out waiting for transcription"
        try:
            _notify(load_config(), msg)
        except Exception:
            pass
        print(msg, flush=True)
        return 1
    # let the overlay flash its done/error card, then make sure it exits
    try:
        _overlays.get_backend(load_config()).reap()
    except Exception:
        session.reap_overlay()
    print(format_result(result, paste=paste, print_text=print_text), flush=True)
    return 0 if result.get("ok") else 1


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
    cfg = load_config()
    session.cancel()
    _notify(cfg, "dictation cancelled")
    print("cancelled", flush=True)
    return 0


def cmd_warm(args) -> int:
    """Pre-download + load the transcriber so the first dictation is instant."""
    ensure_dirs()
    cfg = load_config()
    from .transcribers import get_transcriber
    try:
        get_transcriber({**cfg, "transcriber": transcriber_name(cfg)})
    except Exception as e:
        print(f"warm failed: {e}", file=sys.stderr, flush=True)
        return 1
    print("whistle ready (16.9 MB, resident in this process only)", flush=True)
    return 0


def cmd_listen(args) -> int:
    """Blocking record-until-Ctrl-C, then transcribe+paste. For testing."""
    from .audio_sources import get_source
    from .transcribers import get_transcriber
    from .paste_backends import get_backend as get_paste_backend
    from .pipeline import complete
    ensure_dirs()
    cfg = load_config()
    sr = sample_rate(cfg)
    audio = get_source({**cfg, "audio_source": audio_source_name(cfg)})
    samples = audio.record_blocking(duration_s=args.duration, sample_rate=sr)
    res = complete(samples, sample_rate=sr, cfg=cfg,
                   engine=get_transcriber({**cfg, "transcriber": transcriber_name(cfg)}),
                   remember=hist.append, paste=get_paste_backend(cfg).paste)
    if not res.get("ok"):
        print(format_result(res, paste=False, print_text=True), flush=True)
        return 1
    if not (args.print or args.no_paste):
        _notify(cfg, f"{res['text'][:120]}")
    print(format_result(res, paste=not args.no_paste,
                        print_text=args.print), flush=True)
    return 0


def cmd_transcribe(args) -> int:
    from pathlib import Path as P
    from .audio_sources import get_source
    from .transcribers import transcribe_audio
    ensure_dirs()
    cfg = load_config()
    p = P(args.file)
    if not p.exists():
        print(f"no such file: {p}", file=sys.stderr)
        return 2
    audio = get_source({**cfg, "audio_source": audio_source_name(cfg)})
    samples = audio.load_wav_mono16k(p)
    lang = args.language or cfg.get("language")
    res = transcribe_audio(samples, language=lang, keywords=cfg.get("keywords") or None,
                           word_timestamps=args.words,
                           cfg={**cfg, "transcriber": transcriber_name(cfg)})
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(res.get("text", ""))
        if args.words and res.get("words"):
            for w in res["words"][:50]:
                print(f"  {w}")
    return 0


def cmd_status(args) -> int:
    from . import platform as _platform
    from .transcribers import available as _trans_available
    from .paste_backends import available as _paste_available
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
        "platform": {"os": _platform.os_name(), "desktop": _platform.desktop()},
        "backends": {
            "transcriber": transcriber_name(cfg),
            "transcribers": list(_trans_available()),
            "audio_source": audio_source_name(cfg),
            "notifier": notifier_name(cfg),
            "paste": list(_paste_available()),
        },
        "paste": {
            "wtype": _platform.have("wtype"), "wl-copy": _platform.have("wl-copy"),
            "hyprctl": _platform.have("hyprctl"), "method": paste_method(cfg),
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
    from .paste_backends import get_backend as get_paste_backend
    ensure_dirs()
    cfg = load_config()
    t = hist.last_text()
    if not t:
        print("no dictations yet", flush=True)
        return 1
    m = get_paste_backend(cfg).paste(t)
    print(format_result({"ok": True, "text": t, "method": m.method,
                         "delivered": m.delivered},
                        paste=True, print_text=False), flush=True)
    return 0


def cmd_devices(args) -> int:
    from .audio_sources import get_source
    ensure_dirs()
    cfg = load_config()
    print(get_source({**cfg, "audio_source": audio_source_name(cfg)}).list_sources(),
          flush=True)
    return 0


def cmd_mic_test(args) -> int:
    """Live input level meter — speak and watch the bars move."""
    import time
    import numpy as np
    import sounddevice as sd
    from .audio_sources import get_source
    ensure_dirs()
    cfg = load_config()
    audio = get_source({**cfg, "audio_source": audio_source_name(cfg)})
    try:
        mic_dev = audio.resolve_mic(cfg.get("mic"))
    except Exception as e:
        print(str(e), flush=True)
        return 2
    sr = sample_rate(cfg)
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
    rec = sub.add_parser("_record", help=argparse.SUPPRESS); rec.set_defaults(fn=worker.cmd__record)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
