"""Wave 3 — DATA_DIR lazy-init tripwire (anomaly A2).

Context: before wave 3 the cell's ``config.py`` did
``DATA_DIR.mkdir(parents=True, exist_ok=True)`` at module-import time.
Any ``pytest --collect-only`` run therefore created
``~/Desktop/nuzantara/data/seo_cell/`` on disk — polluting the workspace
and making ``tmp_path``-based fixtures racy because the "pristine" state
assumed by a test was already contaminated by the collector.

This file guards two invariants:

1. The ``config`` module source does not regrow a top-level
   ``DATA_DIR.mkdir(...)``. This is a static check so it keeps working
   even if another test has already forced DATA_DIR into existence.
2. The new ``ensure_data_dir()`` helper actually creates the directory
   when called, and returns the same ``Path`` object so callers can
   chain it safely.

If either assertion fails, the fix shipped in wave 3 has regressed.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

from apps.evaluator.seo_cell import config


def test_import_config_does_not_create_data_dir() -> None:
    """Parse config.py and assert no top-level ``.mkdir(`` call exists.

    Static inspection is preferable to a runtime probe here: by the time
    pytest has collected this file the rest of the suite may already
    have imported ``config`` (cached in ``sys.modules``) and indirectly
    created DATA_DIR via a real factory call. An AST check answers the
    only question that matters — "does importing the module, by itself,
    touch the filesystem?" — without depending on collector order.
    """
    assert "apps.evaluator.seo_cell.config" in sys.modules, (
        "config module should be importable for this test to be meaningful"
    )

    source = Path(config.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # ``.mkdir()`` calls that sit directly under a module-level statement
    # other than a FunctionDef are the regression we want to catch.
    # Anything nested inside a function body (e.g. ``ensure_data_dir``)
    # is fine — that is the lazy path we explicitly want.
    offenders: list[int] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue  # function-scope mkdir is allowed (and expected)
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "mkdir"
            ):
                offenders.append(sub.lineno)

    assert offenders == [], (
        f"config.py must not call .mkdir() at module scope (A2 regression). "
        f"Offending lines: {offenders}"
    )


def test_ensure_data_dir_creates_when_called(tmp_path, monkeypatch) -> None:
    """``ensure_data_dir()`` materialises DATA_DIR on demand and is idempotent.

    We point DATA_DIR at a fresh tmp subpath that does not exist yet, then
    call the helper twice. The first call must create it; the second must
    succeed without raising (``exist_ok=True`` semantics) and return the
    same path object the module exposes.
    """
    target = tmp_path / "seo_cell_under_test"
    assert not target.exists(), "precondition: tmp target should not exist"

    monkeypatch.setattr(config, "DATA_DIR", target)

    returned = config.ensure_data_dir()
    assert target.is_dir(), "first call should create DATA_DIR"
    assert returned == target, "helper should return the (patched) DATA_DIR"

    # Idempotent — a second call on an existing dir must not raise.
    returned_again = config.ensure_data_dir()
    assert returned_again == target
    assert target.is_dir()
