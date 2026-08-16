#!/usr/bin/env python3
"""Guilt + innocence corpus for `test_cost_gate.py` (cicatrix-superscar.md #3:
no guard merges without both proofs, plus mutation-guard cases pinning the
exact comparison operators — `>` not `>=`, `and` not `or` — that a plausible
one-character bug in this file would flip).

Runs standalone (`python3 scripts/ci/test_test_cost_gate.py`) and under pytest.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_cost_gate import (  # noqa: E402
    DEFAULT_ABS_FLOOR_MINUTES,
    DEFAULT_REGRESSION_THRESHOLD_PCT,
    decide,
    evaluate_regression,
    load_baseline,
    touches_test_infra,
)

GATE_SCRIPT = Path(__file__).resolve().parent / "test_cost_gate.py"


def _baseline_file(jobs: dict) -> str:
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"jobs": jobs}, fh)
    fh.close()
    return fh.name


def run_cli(argv: list[str]) -> tuple[int, dict]:
    # `input=""` closes stdin immediately (EOF) — without it, a subprocess
    # inheriting an open (non-tty, non-empty) parent stdin would block
    # forever on main()'s `sys.stdin.read()` fallback when the test passes
    # neither positional changed_files nor --changed-files-file. Verified
    # live: this exact call hung the first version of this corpus.
    proc = _run_cli_raw(argv)
    payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    assert proc.returncode == (1 if payload.get("blocking") else 0), (
        f"exit code {proc.returncode} does not match verdict.blocking={payload.get('blocking')}: "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    return proc.returncode, payload


def _run_cli_raw(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Same subprocess invocation as run_cli(), minus the payload/exit-code
    assertion — for tests that need the raw stderr (e.g. asserting no
    traceback) without run_cli()'s own assertion getting in the way. Keeps
    run_cli()'s contract untouched for its other callers."""
    return subprocess.run(
        [sys.executable, str(GATE_SCRIPT), *argv],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
    )


# =============================================================================
# touches_test_infra() — guilt + innocence
# =============================================================================


def test_a_guilt_conftest_edit_is_test_infra():
    assert touches_test_infra(["apps/backend-rag/backend/tests/unit/conftest.py"]) is True


def test_a_guilt_pytest_ini_edit_is_test_infra():
    assert touches_test_infra(["apps/backend-rag/pytest.ini"]) is True


def test_a_guilt_tests_workflow_edit_is_test_infra():
    assert touches_test_infra([".github/workflows/tests.yml"]) is True


def test_a_guilt_fixtures_dir_inside_a_tests_tree_is_test_infra():
    assert (
        touches_test_infra(["apps/backend-rag/backend/tests/services/fixtures/sample_akta.json"])
        is True
    )


def test_a_guilt_the_gate_editing_itself_is_test_infra():
    """Anti-self-approval (same shape as change_map.py's EXACT_RULES entry
    for its own file): a PR that loosens this gate must not be able to slip
    through as telemetry-only because it 'only touched the gate'."""
    assert touches_test_infra(["scripts/ci/test_cost_gate.py"]) is True
    assert touches_test_infra(["scripts/ci/test_cost_baseline.json"]) is True


def test_a_guilt_one_test_infra_path_among_many_still_counts():
    assert (
        touches_test_infra(
            [
                "apps/backend-rag/backend/app/routers/crm.py",
                "apps/backend-rag/backend/tests/unit/conftest.py",
            ]
        )
        is True
    )


def test_b_innocence_an_ordinary_backend_file_is_not_test_infra():
    assert touches_test_infra(["apps/backend-rag/backend/app/routers/crm.py"]) is False


def test_b_innocence_a_brand_new_test_file_is_not_test_infra():
    """Adding a slow test is exactly the case contract point 2 says must
    stay telemetry-only, never blocking — this is the guard's core innocence
    case, not an edge case."""
    assert (
        touches_test_infra(["apps/backend-rag/backend/tests/services/test_new_feature.py"])
        is False
    )


def test_b_innocence_a_product_directory_literally_named_fixtures_is_not_test_infra():
    """A 'fixtures' directory OUTSIDE any tests/ tree (e.g. business seed
    data) must not trip the guard — co-occurrence with a 'tests' path
    segment is required, not the bare word 'fixtures'."""
    assert touches_test_infra(["apps/backend-rag/backend/data/fixtures/seed.json"]) is False


def test_b_innocence_empty_changed_set_is_not_test_infra():
    assert touches_test_infra([]) is False


def test_b_innocence_malformed_path_is_ignored_not_test_infra():
    assert touches_test_infra(["../../etc/passwd"]) is False


# =============================================================================
# evaluate_regression() — guilt + innocence + mutation-guard
# =============================================================================


def test_a_guilt_regression_over_threshold_and_floor_is_detected():
    r = evaluate_regression(measured_minutes=30.0, baseline_p50_minutes=26.5)
    assert r["baseline_available"] is True
    assert r["regression_detected"] is True
    assert round(r["delta_pct"], 2) == round((30.0 - 26.5) / 26.5 * 100, 2)


def test_b_innocence_small_increase_under_threshold_is_not_a_regression():
    # +5% is under the 10% default threshold.
    r = evaluate_regression(measured_minutes=27.8, baseline_p50_minutes=26.5)
    assert r["regression_detected"] is False


def test_b_innocence_no_baseline_is_never_a_regression():
    r = evaluate_regression(measured_minutes=999.0, baseline_p50_minutes=None)
    assert r["baseline_available"] is False
    assert r["regression_detected"] is False


def test_b_innocence_faster_than_baseline_is_not_a_regression():
    r = evaluate_regression(measured_minutes=10.0, baseline_p50_minutes=26.5)
    assert r["regression_detected"] is False
    assert r["delta_minutes"] < 0


def test_mutation_guard_exact_threshold_boundary_does_not_block():
    """Pins `>` not `>=` on the PERCENT comparison (suite_growth_probe.py
    convention, same comparison shape as its own `trend_delta_pct >
    WEEKLY_GROWTH_PCT_THRESHOLD`): a delta landing EXACTLY on the percent
    threshold must not block. baseline=30.0 makes the abs delta at +10%
    equal 3.0min — safely OVER the 2.0min floor — so this case isolates the
    percent boundary alone; the boundary case in the abs-floor mutation
    guard below is intentionally the mirror of this one, but at the floor
    boundary instead."""
    baseline = 30.0
    measured = baseline * 1.10  # exactly +10.0%, delta=3.0min (over the 2.0min floor)
    r = evaluate_regression(measured_minutes=measured, baseline_p50_minutes=baseline)
    assert round(r["delta_pct"], 6) == 10.0
    assert r["delta_minutes"] > DEFAULT_ABS_FLOOR_MINUTES
    assert r["regression_detected"] is False, (
        "a delta exactly AT the percent threshold must not block — mutating `>` to "
        "`>=` on the percent comparison in evaluate_regression would flip this to True"
    )


def test_mutation_guard_exact_abs_floor_boundary_does_not_block():
    """Mirror of the percent-boundary case above: the abs delta lands
    EXACTLY on the 2.0min floor while the percent is safely over its own
    threshold — isolates `>` not `>=` on the ABS-FLOOR comparison."""
    baseline = 20.0
    measured = baseline + DEFAULT_ABS_FLOOR_MINUTES  # +2.0min exactly, +10.0% exactly too
    # Use a baseline where the percent clears its threshold with margin so
    # only the abs-floor boundary is under test: baseline=100 -> +2.0min is +2%,
    # well under the 10% threshold, so pct_exceeded is unambiguously False —
    # not what we want either. Pick baseline=15.0: +2.0min = +13.3%, over the
    # 10% threshold with margin, while the abs delta sits exactly at the floor.
    baseline = 15.0
    measured = baseline + DEFAULT_ABS_FLOOR_MINUTES
    r = evaluate_regression(measured_minutes=measured, baseline_p50_minutes=baseline)
    assert r["delta_minutes"] == DEFAULT_ABS_FLOOR_MINUTES
    assert r["delta_pct"] > DEFAULT_REGRESSION_THRESHOLD_PCT
    assert r["regression_detected"] is False, (
        "a delta exactly AT the abs floor must not block — mutating `>` to `>=` "
        "on the abs-floor comparison in evaluate_regression would flip this to True"
    )


def test_mutation_guard_just_over_threshold_and_floor_blocks():
    baseline = 20.0
    measured = 20.0 + 2.01  # +10.05% and +2.01min — both just over their lines
    r = evaluate_regression(measured_minutes=measured, baseline_p50_minutes=baseline)
    assert r["regression_detected"] is True


def test_mutation_guard_zero_baseline_never_divides_by_zero():
    """Pins the `baseline_p50_minutes > 0` guard: this repo's own committed
    baseline has change-map at p50_minutes=0.0 (test_cost_baseline.json) —
    a caller must never crash on it."""
    r = evaluate_regression(measured_minutes=0.05, baseline_p50_minutes=0.0)
    assert r["baseline_available"] is True
    assert r["delta_pct"] is None
    assert r["regression_detected"] is False, "0.05min over a zero baseline is under the abs floor"


def test_mutation_guard_zero_baseline_with_real_increase_still_needs_the_floor():
    r = evaluate_regression(measured_minutes=3.0, baseline_p50_minutes=0.0)
    assert r["regression_detected"] is True, "3.0min over a zero baseline clears the 2.0min floor"


def test_mutation_guard_percent_alone_without_abs_floor_does_not_block():
    """A near-zero baseline job growing to 1.5min (still under the abs
    floor) must not block even though the PERCENT increase is enormous —
    pins the `and` (both conditions required), not `or`, in
    evaluate_regression."""
    r = evaluate_regression(measured_minutes=1.5, baseline_p50_minutes=0.5)
    # +200% pct, but only +1.0min absolute — under the 2.0min floor.
    assert r["delta_pct"] == 200.0
    assert r["regression_detected"] is False, (
        "mutating `pct_exceeded and abs_exceeded` to `or` in evaluate_regression "
        "would flip this to True"
    )


def test_mutation_guard_abs_floor_alone_without_percent_does_not_block():
    """A huge baseline job growing by a large absolute amount but a small
    percent must not block either — the other half of the `and` pin."""
    r = evaluate_regression(measured_minutes=105.0, baseline_p50_minutes=100.0)
    # +5min absolute (over the 2.0min floor) but only +5% (under the 10% threshold).
    assert r["delta_minutes"] == 5.0
    assert r["regression_detected"] is False


# =============================================================================
# decide() — guilt + innocence
# =============================================================================


def test_a_guilt_regression_plus_test_infra_touch_blocks():
    r = evaluate_regression(measured_minutes=30.0, baseline_p50_minutes=26.5)
    v = decide(is_test_infra_touch=True, regression=r)
    assert v == {"verdict": "regression_blocking", "blocking": True}


def test_b_innocence_regression_without_test_infra_touch_is_telemetry_only():
    """Contract point 2's core case: same regression magnitude as the guilt
    case above, but the PR never touched test-infra — must NEVER block."""
    r = evaluate_regression(measured_minutes=30.0, baseline_p50_minutes=26.5)
    v = decide(is_test_infra_touch=False, regression=r)
    assert v == {"verdict": "regression_telemetry_only", "blocking": False}


def test_b_innocence_test_infra_touch_without_regression_is_clean():
    r = evaluate_regression(measured_minutes=26.6, baseline_p50_minutes=26.5)
    v = decide(is_test_infra_touch=True, regression=r)
    assert v == {"verdict": "clean", "blocking": False}


def test_b_innocence_missing_baseline_never_blocks_even_with_test_infra_touch():
    r = evaluate_regression(measured_minutes=999.0, baseline_p50_minutes=None)
    v = decide(is_test_infra_touch=True, regression=r)
    assert v == {"verdict": "cannot_verify", "blocking": False}


# =============================================================================
# load_baseline() — I/O edges
# =============================================================================


def test_load_baseline_missing_file_returns_empty_map_and_error():
    jobs, err = load_baseline(Path("/nonexistent/does-not-exist.json"))
    assert jobs == {}
    assert err is not None


def test_load_baseline_valid_file_returns_jobs_map():
    path = Path(_baseline_file({"backend-tests": {"p50_minutes": 26.5}}))
    jobs, err = load_baseline(path)
    assert err is None
    assert jobs["backend-tests"]["p50_minutes"] == 26.5


def test_load_baseline_shapeless_file_is_cannot_verify_not_crash():
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    fh.write("{}")
    fh.close()
    jobs, err = load_baseline(Path(fh.name))
    assert jobs == {}
    assert err is not None


# =============================================================================
# CLI (main()) — end-to-end, exit codes
# =============================================================================


def test_cli_guilt_blocks_on_regression_with_test_infra_touch():
    baseline_path = _baseline_file({"backend-tests": {"p50_minutes": 26.5}})
    rc, payload = run_cli(
        [
            "--baseline",
            baseline_path,
            "--job",
            "backend-tests",
            "--duration-minutes",
            "31.0",
            "apps/backend-rag/backend/tests/unit/conftest.py",
        ]
    )
    assert rc == 1
    assert payload["blocking"] is True
    assert payload["verdict"] == "regression_blocking"


def test_cli_innocence_same_regression_without_test_infra_touch_exits_zero():
    baseline_path = _baseline_file({"backend-tests": {"p50_minutes": 26.5}})
    rc, payload = run_cli(
        [
            "--baseline",
            baseline_path,
            "--job",
            "backend-tests",
            "--duration-minutes",
            "31.0",
            "apps/backend-rag/backend/app/routers/crm.py",
        ]
    )
    assert rc == 0
    assert payload["blocking"] is False
    assert payload["verdict"] == "regression_telemetry_only"


def test_cli_innocence_unknown_job_is_cannot_verify_exits_zero():
    baseline_path = _baseline_file({"backend-tests": {"p50_minutes": 26.5}})
    rc, payload = run_cli(
        [
            "--baseline",
            baseline_path,
            "--job",
            "some-new-job-not-in-baseline",
            "--duration-minutes",
            "999.0",
            "apps/backend-rag/backend/tests/unit/conftest.py",
        ]
    )
    assert rc == 0
    assert payload["verdict"] == "cannot_verify"


def test_cli_innocence_no_changed_files_argument_is_not_test_infra():
    baseline_path = _baseline_file({"backend-tests": {"p50_minutes": 26.5}})
    rc, payload = run_cli(
        [
            "--baseline",
            baseline_path,
            "--job",
            "backend-tests",
            "--duration-minutes",
            "27.0",
        ]
    )
    assert rc == 0
    assert payload["is_test_infra_touch"] is False


def test_cli_guilt_zero_baseline_regression_with_test_infra_touch_blocks_without_crashing():
    """Pins the exact live crash this fix addresses: `change-map` in the real
    committed baseline has p50_minutes=0.0, so evaluate_regression() sets
    delta_pct=None (no percent is defined off a zero baseline) — main()'s
    BLOCKING f-string used to format that None with `:.1f` unconditionally
    and raise TypeError. Must exit 1 (blocking) with zero traceback."""
    baseline_path = _baseline_file({"change-map": {"p50_minutes": 0.0}})
    proc = _run_cli_raw(
        [
            "--baseline",
            baseline_path,
            "--job",
            "change-map",
            "--duration-minutes",
            "3.0",
            "apps/backend-rag/backend/tests/unit/conftest.py",
        ]
    )
    assert "Traceback" not in proc.stderr, f"crashed: stderr={proc.stderr!r}"
    assert proc.returncode == 1, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["blocking"] is True
    assert payload["verdict"] == "regression_blocking"
    assert payload["regression"]["delta_pct"] is None
    assert payload["regression"]["delta_minutes"] == 3.0


def test_cli_innocence_zero_baseline_regression_without_test_infra_touch_exits_zero_without_crashing():
    """Same zero-baseline regression as the guilt case above, but the changed
    file never touches test-infra — must degrade to telemetry-only (exit 0)
    without crashing, same fix, the NOTICE f-string side of main()."""
    baseline_path = _baseline_file({"change-map": {"p50_minutes": 0.0}})
    proc = _run_cli_raw(
        [
            "--baseline",
            baseline_path,
            "--job",
            "change-map",
            "--duration-minutes",
            "3.0",
            "apps/backend-rag/backend/app/routers/crm.py",
        ]
    )
    assert "Traceback" not in proc.stderr, f"crashed: stderr={proc.stderr!r}"
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["blocking"] is False
    assert payload["verdict"] == "regression_telemetry_only"
    assert payload["regression"]["delta_pct"] is None


def test_cli_uses_the_real_committed_baseline_by_default():
    """The default --baseline path resolves to the actual committed
    test_cost_baseline.json shipped in this PR — this test would fail if
    that file went missing or lost the backend-tests key."""
    rc, payload = run_cli(
        [
            "--job",
            "backend-tests",
            "--duration-minutes",
            "1.0",
        ]
    )
    assert rc == 0
    assert payload["regression"]["baseline_available"] is True
    assert payload["regression"]["baseline_p50_minutes"] == 26.5


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
