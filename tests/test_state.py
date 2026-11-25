"""Tests for the shared overlay-state seam (candidate 3)."""
import json
import unittest

from .util import isolated_runtime_dir


class StateTest(unittest.TestCase):
    def setUp(self):
        self._ctx = isolated_runtime_dir()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_round_trip(self):
        from whistle_dictate import state
        state.write(state.Phase.RECORDING, elapsed=1.5,
                    spec=[0.5] * 24, peak=0.7)
        st = state.read()
        self.assertEqual(st["phase"], "recording")
        self.assertEqual(st["elapsed"], 1.5)
        self.assertEqual(len(st["spec"]), 24)
        self.assertAlmostEqual(st["spec"][0], 0.5)

    def test_missing_file_gives_defaults(self):
        from whistle_dictate import state
        st = state.read()
        self.assertEqual(st["phase"], state.Phase.RECORDING)
        self.assertEqual(st["spec"], [0.0] * 24)

    def test_unknown_phase_sanitized(self):
        from whistle_dictate import state
        state.osd_path().write_text(json.dumps({"phase": "bogus"}))
        self.assertEqual(state.read()["phase"], state.Phase.RECORDING)

    def test_spec_clamped_and_padded(self):
        from whistle_dictate import state
        state.osd_path().write_text(json.dumps(
            {"phase": "recording", "spec": [2.0, -1.0, "x"]}))
        spec = state.read()["spec"]
        self.assertEqual(len(spec), 24)
        self.assertEqual(spec[:3], [1.0, 0.0, 0.0])

    def test_phase_constants_cover_overlay_branches(self):
        from whistle_dictate import state
        # every phase the overlay branches on must exist on the seam
        for name in ("RECORDING", "TRANSCRIBING", "DONE", "ERROR", "DISMISS"):
            self.assertIn(getattr(state.Phase, name), state.Phase.ALL)


if __name__ == "__main__":
    unittest.main()
