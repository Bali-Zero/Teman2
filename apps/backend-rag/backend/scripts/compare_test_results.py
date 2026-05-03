#!/usr/bin/env python3
"""
Regression Detection for Autonomous Test-Fix Loop.

Compares before/after pytest-json-report results to detect:
1. Regressions: tests that PASSED before but FAIL after
2. Fixes: tests that FAILED before but PASS after
3. Coverage delta

Usage:
    python3 -m backend.scripts.compare_test_results /tmp/nuz-test-results.json /tmp/nuz-test-results-after.json
    python3 -m backend.scripts.compare_test_results before.json after.json --output /tmp/nuz-regression-report.json
"""

import json
import sys
from pathlib import Path


def load_outcomes(report_path: str) -> dict[str, str]:
    """Load test outcomes from pytest-json-report.

    Returns: {nodeid: outcome} mapping
    """
    with open(report_path) as f:
        report = json.load(f)

    outcomes: dict[str, str] = {}
    for test in report.get("tests", []):
        nodeid = test.get("nodeid", "")
        outcome = test.get("outcome", "unknown")
        if nodeid:
            outcomes[nodeid] = outcome

    return outcomes


def load_summary(report_path: str) -> dict:
    """Load summary counts from report."""
    with open(report_path) as f:
        report = json.load(f)

    summary = report.get("summary", {})
    return {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "error": summary.get("error", 0),
        "skipped": summary.get("skipped", 0),
    }


def compare(before_path: str, after_path: str) -> dict:
    """Compare before/after test results.

    Key distinction:
    - REGRESSION: test passed before, fails after (BAD — caused by our fixes)
    - FIXED: test failed before, passes after (GOOD — our fixes worked)
    - STILL_FAILING: failed before and after (neutral)
    - NEW_FAILURE: test didn't exist before, fails now (investigate)
    """
    before = load_outcomes(before_path)
    after = load_outcomes(after_path)

    before_summary = load_summary(before_path)
    after_summary = load_summary(after_path)

    # Sets for comparison
    before_passed = {k for k, v in before.items() if v == "passed"}
    before_failed = {k for k, v in before.items() if v in ("failed", "error")}
    after_passed = {k for k, v in after.items() if v == "passed"}
    after_failed = {k for k, v in after.items() if v in ("failed", "error")}

    regressions = sorted(before_passed & after_failed)
    fixed = sorted(before_failed & after_passed)
    still_failing = sorted(before_failed & after_failed)
    new_failures = sorted(after_failed - before_failed - before_passed)

    # Determine action
    if len(regressions) > 0:
        action = "BISECT_AND_REVERT"
    elif len(fixed) > 0:
        action = "PROCEED_TO_COMMIT"
    else:
        action = "NO_CHANGE"

    return {
        "action": action,
        "regression_count": len(regressions),
        "fixed_count": len(fixed),
        "still_failing_count": len(still_failing),
        "new_failure_count": len(new_failures),
        "regressions": regressions[:50],  # Cap output size
        "fixed": fixed[:50],
        "new_failures": new_failures[:20],
        "summary_before": before_summary,
        "summary_after": after_summary,
        "delta": {
            "passed": after_summary["passed"] - before_summary["passed"],
            "failed": after_summary["failed"] - before_summary["failed"],
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compare test results for regression detection")
    parser.add_argument("before", help="Path to before test results JSON")
    parser.add_argument("after", help="Path to after test results JSON")
    parser.add_argument(
        "--output",
        "-o",
        default="/tmp/nuz-regression-report.json",
        help="Output path",
    )
    args = parser.parse_args()

    for path in (args.before, args.after):
        if not Path(path).exists():
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    result = compare(args.before, args.after)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print("=== Regression Analysis ===")
    print(f"Action: {result['action']}")
    print("")
    print(
        f"Before: {result['summary_before']['passed']} passed, {result['summary_before']['failed']} failed",
    )
    print(
        f"After:  {result['summary_after']['passed']} passed, {result['summary_after']['failed']} failed",
    )
    print(f"Delta:  {result['delta']['passed']:+d} passed, {result['delta']['failed']:+d} failed")
    print("")
    print(f"Fixed:        {result['fixed_count']}")
    print(f"Regressions:  {result['regression_count']}")
    print(f"Still failing: {result['still_failing_count']}")
    print(f"New failures: {result['new_failure_count']}")

    if result["regressions"]:
        print("\nREGRESSIONS (tests that broke):")
        for r in result["regressions"][:10]:
            print(f"  - {r}")

    if result["fixed"]:
        print("\nFIXED (tests that now pass):")
        for f_item in result["fixed"][:10]:
            print(f"  + {f_item}")

    print(f"\nOutput written to: {args.output}")


if __name__ == "__main__":
    main()
