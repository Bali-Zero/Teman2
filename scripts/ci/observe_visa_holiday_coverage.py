#!/usr/bin/env python3
"""observe_visa_holiday_coverage.py — bites: observation for the holiday-coverage lane.

# bites-observable — this script takes NO arguments: it runs the sentinel's real coverage probe
# on the committed decree table under dry-run (no gateway call, no state file, no board row), so
# nothing an invoker types can name a program to run, a file to write, or a database to reach.

The first line is today's real data (the outcome the Pro tick will see). The next three move the
clock to 100, 30 and 0 days before the first gap D the real data yields, and prove the lane turns
OK, WARN, STALE and would send on the last two. D is read, never typed, so loading the next
decree moves the gap and this observation keeps holding.

Exit 0 only if every tier holds.
"""

from __future__ import annotations

import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import visa_freshness_sentinel as vfs  # noqa: E402


def _at(day) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=timezone.utc)


def main() -> int:
    real = vfs.build_coverage_verdict(datetime.now(timezone.utc))
    print(vfs.coverage_line(real))
    gap = (real.coverage or {}).get("first_gap")
    if real.outcome == vfs.OUTCOME_CANNOT_VERIFY or not gap:
        print("holiday coverage observed: FAILED, the probe gave no answer")
        return 1
    gap_day = datetime.fromisoformat(gap).date()
    expect = [
        (100, vfs.OUTCOME_OK, False),
        (30, vfs.OUTCOME_COVERAGE_WARN, True),
        (0, vfs.OUTCOME_COVERAGE_STALE, True),
    ]
    ok = True
    for days, outcome, sends in expect:
        verdict = vfs.build_coverage_verdict(_at(gap_day - timedelta(days=days)))
        decision = vfs.run_alert_cycle(
            verdict, dry_run=True, now_ts=_at(gap_day - timedelta(days=days)).timestamp(),
            state_path=Path("/nonexistent/visa_holiday_coverage.json"),
        )
        print(f"D-{days}: {vfs.coverage_line(verdict, decision)}")
        ok = ok and verdict.outcome == outcome and decision["would_send"] is sends
    if not ok:
        print("holiday coverage observed: FAILED, a tier did not hold")
        return 1
    print("holiday coverage observed: OK 100d, WARN 30d, STALE 0d (WARN and STALE would send)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
