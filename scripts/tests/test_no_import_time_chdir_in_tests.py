"""Tripwire: no test module may change the process cwd at IMPORT time.

WHY THIS EXISTS
---------------
`apps/backend-rag/backend/tests/integration/zantara/test_tier1_fallback.py` used
to call `os.chdir(...)` at module scope, labelled "change to backend directory
for imports". Module scope means it fired during pytest **collection**, so it
moved the cwd of the entire session — permanently, for every test collected
after it, in file order, in a way nothing announced.

The victim was `apps/backend-rag/tests/test_sentry_lazy_import.py`, which spawns
a subprocess that inherits both the cwd and CI's relative `PYTHONPATH=.`. With
the cwd moved one level down, `.` no longer named `apps/backend-rag`, so the
child died with `ModuleNotFoundError: No module named 'backend'`. `Backend Tests
(Python)` is a required check, so main went red and every open PR in the repo
was blocked by a defect none of them contained.

The signature to remember: **green in isolation, red in the suite**. That is
almost never the failing test's fault — it is something earlier in the session
having mutated process-global state. cwd is the easiest one to mutate by
accident and the hardest to see, because nothing in the failure message
mentions it.

THE RULE
--------
A test module (or conftest) may not call `chdir` anywhere that executes on
import. Inside a test or fixture body is fine — `monkeypatch.chdir()` is better
still, because it restores. Scoped chdir is deliberately NOT flagged here; the
defect is the unrestorable one.

Scope: first-party test roots only. `vendor/` is excluded — it is third-party
code we do not edit, and its suites do not share a pytest session with ours.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PRUNE_DIRS = {
    ".git",
    ".venv",
    ".worktrees",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
}

TEST_FILE_GLOBS = ("test_*.py", "*_test.py", "conftest.py")


def _iter_test_files(root: Path) -> list[Path]:
    """Every first-party test/conftest file under `root`, pruned dirs skipped."""
    found: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in PRUNE_DIRS for part in path.relative_to(root).parts):
            continue
        if any(path.match(pattern) for pattern in TEST_FILE_GLOBS):
            found.append(path)
    return found


def _import_time_chdir_lines(source: str, filename: str = "<probe>") -> list[int]:
    """Line numbers of `chdir(...)` calls that run when the module is imported.

    Descends through module-level `if` / `try` / `with` / `for` / class bodies —
    those all execute at import — but NOT into function bodies, which do not.

    `filename` is passed to `ast.parse` only so that any SyntaxWarning a scanned
    file provokes names that file instead of `<unknown>`.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []

    hits: list[int] = []

    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue  # body runs on call, not on import
            if isinstance(child, ast.Call):
                func = child.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name == "chdir":
                    hits.append(child.lineno)
            walk(child)

    walk(tree)
    return hits


# --- INNOCENCE: scoped chdir is legitimate and must NOT be flagged ------------


def test_chdir_inside_a_function_body_is_not_flagged() -> None:
    source = (
        "import os\n"
        "def test_thing(tmp_path):\n"
        "    os.chdir(tmp_path)\n"
        "def test_other(monkeypatch, tmp_path):\n"
        "    monkeypatch.chdir(tmp_path)\n"
    )
    assert _import_time_chdir_lines(source) == []


# --- GUILT: the exact shape that broke main must be caught --------------------


def test_module_level_chdir_is_flagged() -> None:
    source = "import os\nfrom pathlib import Path\nos.chdir(str(Path('backend')))\n"
    assert _import_time_chdir_lines(source) == [3]


def test_chdir_hidden_in_a_module_level_if_is_flagged() -> None:
    """The original could as easily have been guarded — it would still fire."""
    source = "import os\nif True:\n    os.chdir('backend')\n"
    assert _import_time_chdir_lines(source) == [3]


def test_bare_chdir_import_is_flagged() -> None:
    """`from os import chdir` hides the `os.` prefix a naive grep looks for."""
    source = "from os import chdir\nchdir('backend')\n"
    assert _import_time_chdir_lines(source) == [2]


# --- The live assertion over the real tree ------------------------------------


def test_no_first_party_test_file_chdirs_at_import_time() -> None:
    files = _iter_test_files(REPO_ROOT)

    # Blind-scan guard: zero files walked means the probe is broken, not that
    # the tree is clean (the lesson of W84 / the secrets-audit exit 2).
    assert len(files) > 500, (
        f"probe walked only {len(files)} test files under {REPO_ROOT} — "
        "it is blind, not the tree clean"
    )

    offenders: list[str] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in _import_time_chdir_lines(source, filename=str(path)):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}")

    assert not offenders, (
        "these run chdir at import time, which moves the cwd for every test "
        "collected after them in the same pytest session:\n  "
        + "\n  ".join(offenders)
        + "\nMove the chdir inside the test and use monkeypatch.chdir()."
    )
