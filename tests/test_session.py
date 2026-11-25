"""Tests for the session lifecycle (candidate 1). No processes spawned —
only pid/result files in an isolated runtime dir (our own live pid stands
in for a running worker; SIGTERM paths are not exercised here)."""
import json
import os
import tempfile
import unittest


def _isolated():
    tmp = tempfile.mkdtemp(prefix="wd-sess-")
    os.environ["XDG_RUNTIME_DIR"] = tmp
    return tmp


class SessionTest(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("XDG_RUNTIME_DIR")
        _isolated()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self._old

    def test_not_recording_initially(self):
        from whistle_dictate import session
        self.assertIsNone(session.is_recording())

    def test_dead_pidfile_cleaned(self):
        from whistle_dictate import session
        from whistle_dictate import state
        state.pid_path().write_text("999999999")
        self.assertIsNone(session.is_recording())
        self.assertFalse(state.pid_path().exists())

    def test_live_pid_detected(self):
        from whistle_dictate import session
        from whistle_dictate import state
        state.pid_path().write_text(str(os.getpid()))
        try:
            self.assertEqual(session.is_recording(), os.getpid())
        finally:
            state.pid_path().unlink(missing_ok=True)

    def test_stop_and_wait_not_recording(self):
        from whistle_dictate import session
        self.assertEqual(session.stop_and_wait(timeout=0.2),
                         ("not-recording", None))

    def test_stop_and_wait_ok(self):
        from whistle_dictate import session
        from whistle_dictate import state
        state.pid_path().write_text(str(os.getpid()))
        state.result_path().write_text(json.dumps({"ok": True, "text": "hi"}))
        try:
            status, result = session.stop_and_wait(timeout=2)
        finally:
            state.pid_path().unlink(missing_ok=True)
            state.result_path().unlink(missing_ok=True)
        self.assertEqual(status, "ok")
        self.assertEqual(result["text"], "hi")
        self.assertTrue(state.stop_path().exists())  # stop requested

    def test_stop_and_wait_timeout(self):
        from whistle_dictate import session
        from whistle_dictate import state
        state.pid_path().write_text(str(os.getpid()))
        try:
            self.assertEqual(session.stop_and_wait(timeout=0.2)[0], "timeout")
        finally:
            state.pid_path().unlink(missing_ok=True)
            state.result_path().unlink(missing_ok=True)

    def test_cancel_cleans_up(self):
        from whistle_dictate import session
        from whistle_dictate import state
        state.stop_path().touch()
        self.assertFalse(session.cancel())
        self.assertFalse(state.stop_path().exists())


if __name__ == "__main__":
    unittest.main()
