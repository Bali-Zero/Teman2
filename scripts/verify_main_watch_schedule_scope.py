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
polls every 15 minutes and alerts once main has a commit that has sat
without a real (non-cancelled) tests.yml conclusion for too long, then
again on a bounded escalation cadence — "one alert per outage", computed
purely from timestamp arithmetic, no external state.

Design correction caught in review, before shipping (team-lead, not a
test): the FIRST version of `verdict-liveness` measured staleness as
"now minus the last verdict's own timestamp" — verdict-to-now, not
commit-to-verdict. With tests.yml's schedule cadence at every 2 hours
(task #37), a quiet main with no pushes only ever gets a fresh verdict
every ~2h, so that measure would breach THRESHOLD_MINUTES=45 on EVERY
ordinary quiet stretch and re-alert on every escalation boundary for
hours — alarm fatigue built in on day one, from the opposite direction of
the `cancelled`-exclusion bug this job exists to fix. The corrected
design compares main's CURRENT head commit against the last-verified
commit's SHA: if they're equal, main is fully caught up regardless of how
old that verdict is (zero staleness); if they differ, staleness is
measured from when the first unverified commit landed, not from the old
verdict's timestamp. `compute_stale_minutes()` below models this.

Task #37/#41 red-path proof, workflow_dispatch addendum (2026-07-26): the
arithmetic above was verified by re-executing the shipped bash against
real API data, but that alone doesn't prove the WIRING — that this job
actually runs under GitHub Actions, that the Telegram step actually
executes, that secrets resolve. `workflow_dispatch` with a
`force_test_alert` boolean input (default false) closes that gap: it
widens `verdict-liveness`'s job-level `if:` to also run on manual
dispatch, and overrides ONLY the final should_alert decision (never the
arithmetic feeding it, never THRESHOLD_MINUTES) when the input is
explicitly `true`. Every such send is `[TEST`-prefixed so it can never be
mistaken for a real alert in the chat history.

Self-check: if a future edit changes either job's `if:`, the aggregation
step's `run:` script, the escalation constants, the commit-comparison
logic, or the workflow_dispatch test-mode override in the YAML, this
script fails loudly (exit 2) instead of silently proving the wrong thing.
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

EXPECTED_LIVENESS_IF = "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"

AGGREGATE_STEP_NAME = "Aggregate every currently-failing push-or-schedule main run on this commit"
EXPECTED_AGGREGATE_SELECT_SUBSTRING = (
    'select((.event=="push" or .event=="schedule") '
    'and (.conclusion=="failure" or .conclusion=="timed_out"))'
)

CHECK_STEP_NAME = "Check time since main's last completed tests.yml verdict"
EXPECTED_ESCALATION_CONSTANTS = ("THRESHOLD_MINUTES=45", "CHECK_INTERVAL_MINUTES=15", "ESCALATION_MINUTES=60")

# The specific substring that proves the quiet-period fix is present: the
# branch that short-circuits staleness to zero when main's current head
# equals the last-verified SHA. Checking for this exact comparison (not
# just "the constants exist") is what catches a future edit that reverts
# to the verdict-to-now measure while leaving the constants untouched.
EXPECTED_QUIET_PERIOD_SHORT_CIRCUIT = '"${LAST_VERIFIED_SHA}" = "${CURRENT_HEAD}"'

TELEGRAM_STEP_NAME = "Telegram alert — main has an unverified commit sitting too long"

# The exact override substring that proves the #37/#41 red-path proof
# mechanism is present: force_test_alert=true overrides SHOULD_ALERT
# without touching the arithmetic feeding it. Checking for this literal
# comparison (not just "FORCE_TEST_ALERT is referenced somewhere") is
# what catches a future edit that wires the input to something that
# ALSO changes THRESHOLD_MINUTES or the escalation math — which would
# turn the "escape hatch" into a second, undocumented production path.
EXPECTED_TEST_MODE_OVERRIDE = 'if [ "${FORCE_TEST_ALERT}" = "true" ]; then'
EXPECTED_TEST_MODE_PREFIX = '[TEST — manual workflow_dispatch red-path proof, NOT a real alert]'


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

    if EXPECTED_QUIET_PERIOD_SHORT_CIRCUIT not in check_run_raw:
        print(
            f"FATAL: step '{CHECK_STEP_NAME}'.run no longer contains the\n"
            "  quiet-period short-circuit (current head == last verified sha\n"
            "  -> zero staleness) this script models.\n"
            f"  expected substring: {EXPECTED_QUIET_PERIOD_SHORT_CIRCUIT!r}\n"
            "  Without this branch, a quiet main re-alerts on every ordinary\n"
            "  gap between scheduled tests.yml runs — the exact bug caught\n"
            "  in review before this job first shipped. Update\n"
            "  EXPECTED_QUIET_PERIOD_SHORT_CIRCUIT and compute_stale_minutes()\n"
            "  below to match the new YAML before trusting this script's\n"
            "  verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    if EXPECTED_TEST_MODE_OVERRIDE not in check_run_raw:
        print(
            f"FATAL: step '{CHECK_STEP_NAME}'.run no longer contains the\n"
            "  force_test_alert override (#37/#41 red-path proof) this\n"
            "  script models.\n"
            f"  expected substring: {EXPECTED_TEST_MODE_OVERRIDE!r}\n"
            "  Update EXPECTED_TEST_MODE_OVERRIDE and test_mode_forces_alert()\n"
            "  below to match the new YAML before trusting this script's\n"
            "  verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    # PyYAML's default (YAML 1.1) resolver coerces the bare key `on:` to
    # the boolean `True`, not the string "on" — confirmed empirically
    # here (`list(data.keys())` prints `[..., True, ...]`), a distinct
    # instance of the "guard on FORM not ENTITY" family
    # (cicatrix-superscar #3): `data.get("on")` would silently return
    # None forever, exactly the "blind self_check" failure mode this
    # function exists to prevent becoming.
    on_block = data.get(True) or data.get("on") or {}
    workflow_dispatch = (on_block.get("workflow_dispatch") or {})
    inputs = workflow_dispatch.get("inputs") or {}
    force_input = inputs.get("force_test_alert")
    if force_input is None or force_input.get("default") is not False:
        print(
            "FATAL: on.workflow_dispatch.inputs.force_test_alert missing or\n"
            "  its default is not `false`.\n"
            f"  actual: {force_input!r}\n"
            "  A non-false default would mean an ordinary/unparameterized\n"
            "  manual dispatch sends a test alert by itself — the exact\n"
            "  'escape hatch becomes the live setting' footgun this input\n"
            "  was built to avoid.",
            file=sys.stderr,
        )
        sys.exit(2)

    telegram_step = _step_by_name(liveness_job, TELEGRAM_STEP_NAME)
    if telegram_step is None:
        print(
            f"FATAL: step '{TELEGRAM_STEP_NAME}' not found in job "
            f"'{LIVENESS_JOB_NAME}'.",
            file=sys.stderr,
        )
        sys.exit(2)
    telegram_run_raw = telegram_step.get("run") or ""
    if EXPECTED_TEST_MODE_PREFIX not in telegram_run_raw:
        print(
            f"FATAL: step '{TELEGRAM_STEP_NAME}'.run no longer contains the\n"
            "  [TEST] prefix this script models.\n"
            f"  expected substring: {EXPECTED_TEST_MODE_PREFIX!r}\n"
            "  Without this, a red-path proof send is indistinguishable from\n"
            "  a real alert in the chat history. Update\n"
            "  EXPECTED_TEST_MODE_PREFIX below to match the new YAML before\n"
            "  trusting this script's verdict again.",
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
    return top_event_name in ("schedule", "workflow_dispatch")


UNKNOWN_STALE_SENTINEL = 999999


def compute_stale_minutes(
    last_verified_sha: str | None,
    current_head_sha: str,
    first_unverified_epoch: int | None,
    now_epoch: int,
) -> int:
    """Models the commit-aware staleness computation in the `Check time
    since main's last completed tests.yml verdict` step.

    THIS is the design correction caught in review (see module docstring)
    before the job first shipped — the version this replaces measured
    `now - last_verdict_timestamp` unconditionally, which breaches a
    45-minute threshold on every ordinary gap between 2-hourly scheduled
    runs on a quiet main. The fix: staleness is about UNVERIFIED COMMITS,
    not about elapsed time since a verdict happened to be produced.

    `last_verified_sha=None` models "no qualifying run found in the
    lookback window at all" -> unconditionally unknown/maximally stale
    (mirrors `should_alert`'s own UNKNOWN_STALE_SENTINEL handling one
    layer up).
    `last_verified_sha == current_head_sha` models "main hasn't moved
    since the last real verdict" -> zero staleness, REGARDLESS of how
    long ago that verdict ran. This is the fix.
    Otherwise, staleness is `now - first_unverified_epoch` — the age of
    the OLDEST commit past the last verified one, not the verdict's own
    (stale) timestamp. `first_unverified_epoch=None` models the
    defensive "SHAs differ but compare returned no commits" fallback.
    """
    if last_verified_sha is None:
        return UNKNOWN_STALE_SENTINEL
    if last_verified_sha == current_head_sha:
        return 0
    if first_unverified_epoch is None:
        return UNKNOWN_STALE_SENTINEL
    return (now_epoch - first_unverified_epoch) // 60


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


def test_mode_forces_alert(
    top_event_name: str, force_test_alert_input: bool, arithmetic_would_alert: bool
) -> bool:
    """Models the #37/#41 red-path proof override in the `check` step.

    `FORCE_TEST_ALERT` (the env var feeding this) is itself an expression —
    `github.event_name == 'workflow_dispatch' && inputs.force_test_alert ==
    true` — so it can only ever be true under workflow_dispatch, never
    under schedule, regardless of what a caller passes as
    `force_test_alert_input`. The override, once active, forces
    should_alert=true UNCONDITIONALLY — it does not matter what the real
    arithmetic (`arithmetic_would_alert`) computed, which is the entire
    point: this proves delivery, not staleness.
    """
    force_active = top_event_name == "workflow_dispatch" and force_test_alert_input
    if force_active:
        return True
    return arithmetic_would_alert


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
        "GUILT (red-path proof, 2026-07-26) — a manual workflow_dispatch "
        "must also run the liveness job, or force_test_alert has nothing "
        "to override",
        "workflow_dispatch", True,
    ),
    (
        "INNOCENCE — a workflow_run event (the alert job's trigger) must "
        "not also run the liveness job",
        "workflow_run", False,
    ),
]

# (label, top_event_name, force_test_alert_input, arithmetic_would_alert,
#  expect_should_alert)
TEST_MODE_SCENARIOS = [
    (
        "GUILT — workflow_dispatch with force_test_alert=true must alert "
        "even though the real arithmetic says the gap is healthy (the "
        "whole point: this proves DELIVERY, not staleness)",
        "workflow_dispatch", True, False, True,
    ),
    (
        "INNOCENCE — workflow_dispatch with force_test_alert=false (the "
        "declared default) must defer entirely to the real arithmetic — "
        "an ordinary/unparameterized manual dispatch changes nothing",
        "workflow_dispatch", False, False, False,
    ),
    (
        "INNOCENCE — schedule event can never have force_test_alert=true "
        "in practice (FORCE_TEST_ALERT is itself gated on "
        "event_name=='workflow_dispatch'), and must still alert correctly "
        "off the real arithmetic when it says so",
        "schedule", True, True, True,
    ),
    (
        "INNOCENCE — schedule event, arithmetic says healthy: must not "
        "alert, confirming the override cannot leak into the production "
        "schedule path",
        "schedule", True, False, False,
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

# (label, last_verified_sha, current_head_sha, first_unverified_epoch,
#  now_epoch, expect_stale_minutes)
# Uses relative epochs (0 = "now") rather than real timestamps for
# readability — only the DIFFERENCE matters to compute_stale_minutes().
STALE_MINUTES_SCENARIOS = [
    (
        "INNOCENCE (THE FIX) — main's current head IS the last verified "
        "sha: a quiet main with no pushes, verdict is 3 hours old (well "
        "past a naive 45-min verdict-to-now threshold) but there is "
        "NOTHING NEW to verify. Must be zero staleness, not 180.",
        "sha-a", "sha-a", -3 * 60 * 60, 0, 0,
    ),
    (
        "GUILT — main moved past the last verified sha 50 minutes ago: "
        "real, known staleness past threshold",
        "sha-a", "sha-b", -50 * 60, 0, 50,
    ),
    (
        "INNOCENCE — main moved past the last verified sha only 5 "
        "minutes ago: within the grace period, not yet stale",
        "sha-a", "sha-b", -5 * 60, 0, 5,
    ),
    (
        "GUILT — no qualifying run found at all (last_verified_sha is "
        "None): unconditionally unknown/maximally stale, regardless of "
        "current_head_sha or timestamps",
        None, "sha-b", None, 0, UNKNOWN_STALE_SENTINEL,
    ),
    (
        "GUILT (defensive fallback) — SHAs differ but the compare API "
        "returned no commits (first_unverified_epoch is None): treated "
        "as maximally stale, not silently passed as zero",
        "sha-a", "sha-b", None, 0, UNKNOWN_STALE_SENTINEL,
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

    print("\n== #37/#41 red-path proof: force_test_alert override ==")
    for label, top_event, force_input, arith_would, expect in TEST_MODE_SCENARIOS:
        got = test_mode_forces_alert(top_event, force_input, arith_would)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         top_event={top_event} force_test_alert_input={force_input} "
              f"arithmetic_would_alert={arith_would} "
              f"-> should_alert={got} (expected {expect})")
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

    print("\n== verdict-liveness commit-aware staleness (task #41, quiet-period fix) ==")
    for label, last_sha, head_sha, first_epoch, now_epoch, expect in STALE_MINUTES_SCENARIOS:
        got = compute_stale_minutes(last_sha, head_sha, first_epoch, now_epoch)
        ok = got == expect
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         last_verified_sha={last_sha} current_head_sha={head_sha} "
              f"first_unverified_epoch={first_epoch} now_epoch={now_epoch} "
              f"-> stale_minutes={got} (expected {expect})")
        if not ok:
            failures.append(label)

    total = (
        len(ALERT_SCENARIOS)
        + len(AGGREGATE_SCENARIOS)
        + len(LIVENESS_JOB_SCENARIOS)
        + len(TEST_MODE_SCENARIOS)
        + len(ESCALATION_SCENARIOS)
        + len(STALE_MINUTES_SCENARIOS)
    )
    if failures:
        print(f"\n{len(failures)}/{total} scenarios FAILED", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {total} scenarios PASS.")


if __name__ == "__main__":
    main()
