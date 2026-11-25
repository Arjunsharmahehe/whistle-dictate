"""Tests for the CLI adapter's result rendering (single home)."""
import unittest

from whistle_dictate.cli import format_result


class FormatResultTest(unittest.TestCase):
    def test_failure(self):
        self.assertEqual(
            format_result({"ok": False, "reason": "discarded: silent clip"},
                          paste=True, print_text=False),
            "discarded: silent clip")
        self.assertEqual(
            format_result({"ok": False, "error": "boom"},
                          paste=True, print_text=False), "boom")

    def test_print_mode(self):
        self.assertEqual(
            format_result({"ok": True, "text": "hi", "method": "wtype"},
                          paste=False, print_text=False), "hi")

    def test_pasted(self):
        self.assertEqual(
            format_result({"ok": True, "text": "hi", "method": "wtype",
                           "delivered": True},
                          paste=True, print_text=False),
            "pasted via wtype: hi")

    def test_undelivered_flagged(self):
        msg = format_result({"ok": True, "text": "hi", "method": "clipboard-only",
                             "delivered": False},
                            paste=True, print_text=False)
        self.assertIn("pasted via clipboard-only: hi", msg)
        self.assertIn("Ctrl+V", msg)


if __name__ == "__main__":
    unittest.main()
