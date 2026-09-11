#!/usr/bin/env python3
"""
Task #19 guilt/innocence proof for .github/workflows/fly-deploy.yml's
post-deploy-health job.

NOT a general GitHub Actions expression interpreter — deliberately narrow,
same "known limit" style as scripts/check_watcher_coverage.py. This
hand-encodes the semantics of exactly ONE job's needs:/if: pair as it
exists in this repo today:

    needs: [deploy, run-sql-v2-migrations-post-deploy, run-python-migrations]
    if: |
      always() &&
      needs.deploy.result == 'success'

Bug this replaces (pre-fix): needs: [deploy, run-python-migrations], no
if: at all. Default GitHub Actions job-scheduling rule (from GitHub's docs,
confirmed before building, not assumed): a job is SKIPPED by default if ANY
of its needs: jobs did not succeed — failure OR skipped both count as "did
not succeed". So a post-deploy migration failure (or a skip cascading from
an EARLIER migration job failing) silently skipped this job — the job that
owns BOTH the health check AND the automatic `flyctl releases rollback`.
Skipped is not failed, so nothing downstream fired either: no rollback, no
"deploy fallito" alert. The only signal was the migration job's own local
alert, which reads as "one problem reported" while the automated recovery
silently never ran.

Fix: gate on `deploy` alone via always() + an explicit result check — same
idiom deploy-failure-alert already uses lower in this file. Health-check's
job is to assess the LIVE service, independent of whether ITS post-deploy
migrations succeeded, so migration outcome is deliberately excluded from
the if: condition; the two migration jobs stay in needs: for explicit
ordering only (they were already transitively ordered ahead of this job,
so this doesn't change *when* it runs, only *whether*).

Self-check: if a future edit changes this job's needs:/if: in the YAML,
this script fails loudly (exit 2) instead of silently proving the wrong
thing — it does not try to re-derive the logic below from the YAML, it
only detects that the YAML no longer matches what the logic below assumes.

Follow-up (2026-07-26, same task, reviewer-caught): the two success-
notification steps are also modeled and self-checked below. Bug: the
"Notifica Telegram — deploy OK" step's `if: success()` reflects only THIS
job's own step outcomes — it does not read `needs.*.result` at all. Before
this job could run on a migration-failure path (the fix above), that path
always SKIPPED this job, so no success message could ever fire next to a
failure one. After the fix, a healthy service + a failed migration produces
BOTH: the migration job's own 🔴 alert, then an unqualified ✅ — a green
message arriving after a red one reads as "resolved, disregard the above,"
which is false. Fix: split into a clean-success step (gated on both
migration jobs' results, not just step success) and a degraded-success step
with its own message (service healthy, named migration failed, schema state
unverified).
"""
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fly-deploy.yml"
JOB_NAME = "post-deploy-health"

EXPECTED_NEEDS = ["deploy", "run-sql-v2-migrations-post-deploy", "run-python-migrations"]
EXPECTED_IF = "always() &&\nneeds.deploy.result == 'success'"

CLEAN_SUCCESS_STEP = "Notifica Telegram — deploy OK"
EXPECTED_CLEAN_SUCCESS_IF = (
    "success() &&\n"
    "needs.run-python-migrations.result == 'success' &&\n"
    "needs.run-sql-v2-migrations-post-deploy.result == 'success'"
)

DEGRADED_SUCCESS_STEP = "Notifica Telegram — deploy sano, migration post-deploy degradata"
EXPECTED_DEGRADED_SUCCESS_IF = (
    "success() &&\n"
    "(needs.run-python-migrations.result != 'success' ||\n"
    "needs.run-sql-v2-migrations-post-deploy.result != 'success')"
)


def _normalize(s: str) -> str:
    return re.sub(r"[ \t]+", "", s)


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

    needs = job.get("needs")
    if needs != EXPECTED_NEEDS:
        print(
            f"FATAL: {JOB_NAME}.needs drifted from what this script models.\n"
            f"  expected: {EXPECTED_NEEDS}\n"
            f"  actual:   {needs}\n"
            "  This script proves reachability for the OLD needs/if shape.\n"
            "  Update EXPECTED_NEEDS and the reachability logic below to match\n"
            "  the new YAML before trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    if_raw = (job.get("if") or "").strip()
    if _normalize(if_raw) != _normalize(EXPECTED_IF):
        print(
            f"FATAL: {JOB_NAME}.if drifted from what this script models.\n"
            f"  expected: {EXPECTED_IF!r}\n"
            f"  actual:   {if_raw!r}\n"
            "  Update EXPECTED_IF and the reachability logic below to match\n"
            "  the new YAML before trusting this script's verdict again.",
            file=sys.stderr,
        )
        sys.exit(2)

    for step_name, expected_if in (
        (CLEAN_SUCCESS_STEP, EXPECTED_CLEAN_SUCCESS_IF),
        (DEGRADED_SUCCESS_STEP, EXPECTED_DEGRADED_SUCCESS_IF),
    ):
        step = _step_by_name(job, step_name)
        if step is None:
            print(
                f"FATAL: step '{step_name}' not found in job '{JOB_NAME}'.\n"
                "  This script's success-message split proof assumes this step\n"
                "  exists by this exact name — a rename silently breaks it.",
                file=sys.stderr,
            )
            sys.exit(2)
        step_if = (step.get("if") or "").strip()
        if _normalize(step_if) != _normalize(expected_if):
            print(
                f"FATAL: step '{step_name}'.if drifted from what this script models.\n"
                f"  expected: {expected_if!r}\n"
                f"  actual:   {step_if!r}\n"
                "  Update the EXPECTED_*_SUCCESS_IF constant and the\n"
                "  success_message_kind() logic below to match the new YAML\n"
                "  before trusting this script's verdict again.",
                file=sys.stderr,
            )
            sys.exit(2)


def job_runs(deploy_result: str) -> bool:
    """Models: `always() && needs.deploy.result == 'success'`.

    always() lifts the default "skip if any need didn't succeed" gate, so
    the two migration jobs' results play no role here by design — only
    deploy's result decides whether this job is evaluated at all.
    """
    return deploy_result == "success"


def rollback_and_alert_fire(job_ran: bool, health_check_passed: bool) -> bool:
    """Models the two untouched downstream steps once the job runs:

    Rollback step:      if: failure() && steps.health_check.outputs.healthy == 'false'
    "deploy fallito":    if: failure()

    `failure()` at step level is true iff a prior step in THIS job failed.
    health_check is the first step with real logic, so both conditions
    collapse to "health_check step failed" whenever the job actually ran.
    """
    if not job_ran:
        return False
    return not health_check_passed


def success_message_kind(
    job_ran: bool,
    health_check_passed: bool,
    py_migrations_result: str,
    sqlv2_migrations_result: str,
) -> str:
    """Models the two success-notification steps' if: conditions.

    Returns 'clean', 'degraded', or 'none'. Both steps share the same
    `success()` gate (health_check passed, i.e. no prior step in this job
    failed) — `success()` on its own cannot distinguish clean from degraded,
    since it never reads `needs.*.result`. That is exactly the bug this
    follow-up closes: the split reads the two migration jobs' results
    explicitly, so a healthy-but-migration-failed deploy gets the degraded
    message instead of silently reusing the unqualified one.
    """
    if not (job_ran and health_check_passed):
        return "none"
    migrations_clean = (
        py_migrations_result == "success" and sqlv2_migrations_result == "success"
    )
    return "clean" if migrations_clean else "degraded"


# (label, deploy, run_sql_v2_migrations_post_deploy, run_python_migrations,
#  expect_job_runs)
JOB_SCENARIOS = [
    (
        "GUILT 1 — run-python-migrations fails directly (case named in the task)",
        "success", "success", "failure", True,
    ),
    (
        "GUILT 2 — run-sql-v2-migrations-post-deploy fails, skipping "
        "run-python-migrations as a consequence (2nd entry point, found while building)",
        "success", "failure", "skipped", True,
    ),
    (
        "INNOCENCE 1 — clean deploy, both migration jobs succeed",
        "success", "success", "success", True,
    ),
    (
        "INNOCENCE 2 — deploy itself fails: no new image shipped, nothing to "
        "health-check or roll back (deploy-failure-alert owns this case instead)",
        "failure", "skipped", "skipped", False,
    ),
    (
        "INNOCENCE 3 — deploy itself skipped (pre-deploy run-migrations blocked it)",
        "skipped", "skipped", "skipped", False,
    ),
    (
        "INNOCENCE 4 — deploy itself cancelled (its own timeout-minutes kill, or "
        "the workflow run was cancelled): no new image shipped, nothing to "
        "health-check or roll back, same as INNOCENCE 2's deploy=failure sibling "
        "(deploy-failure-alert's widened if:, PR #5434, owns this case instead — "
        "job_runs() already returns False here by construction, since it checks "
        "only deploy_result == 'success'; this scenario was previously unmodeled)",
        "cancelled", "skipped", "skipped", False,
    ),
]

# (label, job_ran, health_check_passed, expect_rollback_and_alert)
DOWNSTREAM_SCENARIOS = [
    (
        "GUILT — job reached (via GUILT 1/2 above) and the new image fails health "
        "check: rollback + 'deploy fallito' alert must fire",
        True, False, True,
    ),
    (
        "INNOCENCE — job reached and the new image is healthy: no rollback, no "
        "failure alert (the 'deploy OK' step fires instead)",
        True, True, False,
    ),
    (
        "INNOCENCE — job never reached at all: nothing downstream can fire",
        False, False, False,
    ),
]

# (label, job_ran, health_check_passed, py_migrations_result,
#  sqlv2_migrations_result, expect_kind)
SUCCESS_MESSAGE_SCENARIOS = [
    (
        "GUILT — service healthy but run-python-migrations failed: MUST NOT be "
        "an unqualified success (the contradiction the reviewer caught: a green "
        "message after a red one reads as 'resolved, disregard the above')",
        True, True, "failure", "success", "degraded",
    ),
    (
        "GUILT — service healthy but run-sql-v2-migrations-post-deploy failed "
        "(and run-python-migrations transitively skipped): MUST NOT be an "
        "unqualified success",
        True, True, "skipped", "failure", "degraded",
    ),
    (
        "GUILT — service healthy but BOTH migration jobs failed: MUST NOT be an "
        "unqualified success",
        True, True, "failure", "failure", "degraded",
    ),
    (
        "INNOCENCE — clean deploy: service healthy, both migration jobs "
        "succeeded — the unqualified success message",
        True, True, "success", "success", "clean",
    ),
    (
        "INNOCENCE — health check itself failed: neither success step fires "
        "(the failure+rollback path owns this case)",
        True, False, "success", "success", "none",
    ),
    (
        "INNOCENCE — job never reached: neither success step fires",
        False, False, "success", "success", "none",
    ),
]


def main() -> None:
    self_check()

    failures = []

    print("== job reachability (needs:/if: on post-deploy-health) ==")
    for label, deploy, sqlv2, pymig, expect_runs in JOB_SCENARIOS:
        got = job_runs(deploy)
        ok = got == expect_runs
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         deploy={deploy} sql-v2={sqlv2} py-migrations={pymig} "
              f"-> job_runs={got} (expected {expect_runs})")
        if not ok:
            failures.append(label)

    print("\n== downstream composition (rollback + alert, steps unchanged by this fix) ==")
    for label, job_ran, health_ok, expect_fire in DOWNSTREAM_SCENARIOS:
        got = rollback_and_alert_fire(job_ran, health_ok)
        ok = got == expect_fire
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         job_ran={job_ran} health_check_passed={health_ok} "
              f"-> rollback_and_alert_fire={got} (expected {expect_fire})")
        if not ok:
            failures.append(label)

    print("\n== success-message split (clean vs degraded, 2026-07-26 follow-up) ==")
    for label, job_ran, health_ok, py_res, sqlv2_res, expect_kind in SUCCESS_MESSAGE_SCENARIOS:
        got = success_message_kind(job_ran, health_ok, py_res, sqlv2_res)
        ok = got == expect_kind
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         job_ran={job_ran} health_check_passed={health_ok} "
              f"py-migrations={py_res} sql-v2={sqlv2_res} "
              f"-> kind={got!r} (expected {expect_kind!r})")
        if not ok:
            failures.append(label)

    total = len(JOB_SCENARIOS) + len(DOWNSTREAM_SCENARIOS) + len(SUCCESS_MESSAGE_SCENARIOS)
    if failures:
        print(f"\n{len(failures)}/{total} scenarios FAILED", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {total} scenarios PASS.")


if __name__ == "__main__":
    main()
