from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# apps/backend-rag — the directory `backend` is a package inside. This file
# lives at backend/tests/unit/app/setup/, five levels below apps/backend-rag
# (setup -> app -> unit -> tests -> backend -> backend-rag), matching the
# parents[5] idiom used by its neighbours (e.g. test_light_router_startup_imports.py).
BACKEND_ROOT = Path(__file__).resolve().parents[5]


def _guarded_child(script: str, timeout: int, **env_overrides: str):
    """Run the guarded probe with `backend` importable, from ANY cwd.

    These probes run `python -c`, which puts the CURRENT DIRECTORY on the
    child's sys.path — never PYTHONPATH, and never pytest's own
    `pythonpath = .` (that setting feeds pytest's sys.path, it does not
    export anything to a subprocess). So the tests passed when pytest
    happened to be invoked from apps/backend-rag and failed with
    `ModuleNotFoundError: No module named 'backend'` when it was not — which
    is what CI does. They were red on main and, as a REQUIRED check, blocked
    every open PR regardless of its diff.

    Anchoring cwd to BACKEND_ROOT is the fix; PYTHONPATH is belt-and-braces
    for the day someone switches these probes to `-m`, where cwd is not
    added to sys.path.
    """
    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(p for p in (str(BACKEND_ROOT), existing) if p)
    env = {**os.environ, "PYTHONPATH": pythonpath, **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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
    result = _guarded_child(script, timeout=15, SKIP_SENTRY_INIT="1")
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
    result = _guarded_child(
        script, timeout=10, SENTRY_DSN="not-a-real-dsn", SKIP_SENTRY_INIT=""
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "returned_in=" in result.stdout
