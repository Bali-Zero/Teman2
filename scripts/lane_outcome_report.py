#!/usr/bin/env python3
"""Lane outcome report: measure whether a lane's merged work held up.

This script measures three things about squash-merged PRs in a time window:

1. Correction rate -- what fraction of merged commits are fixes that touch the
   same files as an earlier non-fix commit in the same window.  We use file
   overlap (after stripping high-churn paths) rather than a plain ``fix:`` prefix
   count, because a ``fix:`` commit that changes an unrelated surface is not a
   correction of anything in the window; counting it would reward relabelling.

2. Lane attribution -- how much of the merged work came from ``agent/<host>/<lane>/<task>``
   branches.  The source branch is not recoverable from git in this repo (only 2
   of 204 squash bodies mention an ``agent/`` branch), so attribution MUST come
   from the GitHub PR metadata via ``gh pr list``.  ``headRefName`` survives
   branch deletion, so it is the authoritative source.

3. Time to merge -- median and p90 hours from PR creation to merge.  This is
   named ``time_to_merge`` everywhere, never ``time_to_green``: true
   time-to-green requires check-suite history that this script does not fetch,
   and calling creation-to-merge "green" would be misleading.

The repo squash-merges, so ``git log --merges`` returns zero in any window.  We
use ``git log --first-parent origin/main`` and extract PR numbers from the
``(#NNNN)`` suffix that appears at the end of every squash subject.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


# `\Z`, not `$`: Python's `$` also matches just BEFORE a final newline, so
# `"fix: x (#42)\n"` was accepted although the marker is not at the literal end
# the function promises.
PR_SUFFIX_RE = re.compile(r"\(#(\d+)\)\Z")
# `[:(\s]`, not just `:` and `(`. `fix queue baseline census and public timing
# (#4047)` is a REAL squash subject in this repo and is plainly a fix; requiring
# conventional-commit punctuation dropped it from BOTH the numerator and the
# denominator. `fixup!` stays out (`u` is not in the class) and so does
# `prefix:` (the match is anchored at the start).
FIX_PREFIX_RE = re.compile(r"^fix[:(\s]")
AGENT_BRANCH_RE = re.compile(r"^agent/(?P<host>[^/]+)/(?P<lane>[^/]+)/(?P<task>.+)$")


@dataclass(frozen=True)
class Commit:
    """A single commit from ``git log --first-parent``."""

    sha: str
    ts: int
    subject: str
    pr: int | None


@dataclass(frozen=True)
class Chain:
    """A correction chain: a fix commit and the earliest overlapping origin commit."""

    fix_sha: str
    fix_pr: int | None
    origin_sha: str
    origin_pr: int | None
    shared: tuple[str, ...]


def parse_pr_number(subject: str) -> int | None:
    """Return the PR number anchored to the end of the squash subject, or None."""
    match = PR_SUFFIX_RE.search(subject)
    if match is None:
        return None
    return int(match.group(1))


def _git(args: list[str], cwd: str | None = None) -> str:
    """Run a git command and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"git failed: {' '.join(args)}\n{result.stderr}\n")
        raise SystemExit(3)
    return result.stdout.strip()


def commits_in_window(
    since: str,
    until: str,
    ref: str = "origin/main",
    repo_root: str | None = None,
) -> list[Commit]:
    """Return first-parent commits in the window, newest first (git order)."""
    fmt = "%H%x1f%ct%x1f%s"
    stdout = _git(
        ["log", "--first-parent", ref, f"--since={since}", f"--until={until}", f"--pretty=format:{fmt}"],
        cwd=repo_root,
    )
    commits: list[Commit] = []
    if not stdout:
        return commits
    for line in stdout.split("\n"):
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            continue
        sha, ts_str, subject = parts
        commits.append(
            Commit(
                sha=sha,
                ts=int(ts_str),
                subject=subject,
                pr=parse_pr_number(subject),
            )
        )
    return commits


def files_of(sha: str, repo_root: str | None = None) -> frozenset[str]:
    """Return the set of paths touched by a commit."""
    stdout = _git(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
        cwd=repo_root,
    )
    if not stdout:
        return frozenset()
    return frozenset(stdout.split("\n"))


def is_fix(subject: str) -> bool:
    """Return True if the subject starts with ``fix:`` or ``fix(``."""
    return FIX_PREFIX_RE.match(subject) is not None


def correction_chains(
    commits: list[Commit],
    files_for: Callable[[str], frozenset[str]],
    high_churn: frozenset[str] = frozenset(),
) -> list[Chain]:
    """Return correction chains for fix commits that overlap an earlier non-fix commit.

    A commit C is a correction iff ``is_fix(C.subject)`` and there exists an
    earlier commit E in the same window (earlier timestamp, or same timestamp but
    earlier list position) where ``not is_fix(E.subject)`` and the file overlap
    between E and C is non-empty after removing ``high_churn`` paths from both.
    The earliest such E is reported as the origin.
    """
    chains: list[Chain] = []
    cache: dict[str, frozenset[str]] = {}

    def _files(sha: str) -> frozenset[str]:
        if sha not in cache:
            cache[sha] = frozenset(p for p in files_for(sha) if p not in high_churn)
        return cache[sha]

    # ORDER IS THE WHOLE METRIC, and it must not be inherited from the caller.
    # `git log` returns NEWEST FIRST, so slicing `commits[:i]` gives the commits
    # AFTER commit i, not before it. Measured on the 2026-08-20..23 window while
    # this function still did that: it reported fix e952cd17 (ct 1787403089) as a
    # correction of "origin" 0c795f85 (ct 1787409648) — an origin one hour and
    # forty-nine minutes IN THE FUTURE of the fix that supposedly corrected it.
    # The metric was measuring the exact opposite of its own docstring, and it
    # would have kept doing so silently, because both numbers look plausible.
    #
    # Sorting HERE rather than trusting `commits_in_window` is deliberate: this
    # is a pure function and its contract should hold for any caller's ordering,
    # not only for the one that happens to feed it today. `reversed()` before the
    # stable sort makes the tie-break sane too — within one second git's order is
    # newest-first, so reversing puts the genuinely older one first and the stable
    # sort preserves that.
    commits = sorted(reversed(commits), key=lambda c: c.ts)

    seen_fixes: set[str] = set()
    for c_index, commit in enumerate(commits):
        if not is_fix(commit.subject):
            continue
        fix_files = _files(commit.sha)
        if not fix_files:
            continue
        if commit.sha in seen_fixes:
            # A duplicated commit in the input emitted the same chain twice and
            # inflated the rate. The report is about DISTINCT corrections.
            #
            # A refuter also asked for a `earlier.sha == commit.sha` guard against
            # a commit becoming its own origin. It was written, then REMOVED after
            # mutation proved it unreachable: `commits[:c_index]` excludes the
            # commit by index, and an origin must be a NON-fix commit while any
            # duplicate of a fix is itself a fix. Dead code that looks like a
            # guard is worse than no guard — it tells the next reader a case is
            # handled and stops them checking whether it can happen at all.
            continue
        origin: Commit | None = None
        for earlier in commits[:c_index]:
            if earlier.ts > commit.ts:
                # `>` and not `>=`: a merge queue lands several squash commits in
                # the SAME SECOND, and `>=` rejected every one of those pairs, so
                # a fix and the commit it corrected could never form a chain if
                # they landed together — a silent undercount precisely on the
                # busiest batches. Ties are resolved by list position instead,
                # which is well-defined because the slice is sorted oldest-first.
                # The docstring already promised exactly that and the code did
                # the opposite.
                #
                # Kept as a guard at all (rather than relying on the sort alone)
                # because it degrades the failure mode: with the sort removed,
                # this yields an EMPTY result instead of an INVERTED one, and the
                # corpus distinguishes the two — mutating sort-and-guard together
                # kills one more test than mutating the sort alone.
                continue
            if is_fix(earlier.subject):
                continue
            earlier_files = _files(earlier.sha)
            shared = fix_files & earlier_files
            if shared:
                origin = earlier
                break
        if origin is None:
            continue
        seen_fixes.add(commit.sha)
        chains.append(
            Chain(
                fix_sha=commit.sha,
                fix_pr=commit.pr,
                origin_sha=origin.sha,
                origin_pr=origin.pr,
                shared=tuple(sorted(shared)),
            )
        )
    return chains


def eligible_fix_commits(
    commits: list[Commit],
    files_for: Callable[[str], frozenset[str]],
    high_churn: frozenset[str] = frozenset(),
) -> int:
    """Fix-prefixed commits that COULD form a chain — the honest denominator.

    A fix whose only files are high-churn can never chain, by construction, so
    counting it below the line deflates the rate by exactly the number of fixes
    the noise filter made ineligible: the harder you tune the filter, the better
    the number looks. A metric that pays you to hide its own inputs.

    Extracted from `build_report` rather than left inline because a test cannot
    reach an expression buried in a function that also shells out to git — and a
    test that recomputes the rule instead of calling it proves only that the test
    can do arithmetic. That is exactly what happened: the first version of this
    corpus inlined the same comprehension and the mutation survived it.
    """
    return sum(
        1 for c in commits if is_fix(c.subject) and (frozenset(files_for(c.sha)) - high_churn)
    )


def _dedupe_prs(prs: list[dict]) -> list[dict]:
    """One row per PR number.

    `number` was fetched and never used. A duplicated entry counted twice in the
    attribution denominator (and once more in the numerator if it carried an
    agent branch), so `2/3` where the truth is `1/2`. Rows without a usable
    number are kept as-is rather than collapsed, since they cannot be shown to be
    duplicates of anything.
    """
    seen: set[int] = set()
    out: list[dict] = []
    for pr in prs:
        num = pr.get("number") if isinstance(pr, dict) else None
        if isinstance(num, int):
            if num in seen:
                continue
            seen.add(num)
        out.append(pr)
    return out


def attribution(prs: list[dict]) -> dict:
    """Bucket merged PRs by agent branch host/lane.

    Branch shape: ``agent/<host>/<lane>/<task>``.  PRs whose headRefName does not
    match that shape count toward ``total`` but not ``attributed``.
    """
    by_host: dict[str, int] = {}
    by_lane: dict[str, int] = {}
    attributed = 0
    total = len(prs)

    for pr in prs:
        head = pr.get("headRefName") or ""
        match = AGENT_BRANCH_RE.match(head)
        if not match:
            continue
        attributed += 1
        host = match.group("host")
        lane = match.group("lane")
        by_host[host] = by_host.get(host, 0) + 1
        by_lane[lane] = by_lane.get(lane, 0) + 1

    share = attributed / total if total else 0.0
    return {
        "total": total,
        "attributed": attributed,
        "share": share,
        "by_host": by_host,
        "by_lane": by_lane,
    }


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc)


def time_to_merge(prs: list[dict]) -> dict:
    """Return median and p90 hours from PR creation to merge."""
    deltas: list[float] = []
    negative = 0
    for pr in prs:
        created = _parse_iso(pr.get("createdAt"))
        merged = _parse_iso(pr.get("mergedAt"))
        if created is None or merged is None:
            continue
        hours = (merged - created).total_seconds() / 3600.0
        if hours < 0:
            # A merge before its own creation is clock skew or bad data, never a
            # latency. Letting it into the distribution can drag the median and
            # even the p90 negative — a statistic that reports a negative
            # duration has stopped measuring anything.
            negative += 1
            continue
        deltas.append(hours)

    n = len(deltas)
    if n == 0:
        return {"n": 0, "median_hours": 0.0, "p90_hours": 0.0, "negative_discarded": negative}

    sorted_deltas = sorted(deltas)
    median = sorted_deltas[n // 2] if n % 2 else (sorted_deltas[n // 2 - 1] + sorted_deltas[n // 2]) / 2
    # CEIL, not int(). `int((n-1)*0.9)` truncates, so at n=2 it indexes 0 and
    # reports the MINIMUM as the 90th percentile — deltas [1h, 100h] came back as
    # "p90 1h". A percentile that can return the smallest sample is not a
    # percentile. ceil puts it at the upper end for every small n, which is the
    # conservative direction for a latency statistic.
    p90_index = min(n - 1, math.ceil((n - 1) * 0.9))
    p90 = sorted_deltas[p90_index]
    return {
        "n": n,
        "median_hours": round(median, 2),
        "p90_hours": round(p90, 2),
        "negative_discarded": negative,
    }


def _fetch_prs(
    repo: str,
    since: str,
    until: str,
) -> list[dict]:
    """Fetch merged PR metadata from GitHub via ``gh``, one row per PR."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "-R",
            repo,
            "--state",
            "merged",
            "--json",
            "number,headRefName,mergedAt,createdAt,author,title",
            "--search",
            f"base:main merged:{since}..{until} sort:updated-desc",
            "--limit",
            "1000",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"gh pr list failed for {repo}:\n{result.stderr}\n")
        raise SystemExit(3)

    try:
        import json

        all_prs = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Could not parse gh output: {exc}\n")
        raise SystemExit(3)

    since_dt = _parse_iso(f"{since}T00:00:00Z")
    until_dt = _parse_iso(f"{until}T00:00:00Z")
    prs: list[dict] = []
    for pr in all_prs:
        merged_at = _parse_iso(pr.get("mergedAt"))
        if merged_at is None:
            continue
        if since_dt is not None and merged_at < since_dt:
            continue
        if until_dt is not None and merged_at >= until_dt:
            continue
        prs.append(pr)
    return prs


def render_markdown(report: dict, since: str, until: str, host: str) -> str:
    """Render a single markdown section matching the shape of SEAT-MIX.md dated blocks."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    g = report.get("git", {})
    a = report.get("attribution", {})
    t = report.get("time_to_merge", {})
    excluded = g.get("high_churn_excluded") or []

    # SUMMARY ONLY. The first version dumped the whole report, chain details
    # included — 200-plus lines of JSON into a document a human is supposed to
    # read, which is the same "nobody reads it" failure as not publishing at
    # all, wearing the opposite costume. The per-chain evidence stays in
    # `--json`, where a consumer that wants it can ask.
    lines = [
        f"## Lane outcomes ({host}, {since}..{until}, generated {ts})",
        "",
        "```",
        f"commits_in_window      {g.get('commits_in_window', 0)}"
        f"   (with a (#NNNN) merge marker: {g.get('commits_with_pr_suffix', 0)})",
        f"fix-prefixed commits   {g.get('fix_commits', 0)}"
        f"   (eligible to chain, i.e. touching a non-high-churn file: {g.get('fix_commits_eligible', 0)})",
        f"correction chains      {g.get('correction_chains', 0)}"
        f"   (rate over fix-prefixed: {g.get('correction_rate', 0.0)})",
        f"high-churn excluded    {', '.join(excluded) if excluded else '(none)'}",
        "",
        f"builder attribution    {a.get('attributed', 0)}/{a.get('total', 0)}"
        f"  ({a.get('share', 0.0) * 100:.1f}%)   source: {report.get('gh')}",
        f"  by host              {a.get('by_host') or '(none)'}",
        "",
        f"time to MERGE          n={t.get('n', 0)}  median {t.get('median_hours', 0.0)}h"
        f"  p90 {t.get('p90_hours', 0.0)}h",
        "```",
        "",
        "A correction chain is a `fix`-prefixed commit sharing at least one FILE with an",
        "earlier non-`fix` commit in the same window — never the subject prefix alone, which",
        "would reward relabelling. `time to MERGE` is creation-to-merge and is deliberately",
        "not called time-to-green: no check-suite history is fetched here.",
        "",
        "TWO POPULATIONS, on purpose and stated rather than blurred: the commit counts come",
        "from `git log --since/--until` (committer date, LOCAL timezone) and the attribution",
        "and merge-time counts come from the GitHub API filtered on `mergedAt` (UTC). They",
        "cover nearly the same set and not exactly the same set, so do not compute a ratio",
        "with a numerator from one and a denominator from the other.",
        "",
    ]
    return "\n".join(lines)


def separator_for(tail: bytes) -> str:
    """What must be written before an appended section, given the file's last bytes.

    Markdown wants a BLANK line before a heading and this repo's prettier check
    enforces it, so without one the tool generates output that fails the
    formatter — and every PR that ran `--write` would be blocked by the report it
    had just published. Measured: prettier's only complaint about the first
    generated section was exactly this missing line.

    A missing terminal newline is the worse case: the `## ` heading concatenates
    onto the document's last line and renders as prose, so the section is
    published and is not a section.

    Extracted rather than left inline because the write path hardcodes the
    document location, so a test could otherwise only reach this by writing to
    the real file. A rule no test can call is a rule nobody checks.
    """
    if not tail:
        return ""  # empty or new file: the heading may start at byte zero
    if not tail.endswith(b"\n"):
        return "\n\n"
    if not tail.endswith(b"\n\n"):
        return "\n"
    return ""


def _default_window() -> tuple[str, str]:
    """Return the last-7-day ISO date window ending today."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    until = now.date().isoformat()
    since = (now.date() - timedelta(days=7)).isoformat()
    return since, until


def build_report(
    since: str,
    until: str,
    repo: str = "Bali-Zero/Teman2",
    use_gh: bool = True,
    high_churn: frozenset[str] = frozenset(),
    repo_root: str | None = None,
) -> dict:
    """Assemble the whole report. Extracted from `main()` on purpose.

    While this lived inside `main` the only way to reach it was the CLI, so a
    test could assert on the process's stdout and on nothing else — including
    the shape of the dict, which is the part downstream readers consume. Logic
    reachable only through an argv parse is logic no corpus can hold still.
    """
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    commits = commits_in_window(since, until, repo_root=repo_root)
    prs: list[dict] = []
    gh_marker = "skipped" if not use_gh else "fetched"
    if use_gh:
        prs = _dedupe_prs(_fetch_prs(repo, since, until))

    files_for = lambda sha: files_of(sha, repo_root=repo_root)  # noqa: E731
    chains = correction_chains(commits, files_for=files_for, high_churn=high_churn)
    fix_count = sum(1 for c in commits if is_fix(c.subject))
    # A fix with no files left after the high-churn exclusion CANNOT chain, by
    # construction. Counting it in the denominator deflates the rate by exactly
    # the number of fixes the exclusion made ineligible — so the harder you tune
    # the noise filter, the better the rate looks, which is a metric that pays
    # you to hide its own inputs. The eligible count is reported alongside the
    # raw one rather than replacing it: both are true, and the difference is
    # itself information about how much of the window is ledger churn.
    eligible = eligible_fix_commits(commits, files_for, high_churn)

    return {
        "window": {"since": since, "until": until, "repo": repo},
        "git": {
            "commits_in_window": len(commits),
            "commits_with_pr_suffix": sum(1 for c in commits if c.pr is not None),
            "fix_commits": fix_count,
            "fix_commits_eligible": eligible,
            "correction_chains": len(chains),
            "correction_rate": round(len(chains) / eligible, 4) if eligible else 0.0,
            "correction_rate_over_all_fixes": round(len(chains) / fix_count, 4) if fix_count else 0.0,
            "high_churn_excluded": sorted(high_churn),
            "correction_chain_details": [
                {
                    "fix_sha": c.fix_sha,
                    "fix_pr": c.fix_pr,
                    "origin_sha": c.origin_sha,
                    "origin_pr": c.origin_pr,
                    "shared": list(c.shared),
                }
                for c in chains
            ],
        },
        "attribution": attribution(prs),
        "time_to_merge": time_to_merge(prs),
        "gh": gh_marker,
    }


def main(argv: list[str] | None = None) -> int:
    import json

    parser = argparse.ArgumentParser(
        description="Measure lane outcomes for squash-merged PRs in a window.",
    )
    default_since, default_until = _default_window()
    parser.add_argument("--since", default=default_since, help="ISO start date (default: last 7 days)")
    parser.add_argument("--until", default=default_until, help="ISO end date (default: today)")
    parser.add_argument("--repo", default="Bali-Zero/Teman2", help="GitHub repository slug")
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    parser.add_argument("--markdown", action="store_true", help="Emit markdown section to stdout")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append the markdown section to docs/factory/SEAT-MIX.md (the only write this program performs)",
    )
    parser.add_argument(
        "--high-churn",
        action="append",
        default=[],
        help="Repeatable path to exclude from file-overlap checks",
    )
    parser.add_argument("--no-gh", action="store_true", help="Skip all GitHub API calls")
    parser.add_argument("--host", default=os.environ.get("HOSTNAME", "unknown"), help="Host label")
    args = parser.parse_args(argv)

    if not args.json and not args.markdown and not args.write:
        sys.stderr.write("Nothing to do: specify --json, --markdown, and/or --write.\n")
        return 2

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Verify git is available.
    git_check = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
    if git_check.returncode != 0:
        sys.stderr.write("git is not available.\n")
        return 3

    if not args.no_gh:
        gh_check = subprocess.run(["gh", "--version"], capture_output=True, text=True, check=False)
        if gh_check.returncode != 0:
            sys.stderr.write("gh is not available.\n")
            return 3

    report = build_report(
        since=args.since,
        until=args.until,
        repo=args.repo,
        use_gh=not args.no_gh,
        high_churn=frozenset(args.high_churn),
        repo_root=repo_root,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))

    md = ""
    if args.markdown or args.write:
        md = render_markdown(report, args.since, args.until, args.host)
        if args.markdown:
            print(md)

    if args.write:
        target = os.path.join(repo_root, "docs", "factory", "SEAT-MIX.md")
        # A document whose last line has no terminal newline would have the new
        # `## ` heading concatenated onto it, producing a section that no markdown
        # renderer shows as a heading at all — a published report that silently
        # is not a report.
        # And a BLANK line before it, not merely a newline. Markdown wants one
        # before a heading, and this repo's prettier check enforces it — so
        # without this the tool generates output that fails the formatter, and
        # every PR that ran `--write` would be blocked by the report it just
        # published. Measured: prettier's only complaint about the first
        # generated section was exactly this missing blank line.
        tail = b""
        if os.path.exists(target) and os.path.getsize(target) > 0:
            with open(target, "rb") as fh:
                fh.seek(-min(2, os.path.getsize(target)), os.SEEK_END)
                tail = fh.read()
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(separator_for(tail))
            fh.write(md)
        sys.stderr.write(f"Appended to {target}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
