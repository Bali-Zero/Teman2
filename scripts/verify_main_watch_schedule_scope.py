#!/usr/bin/env python3
"""
Task #37 guilt/innocence proof for .github/workflows/main-push-failure-watch.yml's
alert job, after widening its scope from push-only to push-or-schedule.

NOT a general GitHub Actions expression interpreter — deliberately narrow,
same "known limit" style as scripts/verify_post_deploy_health_reachability.py
(task #19) and scripts/check_watcher_coverage.py. This hand-encodes the
semantics of exactly ONE job's `if:` plus one aggregation step's jq `select`
as they exist in this repo today.

Why the widening exists: task #37 added `.github/workflows/tests.yml`'s
first `schedule:` trigger that targets main (hourly, decoupled from push
cadence — see tests.yml's own `on.schedule` comment for the measured
starvation this works around). Before this change, `main-push-failure-
watch.yml`'s alert job fired ONLY on `github.event.workflow_run.event ==
'push'` — a schedule-triggered failure of the exact same workflow, on the
exact same branch, with the exact same conclusion, would silently NOT
alert. That is cron-theater-by-omission (superscar #2, "Esiste ≠ Armato"):
a health check exists, but its own failure is invisible. The fix widens
the `if:` to `event == 'push' OR event == 'schedule'`, and widens the
aggregation step's jq `select` the same way (it had its own independent
`event=push` filter, server-side via the `gh api` query param this time,
not the job-level `if:` — missing this second spot would have left the
top-level gate open while the aggregate always counted zero schedule
failures, silently suppressing the Telegram message anyway).

Self-check: if a future edit changes this job's `if:` or the aggregation
step's `run:` script in the YAML, this script fails loudly (exit 2) instead
of silently proving the wrong thing.
"""
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "main-push-failure-watch.yml"
JOB_NAME = "alert"

# `if: >-` is a YAML *folded* block scalar: GitHub Actions/PyYAML fold a
# normal-indent line break into a single space but preserve the newline
# before any MORE-indented continuation line — exact whitespace/newline
# placement after folding is not worth hand-predicting here, so
# EXPECTED_IF is written as one logical string and compared via
# _normalize(), which collapses all whitespace runs (including newlines)
# to a single space before comparing.
EXPECTED_IF = (
    "(github.event.workflow_run.event == 'push' || "
    "github.event.workflow_run.event == 'schedule') && "
    "github.event.workflow_run.head_branch == 'main' && "
    "(github.event.workflow_run.conclusion == 'failure' || "
    "github.event.workflow_run.conclusion == 'timed_out')"
)

AGGREGATE_STEP_NAME = "Aggregate every currently-failing push-or-schedule main run on this commit"
EXPECTED_AGGREGATE_SELECT_SUBSTRING = (
    'select((.event=="push" or .event=="schedule") '
    'and (.conclusion=="failure" or .conclusion=="timed_out"))'
)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _step_by_name(job: dict, name: str) -> dict | None:
    for step in job.get("steps") or []:
        if step.get("name") == name:
            return step
    return None


def self_check() -> None:
    """Fail loudly if the YAML no longer matches what this script models."""
    data = yaml.safe_load(WORKFLOW.read_text())
    job = (data.get("jobs") or {}).get(JOB_NAME)
    if job is None:
        print(f"FATAL: job '{JOB_NAME}' not found in {WORKFLOW}", file=sys.stderr)
        sys.exit(2)

    if_raw = (job.get("if") or "").strip()
    if _normalize(if_raw) != _normalize(EXPECTED_IF):
        print(
            f"FATAL: {JOB_NAME}.if drifted from what this script models.\n"
            f"  expected: {EXPECTED_IF!r}\n"
            f"  actual:   {if_raw!r}\n"
            "  Update EXPECTED_IF and alert_fires() below to match the new\n"
            "  YAML before trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    step = _step_by_name(job, AGGREGATE_STEP_NAME)
    if step is None:
        print(
            f"FATAL: step '{AGGREGATE_STEP_NAME}' not found in job '{JOB_NAME}'.\n"
            "  This script's aggregate-scope proof assumes this step exists\n"
            "  by this exact name — a rename silently breaks it.",
            file=sys.stderr,
        )
        sys.exit(2)
    run_raw = _normalize(step.get("run") or "")
    if _normalize(EXPECTED_AGGREGATE_SELECT_SUBSTRING) not in run_raw:
        print(
            f"FATAL: step '{AGGREGATE_STEP_NAME}'.run no longer contains the\n"
            "  jq select this script models.\n"
            f"  expected substring: {EXPECTED_AGGREGATE_SELECT_SUBSTRING!r}\n"
            f"  actual run script:  {step.get('run')!r}\n"
            "  Update EXPECTED_AGGREGATE_SELECT_SUBSTRING and\n"
            "  counts_toward_aggregate() below to match the new YAML before\n"
            "  trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)


def alert_fires(event: str, head_branch: str, conclusion: str) -> bool:
    """Models the job-level `if:` on the `alert` job."""
    return (
        event in ("push", "schedule")
        and head_branch == "main"
        and conclusion in ("failure", "timed_out")
    )


def counts_toward_aggregate(event: str, conclusion: str) -> bool:
    """Models the aggregation step's jq `select(...)` clause.

    Unlike alert_fires(), this has no head_branch check — the `gh api`
    call is already scoped to one commit's head_sha, and every workflow_run
    for a given head_sha on THIS repo shares one branch context in
    practice for the push/schedule case this models (a PR-triggered run on
    the same SHA would carry event=='pull_request', already excluded by
    the event check below).
    """
    return event in ("push", "schedule") and conclusion in ("failure", "timed_out")


# (label, event, head_branch, conclusion, expect_fires)
ALERT_SCENARIOS = [
    (
        "GUILT — schedule-triggered run on main fails (task #37's new case: "
        "the hourly Tests & Coverage run breaks and nobody was told before "
        "this widening)",
        "schedule", "main", "failure", True,
    ),
    (
        "GUILT — schedule-triggered run on main times out",
        "schedule", "main", "timed_out", True,
    ),
    (
        "INNOCENCE — push-triggered run on main fails (pre-existing case, "
        "must still fire after the widening)",
        "push", "main", "failure", True,
    ),
    (
        "INNOCENCE — pull_request-triggered run fails: already visible on "
        "the PR itself, must not alert",
        "pull_request", "main", "failure", False,
    ),
    (
        "INNOCENCE — workflow_dispatch-triggered run on main fails: "
        "operator-initiated, operator is already watching",
        "workflow_dispatch", "main", "failure", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on a non-main branch fails "
        "(structurally near-impossible — schedule only fires against the "
        "default branch — but the guard should not rely on that alone)",
        "schedule", "some-other-branch", "failure", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on main is cancelled: excluded "
        "deliberately (see header comment), a routine supersede is not a "
        "silent failure",
        "schedule", "main", "cancelled", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on main succeeds",
        "schedule", "main", "success", False,
    ),
]

# (label, event, conclusion, expect_counts)
AGGREGATE_SCENARIOS = [
    (
        "GUILT — schedule failure must be counted (this is the exact gap "
        "the widening closes: an open top-level if: with an aggregate "
        "still hardcoded to event=push would silently suppress the "
        "Telegram message)",
        "schedule", "failure", True,
    ),
    (
        "INNOCENCE — push failure still counted (pre-existing case)",
        "push", "failure", True,
    ),
    (
        "INNOCENCE — pull_request run on the same head_sha not counted",
        "pull_request", "failure", False,
    ),
    (
        "INNOCENCE — schedule run that succeeded is not counted",
        "schedule", "success", False,
    ),
]


def main() -> None:
    self_check()

    failures = []

    print("== alert job if: (push-or-schedule widening) ==")
    for label, event, head_branch, conclusion, expect in ALERT_SCENARIOS:
        got = alert_fires(event, head_branch, conclusion)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         event={event} head_branch={head_branch} "
              f"conclusion={conclusion} -> alert_fires={got} (expected {expect})")
        if not ok:
            failures.append(label)

    print("\n== aggregate step jq select (mirrors the same widening) ==")
    for label, event, conclusion, expect in AGGREGATE_SCENARIOS:
        got = counts_toward_aggregate(event, conclusion)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         event={event} conclusion={conclusion} "
              f"-> counts_toward_aggregate={got} (expected {expect})")
        if not ok:
            failures.append(label)

    total = len(ALERT_SCENARIOS) + len(AGGREGATE_SCENARIOS)
    if failures:
        print(f"\n{len(failures)}/{total} scenarios FAILED", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {total} scenarios PASS.")


if __name__ == "__main__":
    main()
