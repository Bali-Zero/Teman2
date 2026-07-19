#!/usr/bin/env python3
"""docs_inventory_refresh_liveness.py — liveness guardian for the
`.github/workflows/docs-inventory-refresh.yml` scheduled organ.

P3-prime (2026-07-17, research/operations/2026-07-17-push-pipeline-optimization-spec.md
§P3): making `inventory-check` deterministic (docs_audit.py's classify(), see its
module docstring) moves the docs-orphan TIME-CROSSING decision out of the PR gate
and into this scheduled organ — but that only helps if the organ actually keeps
running. GLM's panel review of the rejected `as_of`-pin design (§P3 Appendix)
named the exact failure this guards against: "cron credentials expire Friday;
Thursday's `as_of` remains valid and CI stays green indefinitely" — i.e. Esiste
!= Armato (cicatrix superscar #2): a scheduled workflow that silently stops
running is invisible from the PR gate's point of view (the gate only ever sees
whatever was last committed, however stale). This script is the "leggi anche lo
STATO DI ATTIVAZIONE" antidote applied to a GitHub-Actions-side organ: it alarms
if the organ hasn't SUCCEEDED in over 2x its own scheduled interval.

HEARTBEAT MECHANISM, AND WHY IT DIFFERS FROM THE PRO-SIDE GENOME PATTERN:
  Pro-side organs (e.g. infra/launchagents/wrappers/pro-git-pull-main.sh, "genome
  G2") write a JSON sidecar to `~/.organism/last_seen/<organ_id>.json` on every
  exit path — the simplest mechanism THERE because the host is long-running and
  owns persistent local storage a guardian can poll, and because there is no
  external ledger of "did the shell loop's last iteration actually finish".

  A GitHub Actions workflow has neither property: runners are ephemeral (no
  local disk survives between runs) and GitHub ALREADY keeps an authoritative,
  tamper-resistant execution ledger for every scheduled run (`gh run list`).
  Two heartbeat mechanisms were considered for this organ (both explicitly
  suggested by the mandate):
    (a) a committed JSON heartbeat file, updated on every run and read by any
        guardian via a plain git read — the direct GH-Actions analogue of the
        Pro-side sidecar.
    (b) the run history itself, via `gh run list`.
  (a) was REJECTED: to remain accurate it would need updating on EVERY
  scheduled run, including the (common) case where there was no doc drift to
  report — but docs-inventory-refresh.yml only pushes a commit/PR when
  `git diff` is non-empty (see its "Check drift" step). Making it commit a
  heartbeat-only change on every no-drift run would mean ~2 extra commits/PRs
  per day for a pure liveness ping, and — worse — committing that heartbeat
  would require either a direct push to `main` (a merge-bypass surface this
  repo does not otherwise have for this workflow, see I1/I5 in the P3-prime
  spec) or riding along inside the same auto-merge PR pipeline as real content
  changes, entangling two concerns that should stay independent.
  (b) was ADOPTED: GitHub's own run history is authoritative BY CONSTRUCTION
  (a run's `conclusion` cannot lie about whether the run actually executed and
  succeeded, unlike a self-reported sidecar file that some code path could
  forget to update) and costs this organ NOTHING extra to produce — it already
  exists the moment the schedule fires. Reading it needs only `gh` CLI (already
  used by this very organ to open its PR) with `actions:read`, no new secrets,
  no new commits, no coupling to the drift-detection logic. This is the
  "simplest mechanism a guardian can verify" the mandate asked to pick.

Usage:
  python3 scripts/docs_inventory_refresh_liveness.py \\
      --repo OWNER/NAME [--workflow docs-inventory-refresh.yml] \\
      [--max-age-hours 24] [--runs-json PATH]

  --repo is REQUIRED (no hardcoded default — see its --help text for why).

  --runs-json reads the `gh run list --json ...` payload from a file instead of
  shelling out to `gh` — used by the test suite (deterministic, no network) and
  available for manual replay of a captured payload.

Exit codes: 0 = alive (a successful run within max-age, AND no stuck flip-PR).
1 = overdue, never succeeded, OR a stuck flip-PR found (ALERT — the
caller/workflow decides how to page). 2 = could not determine liveness at all
(gh CLI missing/failed, malformed JSON) — this is DELIBERATELY distinct from
"1" so a caller can tell "the organ is unhealthy" apart from "I couldn't even
check", and never silently reports "OK" on either.

BLOCKER-4 fix (red-team 2026-07-18): the original version of this script only
checked whether the docs-inventory-refresh.yml WORKFLOW RUN reported
conclusion=="success" — but a run can succeed at the GH-Actions step level
while its actual EFFECT (the flip landing on main) never happens: the "Open
refresh PR" step used to swallow a `gh pr merge --auto` arming failure as a
mere `::warning::` (fixed separately, same red-team round — see that
workflow's own comment), which meant a PR could sit open-but-unarmed forever
with this guardian reporting green throughout. Liveness now checks TWO
independent things and alarms on either: (1) the workflow run itself
(check_liveness, unchanged), and (2) whether the organ's own bot-authored
flip-PR (branch prefix `docs/auto-sync-inventory-`, author
`app/github-actions` — both checked, not just one, to stay entity-matched
rather than a bare substring guess per this repo's guard-over/under-match
discipline) has been sitting OPEN longer than `--pr-max-age-hours` (default
48h, matching this repo's existing "TECH-DEBT >48h" PENDING-ARMS convention —
long enough to absorb normal CI latency, short enough that a genuinely stuck
PR pages before it's forgotten).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

# Two daily schedules 12h apart (docs-inventory-refresh.yml: "0 19 * * *" +
# "0 7 * * *") define the interval this organ is expected to run at. 2x that
# interval, per the mandate's explicit "allarme overdue se l'ultimo run
# riuscito e' piu' vecchio di 2x l'intervallo" — no extra jitter padding
# layered on top: if GitHub's own scheduling jitter (documented to be up to
# several minutes under load, occasionally more) proves this too tight in
# practice, widen it deliberately later with evidence, not preemptively here.
SCHEDULE_INTERVAL_HOURS = 12
DEFAULT_MAX_AGE_HOURS = 2 * SCHEDULE_INTERVAL_HOURS

# BLOCKER-4 fix: how long an organ-authored flip-PR may sit open before the
# EFFECT-check alarms. 48h matches this repo's existing PENDING-ARMS
# "TECH-DEBT >48h" convention (scripts/pending_arms_report.py) rather than
# inventing a new arbitrary number.
DEFAULT_PR_MAX_AGE_HOURS = 48.0
ORGAN_PR_BRANCH_PREFIX = "docs/auto-sync-inventory-"
ORGAN_PR_AUTHOR = "app/github-actions"


def latest_success(runs: List[Dict]) -> Optional[Dict]:
    """The most recent run with conclusion == 'success', or None if there
    isn't one in `runs` (never having succeeded, or simply not represented in
    however many rows were fetched)."""
    candidates = [r for r in runs if r.get("conclusion") == "success"]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.get("updatedAt") or r.get("createdAt") or "")


def _parse_gh_timestamp(raw: str) -> datetime:
    """`gh run list --json` timestamps are ISO-8601 UTC with a trailing 'Z'
    (e.g. '2026-07-17T19:03:11Z') — Python's fromisoformat wants '+00:00'."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def check_liveness(
    runs: List[Dict], now: datetime, max_age: timedelta
) -> Tuple[bool, str]:
    """Pure decision function — no I/O, so it's trivially testable with
    injected `runs`/`now`/`max_age` (including mocked dates, matching this
    repo's guilt+innocence discipline for date-sensitive guards).

    Returns (alive, message).
    """
    run = latest_success(runs)
    if run is None:
        return False, (
            "docs-inventory-refresh has NEVER completed successfully "
            f"(0 successful runs among the {len(runs)} most recent fetched) — "
            "the scheduled cron may never have fired, or every attempt failed."
        )
    ts_raw = run.get("updatedAt") or run.get("createdAt") or ""
    try:
        ts = _parse_gh_timestamp(ts_raw)
    except ValueError:
        return False, f"docs-inventory-refresh: unparseable timestamp {ts_raw!r} on run {run.get('databaseId', '?')}"
    age = now - ts
    if age > max_age:
        return False, (
            f"docs-inventory-refresh last succeeded {age} ago "
            f"(> {max_age} threshold = 2x its {SCHEDULE_INTERVAL_HOURS}h schedule "
            f"interval) — run {run.get('databaseId', '?')} at {ts_raw}. "
            "The organ may be silently disarmed (Esiste != Armato)."
        )
    return True, f"OK — docs-inventory-refresh last succeeded {age} ago (<= {max_age})"


def check_stuck_prs(
    prs: List[Dict],
    now: datetime,
    max_age: timedelta,
    branch_prefix: str = ORGAN_PR_BRANCH_PREFIX,
) -> Tuple[bool, str]:
    """Pure decision function (BLOCKER-4 EFFECT-check) — no I/O, mirrors
    check_liveness()'s testable shape. `prs` is expected pre-filtered to the
    organ's own author (see _fetch_open_organ_prs); this function ALSO
    re-checks the branch-name prefix itself (entity-matched, not a bare
    substring guess) as defense-in-depth against a future caller passing an
    unfiltered list.

    Returns (ok, message) — ok=True means "no stuck flip-PR", False means
    "found one" (the caller should treat this as an alarm condition, same as
    an overdue workflow run).
    """
    organ_prs = [
        pr for pr in prs if pr.get("headRefName", "").startswith(branch_prefix)
    ]
    if not organ_prs:
        return True, "OK — no open organ-authored flip-PR (nothing to be stuck)"
    stuck: List[Tuple[Dict, timedelta]] = []
    for pr in organ_prs:
        ts_raw = pr.get("createdAt", "")
        try:
            ts = _parse_gh_timestamp(ts_raw)
        except ValueError:
            return False, (
                f"docs-inventory-refresh: unparseable createdAt {ts_raw!r} on "
                f"open flip-PR #{pr.get('number', '?')} — treating as stuck "
                "(fail-closed: cannot prove it ISN'T stuck)."
            )
        age = now - ts
        if age > max_age:
            stuck.append((pr, age))
    if not stuck:
        return True, (
            f"OK — {len(organ_prs)} open organ flip-PR(s), all younger than {max_age}"
        )
    lines = [
        f"#{pr.get('number', '?')} ({pr.get('url', '?')}) open {age} "
        f"(> {max_age} threshold)"
        for pr, age in stuck
    ]
    return False, (
        f"docs-inventory-refresh: {len(stuck)} flip-PR(s) stuck OPEN past "
        f"the {max_age} threshold — the organ ran and opened them, but "
        "something downstream (auto-merge arm, required checks, a merge "
        "conflict) never landed the flip on main. Esiste != Armato at the "
        "PR level, not just the workflow-run level (BLOCKER-4). "
        + "; ".join(lines)
    )


def _fetch_open_organ_prs(
    repo: str, author: str = ORGAN_PR_AUTHOR, limit: int = 20
) -> List[Dict]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--author",
            author,
            "-L",
            str(limit),
            "--json",
            "number,headRefName,createdAt,url",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh pr list failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return json.loads(result.stdout)


def _fetch_runs_via_gh(repo: str, workflow: str, limit: int = 20) -> List[Dict]:
    result = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "-L",
            str(limit),
            "--json",
            "databaseId,status,conclusion,createdAt,updatedAt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh run list failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return json.loads(result.stdout)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo",
        required=True,
        help=(
            "OWNER/NAME, e.g. Balizero1987/Teman2 (this repo's actual GitHub slug — "
            "NOT 'Balizero1987/nuzantara', a name that reads plausible but is wrong; "
            "see memory reference_github_repo_slug_teman2). REQUIRED, no hardcoded "
            "default on purpose: a stale/guessed slug here would silently make this "
            "guardian always report 'never ran' against a repo that doesn't exist — "
            "exactly the kind of quiet failure this script exists to prevent "
            "elsewhere. The calling workflow always passes ${{ github.repository }}, "
            "which is authoritative by construction and costs it nothing."
        ),
    )
    p.add_argument(
        "--workflow",
        default="docs-inventory-refresh.yml",
        help="Workflow file basename to check (default: the P3-prime organ).",
    )
    p.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=f"Overdue threshold in hours (default {DEFAULT_MAX_AGE_HOURS} = "
        f"2x the {SCHEDULE_INTERVAL_HOURS}h schedule interval).",
    )
    p.add_argument(
        "--runs-json",
        default=None,
        help="Read the `gh run list --json ...` payload from this file instead "
        "of shelling out to `gh` (deterministic testing / replay).",
    )
    p.add_argument(
        "--pr-max-age-hours",
        type=float,
        default=DEFAULT_PR_MAX_AGE_HOURS,
        help="BLOCKER-4 EFFECT-check: how long an open organ-authored "
        f"flip-PR may sit unmerged before alarming (default "
        f"{DEFAULT_PR_MAX_AGE_HOURS}h).",
    )
    p.add_argument(
        "--pr-branch-prefix",
        default=ORGAN_PR_BRANCH_PREFIX,
        help=f"Branch-name prefix identifying the organ's own flip-PRs "
        f"(default {ORGAN_PR_BRANCH_PREFIX!r}, matches "
        "docs-inventory-refresh.yml's BRANCH= convention).",
    )
    p.add_argument(
        "--prs-json",
        default=None,
        help="Read the `gh pr list --json ...` payload from this file instead "
        "of shelling out to `gh` (deterministic testing / replay).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.runs_json:
            with open(args.runs_json, encoding="utf-8") as f:
                runs = json.load(f)
        else:
            runs = _fetch_runs_via_gh(args.repo, args.workflow)
    except Exception as exc:  # noqa: BLE001 — fail LOUD with an explicit exit 2
        print(f"docs_inventory_refresh_liveness: COULD NOT DETERMINE liveness: {exc}", file=sys.stderr)
        return 2

    # BLOCKER-4 fix: a second, independent I/O fetch for the EFFECT-check
    # (stuck flip-PRs) — kept as its own try/except so a failure here is
    # attributable ("couldn't fetch PRs" vs. "couldn't fetch runs") rather
    # than collapsed into one ambiguous error.
    try:
        if args.prs_json:
            with open(args.prs_json, encoding="utf-8") as f:
                prs = json.load(f)
        else:
            prs = _fetch_open_organ_prs(args.repo)
    except Exception as exc:  # noqa: BLE001 — fail LOUD with an explicit exit 2
        print(f"docs_inventory_refresh_liveness: COULD NOT DETERMINE stuck-PR status: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(tz=timezone.utc)
    max_age = timedelta(hours=args.max_age_hours)
    alive, run_message = check_liveness(runs, now, max_age)

    pr_max_age = timedelta(hours=args.pr_max_age_hours)
    no_stuck_pr, pr_message = check_stuck_prs(prs, now, pr_max_age, args.pr_branch_prefix)

    ok = alive and no_stuck_pr
    print(run_message, file=sys.stderr if not alive else sys.stdout)
    print(pr_message, file=sys.stderr if not no_stuck_pr else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
