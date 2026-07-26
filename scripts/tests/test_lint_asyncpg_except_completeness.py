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


# --------------------------------------------------------------------------
# BLIND-SCAN GUARD (cicatrix #4 / W84 — "0 files traversed != clean").
#
# The linter resolves its sweep root from `Path(__file__).parents[1]`, so
# loading a COPY of the script from a bare tmp dir gives a repo root with no
# scripts/, apps/ or packages/ — exactly what a sparse checkout, a trimmed CI
# worktree, or a renamed source root looks like from the inside.
# --------------------------------------------------------------------------


def _load_from(root: Path):
    """Load the linter so that its perceived repo root is `root`."""
    target = root / "sub" / "lint_asyncpg_except_completeness.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("lint_asyncpg_blind", target)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_guilt_blind_sweep_refuses_to_report_clean(tmp_path, capsys):
    """ZERO in-scope files swept must FAIL LOUD, never print the green banner."""
    mod = _load_from(tmp_path)  # tmp_path has no scripts/ apps/ packages/
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 2, "a blind sweep must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert "no violations" not in captured.out, (
        "the green banner must never appear when nothing was traversed"
    )


def test_innocence_explicit_file_list_with_no_python_is_still_green(tmp_path, capsys):
    """A pre-commit passing only .md files is legitimate — the guard must not bite.

    Same blind root as the guilt case: the ONLY difference is that argv is
    explicit. If the guard keyed on 'scanned == 0' alone it would block this
    innocent commit (cicatrix #3 over-match).
    """
    mod = _load_from(tmp_path)
    rc = mod.main(["README.md", "docs/notes.md"])
    captured = capsys.readouterr()
    assert rc == 0, "explicit non-Python file list must stay green"
    assert "no violations" in captured.out
    assert "BLIND SCAN" not in captured.err


def test_innocence_one_clean_in_scope_file_is_enough(tmp_path, capsys):
    """The guard fires at EXACTLY zero — a single swept file must satisfy it."""
    mod = _load_from(tmp_path)
    _write(tmp_path, "scripts/ok.py", """
        import asyncpg
        try:
            await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, asyncpg.InterfaceError):
            pass
    """)
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "BLIND SCAN" not in captured.err
