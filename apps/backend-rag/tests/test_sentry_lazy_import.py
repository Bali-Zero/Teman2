from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_sentry_config_import_skips_sentry_sdk_when_disabled() -> None:
    """Importing app startup code must not load sentry_sdk when Sentry is off."""
    script = textwrap.dedent(
        """
        import builtins
        import importlib

        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "sentry_sdk" or name.startswith("sentry_sdk."):
                raise AssertionError("sentry_sdk imported before init_sentry opted in")
            if name == "backend.app.setup.app_factory":
                raise AssertionError("setup.__init__ imported app_factory eagerly")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import
        module = importlib.import_module("backend.app.setup.sentry_config")
        module.init_sentry()
        """
    )
    env = {**os.environ, "SKIP_SENTRY_INIT": "1"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_init_sentry_with_dsn_does_not_block_startup() -> None:
    """Sentry opt-in must not block API boot if the SDK import stalls."""
    script = textwrap.dedent(
        """
        import builtins
        import importlib
        import time

        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "sentry_sdk" or name.startswith("sentry_sdk."):
                time.sleep(30)
                raise AssertionError("sentry_sdk import stayed on startup path")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import
        module = importlib.import_module("backend.app.setup.sentry_config")
        started = time.time()
        module.init_sentry()
        elapsed = time.time() - started
        assert elapsed < 2, elapsed
        print(f"returned_in={elapsed:.3f}")
        """
    )
    env = {
        **os.environ,
        "SENTRY_DSN": "not-a-real-dsn",
        "SKIP_SENTRY_INIT": "",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "returned_in=" in result.stdout
