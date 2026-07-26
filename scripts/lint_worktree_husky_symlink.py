#!/usr/bin/env python3
"""lint_worktree_husky_symlink.py — detector for worktrees missing the `.husky/_`
pre-push-gate symlink (superscar family #2, "Esiste != Armato", silent-skip subclass).

`core.hooksPath` in this repo is set to the RELATIVE path `.husky/_`. Git resolves a
relative hooksPath against whichever worktree it is currently operating from — every
`git worktree` shares the same repo config, but each has its own independent working
copy. `.husky/_` is husky's generated shim directory, produced by `npm install`'s
postinstall hook in the MAIN checkout; it is untracked (gitignored), so a bare
`git worktree add` never creates it. When a worktree's `.husky/_` does not resolve to a
real directory, git's hook lookup finds nothing there and silently proceeds as if no
hooks were configured at all: no banner, no error, no suite — `git push` just exits 0.
That is the worst shape a gate can fail in: the push *looks* green because nothing ran,
not because something passed and was recorded honestly.

The cure already exists and is mandatory: `scripts/agent_start.py`'s `SYMLINK_TARGETS`
links `.husky/_` (alongside `.venv`, `.env`, `node_modules`) into every worktree it
creates, and CLAUDE.md requires every agent worktree to be created through that broker.
What did NOT exist, until this script, was DETECTION of the case where that mandate was
bypassed — a worktree "born blind" to its own missing gate. This script is a pure
reporter over that gap. It does not fix anything.

    Report, don't auto-repair. Same discipline as pending_arms_report.py: a detector
    that silently fixes worktrees hides how often the broker is being bypassed, which
    is the signal worth having. If you want the cure, delete the worktree and recreate
    it via `python scripts/agent_start.py`, or manually symlink `.husky/_` yourself and
    re-run this detector to confirm.

## Origin classification and the claude-harness exemption question (decided, not silent)

Every worktree is classified by *where it lives*, not by name pattern alone:

  - `main`               — the repo root itself (always healthy by construction; npm
                            install runs there, `.husky/_` is real, not a symlink).
  - `broker`              — under `<repo>/.worktrees/`, with an `.agent-task.json`
                            sidecar: created by `scripts/agent_start.py` as designed.
  - `broker-path-no-metadata` — under `<repo>/.worktrees/` but NO `.agent-task.json`:
                            almost certainly a bare `git worktree add` targeting the
                            conventional directory, bypassing the broker's symlink step
                            while imitating its location. This is the exact shape this
                            script's own author produced earlier in the session that
                            motivated building this detector.

                            NOTE: `scripts/agent_start.py` runs `git worktree add` FIRST
                            (which makes the worktree visible to `git worktree list`
                            immediately) and `_create_symlinks()` as a later step in the
                            same run -- so a *genuinely* broker-created worktree can
                            transiently classify here (and show a MISSING `.husky/_`
                            finding) for the seconds between those two steps. This is
                            real, true point-in-time state, not a bug in this script or
                            in the broker -- a live scan of a fleet under concurrent
                            creation will occasionally catch one mid-setup. Don't "fix"
                            an isolated flap by adding a grace-period fudge; if this
                            classification is EVER still present on a re-scan a minute
                            later, that's the real finding.
  - `claude-harness`      — under `<repo>/.claude/worktrees/`: Claude Code's OWN native
                            worktree mechanism, distinct from this repo's broker. Covers
                            both `wf_*` Workflow-tool dispatches and named/labeled
                            session worktrees (which may carry a `locked` annotation).
  - `external`            — outside the repo tree entirely (e.g. a worktree added under
                            `/private/tmp/...`).
  - `other`               — inside the repo tree, but neither of the above.

`claude-harness` worktrees bypass `scripts/agent_start.py` BY DESIGN — Claude Code
creates its own isolation and was never routed through this repo's broker, so they were
never promised the `SYMLINK_TARGETS` treatment in the first place. It would be tempting
to treat that as an exemption and drop them from the report.

**Decision: they are NOT exempted.** The risk this script measures — a `git push` that
silently skips the pre-push gate — is a property of filesystem state, not of which tool
created the worktree. There is no evidence a `claude-harness` worktree cannot or will
not `git push`; if it can, it has the identical exposure as a bare `git worktree add`.
Filtering them out would be a silent exemption, which is exactly the failure mode this
whole family (#2, "Esiste != Armato") is about: a scan that quietly narrows its own
scope reports "clean" without saying what it declined to look at. They are counted in
the exit code and listed as findings, tagged with their real origin, so a reader can
still see the pattern the classification reveals (as of this writing: the broker's own
worktrees are 100% compliant; every finding lives in a location the broker doesn't
touch — a useful fact this report would hide if it filtered them out).

## Blind-scan guard (W84 discipline)

Zero worktrees traversed (an empty or failing `git worktree list --porcelain`) is NOT
reported as "clean" — it exits non-zero. `git worktree list` always includes at least
the main worktree in a healthy repo, so seeing zero means the scan itself is broken
(wrong `--repo-root`, git failure, sandbox/TCC denial), not that nothing is wrong.
A scan that cannot see is not proof nothing is wrong.

Usage:
    python3 scripts/lint_worktree_husky_symlink.py [--repo-root PATH] [--json]

Exit codes:
    0   clean — at least one worktree traversed, zero findings
    1   >=1 finding (a worktree whose directory exists on disk, but whose `.husky/_`
        is MISSING or a DANGLING_SYMLINK)
    2   blind-scan guard — zero worktrees traversed (git returned nothing, or the
        `git worktree list --porcelain` invocation itself failed), or a CLI argument
        error (argparse's own exit code)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ORIGIN_MAIN = "main"
ORIGIN_BROKER = "broker"
ORIGIN_BROKER_NO_METADATA = "broker-path-no-metadata"
ORIGIN_CLAUDE_HARNESS = "claude-harness"
ORIGIN_EXTERNAL = "external"
ORIGIN_OTHER = "other"

HEALTH_OK = "OK"
HEALTH_MISSING = "MISSING"
HEALTH_DANGLING = "DANGLING_SYMLINK"
HEALTH_GONE = "GONE"  # worktree directory itself is absent — stale registry entry

FINDING_HEALTHS = frozenset({HEALTH_MISSING, HEALTH_DANGLING})


@dataclass
class WorktreeRecord:
    path: Path
    head: Optional[str]
    branch: Optional[str]
    detached: bool
    locked_reason: Optional[str]
    origin: str
    origin_detail: str
    health: str
    is_symlink: bool

    @property
    def is_finding(self) -> bool:
        return self.health in FINDING_HEALTHS

    @property
    def branch_short(self) -> str:
        if self.detached or not self.branch:
            return "(detached)"
        prefix = "refs/heads/"
        return self.branch[len(prefix):] if self.branch.startswith(prefix) else self.branch


def _run_git_worktree_list(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git worktree list --porcelain failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def parse_porcelain(output: str) -> List[Dict[str, object]]:
    """Parse `git worktree list --porcelain` into one dict per worktree block.

    Blocks are separated by a blank line. Observed real fields (verified live on M5,
    2026-07-26): `worktree <path>`, `HEAD <sha>`, either `branch <ref>` (full
    `refs/heads/...` form) or a bare `detached` line, and an optional
    `locked <reason>` line (reason may be empty). `bare` and `prunable` lines are
    accepted but not currently surfaced — not relevant to this detector's health check.
    """
    blocks: List[Dict[str, object]] = []
    current: Dict[str, object] = {}
    for line in output.splitlines():
        if line == "":
            if current:
                blocks.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current = {
                "path": line[len("worktree "):],
                "head": None,
                "branch": None,
                "detached": False,
                "locked_reason": None,
            }
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line == "detached":
            current["detached"] = True
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line.startswith("locked"):
            reason = line[len("locked"):].strip()
            current["locked_reason"] = reason if reason else "(no reason given)"
        # 'bare' / 'prunable' / anything else: ignored, not load-bearing here.
    if current:
        blocks.append(current)
    return blocks


def classify_origin(wt_path: Path, repo_root: Path) -> Tuple[str, str]:
    path_str = str(wt_path)
    repo_str = str(repo_root)

    if path_str == repo_str:
        return ORIGIN_MAIN, "repo root"

    if not path_str.startswith(repo_str + "/"):
        return ORIGIN_EXTERNAL, "outside repo tree"

    rel = path_str[len(repo_str) + 1:]

    if rel.startswith(".worktrees/"):
        metadata = wt_path / ".agent-task.json"
        if metadata.exists():
            return ORIGIN_BROKER, "scripts/agent_start.py-created (.agent-task.json present)"
        return (
            ORIGIN_BROKER_NO_METADATA,
            "under .worktrees/ but no .agent-task.json -- likely a bare "
            "'git worktree add' imitating the broker's location without its symlink step",
        )

    if rel.startswith(".claude/worktrees/"):
        name = wt_path.name
        if name.startswith("wf_"):
            return (
                ORIGIN_CLAUDE_HARNESS,
                "Workflow-tool dispatch (wf_*) -- bypasses scripts/agent_start.py by design",
            )
        return (
            ORIGIN_CLAUDE_HARNESS,
            "named Claude Code session worktree -- bypasses scripts/agent_start.py by design",
        )

    return ORIGIN_OTHER, "inside repo tree, unrecognized location"


def check_husky_health(wt_path: Path) -> Tuple[str, bool]:
    """Health of `<wt_path>/.husky/_`. Assumes wt_path itself exists on disk.

    Returns (health, is_symlink). `resolves` follows symlinks (Path.exists() does),
    so it is False for both a dangling symlink and a plain absence -- the two are
    told apart by `is_symlink()`, which is True even when the target is missing.
    """
    husky = wt_path / ".husky" / "_"
    is_symlink = husky.is_symlink()
    resolves = husky.exists()
    if resolves:
        return HEALTH_OK, is_symlink
    if is_symlink:
        return HEALTH_DANGLING, True
    return HEALTH_MISSING, False


def scan(repo_root: Path, *, porcelain_output: Optional[str] = None) -> List[WorktreeRecord]:
    """Enumerate every worktree and check `.husky/_` health.

    `porcelain_output`, when given, is used instead of invoking git -- the seam tests
    use to exercise the classifier/health-check against fixture text without needing a
    real git repo on disk.
    """
    output = porcelain_output if porcelain_output is not None else _run_git_worktree_list(repo_root)
    blocks = parse_porcelain(output)

    records: List[WorktreeRecord] = []
    for b in blocks:
        wt_path = Path(str(b["path"]))
        origin, origin_detail = classify_origin(wt_path, repo_root)

        if not wt_path.is_dir():
            health, is_symlink = HEALTH_GONE, False
        else:
            health, is_symlink = check_husky_health(wt_path)

        records.append(
            WorktreeRecord(
                path=wt_path,
                head=b.get("head"),  # type: ignore[arg-type]
                branch=b.get("branch"),  # type: ignore[arg-type]
                detached=bool(b.get("detached", False)),
                locked_reason=b.get("locked_reason"),  # type: ignore[arg-type]
                origin=origin,
                origin_detail=origin_detail,
                health=health,
                is_symlink=is_symlink,
            )
        )
    return records


# --------------------------------------------------------------------------- reporting


def _origin_counts(records: Sequence[WorktreeRecord]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in records:
        counts[r.origin] = counts.get(r.origin, 0) + 1
    return counts


def render_report(records: Sequence[WorktreeRecord]) -> str:
    total = len(records)
    findings = [r for r in records if r.is_finding]
    gone = [r for r in records if r.health == HEALTH_GONE]
    healthy = total - len(findings) - len(gone)
    origin_counts = _origin_counts(records)

    lines: List[str] = []
    lines.append("# Worktree .husky/_ pre-push-gate symlink audit")
    lines.append("")
    lines.append(f"Traversed: {total} worktree(s) (from `git worktree list --porcelain`)")
    for origin in (
        ORIGIN_MAIN,
        ORIGIN_BROKER,
        ORIGIN_BROKER_NO_METADATA,
        ORIGIN_CLAUDE_HARNESS,
        ORIGIN_EXTERNAL,
        ORIGIN_OTHER,
    ):
        if origin in origin_counts:
            lines.append(f"  {origin}: {origin_counts[origin]}")
    lines.append("")
    lines.append(f"Healthy: {healthy}   Findings: {len(findings)}   Gone (stale entry): {len(gone)}")
    lines.append("")

    if findings:
        lines.append(
            f"## Findings: {len(findings)} worktree(s) with a MISSING or DANGLING `.husky/_`"
        )
        lines.append("")
        lines.append(
            "Each row below means `git push` from that worktree silently skips the "
            "pre-push gate -- no banner, no error, exit 0."
        )
        lines.append("")
        lines.append("| origin | health | path | branch | locked |")
        lines.append("|---|---|---|---|---|")
        for r in findings:
            locked = r.locked_reason if r.locked_reason else "-"
            lines.append(
                f"| {r.origin} | {r.health} | `{r.path}` | `{r.branch_short}` | {locked} |"
            )
        lines.append("")
        lines.append(
            "**claude-harness findings are not exempted** -- see the module docstring's "
            "\"Origin classification\" section for why. They bypass "
            "`scripts/agent_start.py` by design, but the exposure they carry (a silently "
            "skipped pre-push gate) does not depend on which tool created the worktree."
        )
        broker_findings = sum(1 for r in findings if r.origin == ORIGIN_BROKER)
        lines.append(
            f"  Right now: {broker_findings} broker-origin finding(s) vs "
            f"{len(findings) - broker_findings} non-broker-origin -- a low broker count "
            "here is the signal that the broker's own symlink step is working; a high "
            "one would mean the cure itself is broken."
        )
        lines.append("")
    else:
        lines.append("## Findings: none")
        lines.append("")

    if gone:
        lines.append(
            f"## Gone: {len(gone)} stale worktree registry entry/entries (informational, NOT a finding)"
        )
        lines.append("")
        lines.append(
            "These paths are listed by `git worktree list` but do not exist on disk "
            "(removed via `rm -rf`/OS cleanup instead of `git worktree remove`, or "
            "pruned mid-scan by a concurrent process). Nothing can `git push` from a "
            "directory that isn't there, so they are not counted as findings -- but "
            "they are real registry debt worth a `git worktree prune` at some point."
        )
        lines.append("")
        for r in gone:
            lines.append(f"  - `{r.path}` (origin: {r.origin})")
        lines.append("")

    return "\n".join(lines) + "\n"


def build_json(records: Sequence[WorktreeRecord]) -> dict:
    total = len(records)
    findings = [r for r in records if r.is_finding]
    gone = [r for r in records if r.health == HEALTH_GONE]
    return {
        "traversed": total,
        "healthy": total - len(findings) - len(gone),
        "findings_count": len(findings),
        "gone_count": len(gone),
        "origin_counts": _origin_counts(records),
        "worktrees": [
            {
                "path": str(r.path),
                "origin": r.origin,
                "origin_detail": r.origin_detail,
                "health": r.health,
                "is_symlink": r.is_symlink,
                "is_finding": r.is_finding,
                "branch": r.branch,
                "detached": r.detached,
                "locked_reason": r.locked_reason,
            }
            for r in records
        ],
    }


# ------------------------------------------------------------------------------- CLI


def _default_repo_root() -> Path:
    """The shared repo root -- deliberately NOT `Path(__file__).resolve().parent.parent`.

    This script is meant to run from inside a broker-created worktree (per its own
    "own worktree, created via agent_start.py" discipline). A file-path-relative
    guess would then resolve to that WORKTREE's root, not the shared repo root --
    silently miscategorizing every real worktree as `external` relative to itself.
    Caught live via dogfooding on 2026-07-26 before this script ever shipped: every
    finding row read `origin: external` including the broker's own siblings.

    `git rev-parse --git-common-dir` returns the ONE `.git` directory every worktree
    shares (worktrees have a `.git` file pointing back at it), regardless of which
    worktree git was invoked from -- its parent is the true, worktree-invariant
    repo root.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    if result.returncode != 0:
        # git itself is unavailable -- fall back to the file-path heuristic. Only
        # correct when this script happens to run from the main checkout, but better
        # than crashing outright; the real git failure will surface again (and be
        # caught as the blind-scan guard) the moment `scan()` calls git itself.
        return Path(__file__).resolve().parent.parent
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = (Path(__file__).resolve().parent / common_dir).resolve()
    return common_dir.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_worktree_husky_symlink.py",
        description=(
            "Detects worktrees whose .husky/_ pre-push-gate symlink is missing or "
            "dangling -- the shape that makes git push silently skip the gate. "
            "Report-only, never mutates anything."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root to scan from (default: resolved from this script's own path).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the markdown report.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root if args.repo_root is not None else _default_repo_root()

    try:
        records = scan(repo_root)
    except RuntimeError as exc:
        print(f"lint_worktree_husky_symlink: {exc}", file=sys.stderr)
        return 2

    if len(records) == 0:
        print(
            "lint_worktree_husky_symlink: 0 worktrees traversed -- this is treated as "
            "a BLIND scan, not a clean one (W84 discipline: a scan that cannot see is "
            "not proof nothing is wrong). `git worktree list` should always include at "
            "least the main worktree; check --repo-root and git's own health.",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(build_json(records), indent=2))
    else:
        print(render_report(records), end="")

    findings = [r for r in records if r.is_finding]
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
