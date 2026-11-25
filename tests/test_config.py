"""Tests for config validation (candidate 6)."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._old_home = os.environ.get("XDG_CONFIG_HOME")
        self.tmp = tempfile.mkdtemp(prefix="wd-cfg-")
        os.environ["XDG_CONFIG_HOME"] = self.tmp

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_home

    def _write(self, body: str):
        from pathlib import Path
        d = Path(self.tmp) / "whistle-dictate"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.toml").write_text(body)

    def _load(self):
        from whistle_dictate import config
        err = io.StringIO()
        with redirect_stderr(err):
            cfg = config.load_config()
        return cfg, err.getvalue()

    def test_unknown_key_warns(self):
        self._write('paste_method = "auto"\nsensitivty = 2.0\n')
        cfg, err = self._load()
        self.assertIn("sensitivty", err)
        self.assertEqual(cfg["sensitivity"], 1.0)  # typo ignored, default kept

    def test_sensitivity_clamped(self):
        self._write('sensitivity = 99.0\n')
        cfg, err = self._load()
        self.assertIn("clamping", err)
        self.assertEqual(cfg["sensitivity"], 3.0)

    def test_bad_sensitivity_type(self):
        self._write('sensitivity = "loud"\n')
        cfg, err = self._load()
        self.assertIn("bad sensitivity", err)
        self.assertEqual(cfg["sensitivity"], 1.0)

    def test_bad_overlay_type(self):
        self._write('overlay = "yes please"\n')
        cfg, err = self._load()
        self.assertIn("overlay must be true/false", err)
        self.assertTrue(cfg["overlay"])

    def test_clean_config_silent(self):
        self._write('paste_method = "auto"\nsensitivity = 1.5\noverlay = false\n')
        cfg, err = self._load()
        self.assertEqual(err, "")
        self.assertEqual(cfg["sensitivity"], 1.5)
        self.assertFalse(cfg["overlay"])


if __name__ == "__main__":
    unittest.main()
