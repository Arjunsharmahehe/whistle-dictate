"""Tests for the paste adapters (candidate 4). Subprocess is faked —
no wtype, wl-copy or hyprctl runs here."""
import unittest
from unittest import mock

from whistle_dictate import paste
from whistle_dictate.paste import PasteResult


class WtypeTest(unittest.TestCase):
    def test_missing_wtype_not_delivered(self):
        with mock.patch.object(paste, "have", return_value=False):
            res = paste.paste_via_wtype("hi")
        self.assertEqual(res.method, "wtype")
        self.assertFalse(res.delivered)

    def test_wtype_success_delivered(self):
        with mock.patch.object(paste, "have", return_value=True), \
             mock.patch.object(paste.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            res = paste.paste_via_wtype("hi")
        self.assertTrue(res.delivered)


class HyprPasteTest(unittest.TestCase):
    def test_modern_adapter_first(self):
        with mock.patch.object(paste, "send_shortcut_modern",
                               return_value=(True, "modern ok")) as modern, \
             mock.patch.object(paste, "send_shortcut_legacy") as legacy:
            ok, _ = paste._hypr_paste()
        self.assertTrue(ok)
        self.assertTrue(modern.called)
        self.assertFalse(legacy.called)

    def test_falls_back_to_legacy(self):
        with mock.patch.object(paste, "send_shortcut_modern",
                               return_value=(False, "no")), \
             mock.patch.object(paste, "send_shortcut_legacy",
                               return_value=(True, "legacy ok")):
            ok, _ = paste._hypr_paste()
        self.assertTrue(ok)

    def test_all_fail_false(self):
        with mock.patch.object(paste, "send_shortcut_modern",
                               return_value=(False, "no")), \
             mock.patch.object(paste, "send_shortcut_legacy",
                               return_value=(False, "no")), \
             mock.patch.object(paste, "_debug_log") as log:
            ok, _ = paste._hypr_paste()
        self.assertFalse(ok)
        self.assertTrue(log.called)


class PasteTextTest(unittest.TestCase):
    def test_empty(self):
        res = paste.paste_text("")
        self.assertEqual(res.method, "empty")
        self.assertFalse(res.delivered)

    def test_wtype_preferred_in_auto(self):
        with mock.patch.object(paste, "paste_via_wtype",
                               return_value=PasteResult("wtype", True)), \
             mock.patch.object(paste, "paste_via_clipboard") as clip:
            res = paste.paste_text("hi", "auto")
        self.assertEqual(res.method, "wtype")
        self.assertFalse(clip.called)

    def test_clipboard_fallback_in_auto(self):
        with mock.patch.object(paste, "paste_via_wtype",
                               return_value=PasteResult("wtype", False, "no")), \
             mock.patch.object(paste, "paste_via_clipboard",
                               return_value=PasteResult("clipboard-only", False, "no keys")):
            res = paste.paste_text("hi", "auto")
        self.assertEqual(res.method, "clipboard-only")
        self.assertFalse(res.delivered)

    def test_forced_wtype_falls_back_to_stdout(self):
        with mock.patch.object(paste, "paste_via_wtype",
                               return_value=PasteResult("wtype", False, "no")):
            res = paste.paste_text("hi", "wtype")
        self.assertEqual(res.method, "stdout")


if __name__ == "__main__":
    unittest.main()
