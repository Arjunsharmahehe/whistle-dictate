"""Tests for the cross-platform backend seams.

No mic, no model, no Hyprland: factories resolve, protocols coerce, and
the pipeline accepts both TranscriptionResult and legacy dicts.
"""
import unittest

from whistle_dictate.transcribers.base import TranscriptionResult
from whistle_dictate import pipeline


class FakeTranscriber:
    name = "fake"
    sample_rate = 16000

    def __init__(self, text="hi"):
        self.text = text

    def transcribe(self, samples, language=None, keywords=None,
                   word_timestamps=False):
        return TranscriptionResult(text=self.text, language=language or "en")


class BackendTest(unittest.TestCase):
    def test_transcriber_factory_unknown_raises(self):
        from whistle_dictate import transcribers
        with self.assertRaises(ValueError):
            transcribers.create("sapi-never-exists")

    def test_transcriber_factory_lists_whistle(self):
        from whistle_dictate import transcribers
        self.assertIn("whistle", transcribers.available())

    def test_transcription_result_roundtrip(self):
        r = TranscriptionResult(text="hi", language="en")
        self.assertEqual(TranscriptionResult.from_dict(r.to_dict()).text, "hi")
        self.assertEqual(TranscriptionResult.from_dict({"text": "x"}).language, None)
        self.assertEqual(TranscriptionResult.from_dict(None).text, "")

    def test_pipeline_accepts_result_object(self):
        from whistle_dictate.paste import PasteResult
        res = pipeline.complete(
            [0.1] * 32000, sample_rate=16000,
            cfg={"language": None, "keywords": [], "paste_method": "auto"},
            engine=FakeTranscriber("  hello  "),
            remember=lambda e: None,
            paste=lambda t, m: PasteResult("wtype", True))
        self.assertTrue(res["ok"])
        self.assertEqual(res["text"], "hello")

    def test_pipeline_accepts_legacy_dict(self):
        from whistle_dictate.paste import PasteResult

        class Legacy:
            def transcribe(self, samples, language=None, keywords=None,
                           **kw):
                return {"text": "yo", "language": "de"}

        res = pipeline.complete(
            [0.1] * 32000, sample_rate=16000,
            cfg={"language": None, "keywords": [], "paste_method": "auto"},
            engine=Legacy(), remember=lambda e: None,
            paste=lambda t, m: PasteResult("wtype", True))
        self.assertTrue(res["ok"])
        self.assertEqual(res["language"], "de")

    def test_paste_factory(self):
        from whistle_dictate import paste_backends
        self.assertIn("auto", paste_backends.available())
        be = paste_backends.create("stdout")
        self.assertEqual(be.paste("hi").method, "stdout")
        with self.assertRaises(ValueError):
            paste_backends.create("darwin-magic")

    def test_audio_factory(self):
        from whistle_dictate import audio_sources
        self.assertIn("sounddevice", audio_sources.available())
        with self.assertRaises(ValueError):
            audio_sources.create("coreaudio-never")

    def test_overlay_factory(self):
        from whistle_dictate import overlays
        noop = overlays.create(False)
        self.assertEqual(noop.name, "noop")
        noop.spawn()
        noop.reap()
        with self.assertRaises(ValueError):
            overlays.create("aqua-never")

    def test_notifier_factory(self):
        from whistle_dictate import notifiers
        noop = notifiers.create("noop")
        self.assertEqual(noop.name, "noop")
        noop.notify("hi")  # never raises
        auto = notifiers.create("auto")
        auto.notify("hi")
        with self.assertRaises(ValueError):
            notifiers.create("growl-never")

    def test_platform_probes(self):
        from whistle_dictate import platform as p
        self.assertIn(p.os_name(), ("linux", "darwin", "windows"))
        self.assertIsInstance(p.desktop(), str)
        self.assertIsInstance(p.have("sh"), bool)

    def test_config_accessors(self):
        from whistle_dictate import config
        cfg = {"transcriber": "whistle", "audio_source": "sounddevice",
               "notifier": "auto"}
        self.assertEqual(config.transcriber_name(cfg), "whistle")
        self.assertEqual(config.audio_source_name(cfg), "sounddevice")
        self.assertEqual(config.notifier_name(cfg), "auto")
        self.assertEqual(config.transcriber_name({}), "whistle")


if __name__ == "__main__":
    unittest.main()
