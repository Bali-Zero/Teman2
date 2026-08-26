#!/usr/bin/env python3
"""spark_coverage_harvester.py — R7 harvester for codex/coverage-* branches.

Born 2026-08-27 alongside the fix for the pipefail crash in
scripts/codex/codex-nightly-coverage-improver.sh (see that file's own
2026-08-27 comment): for at least 10 straight nights that script wrote real,
test-only commits to a `codex/coverage-<module>-<timestamp>` branch and then
silently died one line before ever pushing or opening a PR. This harvester
is the other half of the repair — it does NOT fix why a branch has no PR
(that bug lives in the generator), it finds any branch that legitimately
has unmerged commits and no PR yet and opens one, so a transient harvester
outage or a half-finished generator run never strands real work forever.

Read-only w.r.t. the working tree it runs from — the only mutations are
`git push` of a branch that does not yet exist on the remote, and `gh pr
create`/`gh pr merge --auto` for that exact branch. Never force-pushes,
never touches a branch that already has a PR (open, closed, or merged),
never rewrites history.

Selection contract (guilt vs innocence, cicatrix family #3):
  - guilt:     a codex/coverage-* branch that ALREADY has a PR (any state)
               referencing it is SKIPPED, even if it has unmerged commits.
  - innocence: a codex/coverage-* branch with commits ahead of the base and
               NO PR anywhere is SELECTED.
  - a branch with zero commits ahead of the base (fully merged, or the
    generator aborted before committing) is never selected either way.

Usage:
    python3 scripts/army/spark_coverage_harvester.py [--repo PATH]
        [--remote origin] [--base main] [--repo-slug Balizero1987/Teman2]
        [--log-dir ~/logs/codex-coverage-improver] [--manual] [--dry-run]
        [--json]

`--manual` bypasses the 02:00-06:00 WITA automatic-run window (the nightly
plist itself never calls this harvester — that pairing is a follow-up, not
this repair — so `--manual` is what every invocation should pass until it
does). Without a TTY-facing reason to run outside the window, an
unattended/cron caller should omit `--manual` so a future automatic wiring
fails closed on the window rather than silently running around the clock.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

BRANCH_RE = re.compile(r"^codex/coverage-(?P<module>.+)-(?P<ts>\d{8}_\d{6})$")
WITA = ZoneInfo("Asia/Makassar")
AUTOMATIC_WINDOW_HOURS = range(2, 6)  # [02:00, 06:00) WITA


@dataclass
class Candidate:
    branch: str
    module: str
    ts: str
    commits_ahead: int
    on_remote: bool
    on_local: bool


@dataclass
class HarvestResult:
    branch: str
    action: str  # "opened" | "skipped-has-pr" | "skipped-no-commits" | "failed"
    pr_url: str | None = None
    detail: str = ""


def run(cmd: list[str], cwd: str | None = None, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def discover_candidates(repo: str, remote: str, base: str) -> list[Candidate]:
    """Enumerate codex/coverage-* branches, local and remote, deduped by name.

    A branch that exists in both places is one candidate — `on_remote` and
    `on_local` are independent booleans so the caller can decide whether a
    push is needed before `gh pr create`.
    """
    local_names = _list_refs(repo, "refs/heads/codex/coverage-*")
    remote_names = {
        n[len(f"{remote}/"):] for n in _list_refs(repo, f"refs/remotes/{remote}/codex/coverage-*")
        if n.startswith(f"{remote}/")
    }
    all_names = sorted(set(local_names) | remote_names)

    candidates: list[Candidate] = []
    for name in all_names:
        m = BRANCH_RE.match(name)
        if not m:
            continue  # not this generator's naming scheme — not ours to harvest
        ref_for_diff = name if name in local_names else f"{remote}/{name}"
        ahead = _commits_ahead(repo, ref_for_diff, f"{remote}/{base}")
        candidates.append(Candidate(
            branch=name,
            module=m.group("module"),
            ts=m.group("ts"),
            commits_ahead=ahead,
            on_remote=name in remote_names,
            on_local=name in local_names,
        ))
    return candidates


def _list_refs(repo: str, pattern: str) -> list[str]:
    res = run(["git", "-C", repo, "for-each-ref", "--format=%(refname:short)", pattern])
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def _commits_ahead(repo: str, ref: str, base_ref: str) -> int:
    res = run(["git", "-C", repo, "rev-list", "--count", f"{base_ref}..{ref}"])
    if res.returncode != 0:
        return 0
    try:
        return int(res.stdout.strip() or "0")
    except ValueError:
        return 0


def has_any_pr(repo_slug: str, branch: str) -> bool:
    """True if ANY PR (open, closed, or merged) already references this head.

    Deliberately NOT limited to --state open: a branch whose PR was closed
    without merging should not get a second PR opened behind its back, and
    a merged branch's commits_ahead is already 0 by the time this matters —
    this check is the belt to that suspenders, not a duplicate of it.
    """
    res = run(["gh", "pr", "list", "--repo", repo_slug, "--head", branch,
               "--state", "all", "--json", "number"])
    if res.returncode != 0:
        # gh unavailable/unauthenticated is NOT "no PR exists" — refuse to
        # guess. Caller treats this the same as "has a PR" (skip), which is
        # the fail-safe direction: worst case a real orphan waits one more
        # run, never a duplicate PR opened on a false negative.
        return True
    try:
        return bool(json.loads(res.stdout or "[]"))
    except json.JSONDecodeError:
        return True


def select_branches_to_harvest(
    candidates: list[Candidate], has_pr_fn,
) -> tuple[list[Candidate], list[HarvestResult]]:
    """Pure selection core — no git/gh I/O of its own, fully unit-testable.

    Returns (selected, already-decided results for the rest) so a caller
    gets a complete accounting even for branches it will never act on.
    """
    selected: list[Candidate] = []
    decided: list[HarvestResult] = []
    for c in candidates:
        if c.commits_ahead <= 0:
            decided.append(HarvestResult(c.branch, "skipped-no-commits",
                                          detail=f"{c.commits_ahead} commits ahead of base"))
            continue
        if has_pr_fn(c.branch):
            decided.append(HarvestResult(c.branch, "skipped-has-pr",
                                          detail="a PR already references this branch"))
            continue
        selected.append(c)
    return selected, decided


def guess_seat(log_dir: Path, ts: str) -> str:
    """Best-effort real seat for this run, read from codex's OWN transcript
    banner rather than assumed. The R7 spec names `codex-gpt-5.3-codex-spark`
    for this row, but that seat belongs to the READ-ONLY army.spark_lane
    lane (invoked with `-m gpt-5.3-codex-spark`) — this generator instead
    calls `codex --profile "$CODEX_PROFILE"` (default "power", which is not
    defined in any config.toml on this machine as of 2026-08-27, so codex
    silently falls back to whatever the top-level default model is on the
    night in question). Asserting the spec's seat label here without
    checking would be exactly the fabrication anti-hallucination discipline
    exists to catch — so this reads the log codex itself wrote.
    """
    log_path = log_dir / f"codex-output-{ts}.log"
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "codex (seat unknown — no matching transcript log)"
    m = re.search(r"^model:\s*(\S+)", text, re.MULTILINE)
    if not m:
        return "codex (seat unknown — transcript has no model banner)"
    return f"codex-{m.group(1)}"


def build_pr_body(c: Candidate, seat: str, log_dir: Path) -> str:
    diff_stat = ""
    log_path = log_dir / f"codex-output-{c.ts}.log"
    coverage_note = "not computed by this harvester (would require re-running coverage on this branch)"
    cov_json = log_dir / f"coverage-{c.ts[:8]}.json"
    if cov_json.is_file():
        try:
            data = json.loads(cov_json.read_text(encoding="utf-8"))
            for fname, info in data.get("files", {}).items():
                slug = fname.replace("/", "_").removesuffix(".py")
                if slug == c.module:
                    pct = info.get("summary", {}).get("percent_covered")
                    if pct is not None:
                        coverage_note = f"target file was at {pct:.1f}% coverage before this run (after-run % not re-measured by this harvester)"
                    break
        except (json.JSONDecodeError, OSError):
            pass

    return (
        "## Spark nightly coverage — harvested\n\n"
        f"**Branch:** `{c.branch}`\n"
        f"**Module slug:** `{c.module}`\n"
        f"**Commits ahead of base:** {c.commits_ahead}\n"
        f"**Coverage:** {coverage_note}\n\n"
        "This branch was generated by `scripts/codex/codex-nightly-coverage-improver.sh` "
        "and left without a PR by the pipefail bug fixed in this same PR series "
        "(see `scripts/codex/codex-nightly-coverage-improver.sh`'s 2026-08-27 comment "
        "on the `NON_TEST_CHANGES` line) — this harvester found it dangling with real, "
        "unmerged commits and opened the PR the generator should have.\n\n"
        f"lanes: [{{lane: build, role: build, seat: {seat}}}]\n\n"
        "### Verification\n"
        "- [ ] CI green (especially the new test cases)\n"
        "- [ ] Manual review\n\n"
        "🤖 Harvested by `scripts/army/spark_coverage_harvester.py` (R7)\n"
        f"{diff_stat}"
    )


def in_automatic_window(now: float | None = None) -> bool:
    ts = now if now is not None else time.time()
    dt = datetime.datetime.fromtimestamp(ts, tz=WITA)
    return dt.hour in AUTOMATIC_WINDOW_HOURS


def harvest(repo: str, remote: str, base: str, repo_slug: str, log_dir: Path,
            dry_run: bool) -> list[HarvestResult]:
    candidates = discover_candidates(repo, remote, base)
    selected, results = select_branches_to_harvest(
        candidates, lambda b: has_any_pr(repo_slug, b))

    for c in selected:
        if dry_run:
            results.append(HarvestResult(c.branch, "would-open",
                                          detail="--dry-run: no push/PR performed"))
            continue

        if not c.on_remote:
            push = run(["git", "-C", repo, "push", "-u", remote, c.branch])
            if push.returncode != 0:
                results.append(HarvestResult(c.branch, "failed",
                                              detail=f"push failed: {push.stderr.strip()[:300]}"))
                continue

        seat = guess_seat(log_dir, c.ts)
        title = f"test(coverage): {c.module} — Spark nightly"
        body = build_pr_body(c, seat, log_dir)
        pr = run(["gh", "pr", "create", "--repo", repo_slug, "--base", base,
                  "--head", c.branch, "--title", title, "--body", body])
        if pr.returncode != 0:
            results.append(HarvestResult(c.branch, "failed",
                                          detail=f"gh pr create failed: {pr.stderr.strip()[:300]}"))
            continue
        pr_url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else ""
        # Arm auto-merge NAKED (no --squash — the merge queue rejects every
        # strategy flag) so it merges only once CI actually goes green on
        # its own; never a forced/admin merge.
        num = pr_url.rstrip("/").rsplit("/", 1)[-1]
        run(["gh", "pr", "merge", num, "--auto"])
        results.append(HarvestResult(c.branch, "opened", pr_url=pr_url))

    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--remote", default="origin")
    p.add_argument("--base", default="main")
    p.add_argument("--repo-slug", default="Balizero1987/Teman2")
    p.add_argument("--log-dir", default=str(Path.home() / "logs" / "codex-coverage-improver"))
    p.add_argument("--manual", action="store_true",
                   help="bypass the 02:00-06:00 WITA automatic-run window")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if not args.manual and not in_automatic_window():
        msg = "outside the 02:00-06:00 WITA automatic window and --manual not passed — refusing to run"
        if args.json:
            print(json.dumps({"error": msg}))
        else:
            print(f"SKIP: {msg}", file=sys.stderr)
        return 1

    results = harvest(args.repo, args.remote, args.base, args.repo_slug,
                       Path(args.log_dir).expanduser(), args.dry_run)

    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2))
    else:
        if not results:
            print("no codex/coverage-* branches found — nothing to harvest")
        for r in results:
            line = f"{r.action}: {r.branch}"
            if r.pr_url:
                line += f" -> {r.pr_url}"
            if r.detail:
                line += f" ({r.detail})"
            print(line)

    return 0 if all(r.action != "failed" for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
