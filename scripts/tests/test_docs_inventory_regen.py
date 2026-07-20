"""Tests for scripts/docs_inventory_regen.sh — the SSOT wrapper the
docs-inventory-refresh.yml organ calls (BLOCKER-3, red-team 2026-07-18).

The REAL wrapper script is copied verbatim into a fake repo alongside STUB
scripts/docs_sync.py and scripts/docs_audit.py (both real, controllable
Python scripts, not mocks) — since docs_inventory_regen.sh computes its own
SCRIPT_DIR from `${BASH_SOURCE[0]}` and invokes `python3 scripts/<tool>.py`
relative to that, a copy in a fresh directory naturally picks up the stubs
placed alongside it. This exercises the REAL bash control-flow (the
exit-code distinguishing logic), not a hand-copied duplicate of it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_REGEN_SH = REPO_ROOT / "scripts" / "docs_inventory_regen.sh"

_STUB_SYNC_OK = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
_STUB_AUDIT_OK = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"


def _make_fake_repo(tmp_path: Path, *, sync_exit: str, audit_exit: str) -> Path:
    """`sync_exit`/`audit_exit` are full Python script bodies (not just exit
    codes) so a test can also emit stderr text or simulate a real traceback,
    not only `sys.exit(N)`.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(REAL_REGEN_SH, scripts_dir / "docs_inventory_regen.sh")
    (scripts_dir / "docs_sync.py").write_text(sync_exit, encoding="utf-8")
    (scripts_dir / "docs_audit.py").write_text(audit_exit, encoding="utf-8")
    return tmp_path


def _run_regen(
    fake_repo: Path, env: dict | None = None, *args: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(fake_repo / "scripts" / "docs_inventory_regen.sh"), *args],
        cwd=fake_repo,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_clean_run_both_tools_exit_0(tmp_path):
    """INNOCENCE baseline: both tools succeed cleanly -> wrapper exits 0."""
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_OK
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_audit_expected_drift_exit_1_is_swallowed(tmp_path):
    """INNOCENCE: docs_audit.py returning 1 ('content changed', intentional
    per its own documented contract) must NOT fail the wrapper — that is the
    pre-existing, correct behavior BLOCKER-3 must not regress.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit="#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n",
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, (
        f"expected drift (exit 1) must be swallowed: {result.stdout}{result.stderr}"
    )


def test_docs_audit_crash_exit_2_propagates(tmp_path):
    """GUILT (red-team 2026-07-18 BLOCKER-3): docs_audit.py CRASHING (its own
    dedicated exit 2, P3-prime __main__ crash boundary) must FAIL this
    wrapper for real — the old `|| true` swallowed 1 and 2 identically,
    making a genuine crash silently indistinguishable from 'nothing
    changed' on an apparently-green run.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('docs_audit: CRASHED — RuntimeError: synthetic', file=sys.stderr)\n"
            "sys.exit(2)\n"
        ),
    )
    result = _run_regen(fake_repo)
    assert result.returncode != 0, (
        f"a docs_audit.py crash (exit 2) must fail the wrapper, not be "
        f"silently absorbed: got exit {result.returncode}"
    )
    assert "CRASHED" in (result.stdout + result.stderr) or result.returncode == 2


def test_docs_sync_crash_propagates(tmp_path):
    """GUILT: docs_sync.py (write mode, no --check/--diff) legitimately
    ALWAYS returns 0 — the ONLY way it returns non-zero here is a genuine
    crash. That must fail the wrapper too, not be swallowed by a blanket
    `|| true` (the old behavior).
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('boom', file=sys.stderr)\n"
            "sys.exit(1)\n"
        ),
        audit_exit=_STUB_AUDIT_OK,
    )
    result = _run_regen(fake_repo)
    assert result.returncode != 0, (
        "a docs_sync.py crash must fail the wrapper, not be silently absorbed"
    )
    # And the wrapper must not even attempt the docs_audit.py step afterward
    # (fail fast, don't paper over one crash by racing ahead to the next tool).
    assert "regenerating docs/DOCS_INVENTORY.md" not in result.stderr


def test_docs_audit_stats_json_path_still_used_on_clean_run(tmp_path):
    """Sanity: the DOCS_AUDIT_STATS_JSON capture path (added earlier the same
    day for the flip-count surfacing feature) still works after the
    BLOCKER-3 exit-code rework — not a red-team-mandated test, but cheap
    insurance against a regression in an adjacent code path this same PR
    touches.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('{\"flips_this_run\": 0}')\n"
            "sys.exit(0)\n"
        ),
    )
    stats_path = tmp_path / "stats.json"
    import os

    env = {**os.environ, "DOCS_AUDIT_STATS_JSON": str(stats_path)}
    result = _run_regen(fake_repo, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert stats_path.exists()
    assert '"flips_this_run": 0' in stats_path.read_text()


# ============================================================================
# Footgun fix (2026-07-19, PR #2626 landing incident): the wrapper's default
# invocation used to pass docs_audit.py no time-mode flag at all, which
# silently meant "real today" inside docs_audit.py itself (see
# test_docs_audit.py's own guilt/innocence pair for that half). The fix has
# a WRAPPER-side half too: the default must thread --gate-consistent, and
# only an explicit --organ argument may thread --as-of <today> instead. The
# stub below captures its own argv so these tests verify the WRAPPER's
# arg-passing plumbing specifically — a bug here (e.g. --organ silently
# swallowed, or the wrong flag threaded) would not be caught by
# test_docs_audit.py's tests, which invoke docs_audit.py directly and never
# exercise this wrapper's own argument-forwarding logic at all.
# ============================================================================

_STUB_AUDIT_CAPTURE_ARGV = (
    "#!/usr/bin/env python3\n"
    "import sys, pathlib\n"
    "pathlib.Path(__file__).parent.joinpath('captured_argv.txt').write_text(\n"
    "    '\\n'.join(sys.argv[1:])\n"
    ")\n"
    "sys.exit(0)\n"
)


def test_default_invocation_passes_gate_consistent_not_as_of(tmp_path):
    """INNOCENCE (wrapper plumbing): with no arguments, the wrapper must pass
    --gate-consistent to docs_audit.py and must NOT pass --as-of — the
    PR-side/contributor-safe default.
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, result.stdout + result.stderr
    captured = (fake_repo / "scripts" / "captured_argv.txt").read_text()
    assert "--gate-consistent" in captured.split("\n"), captured
    assert "--as-of" not in captured, captured


def test_organ_flag_passes_as_of_today_not_gate_consistent(tmp_path):
    """GUILT/mechanism (wrapper plumbing): with --organ, the wrapper must
    pass --as-of <today, YYYY-MM-DD> to docs_audit.py and must NOT pass
    --gate-consistent — the scheduled refresh organ's dated/wall-clock mode,
    now requiring this explicit opt-in instead of being the silent default.
    """
    import datetime

    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo, None, "--organ")
    assert result.returncode == 0, result.stdout + result.stderr
    captured = (fake_repo / "scripts" / "captured_argv.txt").read_text().split("\n")
    assert "--gate-consistent" not in captured, captured
    assert "--as-of" in captured, captured
    as_of_value = captured[captured.index("--as-of") + 1]
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    assert as_of_value == today, (as_of_value, today)


# ============================================================================
# Strict arg validation (R1 red-team, PR #2863, 2026-07-20): the FIRST
# version of the wrapper's arg parsing only ever inspected `${1:-}` — any
# OTHER argument (an unknown flag, `--organ` misplaced as $2, a typo) fell
# through to ORGAN_MODE=false SILENTLY, meaning a misconfigured caller got
# gate-consistent mode instead of organ mode (or vice versa) with zero
# error signal — the exact "footgun via silent default" class this whole
# script exists to cure, one layer up at the CLI-parsing level. These tests
# prove the fix: anything other than zero args or exactly one `--organ` is
# now a hard, explicit exit-2 usage error, and MUST NOT reach the point of
# invoking docs_audit.py at all (no captured_argv.txt is even written).
# ============================================================================


def test_unknown_single_arg_is_rejected_not_silently_gate_consistent(tmp_path):
    """GUILT: a single unrecognized argument (e.g. a typo, or an unrelated
    flag like --quiet) must be a hard usage error, not a silent fall-through
    to gate-consistent mode.
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo, None, "--quiet")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "unknown argument" in result.stderr, result.stderr
    assert not (fake_repo / "scripts" / "captured_argv.txt").exists(), (
        "docs_audit.py must never be invoked when arg parsing fails"
    )


def test_organ_as_second_arg_is_rejected_not_silently_ignored(tmp_path):
    """GUILT: `--organ` passed as a SECOND argument (with something else as
    $1) must be a hard usage error, not silently treated as "no args" (the
    original bug: only `${1:-}` was ever inspected, so `script foo --organ`
    would silently run gate-consistent mode with --organ completely
    ignored).
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo, None, "foo", "--organ")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "too many arguments" in result.stderr, result.stderr
    assert not (fake_repo / "scripts" / "captured_argv.txt").exists()


def test_organ_plus_extra_arg_is_rejected(tmp_path):
    """GUILT: `--organ` followed by anything else (`script --organ typo`)
    must also be rejected — the fix is not just "check $1", it validates
    the COMPLETE argument list.
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo, None, "--organ", "typo")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "too many arguments" in result.stderr, result.stderr
    assert not (fake_repo / "scripts" / "captured_argv.txt").exists()


def test_no_args_still_works_after_strict_validation(tmp_path):
    """INNOCENCE: the strict validation must not break the ordinary
    zero-args call — still gate-consistent, still exit 0.
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, result.stdout + result.stderr
    captured = (fake_repo / "scripts" / "captured_argv.txt").read_text()
    assert "--gate-consistent" in captured.split("\n"), captured


def test_organ_alone_still_works_after_strict_validation(tmp_path):
    """INNOCENCE: the strict validation must not break the ordinary
    single `--organ` call — still dated/as-of mode, still exit 0.
    """
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_CAPTURE_ARGV
    )
    result = _run_regen(fake_repo, None, "--organ")
    assert result.returncode == 0, result.stdout + result.stderr
    captured = (fake_repo / "scripts" / "captured_argv.txt").read_text()
    assert "--as-of" in captured.split("\n"), captured
