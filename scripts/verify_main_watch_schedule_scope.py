#!/usr/bin/env python3
"""
Guilt/innocence proof for .github/workflows/main-push-failure-watch.yml,
covering two changes made to it on 2026-07-26:

  - Task #37: widened the `alert` job's scope from push-only to
    push-or-schedule, after `tests.yml` grew its first `schedule:`
    trigger targeting main.
  - Task #41: added a second job, `verdict-liveness`, that alerts on the
    ABSENCE of a completed test verdict rather than reacting to any one
    event — closing the blind spot the task #37 widening alone leaves:
    `alert` deliberately excludes `cancelled` (see header comment), so a
    long streak of cancelled-via-supersede runs produces zero events
    `alert` would ever fire on, even after the widening.

NOT a general GitHub Actions expression interpreter — deliberately narrow,
same "known limit" style as scripts/verify_post_deploy_health_reachability.py
(task #19) and scripts/check_watcher_coverage.py. This hand-encodes the
semantics of exactly two jobs' `if:` conditions, one aggregation step's jq
`select`, and one escalation-arithmetic step, as they exist in this repo
today.

Task #37 widening, why it exists: before this change, `main-push-failure-
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

Task #41 verdict-liveness, why it exists: a REACTIVE per-event watcher
with `cancelled` excluded cannot distinguish "one routine supersede" from
"main has stopped producing verdicts at all" — it only ever sees
individual events, never the gap between them. `verdict-liveness` instead
polls every 15 minutes and alerts once the gap since the last real
(non-cancelled) tests.yml conclusion on main exceeds a threshold, then
again on a bounded escalation cadence — "one alert per outage", computed
purely from timestamp arithmetic, no external state.

Self-check: if a future edit changes either job's `if:`, the aggregation
step's `run:` script, or the escalation constants in the YAML, this script
fails loudly (exit 2) instead of silently proving the wrong thing.
"""
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "main-push-failure-watch.yml"
ALERT_JOB_NAME = "alert"
LIVENESS_JOB_NAME = "verdict-liveness"

# `if: >-` is a YAML *folded* block scalar: GitHub Actions/PyYAML fold a
# normal-indent line break into a single space but preserve the newline
# before any MORE-indented continuation line — exact whitespace/newline
# placement after folding is not worth hand-predicting here, so
# EXPECTED_IF is written as one logical string and compared via
# _normalize(), which collapses all whitespace runs (including newlines)
# to a single space before comparing.
EXPECTED_ALERT_IF = (
    "github.event_name == 'workflow_run' && "
    "(github.event.workflow_run.event == 'push' || "
    "github.event.workflow_run.event == 'schedule') && "
    "github.event.workflow_run.head_branch == 'main' && "
    "(github.event.workflow_run.conclusion == 'failure' || "
    "github.event.workflow_run.conclusion == 'timed_out')"
)

EXPECTED_LIVENESS_IF = "github.event_name == 'schedule'"

AGGREGATE_STEP_NAME = "Aggregate every currently-failing push-or-schedule main run on this commit"
EXPECTED_AGGREGATE_SELECT_SUBSTRING = (
    'select((.event=="push" or .event=="schedule") '
    'and (.conclusion=="failure" or .conclusion=="timed_out"))'
)

CHECK_STEP_NAME = "Check time since main's last completed tests.yml verdict"
EXPECTED_ESCALATION_CONSTANTS = ("THRESHOLD_MINUTES=45", "CHECK_INTERVAL_MINUTES=15", "ESCALATION_MINUTES=60")


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
    jobs = data.get("jobs") or {}

    alert_job = jobs.get(ALERT_JOB_NAME)
    if alert_job is None:
        print(f"FATAL: job '{ALERT_JOB_NAME}' not found in {WORKFLOW}", file=sys.stderr)
        sys.exit(2)

    if_raw = (alert_job.get("if") or "").strip()
    if _normalize(if_raw) != _normalize(EXPECTED_ALERT_IF):
        print(
            f"FATAL: {ALERT_JOB_NAME}.if drifted from what this script models.\n"
            f"  expected: {EXPECTED_ALERT_IF!r}\n"
            f"  actual:   {if_raw!r}\n"
            "  Update EXPECTED_ALERT_IF and alert_fires() below to match the\n"
            "  new YAML before trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    step = _step_by_name(alert_job, AGGREGATE_STEP_NAME)
    if step is None:
        print(
            f"FATAL: step '{AGGREGATE_STEP_NAME}' not found in job '{ALERT_JOB_NAME}'.\n"
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

    liveness_job = jobs.get(LIVENESS_JOB_NAME)
    if liveness_job is None:
        print(f"FATAL: job '{LIVENESS_JOB_NAME}' not found in {WORKFLOW}", file=sys.stderr)
        sys.exit(2)

    liveness_if_raw = (liveness_job.get("if") or "").strip()
    if _normalize(liveness_if_raw) != _normalize(EXPECTED_LIVENESS_IF):
        print(
            f"FATAL: {LIVENESS_JOB_NAME}.if drifted from what this script models.\n"
            f"  expected: {EXPECTED_LIVENESS_IF!r}\n"
            f"  actual:   {liveness_if_raw!r}\n"
            "  Update EXPECTED_LIVENESS_IF below to match the new YAML before\n"
            "  trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    check_step = _step_by_name(liveness_job, CHECK_STEP_NAME)
    if check_step is None:
        print(
            f"FATAL: step '{CHECK_STEP_NAME}' not found in job '{LIVENESS_JOB_NAME}'.\n"
            "  This script's escalation-arithmetic proof assumes this step\n"
            "  exists by this exact name — a rename silently breaks it.",
            file=sys.stderr,
        )
        sys.exit(2)
    check_run_raw = check_step.get("run") or ""
    missing_constants = [c for c in EXPECTED_ESCALATION_CONSTANTS if c not in check_run_raw]
    if missing_constants:
        print(
            f"FATAL: step '{CHECK_STEP_NAME}'.run no longer contains the\n"
            "  escalation constants this script models.\n"
            f"  missing: {missing_constants!r}\n"
            "  Update EXPECTED_ESCALATION_CONSTANTS and should_alert() below\n"
            "  to match the new YAML before trusting this script's verdict\n"
            "  again.",
            file=sys.stderr,
        )
        sys.exit(2)


def alert_fires(
    top_event_name: str, wr_event: str, head_branch: str, conclusion: str
) -> bool:
    """Models the job-level `if:` on the `alert` job.

    `top_event_name` is `github.event_name` — what triggered THIS
    workflow's own run (always 'workflow_run' in real traffic, except
    when the new task #41 `schedule` trigger fires this same workflow,
    in which case `github.event.workflow_run` doesn't exist at all).
    `wr_event` is `github.event.workflow_run.event` — what triggered the
    OTHER workflow whose completion is being reported on.
    """
    return (
        top_event_name == "workflow_run"
        and wr_event in ("push", "schedule")
        and head_branch == "main"
        and conclusion in ("failure", "timed_out")
    )


def liveness_job_runs(top_event_name: str) -> bool:
    """Models the job-level `if:` on the `verdict-liveness` job."""
    return top_event_name == "schedule"


UNKNOWN_STALE_SENTINEL = 999999


def should_alert(
    stale_minutes: int,
    threshold: int = 45,
    check_interval: int = 15,
    escalation: int = 60,
) -> bool:
    """Models the escalation arithmetic in the `Check time since main's
    last completed tests.yml verdict` step.

    Unknown (no qualifying run found at all in the lookback window):
    ALWAYS alert, every check — deliberately NOT routed through the
    boundary-crossing math below. Caught by this script's own guilt
    scenario before shipping: `stale_minutes - threshold` for the
    sentinel value doesn't reliably land within `check_interval` of an
    `escalation` boundary, so the boundary heuristic can go silent on
    the single worst-case input it most needs to catch. "We don't even
    know when main last passed" is categorically worse than "known,
    bounded staleness" and gets its own unconditional branch instead of
    trusting arithmetic tuned for a different case to also cover it.
    Healthy: stale_minutes < threshold -> no alert.
    First breach: the first check to observe stale_minutes >= threshold
    has overflow (stale_minutes - threshold) somewhere in
    [0, check_interval) — see the step's own comment for why that window
    is guaranteed regardless of exactly when the breach occurred between
    two 15-minute checks.
    Reminder: once overflow crosses a multiple of `escalation`, alert
    again — bounded, "one alert per outage segment" rather than one per
    15-minute check.
    """
    if stale_minutes >= UNKNOWN_STALE_SENTINEL:
        return True
    if stale_minutes < threshold:
        return False
    overflow = stale_minutes - threshold
    boundary = overflow % escalation
    return overflow < check_interval or boundary < check_interval


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


# (label, top_event_name, wr_event, head_branch, conclusion, expect_fires)
ALERT_SCENARIOS = [
    (
        "GUILT — schedule-triggered run on main fails (task #37's new case: "
        "the scheduled Tests & Coverage run breaks and nobody was told "
        "before the task #37 widening)",
        "workflow_run", "schedule", "main", "failure", True,
    ),
    (
        "GUILT — schedule-triggered run on main times out",
        "workflow_run", "schedule", "main", "timed_out", True,
    ),
    (
        "INNOCENCE — push-triggered run on main fails (pre-existing case, "
        "must still fire after the widening)",
        "workflow_run", "push", "main", "failure", True,
    ),
    (
        "INNOCENCE — pull_request-triggered run fails: already visible on "
        "the PR itself, must not alert",
        "workflow_run", "pull_request", "main", "failure", False,
    ),
    (
        "INNOCENCE — workflow_dispatch-triggered run on main fails: "
        "operator-initiated, operator is already watching",
        "workflow_run", "workflow_dispatch", "main", "failure", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on a non-main branch fails "
        "(structurally near-impossible — schedule only fires against the "
        "default branch — but the guard should not rely on that alone)",
        "workflow_run", "schedule", "some-other-branch", "failure", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on main is cancelled: excluded "
        "deliberately (see header comment), a routine supersede is not a "
        "silent failure",
        "workflow_run", "schedule", "main", "cancelled", False,
    ),
    (
        "INNOCENCE — schedule-triggered run on main succeeds",
        "workflow_run", "schedule", "main", "success", False,
    ),
    (
        "INNOCENCE (task #41 self-trigger safety) — this workflow's OWN "
        "schedule trigger (the verdict-liveness path) must never be "
        "mistaken for a workflow_run report, even with matching-looking "
        "sub-fields",
        "schedule", "push", "main", "failure", False,
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

# (label, top_event_name, expect_runs)
LIVENESS_JOB_SCENARIOS = [
    (
        "GUILT — this workflow's own schedule trigger must run the "
        "liveness job (the whole point of task #41)",
        "schedule", True,
    ),
    (
        "INNOCENCE — a workflow_run event (the alert job's trigger) must "
        "not also run the liveness job",
        "workflow_run", False,
    ),
]

# (label, stale_minutes, expect_alert)
ESCALATION_SCENARIOS = [
    (
        "INNOCENCE — healthy gap, well under threshold (measured healthy "
        "gap tonight was ~20-25 min)",
        20, False,
    ),
    (
        "INNOCENCE — just under threshold",
        44, False,
    ),
    (
        "GUILT — first breach, exactly at threshold: must alert",
        45, True,
    ),
    (
        "GUILT — first breach, a few minutes past threshold (still within "
        "one check-interval of crossing)",
        50, True,
    ),
    (
        "INNOCENCE — well past first breach but not yet at the next "
        "escalation boundary: must NOT re-alert (this is what makes it "
        "'one alert per outage' instead of one per 15-min check)",
        90, False,
    ),
    (
        "GUILT — crossed the 60-minute escalation boundary past first "
        "breach (45 + 60 = 105): reminder must fire",
        105, True,
    ),
    (
        "INNOCENCE — between escalation boundaries again",
        150, False,
    ),
    (
        "GUILT — no qualifying run found at all in the lookback window: "
        "treated as maximally stale, must alert, not silently pass",
        999999, True,
    ),
]


def main() -> None:
    self_check()

    failures = []

    print("== alert job if: (push-or-schedule widening + self-trigger safety) ==")
    for label, top_event, wr_event, head_branch, conclusion, expect in ALERT_SCENARIOS:
        got = alert_fires(top_event, wr_event, head_branch, conclusion)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         top_event={top_event} wr_event={wr_event} "
              f"head_branch={head_branch} conclusion={conclusion} "
              f"-> alert_fires={got} (expected {expect})")
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

    print("\n== verdict-liveness job if: (task #41) ==")
    for label, top_event, expect in LIVENESS_JOB_SCENARIOS:
        got = liveness_job_runs(top_event)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         top_event={top_event} "
              f"-> liveness_job_runs={got} (expected {expect})")
        if not ok:
            failures.append(label)

    print("\n== verdict-liveness escalation arithmetic (task #41) ==")
    for label, stale_minutes, expect in ESCALATION_SCENARIOS:
        got = should_alert(stale_minutes)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         stale_minutes={stale_minutes} "
              f"-> should_alert={got} (expected {expect})")
        if not ok:
            failures.append(label)

    total = (
        len(ALERT_SCENARIOS)
        + len(AGGREGATE_SCENARIOS)
        + len(LIVENESS_JOB_SCENARIOS)
        + len(ESCALATION_SCENARIOS)
    )
    if failures:
        print(f"\n{len(failures)}/{total} scenarios FAILED", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {total} scenarios PASS.")


if __name__ == "__main__":
    main()
