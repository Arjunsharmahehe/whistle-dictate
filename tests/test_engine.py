"""Tests for the engine seam (candidate 2): constructed, substitutable,
no model download. A fake `cactus` module stands in for the real one."""
import sys
import types
import unittest


class FakeWhistle:
    last_kwargs = None

    def __init__(self, weights=None):
        FakeWhistle.last_weights = weights

    def transcribe(self, samples, language=None, keywords=None,
                   word_timestamps=False):
        FakeWhistle.last_kwargs = dict(language=language, keywords=keywords,
                                       word_timestamps=word_timestamps)
        return {"text": "fake transcript", "language": language or "en"}


def _install_fake_cactus():
    mod = types.ModuleType("cactus")
    mod.Whistle = FakeWhistle
    mod.__version__ = "fake"
    sys.modules["cactus"] = mod
    return mod


class EngineTest(unittest.TestCase):
    def setUp(self):
        self._had = sys.modules.get("cactus")
        _install_fake_cactus()
        from whistle_dictate import engine
        engine._default = None  # fresh singleton per test

    def tearDown(self):
        from whistle_dictate import engine
        engine._default = None
        if self._had is None:
            sys.modules.pop("cactus", None)
        else:
            sys.modules["cactus"] = self._had

    def test_engine_passes_args_through(self):
        from whistle_dictate import engine
        eng = engine.WhistleEngine()
        res = eng.transcribe([0.1] * 100, language="de", keywords=["x"])
        text = res["text"] if isinstance(res, dict) else res.text
        self.assertEqual(text, "fake transcript")
        self.assertEqual(FakeWhistle.last_kwargs["language"], "de")
        self.assertEqual(FakeWhistle.last_kwargs["keywords"], ["x"])

    def test_transcribe_audio_uses_injected_engine(self):
        from whistle_dictate import engine
        stub = FakeWhistle()
        res = engine.transcribe_audio([0.1] * 100, engine=stub)
        self.assertEqual(res["text"], "fake transcript")

    def test_get_whistle_is_shared_default(self):
        from whistle_dictate import engine
        self.assertIs(engine.get_whistle(), engine.get_whistle())


if __name__ == "__main__":
    unittest.main()
