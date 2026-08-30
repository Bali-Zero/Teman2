#!/usr/bin/env python3
"""lint_arm_probe.py — executable antidote for the autoMergeRequest null-ambiguity trap.

THE FINDING (measured 2026-08-29/30, PR #5275): GitHub's `autoMergeRequest` GraphQL
field reads null in (at least) three different states — a PR the merge queue has
ACCEPTED and is now processing (the request is CONSUMED, not disarmed), a PR the
queue EJECTED, and a PR that was genuinely never armed — and non-null in only one.
`mergeQueueEntry` (the per-PR authoritative field), its sibling boolean
`isInMergeQueue`, and the branch-level `mergeQueue(branch:...){entries}` snapshot
are the only POSITIVE probes: a PR is IN the queue *because* the request is live.
Reading `autoMergeRequest == null` as "disarmed, needs re-arming" therefore fires
precisely when arming SUCCEEDED — confirmed live on PR #5275 (`autoMergeRequest:
null` simultaneously with `mergeQueueEntry {state: QUEUED, position: 3}`, and
`gh pr merge --auto` on it refusing with "already queued to merge") and, per the
mandate that produced this lint, twice before in production (#4756, #5012: a
sentinel announced "ARM CONSUMED / re-arm needed" against a PR that was actually
`mergeQueueEntry.state = AWAITING_CHECKS, position 1`).

THE ANTIDOTE: this lint. A file that TESTS `autoMergeRequest` for truthiness/
nullness (a "decision position" — a `.get` lookup or bracket subscript keyed
on the literal field name, or a jq `== null` / `select(...)` filter on it)
must also reference one of the positive-probe markers — `mergeQueueEntry`,
`isInMergeQueue`, or `mergeQueue(` — somewhere in the SAME FILE. A file that only
REQUESTS the field (a `--json ...,autoMergeRequest` field list, or a GraphQL
mutation's return-selection) without ever testing it is not flagged — nothing
decides on it, so there is nothing to protect (mq.sh's confirm-step echo,
github_publisher.py's `_enable_auto_merge` mutation selection).

Detection classes:
  FAIL   — a decision-position `autoMergeRequest` line with NO positive-probe
           marker anywhere in the file, and no inline suppression marker on
           that line.
  (clean) — decision-position usage WITH a positive-probe marker in the same
           file, OR no decision-position usage at all.

Suppression marker (CONTENT-based, not a directory exemption — cicatrix #3/
W109, "an exemption keyed to where a file sits, rather than what it is, is
itself a scar"): a source line carrying the literal string
`lint-arm-probe:fixture` is a synthetic guilt/innocence sample embedded in
this lint's OWN test file, not real decision code, and is excluded entirely
(from both findings AND positive-probe detection). The marker sits on the
Python SOURCE line that DEFINES a fixture string constant — as a trailing
`#` comment, which Python discards at parse time and which therefore never
becomes part of the fixture TEXT a test hands to `scan_text()`. That is what
lets the guilt fixture still register as a finding *inside the unit test*
(the runtime string has no marker) while the static .py file that defines it
is invisible to this lint's own repo-wide scan (the source line does).
Nothing else may carry this marker — `scripts/tests/test_lint_arm_probe.py`
is the only tracked file that does
(`test_marker_appears_only_in_this_lints_own_test_file`).

Scope notes (deliberate): file-level, not function-level, co-occurrence. A
file whose own decision logic is safe only because a DIFFERENT file checks
queue membership before ever acting on its output (a "candidates" filter
piped into a caller that cross-references `mergeQueue(...)` before acting)
still reads `autoMergeRequest == null` as part of its own predicate, with
nothing in ITS file proving that null here means anything narrower than "not
armed" — so it FAILS this lint even when the full pipeline is safe today.
That is intentional, not a false positive: the safety property in that shape
lives in a caller/callee CONTRACT, not in the file itself, and a future
caller that skips the cross-check reintroduces the exact bug this lint
exists to catch (see the audit report that shipped alongside this lint for
the one file this currently affects).

Exit code: 0 = clean · 1 = one or more FAIL findings · 4 = operational error
(unreadable file — a scan that cannot see is not clean, W84 fail-visible
discipline).

Tests: scripts/tests/test_lint_arm_probe.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


def _canonical_repo_root() -> Path:
    """Repo root, worktree-hardened (same discipline as lint_home_fork.py):
    running from .worktrees/<lane>/ must lint against the MAIN checkout — a
    worktree is ephemeral, treating it as the source of truth would replay
    W81."""
    root = Path(__file__).resolve().parent.parent
    parts = root.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        return Path(*parts[:idx])
    return root


REPO_ROOT = _canonical_repo_root()

_SCAN_EXTS = {".py", ".sh", ".bash", ".yml", ".yaml"}
_PRUNE_DIRS = {
    "node_modules", ".venv", "venv", ".git", "__pycache__",
    ".worktrees", "dist", "build", ".next",
}

SUPPRESSION_MARKER = "lint-arm-probe:fixture"

_FIELD_TOKEN = "autoMergeRequest"

# The three positive-probe shapes this repo's consumers actually use (audit,
# 2026-08-29): PullRequest.mergeQueueEntry, PullRequest.isInMergeQueue, and
# the branch-level repository.mergeQueue(branch:"main"){entries...} snapshot.
_POSITIVE_PROBE_RE = re.compile(r"mergeQueueEntry|isInMergeQueue|mergeQueue\(")

# Decision-position patterns: autoMergeRequest being TESTED/FILTERED, not
# merely requested as a field. Anchored on how this repo's own consumers
# actually read the field (measured across 17 files) — not a generic
# "field appears" match, which would flag `--json ...,autoMergeRequest`
# field-selection lines and GraphQL query-declaration lines that are never
# parsed downstream (guard-over-match, cicatrix #3).
_DECISION_PATTERNS = [
    # dict.get("autoMergeRequest") / dict.get('autoMergeRequest')
    re.compile(r"""\.get\(\s*["']""" + _FIELD_TOKEN + r"""["']"""),
    # dict["autoMergeRequest"] / dict['autoMergeRequest']
    re.compile(r"""\[\s*["']""" + _FIELD_TOKEN + r"""["']\s*\]"""),
    # jq: .autoMergeRequest==null / .autoMergeRequest != null
    re.compile(r"""\.""" + _FIELD_TOKEN + r"""\s*(==|!=)\s*null"""),
    # jq: select(...autoMergeRequest...)
    re.compile(r"""select\([^)]*""" + _FIELD_TOKEN + r"""[^)]*\)"""),
]


# ---------------------------------------------------------------- scanning


def _is_full_comment_line(line: str) -> bool:
    """First non-whitespace char is `#` — a whole-line comment in Python,
    bash and YAML alike. A trailing inline `code  # comment` is NOT stripped
    (this lint does not attempt a string-literal-aware tokenizer); a comment
    mentioning autoMergeRequest AFTER real code on the same line could in
    principle still match, but no consumer in this repo's audit does that —
    documented limitation, not a silent gap."""
    return line.lstrip().startswith("#")


def _has_decision_pattern(line: str) -> bool:
    return any(p.search(line) for p in _DECISION_PATTERNS)


def scan_text(text: str, relpath: str) -> dict[str, Any]:
    """Pure function, no file I/O — the unit-testable core. Returns
    {"findings": [str], "has_positive_probe": bool, "decision_lines": [(int, str)]}.
    """
    lines = text.splitlines()
    has_positive_probe = False
    decision_lines: list[tuple[int, str]] = []

    for line_no, line in enumerate(lines, start=1):
        if SUPPRESSION_MARKER in line:
            continue
        if _is_full_comment_line(line):
            continue
        if _POSITIVE_PROBE_RE.search(line):
            has_positive_probe = True
        if _FIELD_TOKEN in line and _has_decision_pattern(line):
            decision_lines.append((line_no, line.strip()))

    findings: list[str] = []
    if decision_lines and not has_positive_probe:
        for line_no, snippet in decision_lines:
            findings.append(
                f"{relpath}:{line_no}: autoMergeRequest tested in a decision "
                f"position with no mergeQueueEntry/isInMergeQueue/mergeQueue( "
                f"probe anywhere in this file — null here can mean queued, "
                f"ejected, or never-armed, and this file cannot tell them "
                f"apart. {snippet[:160]}"
            )

    return {
        "findings": findings,
        "has_positive_probe": has_positive_probe,
        "decision_lines": decision_lines,
    }


# ---------------------------------------------------------------- discovery


def _walk_files(root: Path, errors: list[str]) -> list[Path]:
    """os.walk with the standard vendored/ephemeral prune list; unreadable
    dirs become operational errors (fail-visible), never a silent skip."""
    found: list[Path] = []
    if not root.exists():
        return found

    def _onerror(exc: OSError) -> None:
        errors.append(f"root unreadable ({type(exc).__name__}): {exc.filename or root}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=_onerror):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        for fn in filenames:
            if Path(fn).suffix.lower() in _SCAN_EXTS:
                found.append(Path(dirpath) / fn)
    return found


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def run(root_paths: list[Path], repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    findings: list[str] = []

    seen: set[Path] = set()
    files: list[Path] = []
    for root in root_paths:
        for path in _walk_files(root, errors):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    files.sort()

    for path in files:
        relpath = _rel(path, repo_root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"file unreadable ({type(exc).__name__}): {relpath}")
            continue
        if _FIELD_TOKEN not in text:
            continue
        result = scan_text(text, relpath)
        findings.extend(result["findings"])

    exit_code = (1 if findings else 0) | (4 if errors else 0)
    return {
        "schema": 1,
        "findings": findings,
        "errors": errors,
        "files_scanned": len(files),
        "exit": exit_code,
    }


# ---------------------------------------------------------------- main


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", action="append", default=None,
        help="repeatable; default: repo root (whole tracked tree, standard prunes)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    roots = args.root if args.root else ["."]
    root_paths = [
        (Path(r) if Path(r).is_absolute() else repo_root / r) for r in roots
    ]

    result = run(root_paths, repo_root)

    if args.json:
        print(json.dumps(result, indent=2))
        return result["exit"]

    print(f"[arm-probe-lint] scanned {result['files_scanned']} file(s) under "
          f"{', '.join(str(_rel(r, repo_root)) for r in root_paths)}")
    print(f"[findings] {len(result['findings'])}")
    for f in result["findings"]:
        print(f"  - {f}")
    if result["errors"]:
        print(f"[errors] {len(result['errors'])} operational error(s) — scan is PARTIAL, not clean:")
        for e in result["errors"]:
            print(f"  - {e}")
    if not result["findings"] and not result["errors"]:
        print("  clean — every decision-position autoMergeRequest read is co-located "
              "with a mergeQueueEntry/isInMergeQueue/mergeQueue( probe")
    if result["exit"]:
        print(
            f"ARM-PROBE LINT FAIL (exit {result['exit']}: 1=unsafe-decision 4=scan-error) — "
            f"autoMergeRequest reads null while QUEUED, EJECTED, and NEVER-ARMED alike; "
            f"cross-check mergeQueueEntry/isInMergeQueue/mergeQueue( before treating null "
            f"as disarmed"
        )
    return result["exit"]


if __name__ == "__main__":
    sys.exit(main())
