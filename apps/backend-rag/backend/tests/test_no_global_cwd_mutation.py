"""No test module may move the process working directory at import time.

A module-level ``os.chdir`` runs during *collection* and is never undone, so it
relocates the cwd of the whole pytest process for every test collected after it.
Nothing in-process usually notices — imports already resolved through ``sys.path``
— which is why this survived a long time. Subprocesses do notice: they re-resolve
relative paths, and the CI command exports ``PYTHONPATH=.``.

Lived instance: ``backend/tests/integration/zantara/test_tier1_fallback.py`` chdir'd
into ``backend/`` at import time, so ``PYTHONPATH=.`` came to mean
``apps/backend-rag/backend``, and the ``python -c`` child spawned by
``tests/test_sentry_lazy_import.py`` died on ``ModuleNotFoundError: No module named
'backend'`` — a test in another tree, failing for a line it never touches. It only
surfaced when #3227 added that file to the CI pytest invocation for the first time.

Inside a test body ``monkeypatch.chdir`` is fine: pytest restores it.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_TREES = ("backend/tests", "tests")


def _module_level_chdirs(source: str, label: str = "<inline>") -> list[str]:
    """Return ``label:lineno`` for every ``*.chdir(...)`` reachable at import time.

    Walks only the module's top-level statements, so a call nested in a function or
    method body — which runs when that test runs, under pytest's fixtures — is not
    reported. Matches on the attribute name rather than on ``os.chdir`` specifically:
    ``from os import chdir as cd`` and ``pathlib``-flavoured aliases mutate the same
    process state, and matching the import spelling would be exactly the over-match
    that lets the next instance through.
    """
    hits: list[str] = []

    def visit(node: ast.AST) -> None:
        # `ast.walk` would descend into function bodies, which do NOT run at import
        # time — that reads every fixture's scoped chdir as an offence. Recurse by
        # hand and stop at anything deferred to call time. A ClassDef body is not
        # deferred, so it stays in scope.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "chdir"
        ):
            hits.append(f"{label}:{node.lineno}")
        for child in ast.iter_child_nodes(node):
            visit(child)

    for stmt in ast.parse(source, label).body:
        visit(stmt)
    return hits


def test_no_test_module_chdirs_at_import_time() -> None:
    """The real suite carries no import-time chdir."""
    offenders: list[str] = []
    scanned = 0
    for tree in TEST_TREES:
        root = BACKEND_ROOT / tree
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            try:
                source = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            offenders += _module_level_chdirs(
                source, str(path.relative_to(BACKEND_ROOT))
            )

    # A scan that walked nothing is not a clean scan (W84): fail loudly instead of
    # reporting an empty offender list as success.
    assert scanned > 100, f"only {scanned} test modules scanned — the walk is broken"
    assert not offenders, (
        "module-level chdir moves the cwd for the entire pytest process and is never "
        "restored; use monkeypatch.chdir inside the test instead: " + ", ".join(offenders)
    )


def test_detector_flags_an_import_time_chdir() -> None:
    """Guilt: the shape this guard exists to catch is caught."""
    guilty = "import os\nbackend_path = '/x'\nos.chdir(backend_path)\n"
    assert _module_level_chdirs(guilty) == ["<inline>:3"]

    aliased = "from os import chdir\nimport pathlib\npathlib.os.chdir('/x')\n"
    assert _module_level_chdirs(aliased) == ["<inline>:3"]

    guarded = "import os\nif True:\n    os.chdir('/x')\n"
    assert _module_level_chdirs(guarded) == ["<inline>:3"], (
        "a chdir under a module-level `if` still runs at import time"
    )


def test_detector_leaves_scoped_chdir_alone() -> None:
    """Innocence: a chdir that runs per-test, restored by pytest, is not an offence."""
    scoped = (
        "import os\n"
        "def test_thing(tmp_path, monkeypatch):\n"
        "    monkeypatch.chdir(tmp_path)\n"
        "    assert os.getcwd()\n"
    )
    assert _module_level_chdirs(scoped) == []

    in_fixture = (
        "import os\n"
        "import pytest\n"
        "@pytest.fixture\n"
        "def somewhere_else(tmp_path):\n"
        "    old = os.getcwd()\n"
        "    os.chdir(tmp_path)\n"
        "    yield tmp_path\n"
        "    os.chdir(old)\n"
    )
    assert _module_level_chdirs(in_fixture) == []

    mentioned_only = "CHDIR_IS_BANNED = 'os.chdir'\n"
    assert _module_level_chdirs(mentioned_only) == []
