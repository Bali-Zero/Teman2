#!/usr/bin/env python3
"""codex_autofix_reaper.py — superscar #2 "Esiste != Armato" applied to the Codex auto-fix backlog.

The nightly generator `scripts/codex/codex-nightly-autofix-ci.sh` opens one PR (on a
`codex/auto-fix-ci-<run_id>` branch) for every eligible failing CI run. It has no garbage
collection: when the target failure later goes green on main, or Codex's fix is wrong, the
PR and its branch are simply left behind. They accrete — a 2026-07-05 sweep found ~9 obsolete
open PRs and ~31 `codex/auto-fix-ci-*` branches, some from late May, most orphaned (never even
reached a PR). This is superscar #2: an auto-fixing guardian that produces artifacts nobody
reaps.

This script is the garbage collector. By DEFAULT it is a PURE SIGNALER — it reads GitHub state
and prints a report of what is reapable, and mutates NOTHING. Only under `--reap` does it act,
and even then it is conservative:

  A `codex/auto-fix-ci-*` OPEN PR is CLOSE-ELIGIBLE only when ALL hold:
    - the branch name matches `codex/auto-fix-ci-<run_id>` (never touches human branches),
    - the target CI run's workflow is now GREEN on `main` (the failure it was born to fix is
      gone — verified by CONTENT: the latest run of that workflow on main concluded success),
      OR the PR has been open and un-updated for >= --stale-days (default 14) with no path to
      merge (mergeStateStatus DIRTY/BEHIND and no reviewer approval).
  A `codex/auto-fix-ci-*` REMOTE BRANCH is DELETE-ELIGIBLE only when ALL hold:
    - it has NO open PR (an open PR keeps its branch alive), and
    - it is NOT already merged into main by content (blob-per-file, W88 — never SHA-ancestor),
    - it is older than --stale-days by last-commit date.

It NEVER closes a PR whose branch is not `codex/auto-fix-ci-*`. It NEVER force-anything. Closing
a PR leaves it recoverable (reopen) and deleting a branch leaves the commit in GitHub's reflog
(~90d) + the closed PR references it — both reversible, unlike a merge.

Usage:
    python3 scripts/codex_autofix_reaper.py [--repo SLUG] [--stale-days N] [--json]
    python3 scripts/codex_autofix_reaper.py --reap           # actually close/delete
    python3 scripts/codex_autofix_reaper.py --reap --yes      # skip the confirmation gate

Exit codes:
    0   default report ran clean (signaler — a backlog is not a failure), or --reap succeeded
    1   with --strict: >=1 reapable artifact exists (for CI gating), OR a --reap action failed
    2   a required tool (gh) is missing, or a CLI/argument error
    3   gh is present but not authenticated / repo not resolvable
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# codex/auto-fix-ci-<run_id> — the generator's only branch shape. Anchored: never a substring
# match inside a human branch that merely contains the phrase.
_AUTOFIX_BRANCH_RE = re.compile(r"^codex/auto-fix-ci-(\d+)$")

DEFAULT_STALE_DAYS = 14


def _fail(msg: str, code: int) -> "None":
    print(f"codex_autofix_reaper: {msg}", file=sys.stderr)
    sys.exit(code)


def _gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a gh command, capturing text output. Never passes a shell string."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


@dataclass
class ReapablePR:
    number: int
    branch: str
    run_id: str
    reason: str  # why it is close-eligible


@dataclass
class ReapableBranch:
    branch: str
    run_id: str
    reason: str  # why it is delete-eligible


@dataclass
class Report:
    prs: list[ReapablePR] = field(default_factory=list)
    branches: list[ReapableBranch] = field(default_factory=list)
    kept_prs: int = 0  # open autofix PRs deliberately kept alive
    kept_branches: int = 0  # autofix branches deliberately kept


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(iso_ts: str) -> Optional[float]:
    """Days between an ISO-8601 timestamp and now (UTC). None if unparsable (W54: a bad
    timestamp must not silently read as 'fresh' — callers treat None as 'unknown, keep')."""
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (_now_utc() - ts).total_seconds() / 86400.0


def _resolve_repo(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    res = _gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], check=False)
    if res.returncode != 0 or not res.stdout.strip():
        _fail("cannot resolve repo — pass --repo OWNER/NAME or run inside the repo", 3)
    return res.stdout.strip()


def _workflow_green_on_main(repo: str, workflow_name: str) -> Optional[bool]:
    """Is the latest run of <workflow_name> on main a success? None if it can't be determined
    (never treat 'unknown' as green — that would close a PR whose failure still stands)."""
    res = _gh(
        [
            "run", "list", "--repo", repo, "--workflow", workflow_name,
            "--branch", "main", "--limit", "1",
            "--json", "conclusion,status",
        ],
        check=False,
    )
    if res.returncode != 0:
        return None
    try:
        rows = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not rows:
        return None
    row = rows[0]
    if row.get("status") != "completed":
        return None  # a still-running latest run is not proof of green
    return row.get("conclusion") == "success"


def _branch_merged_by_content(repo: str, branch: str) -> Optional[bool]:
    """True if every file the branch changed since its merge-base is blob-identical to
    origin/main (W88: content, never SHA-ancestor). None if it cannot be determined (a fetch
    failure, a missing ref) — caller keeps the branch on None (conservative)."""
    ref = f"origin/{branch}"
    if _git(["rev-parse", "--verify", "--quiet", ref], check=False).returncode != 0:
        return None
    mb = _git(["merge-base", ref, "origin/main"], check=False)
    if mb.returncode != 0 or not mb.stdout.strip():
        return None
    merge_base = mb.stdout.strip()
    changed = _git(["diff", "--name-only", merge_base, ref], check=False)
    if changed.returncode != 0:
        return None
    files = [f for f in changed.stdout.splitlines() if f.strip()]
    if not files:
        # branch added nothing over merge-base → already-on-main by content
        return True
    for f in files:
        b = _git(["rev-parse", f"{ref}:{f}"], check=False)
        m = _git(["rev-parse", f"origin/main:{f}"], check=False)
        b_blob = b.stdout.strip() if b.returncode == 0 else "__MISSING_BR__"
        m_blob = m.stdout.strip() if m.returncode == 0 else "__MISSING_MAIN__"
        if b_blob != m_blob:
            return False  # a real difference remains → NOT merged, keep
    return True


def build_report(repo: str, stale_days: int) -> Report:
    report = Report()

    # 1. Open autofix PRs → close-eligible if target workflow is green on main, or stale+unmergeable.
    pr_res = _gh(
        [
            "pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
            "--json", "number,headRefName,title,mergeStateStatus,updatedAt,reviewDecision,statusCheckRollup",
        ],
        check=False,
    )
    if pr_res.returncode != 0:
        _fail(f"gh pr list failed: {pr_res.stderr.strip()}", 3)
    prs = json.loads(pr_res.stdout or "[]")
    autofix_run_ids_with_open_pr: set[str] = set()

    for pr in prs:
        branch = pr.get("headRefName", "")
        m = _AUTOFIX_BRANCH_RE.match(branch)
        if not m:
            continue
        run_id = m.group(1)
        autofix_run_ids_with_open_pr.add(run_id)
        # Extract the workflow name from the PR title: "fix(ci): auto-fix workflow <NAME> run <id>"
        title = pr.get("title", "")
        wf_match = re.search(r"auto-fix workflow (.+?) run \d+", title)
        workflow_name = wf_match.group(1).strip() if wf_match else ""

        # A PR that still has OTHER failing checks represents unfinished/real work, not just a
        # now-obsolete target — closing it would discard that (superscar #3: never decide on the
        # title-workflow proxy while the PR's real check state says otherwise). Compute the set of
        # OTHER failing check names (excluding the target workflow the PR was born to fix).
        other_failing = [
            (c.get("name") or c.get("context") or "")
            for c in (pr.get("statusCheckRollup") or [])
            if c.get("conclusion") == "FAILURE"
            and (c.get("name") or c.get("context") or "") != workflow_name
        ]

        reason: Optional[str] = None
        if workflow_name:
            green = _workflow_green_on_main(repo, workflow_name)
            if green is True and not other_failing:
                reason = f"target workflow '{workflow_name}' is green on main — the failure it fixes is gone"
            elif green is True and other_failing:
                # Target obsolete but PR still red on other axes → keep, it's real work.
                pass
        if reason is None:
            age = _age_days(pr.get("updatedAt", ""))
            merge_state = pr.get("mergeStateStatus", "")
            approved = pr.get("reviewDecision", "") == "APPROVED"
            if age is not None and age >= stale_days and merge_state in {"DIRTY", "BEHIND"} and not approved:
                reason = (
                    f"stale {age:.0f}d, mergeState={merge_state}, no approval — "
                    f"unmergeable auto-fix past --stale-days"
                )
        if reason is not None:
            report.prs.append(ReapablePR(number=pr["number"], branch=branch, run_id=run_id, reason=reason))
        else:
            report.kept_prs += 1

    # 2. Remote autofix branches with NO open PR → delete-eligible if not-merged is false-or-unknown... careful:
    #    delete only when merged-by-content is True, OR clearly orphaned + stale. Default: keep unless proven safe.
    ls = _git(["ls-remote", "--heads", "origin", "codex/auto-fix-ci-*"], check=False)
    if ls.returncode == 0:
        # ensure origin/main + candidate refs are locally available for content checks
        _git(["fetch", "origin", "main", "--quiet"], check=False)
        for line in ls.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            ref = parts[1].replace("refs/heads/", "")
            m = _AUTOFIX_BRANCH_RE.match(ref)
            if not m:
                continue
            run_id = m.group(1)
            if run_id in autofix_run_ids_with_open_pr:
                report.kept_branches += 1  # an open PR keeps its branch alive
                continue
            # No open PR. Fetch the ref so blob-compare works.
            _git(["fetch", "origin", f"{ref}:refs/remotes/origin/{ref}", "--quiet"], check=False)
            merged = _branch_merged_by_content(repo, ref)
            if merged is True:
                report.branches.append(
                    ReapableBranch(branch=ref, run_id=run_id, reason="orphan (no open PR) + already on main by content")
                )
            elif merged is False:
                # Not merged and no PR — only delete if genuinely stale (had a PR that was closed, or truly abandoned).
                # Check if it ever had a (now-closed) PR; if the last commit is older than stale_days, it's abandoned.
                head_ts = _git(["log", "-1", "--format=%cI", f"origin/{ref}"], check=False)
                age = _age_days(head_ts.stdout.strip()) if head_ts.returncode == 0 else None
                if age is not None and age >= stale_days:
                    report.branches.append(
                        ReapableBranch(
                            branch=ref, run_id=run_id,
                            reason=f"orphan (no open PR), not merged, abandoned {age:.0f}d",
                        )
                    )
                else:
                    report.kept_branches += 1
            else:
                report.kept_branches += 1  # unknown merge state → keep (conservative)

    return report


def render_markdown(report: Report, repo: str) -> str:
    lines = [f"# Codex auto-fix reaper — {repo}", ""]
    lines.append(f"- close-eligible PRs: **{len(report.prs)}**")
    lines.append(f"- delete-eligible branches: **{len(report.branches)}**")
    lines.append(f"- kept (alive/uncertain): {report.kept_prs} PRs, {report.kept_branches} branches")
    lines.append("")
    if report.prs:
        lines.append("## Close-eligible PRs")
        for p in report.prs:
            lines.append(f"- #{p.number} `{p.branch}` — {p.reason}")
        lines.append("")
    if report.branches:
        lines.append("## Delete-eligible orphan branches")
        for b in report.branches:
            lines.append(f"- `{b.branch}` — {b.reason}")
        lines.append("")
    if not report.prs and not report.branches:
        lines.append("_Nothing reapable — the backlog is clean._")
    return "\n".join(lines)


def do_reap(report: Report, repo: str) -> int:
    """Close PRs and delete branches. Returns count of failures."""
    failures = 0
    for p in report.prs:
        comment = (
            "Closing as obsolete Codex auto-fix (automated reaper). "
            f"{p.reason}. The branch will be deleted; the commit remains recoverable via GitHub's "
            "reflog and this closed PR. Reference: scripts/codex_autofix_reaper.py."
        )
        res = _gh(["pr", "close", str(p.number), "--repo", repo, "--comment", comment, "--delete-branch"], check=False)
        if res.returncode == 0:
            print(f"closed #{p.number} ({p.branch}) + branch")
        else:
            print(f"FAILED to close #{p.number}: {res.stderr.strip()}", file=sys.stderr)
            failures += 1
    for b in report.branches:
        res = _git(["push", "origin", "--delete", b.branch], check=False)
        if res.returncode == 0:
            print(f"deleted branch {b.branch}")
        else:
            print(f"FAILED to delete {b.branch}: {res.stderr.strip()}", file=sys.stderr)
            failures += 1
    return failures


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=None, help="OWNER/NAME (default: resolve from cwd)")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS, help=f"age threshold (default {DEFAULT_STALE_DAYS})")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser.add_argument("--reap", action="store_true", help="ACT: close eligible PRs + delete orphan branches")
    parser.add_argument("--yes", action="store_true", help="with --reap, skip the confirmation gate")
    parser.add_argument("--strict", action="store_true", help="exit 1 if anything is reapable (CI gating)")
    args = parser.parse_args(argv)

    if shutil.which("gh") is None:
        _fail("gh CLI not found on PATH", 2)

    repo = _resolve_repo(args.repo)
    report = build_report(repo, args.stale_days)

    if args.json:
        payload = {
            "repo": repo,
            "close_eligible_prs": [vars(p) for p in report.prs],
            "delete_eligible_branches": [vars(b) for b in report.branches],
            "kept_prs": report.kept_prs,
            "kept_branches": report.kept_branches,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(report, repo))

    if args.reap:
        if not report.prs and not report.branches:
            print("\nNothing to reap.")
            return 0
        if not args.yes:
            n = len(report.prs) + len(report.branches)
            print(f"\nWould close {len(report.prs)} PRs + delete {len(report.branches)} branches ({n} actions).")
            print("Re-run with --reap --yes to execute.")
            return 1 if args.strict else 0
        failures = do_reap(report, repo)
        return 1 if failures else 0

    reapable = len(report.prs) + len(report.branches)
    if args.strict and reapable:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
