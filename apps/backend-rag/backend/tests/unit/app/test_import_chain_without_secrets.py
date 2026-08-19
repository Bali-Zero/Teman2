"""The CI import-chain smoke test must pass without production secrets.

`backend/app/utils/__init__.py` is a tollbooth: importing ANY leaf module
under `backend.app.utils` first runs this package's `__init__.py`. Before the
fix in this PR, that file eagerly imported `verify_internal_api_key` from
`backend.app.utils.internal_api_auth`, which reaches all the way to
`backend.app.core.config.Settings()` at import time — and `Settings()`
validates eagerly, raising unless `JWT_SECRET_KEY`/`API_KEYS` are set. So
importing a plain, secret-free module like `service_accounts` (or anything
importing `backend.app.dependencies`, which walks through
`backend.app.deps.auth` -> `backend.app.utils.service_accounts`) required
production secrets to be configured — exactly the CI failure this test
locks in as fixed (CI job run 32240840040, "Backend Tests (Python)").

Guilt cases run in a SUBPROCESS with a STRIPPED environment (never inheriting
`os.environ`) and a cwd that is deliberately NOT `apps/backend-rag`. That
directory contains a `.env` symlink, and `Settings` (pydantic-settings) reads
`.env` from the process cwd — so running the reproduction with
cwd=apps/backend-rag silently supplies JWT_SECRET_KEY/API_KEYS from the local
dotfile and the test would pass even with the eager-import bug still present
(this is exactly how the bug looked green in local ad-hoc checks while CI,
whose checkout has no `.env`, failed). `tmp_path` has no such file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_RAG_ROOT = Path(__file__).resolve().parents[4]
CRM_CELL_ROOT = BACKEND_RAG_ROOT.parent / "crm-cell"
VENV_PYTHON = BACKEND_RAG_ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _run_stripped(code: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run `code` in a fresh interpreter with a minimal, secret-free env.

    `env=` is an explicit minimal mapping (never `{**os.environ, ...}`) so a
    JWT_SECRET_KEY/API_KEYS exported in the developer's own shell can't mask
    the bug this test exists to catch.
    """
    stripped_env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": f"{BACKEND_RAG_ROOT}:{CRM_CELL_ROOT}",
    }
    return subprocess.run(
        [PYTHON, "-c", code],
        cwd=tmp_path,  # NOT apps/backend-rag — see module docstring.
        env=stripped_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_dependencies_import_chain_succeeds_without_secrets(tmp_path: Path) -> None:
    """Guilt: this is the exact assertion that was red in CI run 32240840040."""
    result = _run_stripped(
        "from backend.app.dependencies import get_current_user; print('IMPORT OK')",
        tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "IMPORT OK" in result.stdout


def test_service_accounts_imports_without_secrets(tmp_path: Path) -> None:
    """Guilt: a plain leaf util must not pay the package's tollbooth."""
    result = _run_stripped(
        "import backend.app.utils.service_accounts; print('IMPORT OK')",
        tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "IMPORT OK" in result.stdout


def test_verify_internal_api_key_still_resolves_to_the_real_object() -> None:
    """Innocence: the lazy `__getattr__` must not silently swap identity.

    Runs in-process in the normal test env — `backend/tests/conftest.py` sets
    JWT_SECRET_KEY/API_KEYS via `os.environ.setdefault` before any import, so
    `Settings()` validates fine here and this needs no subprocess.
    """
    from backend.app.utils import verify_internal_api_key as via_package
    from backend.app.utils.internal_api_auth import (
        verify_internal_api_key as via_module,
    )

    assert via_package is via_module
