"""Tests for scripts/lint_test_pool_codec_parity.py (L12-PR1, 2026-08-29).

Guilt+innocence discipline (cicatrix-superscar.md #3, "Guard-over-match"):
every accepted shape gets an INNOCENCE test proving it is NOT flagged, and
every bad shape gets a GUILT test proving it IS.

Real-tree note (spec-vs-code disagreement, reported plainly, not papered
over): the PR spec's Build step 5 named exactly TWO bare pools
(`test_bridge_wa_media.py`, `test_intake_review.py`, both under
`apps/backend-rag/backend/tests/routers/`) and its acceptance criterion said
"the live test tree has no bare pool" after converting them. Running the
finished linter against the FULL `apps/backend-rag/backend/tests` tree finds
28 additional pre-existing bare `asyncpg.create_pool()` calls in files this
PR's `Files:` list never named (garuda_orders/garuda_portal/garuda_ops/
intake/compliance/hr/visa_engine test suites, an `app/routers/` tree
DIFFERENT from the `routers/` one the spec meant, etc.) -- a much larger,
separately-scoped cleanup. The LIVE-TREE regression test below is therefore
scoped to `apps/backend-rag/backend/tests/routers/`, the exact directory the
spec named and this PR actually fixed, rather than the whole tree -- an
honest regression guard for what this PR did, not a silently-weakened
assertion pretending the wider tree is clean when it is not.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "lint_test_pool_codec_parity.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_ROUTERS_ROOT = REPO_ROOT / "apps" / "backend-rag" / "backend" / "tests" / "routers"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_test_pool_codec_parity", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_module()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# GUILT — a bare pool must exit 1 and name the exact offending line.
# ---------------------------------------------------------------------------


def test_guilt_bare_attribute_call_is_a_violation(tmp_path, capsys) -> None:
    _write(
        tmp_path,
        "test_bad_pool.py",
        "import asyncpg\n"
        "import pytest_asyncio\n"
        "\n"
        "\n"
        "@pytest_asyncio.fixture\n"
        "async def pool():\n"
        "    p = await asyncpg.create_pool(dsn='postgresql://x', min_size=1, max_size=3)\n"
        "    yield p\n"
        "    await p.close()\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "test_bad_pool.py:7:" in captured.out
    assert "asyncpg.create_pool without init=" in captured.out


def test_guilt_bare_from_import_create_pool_is_a_violation(tmp_path, capsys) -> None:
    _write(
        tmp_path,
        "test_bad_pool_bare_import.py",
        "from asyncpg import create_pool\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    p = await create_pool('postgresql://x', min_size=1, max_size=3)\n"
        "    return p\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "test_bad_pool_bare_import.py:5:" in captured.out


def test_guilt_pytest_importorskip_alias_is_still_a_violation(tmp_path, capsys) -> None:
    """The real-tree under-match this linter's first draft had: several
    `garuda_orders`/`garuda_portal`/`garuda_ops` test files bind `asyncpg`
    via `asyncpg = pytest.importorskip("asyncpg")` rather than a plain
    `import asyncpg`. A scanner that only recognises `ast.Import` misses
    every `asyncpg.create_pool(...)` call in such a file."""
    _write(
        tmp_path,
        "test_bad_pool_importorskip.py",
        "import pytest\n"
        "\n"
        "asyncpg = pytest.importorskip('asyncpg')\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    p = await asyncpg.create_pool('postgresql://x', min_size=1, max_size=2)\n"
        "    return p\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "test_bad_pool_importorskip.py:7:" in captured.out


# ---------------------------------------------------------------------------
# INNOCENCE — must never be flagged.
# ---------------------------------------------------------------------------


def test_innocence_init_keyword_present_is_clean(tmp_path, capsys) -> None:
    _write(
        tmp_path,
        "test_good_pool.py",
        "import asyncpg\n"
        "\n"
        "from backend.tests.fixtures.prod_shaped_pool import init_prod_shaped_connection\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    p = await asyncpg.create_pool(\n"
        "        dsn='postgresql://x', min_size=1, max_size=3, init=init_prod_shaped_connection\n"
        "    )\n"
        "    return p\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "violation" not in captured.out


def test_innocence_mock_patch_string_and_fake_functions_are_never_inspected(tmp_path, capsys) -> None:
    """The false-positive class the AST approach avoids "for free": a
    string argument to `patch(...)`/`monkeypatch.setattr(...)` naming
    "asyncpg.create_pool", an `AsyncMock`/`MagicMock` assignment, and a
    function merely NAMED `fake_create_pool` are none of them a `Call` whose
    `func` is literally `asyncpg.create_pool` or a name bound via
    `from asyncpg import create_pool` -- so the scanner never even looks at
    them, not via an allowlist."""
    _write(
        tmp_path,
        "test_mocked_pool.py",
        "from unittest.mock import AsyncMock, MagicMock, patch\n"
        "\n"
        "\n"
        "def test_one(monkeypatch):\n"
        "    with patch('backend.app.core.database.asyncpg.create_pool', new_callable=AsyncMock):\n"
        "        pass\n"
        "\n"
        "\n"
        "def test_two(monkeypatch):\n"
        "    monkeypatch.setattr('some.module.asyncpg.create_pool', MagicMock())\n"
        "\n"
        "\n"
        "async def fake_create_pool(**kwargs):\n"
        "    return MagicMock()\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "violation" not in captured.out


def test_innocence_empty_tree_is_clean(tmp_path, capsys) -> None:
    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "0 file(s) scanned" in captured.out


def test_innocence_double_star_unpacking_is_unverifiable_not_a_violation(tmp_path, capsys) -> None:
    """A call that unpacks `**kwargs` cannot be statically proven to omit
    `init=` -- the linter must downgrade it to an UNVERIFIABLE note, not a
    hard exit-1 finding."""
    _write(
        tmp_path,
        "test_dynamic_pool.py",
        "import asyncpg\n"
        "\n"
        "\n"
        "async def pool(**kwargs):\n"
        "    p = await asyncpg.create_pool('postgresql://x', **kwargs)\n"
        "    return p\n",
    )

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert "UNVERIFIABLE" in captured.out
    assert "test_dynamic_pool.py:5:" in captured.out


# ---------------------------------------------------------------------------
# ERROR — a scan that could not read a file must never report exit 0.
# ---------------------------------------------------------------------------


def test_error_syntax_error_in_scanned_file_exits_2_not_0(tmp_path, capsys) -> None:
    _write(tmp_path, "test_broken.py", "def broken(:\n    pass\n")

    rc = lint.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 2
    assert "syntax error" in captured.err


def test_error_missing_root_exits_2_not_0(tmp_path, capsys) -> None:
    missing = tmp_path / "does-not-exist"

    rc = lint.main(["--root", str(missing)])
    captured = capsys.readouterr()

    assert rc == 2
    assert "not found" in captured.err


# ---------------------------------------------------------------------------
# LIVE TREE — regression guard for the exact scope this PR fixed.
# ---------------------------------------------------------------------------


def test_live_tree_fixed_routers_directory_is_clean(capsys) -> None:
    """`apps/backend-rag/backend/tests/routers/` is the exact directory the
    spec's Build step 5 named ("the two bare test pools") -- both
    `test_bridge_wa_media.py` and `test_intake_review.py` now import
    `create_prod_shaped_pool`. This is the regression guard: it is only
    meaningful because it is run against the REAL tree, not a synthetic one.
    """
    assert FIXED_ROUTERS_ROOT.is_dir(), f"expected directory missing: {FIXED_ROUTERS_ROOT}"

    rc = lint.main(["--root", str(FIXED_ROUTERS_ROOT)])
    captured = capsys.readouterr()

    assert rc == 0, captured.out
    assert "file(s) scanned" in captured.out
