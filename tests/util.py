"""Shared test fixtures: isolated XDG dirs so tests never touch real config."""
import os
import tempfile
from contextlib import contextmanager


@contextmanager
def isolated_runtime_dir():
    """Point XDG_RUNTIME_DIR at a fresh temp dir (state files live here)."""
    old = os.environ.get("XDG_RUNTIME_DIR")
    os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="wd-test-run-")
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = old


@contextmanager
def isolated_config_home():
    """Point XDG_CONFIG_HOME at a fresh temp dir (config.toml lives here)."""
    old = os.environ.get("XDG_CONFIG_HOME")
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="wd-test-cfg-")
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = old
