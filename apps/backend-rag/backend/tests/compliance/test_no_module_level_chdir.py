"""No test module may move the process working directory at import time.

Why this guard exists (2026-07-27): `backend/tests/integration/zantara/
test_tier1_fallback.py` carried a module-level `os.chdir(...)`. pytest imports
every collected module BEFORE running a single test, so that one line moved the
cwd of the whole session — permanently, and for tests that had nothing to do
with it. It stayed invisible for as long as nothing depended on the cwd; the
moment PR #3227 armed `tests/test_sentry_lazy_import.py` (which shells out to a
fresh interpreter that resolves `import backend` from the cwd), main's required
`Backend Tests (Python)` leg went red and stayed red, blocking every PR.

The failure and its cause were in different files, and the failing test was
innocent. That is the signature of process-global state set at import time, so
the cure is structural rather than a fix to either file: a module-level `chdir`
in a test tree is banned outright, and this test is what arms the ban.

Scope note: the ban is on the MODULE level only. A `chdir` inside a test
function that restores it — or, better, `monkeypatch.chdir` / `tmp_path` — is
legitimate and must keep passing (innocence corpus below).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

# `apps/backend-rag` — parents: compliance -> tests -> backend -> apps/backend-rag
_BACKEND_RAG_ROOT = Path(__file__).resolve().parents[3]

# Every python test tree this repo's backend CI collects. `tests/` is the
# top-level one CI passes explicitly (test_sentry_lazy_import.py lives there);
# `backend/tests/` is the main suite.
_TEST_ROOTS = (
    _BACKEND_RAG_ROOT / "backend" / "tests",
    _BACKEND_RAG_ROOT / "tests",
)


def _is_chdir_call(node: ast.AST) -> bool:
    """True for `os.chdir(...)` / `chdir(...)` / `pathlib.os.chdir(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "chdir"
    if isinstance(func, ast.Name):
        return func.id == "chdir"
    return False


def _module_level_chdir_lines(source: str) -> list[int]:
    """Line numbers of `chdir` calls reachable at IMPORT time.

    Walks only the statements that execute when the module is imported: the
    module body plus the bodies of module-level `if` / `try` / `with` / `for` /
    `while` blocks. Deliberately does NOT descend into `FunctionDef`,
    `AsyncFunctionDef` or `ClassDef` bodies — a chdir inside a function runs
    when that function is CALLED, which is the legitimate case.
    """
    tree = ast.parse(source)
    found: list[int] = []

    def walk(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(
                stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            for sub in ast.walk(stmt):
                if isinstance(
                    sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    # A nested def inside a module-level `if` is still deferred.
                    continue
                if _is_chdir_call(sub):
                    found.append(sub.lineno)


    walk(tree.body)
    return sorted(set(found))


def _iter_test_sources() -> list[Path]:
    files: list[Path] = []
    for root in _TEST_ROOTS:
        if not root.is_dir():
            continue
        files.extend(
            p
            for p in root.rglob("*.py")
            if "__pycache__" not in p.parts and "_obsolete" not in p.parts
        )
    return files


def test_guard_flags_a_module_level_chdir() -> None:
    """GUILT: the exact shape that broke main must be detected."""
    guilty = textwrap.dedent(
        """
        import os
        from pathlib import Path

        backend_path = Path(__file__).parent.parent
        os.chdir(str(backend_path / "backend"))

        def test_something():
            assert True
        """
    )
    assert _module_level_chdir_lines(guilty) == [6]


def test_guard_flags_a_chdir_hidden_in_a_module_level_if() -> None:
    """GUILT: guarding the call with an `if` does not defer it to call time."""
    guilty = textwrap.dedent(
        """
        import os

        if os.environ.get("CI"):
            os.chdir("/tmp")
        """
    )
    assert _module_level_chdir_lines(guilty) == [5]


def test_guard_does_not_flag_chdir_inside_a_test_or_fixture() -> None:
    """INNOCENCE: a scoped chdir is legitimate and must keep passing.

    Covers the three legitimate shapes: `monkeypatch.chdir`, a plain `os.chdir`
    inside a function body, and one inside a fixture. None of them run at import
    time, so none of them can poison a sibling module.
    """
    innocent = textwrap.dedent(
        """
        import os
        import pytest

        @pytest.fixture
        def in_tmp(tmp_path, monkeypatch):
            monkeypatch.chdir(tmp_path)
            yield tmp_path

        def test_uses_monkeypatch(tmp_path, monkeypatch):
            monkeypatch.chdir(tmp_path)
            assert True

        def test_restores_by_hand(tmp_path):
            previous = os.getcwd()
            os.chdir(tmp_path)
            try:
                assert True
            finally:
                os.chdir(previous)
        """
    )
    assert _module_level_chdir_lines(innocent) == []


def test_no_backend_test_module_changes_the_cwd_at_import_time() -> None:
    """The real sweep over both collected test trees."""
    sources = _iter_test_sources()
    # Fail loud rather than silently pass on an empty scan (a guard that walks
    # zero files is not a green guard, it is a blind one).
    assert len(sources) > 100, (
        f"expected to scan the whole backend test tree, found {len(sources)} "
        f"files under {[str(r) for r in _TEST_ROOTS]} — the roots are wrong"
    )

    offenders: list[str] = []
    for path in sources:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable file
            continue
        try:
            lines = _module_level_chdir_lines(source)
        except SyntaxError:  # pragma: no cover - not this guard's job to police
            continue
        for line in lines:
            offenders.append(f"{path.relative_to(_BACKEND_RAG_ROOT)}:{line}")

    assert not offenders, (
        "module-level chdir moves the cwd of the ENTIRE pytest session at "
        "collection time and breaks unrelated tests that shell out "
        "(see this file's docstring). Move it inside the test/fixture, or use "
        "monkeypatch.chdir/tmp_path:\n  " + "\n  ".join(offenders)
    )
