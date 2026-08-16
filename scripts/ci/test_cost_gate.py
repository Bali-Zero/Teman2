#!/usr/bin/env python3
"""test_cost_gate.py — block only the test-cost REGRESSION a PR introduces.

Spec: research/operations/2026-08-14-merge-os-v3-research-council.md §C1/§6
step 3 ("test-cost regression gate that blocks only the regression a PR
introduces (hard on PRs touching test infra/fixtures/timeouts, telemetry-only
elsewhere)"). This is a slice of that step, same family as
`scripts/suite_growth_probe.py` (the nightly telemetry organ this gate reads
its baseline from) — that organ measures the TREND across the whole suite over
time; this gate judges ONE PR's ONE job run against a committed reference.

WHAT THIS DOES NOT DO (scope, matching the mandate that dispatched this build):
  - It never calls Pro live from CI — CI cannot see Pro (council contract point
    3). The comparison baseline is `scripts/ci/test_cost_baseline.json`, a
    committed snapshot of one `suite_growth_probe.py` record. Refreshing that
    snapshot is a manual, periodic, out-of-band step (see that file's `_doc`).
  - It never selects, skips, or deletes a test. It answers exactly one
    question: "is THIS job's measured duration on THIS PR run enough worse
    than the committed baseline, on a PR that touched the surface where a
    regression like that could be introduced on purpose or by accident, to
    block?" Anything else (suite diet, ownership SLA) is a separate artifact
    (research/operations/2026-08-15-suite-diet-round1.md).
  - It is NOT wired into tests.yml yet (built != armed, scar family #2 —
    declared, not hidden). Wiring a step to measure "this run's actual job
    duration" and feed it to `--duration-minutes` is the next PR. This module
    is complete and independently testable without that wiring: every
    guilt/innocence case below drives it exactly the way a wired caller would
    (synthetic `--duration-minutes` + a synthetic changed-file list), so the
    logic is proven before a single CI minute is spent running it live.

CONTRACT (research council §6 step 3, all four points):
  1. HARD (blocking) only on a PR that touches test-infra: conftest.py,
     pytest.ini/tox.ini, fixtures/ under a tests/ tree, .github/workflows/
     tests.yml itself, or this gate's own files (self-reference, same
     anti-self-approval shape as scripts/ci/change_map.py's EXACT_RULES entry
     for itself — a PR that edits the gate must not be able to loosen the gate
     and pass its own loosened check unexamined).
  2. Telemetry-only (a notice, never a non-zero exit) on every other PR —
     including one that DOES regress a job's duration, as long as it did not
     touch test-infra. Ordinary feature PRs that happen to add slow tests are
     not blocked by this gate; that is the suite-diet report's job, not this
     one's (§6 step 3's own scope line: "NO auto-deletion on slowness/flake
     alone").
  3. Comparison = this run's measured duration for ONE job vs the COMMITTED
     baseline's p50 for that job (never p95 — p95 already answers a different
     question, "how close to the timeout ceiling", which is
     `suite_growth_probe.py`'s job, not this gate's; p50 is the stable center
     a single run's regression should be measured against).
  4. Threshold: declared here, not implicit. `DEFAULT_REGRESSION_THRESHOLD_PCT
     = 10.0` — the council doc's own worked example ("+10% sul job toccato").
     A percent alone cannot judge jobs whose baseline p50 is near zero (this
     repo's own committed baseline has `change-map` at `p50_minutes: 0.0` —
     see test_cost_baseline.json) — ANY absolute increase above that baseline
     would read as an "infinite" or triple-digit percent regression, which is
     noise, not signal. `DEFAULT_ABS_FLOOR_MINUTES = 2.0` requires the
     absolute delta to also clear a real floor before either threshold counts
     as a regression — chosen as roughly the smallest delta this repo's own
     suite-growth telemetry (P95_TIMEOUT_PCT/WEEKLY_GROWTH_PCT thresholds in
     suite_growth_probe.py) treats as a signal rather than run-to-run jitter
     on a shared GitHub Actions runner.

MISSING DATA IS NEVER A BLOCK (scar family #9 "il proxy mente" / #2 "esiste
!= armato" both apply here in mirror form): a job absent from the committed
baseline, or a caller that never supplies `--duration-minutes`, degrades to
verdict `cannot_verify` — exit 0, always, regardless of what the PR touched.
Blocking on data this gate does not actually have would itself be the guard
misbehaving on absence rather than on evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# --- declared thresholds (contract point 4) ---------------------------------

DEFAULT_REGRESSION_THRESHOLD_PCT = 10.0
DEFAULT_ABS_FLOOR_MINUTES = 2.0

DEFAULT_BASELINE_PATH = Path(__file__).resolve().parent / "test_cost_baseline.json"

# --- test-infra classification (contract point 1) ---------------------------
#
# Deliberately narrow (scar family #3 — over-match traps): this is NOT "any
# file under tests/", which would hard-block every ordinary PR that adds a
# test (exactly the outcome contract point 2 forbids). It is the specific,
# structural surface where a change can silently inflate or hide suite cost:
# the fixture/config machinery tests run UNDER, not the tests themselves.

TEST_INFRA_EXACT = frozenset(
    {
        ".github/workflows/tests.yml",
        "scripts/ci/test_cost_gate.py",
        "scripts/ci/test_test_cost_gate.py",
        "scripts/ci/test_cost_baseline.json",
        "scripts/suite_growth_probe.py",
        "apps/backend-rag/pytest.ini",
    }
)

TEST_INFRA_BASENAMES = frozenset({"conftest.py", "pytest.ini", "tox.ini"})


def _normalize(raw: str) -> str | None:
    """Repo-relative POSIX path, or None for malformed input.

    Deliberately the same shape as scripts/ci/change_map.py's own
    `_normalize` (duplicated, not imported — scripts/ is a flat bag of
    standalone tools per that module's and suite_growth_probe.py's own
    declared convention).
    """
    if raw != raw.strip():
        return None
    path = raw
    while path.startswith("./"):
        path = path[2:]
    if not path or "\x00" in path or "\n" in path or "\r" in path:
        return None
    if path.startswith("/") or any(part == ".." for part in path.split("/")):
        return None
    return path


def _is_test_infra_path(path: str) -> bool:
    """Guilt case: conftest.py / pytest.ini / tests.yml / this gate's own
    files / a fixtures/ dir inside a tests/ tree. Innocence case: an ordinary
    product file, or a new `test_*.py` file that is not itself fixture/config
    machinery — see test_test_cost_gate.py for both, guilt AND innocence,
    registered per infra/guard-conformance/registry.json's own convention
    (cicatrix-superscar.md #3: no guard merges without both proofs)."""
    if path in TEST_INFRA_EXACT:
        return True
    basename = path.rsplit("/", 1)[-1]
    if basename in TEST_INFRA_BASENAMES:
        return True
    # "fixtures" must sit INSIDE a "tests" tree — a product directory that
    # happens to be named fixtures/ (e.g. business seed data, unrelated to
    # the test suite) must not trip this guard. Scoping to co-occurrence with
    # a "tests" path segment is the innocence half of this exact rule.
    parts = path.split("/")
    if "fixtures" in parts and "tests" in parts:
        return True
    return False


def touches_test_infra(paths: list[str]) -> bool:
    """True when ANY normalized path in `paths` is test-infra (contract point 1)."""
    for raw in paths:
        path = _normalize(raw)
        if path is not None and _is_test_infra_path(path):
            return True
    return False


# --- regression math (contract points 3 and 4) -------------------------------


def evaluate_regression(
    measured_minutes: float,
    baseline_p50_minutes: float | None,
    threshold_pct: float = DEFAULT_REGRESSION_THRESHOLD_PCT,
    abs_floor_minutes: float = DEFAULT_ABS_FLOOR_MINUTES,
) -> dict[str, Any]:
    """Pure comparison of one measured duration against one committed p50.

    Never raises (no baseline, negative measurement, zero baseline are all
    explicit branches, not exceptions a caller has to catch). A regression is
    only `True` when BOTH the percent threshold AND the absolute floor are
    cleared — see module docstring, contract point 4, for why the floor
    exists (a near-zero baseline turns any real increase into a nonsensical
    percent).
    """
    if baseline_p50_minutes is None:
        return {
            "baseline_available": False,
            "baseline_p50_minutes": None,
            "measured_minutes": measured_minutes,
            "delta_minutes": None,
            "delta_pct": None,
            "threshold_pct": threshold_pct,
            "abs_floor_minutes": abs_floor_minutes,
            "regression_detected": False,
        }

    delta_minutes = measured_minutes - baseline_p50_minutes
    delta_pct: float | None
    if baseline_p50_minutes > 0:
        delta_pct = delta_minutes / baseline_p50_minutes * 100.0
        pct_exceeded = delta_pct > threshold_pct
    else:
        # No percent is defined off a zero baseline (division by zero) — fall
        # back to the absolute floor alone rather than fabricating a percent
        # or silently treating a zero baseline as "cannot regress".
        delta_pct = None
        pct_exceeded = delta_minutes > abs_floor_minutes

    abs_exceeded = delta_minutes > abs_floor_minutes
    regression_detected = pct_exceeded and abs_exceeded

    return {
        "baseline_available": True,
        "baseline_p50_minutes": baseline_p50_minutes,
        "measured_minutes": measured_minutes,
        "delta_minutes": delta_minutes,
        "delta_pct": delta_pct,
        "threshold_pct": threshold_pct,
        "abs_floor_minutes": abs_floor_minutes,
        "regression_detected": regression_detected,
    }


def decide(is_test_infra_touch: bool, regression: dict[str, Any]) -> dict[str, Any]:
    """Combine contract points 1+2+3+4 into one verdict.

    `blocking=True` is the ONLY case that should ever produce a non-zero
    exit — every other branch (no baseline, no regression, regression on a
    PR that never touched test-infra) is a pass, by design (contract point
    2: telemetry-only PRs are never failed by this gate)."""
    if not regression.get("baseline_available"):
        return {"verdict": "cannot_verify", "blocking": False}
    if not regression["regression_detected"]:
        return {"verdict": "clean", "blocking": False}
    if is_test_infra_touch:
        return {"verdict": "regression_blocking", "blocking": True}
    return {"verdict": "regression_telemetry_only", "blocking": False}


# --- I/O + CLI ---------------------------------------------------------------


def load_baseline(path: Path) -> tuple[dict[str, Any], str | None]:
    """(jobs_map, error). jobs_map is `{}` on any read/parse failure — the
    caller (main) treats an empty map exactly like "job not found", which
    routes through `cannot_verify`, never a fabricated block or pass."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, f"could not read baseline {path}: {exc}"
    except json.JSONDecodeError as exc:
        return {}, f"could not parse baseline {path}: {exc}"
    jobs = raw.get("jobs")
    if not isinstance(jobs, dict):
        return {}, f"baseline {path} has no 'jobs' mapping"
    return jobs, None


def _read_paths(argv_paths: list[str], stdin_text: str) -> list[str]:
    if argv_paths:
        return [line for arg in argv_paths for line in arg.splitlines()]
    return [line for line in stdin_text.splitlines() if line.strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH), help="path to test_cost_baseline.json")
    parser.add_argument("--job", required=True, help="job key as it appears in the baseline (e.g. backend-tests)")
    parser.add_argument("--duration-minutes", type=float, required=True, help="this run's measured job duration")
    parser.add_argument("--threshold-pct", type=float, default=DEFAULT_REGRESSION_THRESHOLD_PCT)
    parser.add_argument("--abs-floor-minutes", type=float, default=DEFAULT_ABS_FLOOR_MINUTES)
    parser.add_argument(
        "--changed-files-file",
        default=None,
        help="path to a file of changed paths, one per line (default: read stdin, or trailing argv)",
    )
    parser.add_argument(
        "changed_files",
        nargs="*",
        help="changed paths as positional args (alternative to stdin/--changed-files-file)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.changed_files_file:
        stdin_text = Path(args.changed_files_file).read_text(encoding="utf-8")
        changed = _read_paths([], stdin_text)
    elif args.changed_files:
        changed = _read_paths(args.changed_files, "")
    elif not sys.stdin.isatty():
        changed = _read_paths([], sys.stdin.read())
    else:
        changed = []

    is_test_infra_touch = touches_test_infra(changed)

    jobs, baseline_error = load_baseline(Path(args.baseline))
    job_entry = jobs.get(args.job) if isinstance(jobs, dict) else None
    baseline_p50 = job_entry.get("p50_minutes") if isinstance(job_entry, dict) else None

    regression = evaluate_regression(
        args.duration_minutes,
        baseline_p50,
        threshold_pct=args.threshold_pct,
        abs_floor_minutes=args.abs_floor_minutes,
    )
    verdict = decide(is_test_infra_touch, regression)

    result: dict[str, Any] = {
        "job": args.job,
        "is_test_infra_touch": is_test_infra_touch,
        "changed_file_count": len(changed),
        "regression": regression,
        "baseline_error": baseline_error,
        **verdict,
    }
    print(json.dumps(result, sort_keys=True))

    # delta_pct is None when baseline_p50_minutes == 0 (evaluate_regression's
    # own explicit branch — no percent is defined off a zero baseline). The
    # human-readable messages below must degrade gracefully on that, same as
    # the JSON above already does via json.dumps: delta_minutes is always
    # available even when delta_pct is not, so report that instead of
    # crashing on `None.__format__`.
    delta_pct_display = (
        f"{regression['delta_pct']:.1f}%" if regression["delta_pct"] is not None else "n/a (baseline is 0)"
    )

    if verdict["blocking"]:
        print(
            f"test_cost_gate: BLOCKING — {args.job} measured {args.duration_minutes:.1f}min, "
            f"{delta_pct_display} over baseline p50={baseline_p50:.1f}min "
            f"(delta {regression['delta_minutes']:.1f}min) "
            f"(threshold {args.threshold_pct:.0f}%, floor {args.abs_floor_minutes:.1f}min) "
            "and this PR touches test-infra.",
            file=sys.stderr,
        )
    elif verdict["verdict"] == "regression_telemetry_only":
        print(
            f"test_cost_gate: NOTICE (not blocking) — {args.job} measured "
            f"{args.duration_minutes:.1f}min, {delta_pct_display} over baseline "
            f"p50={baseline_p50:.1f}min (delta {regression['delta_minutes']:.1f}min), "
            "but this PR does not touch test-infra.",
            file=sys.stderr,
        )
    elif verdict["verdict"] == "cannot_verify":
        detail = baseline_error or f"job '{args.job}' not in baseline"
        print(f"test_cost_gate: cannot verify ({detail}) — not blocking.", file=sys.stderr)
    else:
        print(f"test_cost_gate: clean — {args.job} within threshold of baseline.", file=sys.stderr)

    return 1 if verdict["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
