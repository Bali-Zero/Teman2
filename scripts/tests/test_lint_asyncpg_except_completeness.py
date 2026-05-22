"""W34 (2026-05-23) — tests for lint_asyncpg_except_completeness.py.

Verifies the linter correctly:
- Detects `except asyncpg.PostgresError:` without InterfaceError (violation)
- Accepts `except (asyncpg.PostgresError, asyncpg.InterfaceError, ...)` (clean)
- Ignores venv/site-packages paths (vendored asyncpg has the bare pattern legitimately)
- Ignores test directories
- Respects ALLOW_PREFIXES policy
- Returns exit 0 on clean / exit 1 on violations
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from textwrap import dedent

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_asyncpg_except_completeness.py"


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("lint_asyncpg", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content), encoding="utf-8")
    return path


def test_bare_postgres_error_is_violation(tmp_path, lint, monkeypatch):
    bad = _write(tmp_path, "scripts/daemon.py", """
        import asyncpg
        try:
            await conn.execute("SELECT 1")
        except asyncpg.PostgresError:
            pass
    """)
    violations = lint.find_violations(bad)
    assert len(violations) == 1
    assert "PostgresError" in violations[0][1]


def test_tuple_with_postgres_no_interface_is_violation(tmp_path, lint):
    bad = _write(tmp_path, "scripts/daemon.py", """
        import asyncpg
        try:
            await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError):
            pass
    """)
    violations = lint.find_violations(bad)
    assert len(violations) == 1


def test_tuple_with_both_is_clean(tmp_path, lint):
    good = _write(tmp_path, "scripts/daemon.py", """
        import asyncpg
        try:
            await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError):
            pass
    """)
    violations = lint.find_violations(good)
    assert violations == []


def test_venv_path_out_of_scope(lint, tmp_path):
    """Vendored asyncpg in .venv legitimately uses `except asyncpg.PostgresError`."""
    path = tmp_path / "apps" / "backend-rag" / ".venv" / "lib" / "site-packages" / "asyncpg" / "cluster.py"
    assert not lint.is_in_scope(path, tmp_path)


def test_node_modules_out_of_scope(lint, tmp_path):
    path = tmp_path / "node_modules" / "something" / "file.py"
    assert not lint.is_in_scope(path, tmp_path)


def test_tests_dir_out_of_scope(lint, tmp_path):
    path = tmp_path / "apps" / "backend-rag" / "tests" / "test_something.py"
    assert not lint.is_in_scope(path, tmp_path)


def test_allow_prefix_routers_out_of_scope(lint, tmp_path):
    path = tmp_path / "apps" / "backend-rag" / "backend" / "app" / "routers" / "lead_capture.py"
    assert not lint.is_in_scope(path, tmp_path)


def test_scripts_in_scope(lint, tmp_path):
    """scripts/*.py (daemons + cron entries) ARE in scope."""
    path = tmp_path / "scripts" / "pg-to-organism-bridge.py"
    assert lint.is_in_scope(path, tmp_path)


def test_cell_in_scope(lint, tmp_path):
    path = tmp_path / "apps" / "cell" / "cell" / "core" / "pulse.py"
    assert lint.is_in_scope(path, tmp_path)


def test_no_postgres_at_all_returns_empty(tmp_path, lint):
    """Files without any asyncpg.PostgresError mention shouldn't be inspected at all."""
    clean = _write(tmp_path, "scripts/clean.py", """
        def foo():
            return 42
    """)
    violations = lint.find_violations(clean)
    assert violations == []


def test_main_exit_0_on_clean(monkeypatch, capsys):
    """Run on the live codebase — should be green now after W34 fixes."""
    # cd to repo root not needed — script uses parents[1] of __file__
    mod = _load_lint_module()
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0, f"linter should be green post-W34; output:\n{captured.out}"
    assert "no violations" in captured.out
