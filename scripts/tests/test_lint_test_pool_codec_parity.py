"""Tests for scripts/lint_test_pool_codec_parity.py (L12-PR1, 2026-08-29/30).

Guilt+innocence discipline (cicatrix-superscar.md #3, "Guard-over-match"):
every accepted shape gets an INNOCENCE test proving it is NOT flagged, and
every bad shape gets a GUILT test proving it IS.

BASELINE ISOLATION (important, read before adding a test). Every test that
scans a synthetic `tmp_path` tree passes `--no-baseline`. Without it, the
DEFAULT baseline (`infra/test-pool-parity/baseline.json`, real repo-relative
paths) is loaded and compared against a synthetic scan that can never
contain those paths -- every one of the real baseline's ~25 entries would
then look "shrunk to 0" (the file exists on disk, relative to the real repo
root the test process's cwd resolves to, but the synthetic scan never
touched it) and FAIL as a stale-baseline entry. `--no-baseline` isolates
scanner-behavior tests from baseline-behavior tests; the baseline-specific
tests below build their OWN isolated baseline file instead.

Real-tree note (spec-vs-code disagreement, reported plainly, not papered
over, 2026-08-30 update): the orchestrator independently verified the real
count at 30 pre-existing bare pools; this PR's diff fixed 4 of them
(`test_bridge_wa_media.py`, `test_intake_review.py`,
`test_outbox_consumer.py`'s bare `asyncpg.connect()`, and
`test_magic_link_store_integration.py`'s two `create_pool` sites --
counting as one file), leaving 26 across 25 files in
`infra/test-pool-parity/baseline.json`. The orchestrator explicitly
rejected narrowing the scan to `tests/routers/` (hiding 26 real findings
behind a directory fence is the blanket-exemption anti-pattern
`test_jsonb_double_encoding_class_guard.py`'s own header warns against);
the shrink-only enumerated baseline is the replacement, and the spec's own
acceptance command (`--root apps/backend-rag/backend/tests`, no other
flags) now genuinely exits 0.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "lint_test_pool_codec_parity.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_PATH = REPO_ROOT / "infra" / "test-pool-parity" / "baseline.json"


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


def _write_baseline(tmp_path: Path, mapping: dict[str, int], name: str = "baseline.json") -> Path:
    payload = {
        "_meta": {
            "generated": "2026-08-30",
            "generated_by": "test fixture",
            "why": "synthetic baseline for an isolated test tree",
        },
        **mapping,
    }
    p = tmp_path / name
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# GUILT — a bare pool must exit 1 and name the exact offending line.
# (scanner behavior -- --no-baseline, isolated from the real baseline)
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "test_bad_pool_importorskip.py:7:" in captured.out


# ---------------------------------------------------------------------------
# INNOCENCE — must never be flagged.
# (scanner behavior -- --no-baseline, isolated from the real baseline)
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "violation" not in captured.out


def test_innocence_empty_tree_is_clean(tmp_path, capsys) -> None:
    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
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

    rc = lint.main(["--root", str(tmp_path), "--no-baseline"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "UNVERIFIABLE" in captured.out
    assert "test_dynamic_pool.py:5:" in captured.out


# ---------------------------------------------------------------------------
# ERROR — a scan that could not read a file must never report exit 0.
# (the error path short-circuits before baseline logic runs either way)
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
# BASELINE — the shrink-only enumerated registry (2026-08-30).
# Each test builds its OWN isolated tmp_path baseline; none touches the
# real infra/test-pool-parity/baseline.json.
# ---------------------------------------------------------------------------


def test_guilt_baselined_file_gains_one_more_pool_is_a_new_violation(tmp_path, capsys) -> None:
    """A file already tracked at count=1 that grows to 2 bare pools must
    still fail -- the baseline compares an exact COUNT, not mere presence,
    so a second bare pool sneaking into an already-known-bad file is not
    free cover."""
    bad = _write(
        tmp_path,
        "test_grows.py",
        "import asyncpg\n"
        "\n"
        "\n"
        "async def pool_one():\n"
        "    return await asyncpg.create_pool('postgresql://x')\n"
        "\n"
        "\n"
        "async def pool_two():\n"
        "    return await asyncpg.create_pool('postgresql://y')\n",
    )
    baseline_path = _write_baseline(tmp_path, {str(bad): 1})

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(baseline_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "NEW" in captured.out
    assert "test_grows.py:5:" in captured.out
    assert "test_grows.py:9:" in captured.out


def test_guilt_file_absent_from_baseline_with_a_bare_pool_fails(tmp_path, capsys) -> None:
    bad = _write(
        tmp_path,
        "test_unlisted.py",
        "import asyncpg\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    return await asyncpg.create_pool('postgresql://x')\n",
    )
    # Baseline exists and tracks an unrelated, genuinely-clean file --
    # proves the untracked file with a real finding fails on its own merit,
    # not merely because the baseline happened to be empty.
    other = _write(tmp_path, "unrelated.py", "x = 1\n")
    baseline_path = _write_baseline(tmp_path, {str(other): 0})

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(baseline_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "NEW" in captured.out
    assert "test_unlisted.py:5:" in captured.out
    assert str(bad) in captured.out


def test_guilt_baseline_names_a_file_that_no_longer_exists(tmp_path, capsys) -> None:
    """A baseline entry pointing at a file that is gone (renamed, deleted,
    or -- the intended case -- FIXED and the file removed) must fail with
    a message telling the author to remove the entry. A stale reference
    that silently passes is how this registry rots."""
    ghost = tmp_path / "ghost.py"  # deliberately never created
    baseline_path = _write_baseline(tmp_path, {str(ghost): 1})

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(baseline_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "no longer exists" in captured.out
    assert "remove this entry" in captured.out
    assert str(ghost) in captured.out


def test_guilt_baselined_file_that_shrank_must_shrink_the_baseline_too(tmp_path, capsys) -> None:
    """A file baselined at count=2 that now has only 1 bare pool (someone
    fixed one but forgot to update the baseline) must fail with the
    shrink message and print the exact replacement line -- never silently
    pass just because the file is now "better than the baseline requires"."""
    fixed = _write(
        tmp_path,
        "test_partially_fixed.py",
        "import asyncpg\n"
        "\n"
        "from backend.tests.fixtures.prod_shaped_pool import init_prod_shaped_connection\n"
        "\n"
        "\n"
        "async def pool_one():\n"
        "    return await asyncpg.create_pool('postgresql://x', init=init_prod_shaped_connection)\n"
        "\n"
        "\n"
        "async def pool_two():\n"
        "    return await asyncpg.create_pool('postgresql://y')\n",
    )
    baseline_path = _write_baseline(tmp_path, {str(fixed): 2})

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(baseline_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "STALE" in captured.out
    assert "shrink the baseline" in captured.out
    assert f'"{fixed}": 1' in captured.out


def test_innocence_baselined_file_matching_exactly_is_suppressed(tmp_path, capsys) -> None:
    bad = _write(
        tmp_path,
        "test_known_debt.py",
        "import asyncpg\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    return await asyncpg.create_pool('postgresql://x')\n",
    )
    baseline_path = _write_baseline(tmp_path, {str(bad): 1})

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(baseline_path)])
    captured = capsys.readouterr()

    assert rc == 0, captured.out
    assert "1 suppressed by baseline" in captured.out
    assert "0 new" in captured.out


def test_error_explicit_baseline_path_missing_exits_2(tmp_path, capsys) -> None:
    missing_baseline = tmp_path / "no-such-baseline.json"

    rc = lint.main(["--root", str(tmp_path), "--baseline", str(missing_baseline)])
    captured = capsys.readouterr()

    assert rc == 2
    assert "baseline file not found" in captured.err


def test_write_baseline_generates_a_file_the_check_mode_then_accepts(tmp_path, capsys) -> None:
    """`--write-baseline` is the only sanctioned way to produce/regenerate
    the registry -- proves the round trip: generate from a raw scan, then
    immediately check against what was just written, and it must be clean."""
    _write(
        tmp_path,
        "test_needs_baseline.py",
        "import asyncpg\n"
        "\n"
        "\n"
        "async def pool():\n"
        "    return await asyncpg.create_pool('postgresql://x')\n",
    )
    generated_path = tmp_path / "generated-baseline.json"

    rc_write = lint.main(["--root", str(tmp_path), "--write-baseline", str(generated_path)])
    write_out = capsys.readouterr().out
    assert rc_write == 0
    assert generated_path.is_file()
    assert "wrote baseline with 1 file(s)" in write_out

    rc_check = lint.main(["--root", str(tmp_path), "--baseline", str(generated_path)])
    check_out = capsys.readouterr().out
    assert rc_check == 0, check_out
    assert "1 suppressed by baseline" in check_out


# ---------------------------------------------------------------------------
# LIVE TREE — the spec's own acceptance command, verbatim.
# ---------------------------------------------------------------------------


def test_live_tree_default_baseline_honors_the_acceptance_command(capsys) -> None:
    """`python scripts/lint_test_pool_codec_parity.py --root
    apps/backend-rag/backend/tests` -- no other flags -- is the literal
    acceptance command. With the shrink-only baseline wired in by DEFAULT
    it must exit 0 today, honestly: this scans the WHOLE real tree (not a
    directory narrowed to hide the 26 pre-existing findings, which the
    orchestrator explicitly rejected as the blanket-exemption anti-pattern).

    `--root` MUST be the literal relative string, matching how this tool is
    always actually invoked (from the repo root) -- the baseline's keys are
    repo-relative path strings, and an absolute `--root` would make every
    discovered path's string form absolute too, so it would never match a
    single baseline entry (see module docstring on both files).
    """
    real_root = "apps/backend-rag/backend/tests"
    assert (REPO_ROOT / real_root).is_dir(), (
        f"this test assumes cwd == repo root (found {Path.cwd()}); "
        f"expected directory missing at {REPO_ROOT / real_root}"
    )
    assert DEFAULT_BASELINE_PATH.is_file(), f"expected baseline missing: {DEFAULT_BASELINE_PATH}"

    rc = lint.main(["--root", real_root])
    captured = capsys.readouterr()

    assert rc == 0, captured.out
    assert "suppressed by baseline" in captured.out
    assert "0 new" in captured.out


def test_live_tree_no_baseline_reveals_exactly_what_baseline_suppresses(capsys) -> None:
    """Proves the baseline is SUPPRESSING pre-existing findings, not that
    they vanished: the count `--no-baseline` reports as raw violations must
    equal exactly the count the default run reports as suppressed. Not
    hardcoded to today's number (26) on purpose -- the baseline is
    shrink-only and this cross-check stays true at any point along that
    shrink, as long as the two runs are consistent with each other."""
    real_root = "apps/backend-rag/backend/tests"

    rc_default = lint.main(["--root", real_root])
    default_out = capsys.readouterr().out
    assert rc_default == 0, default_out

    rc_raw = lint.main(["--root", real_root, "--no-baseline"])
    raw_out = capsys.readouterr().out
    assert rc_raw == 1, raw_out

    suppressed_match = re.search(r"(\d+) suppressed by baseline", default_out)
    assert suppressed_match, default_out
    suppressed = int(suppressed_match.group(1))
    assert suppressed > 0, "baseline should be suppressing real pre-existing debt"

    raw_match = re.search(r"(\d+) violation\(s\) found", raw_out)
    assert raw_match, raw_out
    raw_violations = int(raw_match.group(1))

    assert raw_violations == suppressed, (
        f"--no-baseline found {raw_violations} but the default run only "
        f"suppressed {suppressed} -- the baseline is not suppressing "
        "cleanly (some finding is neither tracked nor freshly reported, or "
        "double-counted)"
    )
