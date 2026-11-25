"""Tests for the dictation pipeline (candidate 2).

The whole record→transcribe→history→paste chain runs here with a stub
engine and fake side effects — no mic, no model, no Hyprland.
"""
import unittest

from whistle_dictate import pipeline
from whistle_dictate.paste import PasteResult


class StubEngine:
    def __init__(self, text="hello world", language="en", fail=None):
        self.text = text
        self.language = language
        self.fail = fail
        self.seen = []

    def transcribe(self, samples, language=None, keywords=None):
        self.seen.append((len(samples), language, keywords))
        if self.fail:
            raise RuntimeError(self.fail)
        return {"text": self.text, "language": self.language}


def _cfg(**over):
    cfg = {"language": None, "keywords": [], "paste_method": "auto"}
    cfg.update(over)
    return cfg


class PipelineTest(unittest.TestCase):
    def test_short_clip_discarded_without_side_effects(self):
        calls = []
        res = pipeline.transcribe_samples([0.0] * 100, sample_rate=16000,
                                          cfg=_cfg(), engine=StubEngine())
        self.assertFalse(res["ok"])
        self.assertIn("silent", res["reason"])
        self.assertEqual(calls, [])

    def test_blank_transcript_discarded(self):
        remembered, pasted = [], []
        res = pipeline.complete(
            [0.0] * 20000, sample_rate=16000, cfg=_cfg(),
            engine=StubEngine(text="   "),
            remember=remembered.append,
            paste=lambda t, m: pasted.append((t, m)) or PasteResult("wtype", True))
        self.assertFalse(res["ok"])
        self.assertEqual(remembered, [])
        self.assertEqual(pasted, [])

    def test_success_records_history_and_pastes(self):
        remembered, pasted = [], []
        eng = StubEngine(text="  hello world ", language="de")
        res = pipeline.complete(
            [0.1] * 32000, sample_rate=16000, cfg=_cfg(),
            engine=eng, remember=remembered.append,
            paste=lambda t, m: pasted.append((t, m)) or PasteResult("wtype", True))
        self.assertTrue(res["ok"])
        self.assertEqual(res["text"], "hello world")  # stripped
        self.assertEqual(res["method"], "wtype")
        self.assertTrue(res["delivered"])
        self.assertEqual(remembered[0]["text"], "hello world")
        self.assertEqual(remembered[0]["language"], "de")
        self.assertEqual(pasted, [("hello world", "auto")])
        # language=None default passes through to the engine
        self.assertEqual(eng.seen[0][1], None)

    def test_engine_failure_is_error_result(self):
        res = pipeline.complete(
            [0.1] * 32000, sample_rate=16000, cfg=_cfg(),
            engine=StubEngine(fail="boom"),
            remember=lambda e: None,
            paste=lambda t, m: PasteResult("wtype", True))
        self.assertFalse(res["ok"])
        self.assertIn("boom", res["error"])

    def test_undelivered_paste_surfaced(self):
        res = pipeline.complete(
            [0.1] * 32000, sample_rate=16000, cfg=_cfg(),
            engine=StubEngine(text="hi"),
            remember=lambda e: None,
            paste=lambda t, m: PasteResult("clipboard-only", False, "no keys"))
        self.assertTrue(res["ok"])
        self.assertFalse(res["delivered"])
        self.assertEqual(res["method"], "clipboard-only")


if __name__ == "__main__":
    unittest.main()
