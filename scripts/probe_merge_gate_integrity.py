#!/usr/bin/env python3
"""probe_merge_gate_integrity.py — did every required check have REAL, pre-merge
compute, or did the merge decide on an object instead of a result?

Born 2026-08-21 from PENDING-ARMS idx~49 (`.claude/skills/modus/PENDING-ARMS.md`,
"Branch protection did not hold" / PR #3227). That investigation reproduced the
raw claim (57 check-runs, 19/25 required contexts not-green) but found the
2026-08-08 explanation attached to it could not be right: the `merge-queue-main`
ruleset it blamed was created 2h29m AFTER #3227 merged. The real mechanism,
measured: every check-suite for that PR's final commit was created 2-3 SECONDS
before the merge completed — the gate could not have looked at results that did
not exist yet. `run_started_at` on a workflow-run object is queue-CREATION time,
not compute-start time; a sampled job did not actually begin executing until 24
minutes after the run was created (superscar #2, "esiste != armato", applied to
a single check-run: the object existed, the result did not).

This script is the PASSIVE, non-provoking antidote the team-lead asked for
instead of a canary that would deliberately race a live merge on `main`: for
any commit that already landed, verify after the fact that every required
context had a `merge_group`-triggered job which (a) exists, (b) concluded
`success`, (c) had nonzero real execution duration, and (d) COMPLETED BEFORE
(within a small grace window of) the merge decision. It never provokes the
condition — it only detects whether it recurred.

WHY `merge_group`-triggered jobs specifically, not all check-runs on the merge
commit (measured live 2026-08-21, not assumed): under the current merge-queue
regime, GitHub's queue tests the merge commit BEFORE fast-forwarding `main` to
it, and those `merge_group`-event workflow runs land on that SAME final SHA —
confirmed on PR #4464 (28 merge_group runs, all `success`, all 46 jobs covering
every one of the 27 required contexts by EXACT name match, not substring — see
the corpus fixture). Separately, `push`-triggered runs ALSO fire on that same
SHA after the fast-forward (8 more on #4464) and are noise for this purpose:
they are the re-triggered, sometimes-cancelled runs the 2026-08-08 ledger
update already identified as misleading when counted together with everything
else. Filtering to `event=merge_group` is what makes this probe judge the
PRE-merge evaluation instead of post-merge chatter.

WHY A GRACE WINDOW around `merged_at` (measured, not assumed): on the same
#4464 innocence fixture, one legitimate job ("Test Summary") completed ONE
SECOND after the recorded merge timestamp — API/webhook propagation lag on a
healthy merge, not evidence of a race. A strict `completed_at <= merged_at`
would have been a guard-over-match (superscar #3) flagging a clean merge. The
historical #3227 case is not a close call either way: its gap was ~24 MINUTES,
three orders of magnitude past any reasonable grace window, and it has ZERO
merge_group runs at all (the queue did not exist yet) — the guilt case is
caught by "no gate evidence found", which needs no timing threshold whatsoever.

WHY EXACT job-name match against required contexts, not substring (superscar
#3 discipline applied to this tool itself): `comm -23` between the 27 required
context strings and the 46 merge_group job names on the innocence fixture
returned nothing missing under EXACT line equality — required contexts are the
literal job-name strings this repo already uses (including matrix suffixes
like "Frontend Tests (Next.js) (mouth, true)"), so substring matching would
only invite the guard-over-match this repo has paid for ten times already
(W68/W72/W73/.../W119 in cicatrix-superscar.md family #3).

SEGNALATORE, NON AUTO-ATTUATORE (same contract as pending_arms_report.py):
this script never writes, edits, arms, or blocks anything. It reads GitHub
Actions data (or an offline fixture) and reports a verdict. Wiring it to alert
on every push to `main` is a separate, deliberately thin workflow
(.github/workflows/merge-gate-integrity-watch.yml) that calls this script and
sends a Telegram P0 on a finding — never a merge-blocking check, both because
retroactive-by-construction detection cannot gate the merge it is checking,
and because a NEW gate that can itself misfire is exactly the risk this tool
exists to catch elsewhere, not reproduce here.

Usage:
    probe_merge_gate_integrity.py --sha <merge_commit_sha> [--merged-at <iso8601>]
    probe_merge_gate_integrity.py --fixture scripts/tests/fixtures/merge_gate_integrity/guilt_3227.json
    probe_merge_gate_integrity.py --sha <sha> --json

Exit codes:
    0   clean — every required context had real, pre-merge, successful compute
    1   VIOLATION — at least one required context did not (a genuine finding,
        including "zero merge_group runs at all" — that is a positive result,
        not a blind spot, and must never be conflated with exit 3)
    2   usage error (argparse's own exit code)
    3   CANNOT-VERIFY — a GitHub API call failed or returned unparseable data;
        "could not check" is never reported as "clean" (W106b)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

DEFAULT_GRACE_SECONDS = 30
PASSING_CONCLUSIONS = {"success"}


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _latest_completed_by_name(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse possibly-duplicate job entries (retries/re-queues) to the
    latest COMPLETED one per name, by completed_at. A job still in-progress
    (no completed_at) is never preferred over a completed sibling, and never
    substitutes for a missing completed result on its own."""
    best: dict[str, dict[str, Any]] = {}
    for job in jobs:
        name = job.get("name")
        if not name:
            continue
        if job.get("status") != "completed" or not job.get("completed_at"):
            continue
        prev = best.get(name)
        if prev is None or _parse_ts(job["completed_at"]) > _parse_ts(prev["completed_at"]):
            best[name] = job
    return best


def evaluate(
    merge_group_jobs: list[dict[str, Any]],
    required_contexts: Sequence[str],
    merged_at: str,
    grace_seconds: int = DEFAULT_GRACE_SECONDS,
) -> dict[str, Any]:
    """Pure function — no network. Returns {"clean": bool, "findings": [str],
    "merge_group_job_count": int}. See module docstring for why each rule
    exists and what live data it was measured against."""
    findings: list[str] = []

    if not merge_group_jobs:
        findings.append(
            "no merge_group workflow runs found for this merge commit — "
            "no evidence the branch-protection gate evaluated anything "
            "before the merge decision"
        )
        return {
            "clean": False,
            "findings": findings,
            "merge_group_job_count": 0,
        }

    merged_dt = _parse_ts(merged_at)
    deadline = merged_dt + timedelta(seconds=grace_seconds)
    latest = _latest_completed_by_name(merge_group_jobs)

    for ctx in required_contexts:
        job = latest.get(ctx)
        if job is None:
            findings.append(
                f"{ctx!r}: no completed merge_group job with this exact name "
                f"(never evaluated pre-merge)"
            )
            continue

        conclusion = job.get("conclusion")
        if conclusion not in PASSING_CONCLUSIONS:
            findings.append(f"{ctx!r}: conclusion={conclusion!r} (not success)")
            continue

        started_at = job.get("started_at")
        completed_at = job.get("completed_at")
        if not started_at or not completed_at:
            findings.append(f"{ctx!r}: missing started_at/completed_at on a completed job")
            continue

        started_dt = _parse_ts(started_at)
        completed_dt = _parse_ts(completed_at)
        duration = (completed_dt - started_dt).total_seconds()
        if duration <= 0:
            findings.append(
                f"{ctx!r}: zero/negative execution duration ({duration:.1f}s) — "
                f"looks like a phantom result, not real compute"
            )
            continue

        if completed_dt > deadline:
            late_by = (completed_dt - merged_dt).total_seconds()
            findings.append(
                f"{ctx!r}: completed {late_by:.1f}s after the merge decision "
                f"(grace={grace_seconds}s) — the gate could not have seen this result"
            )

    return {
        "clean": not findings,
        "findings": findings,
        "merge_group_job_count": len(merge_group_jobs),
    }


def _gh_api_json(path: str) -> Any:
    """Single-page fetch — returns the raw parsed JSON document."""
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed (rc={proc.returncode}): {proc.stderr[-400:]}")
    return json.loads(proc.stdout)


def _gh_api_paginated_stream(path: str, jq_filter: str) -> list[Any]:
    """Paginated fetch that STREAMS elements via a jq filter, never
    concatenates raw pages. `actions/runs?...` returns an OBJECT wrapping
    the array (`{"total_count": N, "workflow_runs": [...]}`) — `--paginate`
    with a bare `--jq '.'` prints that whole object once per page, and
    `list.extend(dict)` silently iterates its KEYS (strings), not its items.
    Measured live 2026-08-21: this exact mistake produced
    'string indices must be integers, not str' on the very first real
    invocation against Bali-Zero/Teman2. `jq_filter` must stream ONE JSON
    value per output line (e.g. `.workflow_runs[]`), which is what
    `--paginate` actually concatenates correctly across pages."""
    proc = subprocess.run(
        ["gh", "api", path, "--paginate", "--jq", jq_filter],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed (rc={proc.returncode}): {proc.stderr[-400:]}")
    out: list[Any] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def fetch_live(repo: str, sha: str, merged_at: Optional[str]) -> tuple[list[dict], list[str], str]:
    """Network path. Raises on any failure — callers map that to CANNOT-VERIFY,
    never to a silent 'clean'."""
    runs = _gh_api_paginated_stream(
        f"repos/{repo}/actions/runs?head_sha={sha}&event=merge_group&per_page=100",
        ".workflow_runs[]",
    )
    jobs: list[dict[str, Any]] = []
    for run in runs:
        run_id = run["id"]
        run_jobs = _gh_api_json(f"repos/{repo}/actions/runs/{run_id}/jobs")
        for job in run_jobs.get("jobs", []):
            jobs.append(
                {
                    "name": job.get("name"),
                    "status": job.get("status"),
                    "conclusion": job.get("conclusion"),
                    "started_at": job.get("started_at"),
                    "completed_at": job.get("completed_at"),
                }
            )

    protection = _gh_api_json(f"repos/{repo}/branches/main/protection")
    required = list(protection.get("required_status_checks", {}).get("contexts", []))

    if merged_at is None:
        # NOT commit.committer.date — measured live 2026-08-21 on PR #4464:
        # the merge commit's own committer date (19:58:37Z, when the queue
        # authored/tested it) landed 26 MINUTES before the PR's actual
        # `merged_at` (20:25:03Z, when GitHub fast-forwarded main to it) —
        # using the committer date as merged_at falsely flagged all 27
        # required contexts as "completed after the merge" on a fixture this
        # tool itself proved clean. The commit's own timestamp is a proxy
        # for when the queue STARTED testing it, not for the merge DECISION
        # (W106 family: a proxy frozen at the wrong moment). The authoritative
        # source is the associated PR's `merged_at`, via the dedicated
        # "commit -> pull requests" endpoint.
        pulls = _gh_api_json(f"repos/{repo}/commits/{sha}/pulls")
        merged = [p for p in pulls if p.get("merged_at")]
        if not merged:
            raise RuntimeError(
                f"no merged pull request found for commit {sha} — cannot determine "
                f"merged_at without --merged-at (a direct push or admin merge has no "
                f"associated PR to read it from)"
            )
        merged_at = max(p["merged_at"] for p in merged)

    return jobs, required, merged_at


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--sha", help="merge commit SHA on main to probe (live gh api)")
    src.add_argument("--fixture", help="path to an offline fixture JSON (see scripts/tests/fixtures/merge_gate_integrity/)")
    parser.add_argument("--repo", default="Bali-Zero/Teman2", help="owner/repo for --sha (default: Bali-Zero/Teman2)")
    parser.add_argument("--merged-at", default=None, help="ISO8601 merge timestamp; default: fetched from the commit's committer date")
    parser.add_argument("--grace-seconds", type=int, default=DEFAULT_GRACE_SECONDS, help=f"tolerance for a job completing shortly after merged_at (default {DEFAULT_GRACE_SECONDS}s — see module docstring for why this exists)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of prose")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        if args.fixture:
            with open(args.fixture) as f:
                data = json.load(f)
            jobs = data["merge_group_jobs"]
            required = data["required_contexts"]
            merged_at = args.merged_at or data["merged_at"]
            subject = data.get("merge_commit_sha", args.fixture)
        else:
            jobs, required, merged_at = fetch_live(args.repo, args.sha, args.merged_at)
            subject = args.sha
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure here is CANNOT-VERIFY
        if args.json:
            print(json.dumps({"verdict": "CANNOT-VERIFY", "error": str(exc)}))
        else:
            print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return 3

    result = evaluate(jobs, required, merged_at, grace_seconds=args.grace_seconds)

    if args.json:
        print(json.dumps({"subject": subject, "merged_at": merged_at, **result}, indent=2))
    else:
        verdict = "CLEAN" if result["clean"] else "VIOLATION"
        print(f"{verdict}: {subject} (merged_at={merged_at}, merge_group_jobs={result['merge_group_job_count']})")
        for finding in result["findings"]:
            print(f"  - {finding}")

    return 0 if result["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
