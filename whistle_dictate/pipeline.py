"""Dictation pipeline: samples in, result out.

This is the record→transcribe→history→paste decision chain that used to live
inline in `cmd__record`, wired directly to the `get_whistle()` global, the
real `paste_text`, and real history. Nothing here touches the mic, the model,
or Hyprland: every side effect arrives as an injected callable, so the whole
flow — including every discard and fallback path — runs in tests with a stub
engine in milliseconds.

Conventions:
- `engine`: anything with `.transcribe(samples, language, keywords)`
  (a `WhistleEngine`, or a stub in tests).
- `remember(entry)`: records one history entry (real: `history.append`).
- `paste(text, method)`: returns a `PasteResult` (real: `paste.paste_text`).
- result dicts keep the on-disk shape the CLI already uses:
  `{"ok": True, "text", "method", "delivered", "language"}` or
  `{"ok": False, "reason"}` / `{"ok": False, "error"}`.
"""
from __future__ import annotations

from .config import paste_method as _paste_method

MIN_SAMPLES = 1600


def empty_clip(reason: str = "discarded: silent clip") -> dict:
    """Result constructor: nothing worth transcribing was recorded."""
    return {"ok": False, "reason": reason}


def load_error(err) -> dict:
    """Result constructor: the engine itself failed to load."""
    return {"ok": False, "error": f"model load failed: {err}"}


def transcribe_samples(samples, *, sample_rate: int, cfg: dict, engine) -> dict:
    """Transcribe, mapping every expected failure to a result dict (no raise)."""
    if samples is None or len(samples) < MIN_SAMPLES:
        return empty_clip()
    try:
        res = engine.transcribe(samples,
                                language=cfg.get("language"),
                                keywords=cfg.get("keywords") or None)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    text = (res.get("text") or "").strip()
    if not text:
        return empty_clip()
    return {"ok": True, "text": text, "language": res.get("language"),
            "duration_s": round(len(samples) / sample_rate, 2),
            "ttft_ms": res.get("ttft_ms"), "decode_tps": res.get("decode_tps")}


def complete(samples, *, sample_rate: int, cfg: dict, engine,
             remember, paste) -> dict:
    """Full chain: transcribe → history → paste. Side effects only via seams."""
    res = transcribe_samples(samples, sample_rate=sample_rate, cfg=cfg,
                             engine=engine)
    if not res.get("ok"):
        return res
    remember({"text": res["text"], "language": res.get("language"),
              "duration_s": res.get("duration_s"),
              "ttft_ms": res.get("ttft_ms"),
              "decode_tps": res.get("decode_tps")})
    pr = paste(res["text"], _paste_method(cfg))
    return {"ok": True, "text": res["text"], "method": pr.method,
            "delivered": pr.delivered, "language": res.get("language")}
