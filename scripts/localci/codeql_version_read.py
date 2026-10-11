#!/usr/bin/env python3
"""Version sentinel for the two CodeQL contexts: does the newest hosted CodeQL analysis of a language on main report the CLI the
matrix pins? Run by the localci runner at PLAN time on the host, from BASE, with the operator's gh (a read): hosted picks its CLI per
run by feature flag (2.27.1 -> 2.27.2 around 2026-10-09), and a local analysis on another CLI is not the hosted check.

    codeql_version_read.py --repo OWNER/NAME --language python|javascript --pin 2.27.2

Exit 0 = the newest analysis of that language on refs/heads/main reports the pin, is at most 7 days old, and the newest completed
security.yml run of the repository's own main (head_repository is the repo, head_branch main, event schedule or workflow_dispatch: a fork's
PR branch named main is not it) has this language's CodeQL job concluded success. Every other exit is "no verdict", never green:
3 = it reports another version (the line names both) · 4 = no analysis of that language in the newest page · 5 = the newest analysis is
older than 7 days (hosted has not analysed main since, so the CLI it runs now is unknown) · 6 = the newest completed security.yml run on
main has this language's job red (hosted main fails on this leg: a CLI upgrade that dies before it uploads shows here and nowhere else) ·
1 = a read failed (its stderr line starts with the CANNOT-VERIFY marker, which the runner asks again on, then gives up) · 2 = bad arguments.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys

CANNOT = "::error::codeql_version_read: CANNOT-VERIFY"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")   # and neither segment is "." or "..": they would climb out of the API path
LANG_RE = re.compile(r"^[a-z][a-z-]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PAGE = 100
MAX_AGE_DAYS = 7
WORKFLOW = "security.yml"
# The events on which security.yml runs a run whose head_branch is main of THIS repository, from its `on:` block (.github/workflows/security.yml):
# `push` lists branches [develop] only, `pull_request` and `merge_group` runs carry the PR's or the queue's ref, and `schedule` and
# `workflow_dispatch` run on the default branch. A fork's pull_request run can carry head_branch "main" too: it is neither this repository's nor these events.
MAIN_EVENTS = frozenset({"schedule", "workflow_dispatch"})


def fail(marker: str, msg: str, rc: int) -> int:
    print(f"{marker} {msg}", file=sys.stderr)
    return rc


def newest(analyses: list, category: str) -> dict | None:
    """The newest CodeQL analysis (by created_at) whose category is exactly `category`; None when the page holds none."""
    mine = [a for a in analyses if isinstance(a, dict) and a.get("category") == category and isinstance(a.get("created_at"), str)
            and isinstance(a.get("tool"), dict) and a["tool"].get("name") == "CodeQL"]   # another scanner can upload under the same category
    return max(mine, key=lambda a: a["created_at"]) if mine else None


def own_main_run(r: object, repo: str) -> bool:
    """A security.yml run of this repository's own main: the head repository is `repo` (a fork's run is not), the head branch is main, and the
    event is one that runs the workflow on main (MAIN_EVENTS)."""
    head = r.get("head_repository") if isinstance(r, dict) else None
    return (isinstance(r, dict) and isinstance(r.get("created_at"), str) and isinstance(r.get("id"), int) and r.get("head_branch") == "main"
            and r.get("event") in MAIN_EVENTS and isinstance(head, dict) and isinstance(head.get("full_name"), str) and head["full_name"].lower() == repo.lower())


def age_days(stamp: str, now: datetime.datetime) -> float | None:
    try:
        return (now - datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() / 86400
    except ValueError:
        return None


def gh_json(run, path: str):
    """The decoded answer of `gh api path`, or the CANNOT-VERIFY line (a str) saying why not."""
    try:
        res = run(["gh", "api", path], capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            return f"(read failed) gh api rc={res.returncode}: {res.stderr.strip()[-200:]}"
        return json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return f"(read failed) {type(e).__name__}"


def main(argv: list[str] | None = None, run=subprocess.run, now: datetime.datetime | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--pin", required=True)
    args = ap.parse_args(argv)
    if not (REPO_RE.match(args.repo) and LANG_RE.match(args.language) and VERSION_RE.match(args.pin)) or any(seg in (".", "..") for seg in args.repo.split("/")):
        return fail("::error::codeql_version_read:", "repo, language or pin is not in its plain shape", 2)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    doc = gh_json(run, f"repos/{args.repo}/code-scanning/analyses?ref=refs/heads/main&per_page={PAGE}")
    if isinstance(doc, str):
        return fail(CANNOT, doc, 1)
    if not isinstance(doc, list):
        return fail(CANNOT, "(read failed) the analyses answer is not a list", 1)
    category = f"/language:{args.language}"
    top = newest(doc, category)
    if top is None:
        return fail("::error::codeql_version_read: NO-ANALYSIS", f"none of the newest {PAGE} analyses on main has category {category}", 4)
    tool = top.get("tool") if isinstance(top.get("tool"), dict) else {}
    seen = tool.get("version")
    if seen != args.pin:
        return fail("::error::codeql_version_read: MISMATCH",
                    f"hosted CodeQL for {args.language} reports {seen!r} (analysis {top.get('id')}, {top['created_at']}); the matrix pins {args.pin!r}", 3)
    age = age_days(top["created_at"], now)
    if age is None:
        return fail(CANNOT, f"(read failed) analysis {top.get('id')} has an unreadable created_at {top['created_at']!r}", 1)
    if age > MAX_AGE_DAYS:
        return fail("::error::codeql_version_read: STALE",
                    f"the newest hosted {args.language} analysis on main (analysis {top.get('id')}, {top['created_at']}) is {int(age)} days old (limit {MAX_AGE_DAYS}): "
                    "the CLI hosted runs today is not known", 5)
    runs = gh_json(run, f"repos/{args.repo}/actions/workflows/{WORKFLOW}/runs?branch=main&status=completed&per_page={PAGE}")
    if isinstance(runs, str):
        return fail(CANNOT, runs, 1)
    rows = [r for r in (runs.get("workflow_runs") if isinstance(runs, dict) else None) or [] if own_main_run(r, args.repo)]
    if not rows:
        return fail(CANNOT, f"(read failed) no completed {WORKFLOW} run of {args.repo} main ({'/'.join(sorted(MAIN_EVENTS))}) in the answer", 1)
    last = max(rows, key=lambda r: r["created_at"])
    jobs = gh_json(run, f"repos/{args.repo}/actions/runs/{last['id']}/jobs?per_page=100")
    if isinstance(jobs, str):
        return fail(CANNOT, jobs, 1)
    job_name = f"CodeQL Analysis ({args.language})"
    mine = [j for j in (jobs.get("jobs") if isinstance(jobs, dict) else None) or [] if isinstance(j, dict) and j.get("name") == job_name]
    if len(mine) != 1:
        return fail(CANNOT, f"(read failed) run {last['id']} lists {len(mine)} jobs named {job_name!r}", 1)
    if mine[0].get("conclusion") != "success":
        return fail("::error::codeql_version_read: MAIN-RED",
                    f"the newest completed {WORKFLOW} run on main (run {last['id']}, {last['created_at']}) has {job_name!r} concluded "
                    f"{mine[0].get('conclusion')!r}: hosted main is red on this leg", 6)
    print(f"codeql_version_read: {args.language}: newest analysis {top.get('id')} ({top['created_at']}, {int(age)} days) reports {seen} == the pin; "
          f"{job_name!r} succeeded in the newest completed {WORKFLOW} run on main ({last['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
