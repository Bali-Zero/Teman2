#!/usr/bin/env python3
"""check_ledger_no_silent_loss.py — the residual arming step for the `merge=union`
PENDING-ARMS entry (opened 2026-08-02).

`.gitattributes` declares `.claude/skills/modus/PENDING-ARMS.md merge=union`, a
built-in git driver that keeps both sides' lines on any textual conflict —
exactly right for an append-only registry. But GitHub's OWN mergeability
computation does not apply `.gitattributes` merge drivers: it reports
`mergeable: false` / `mergeStateStatus: DIRTY` on a plain three-way merge even
when `git merge --no-commit` succeeds cleanly in both directions. The
documented escape (`gh pr update-branch`) also fails on this file ("Cannot
update PR branch due to conflicts"). The only path is a LOCAL `git merge
origin/main` + push.

The danger this check exists for: a session that reads GitHub's false
`mergeable: false` as a REAL conflict and hand-resolves it by picking one
side, silently dropping the other side's rows — exactly what `merge=union`
was added to prevent, and exactly the kind of loss no git-level conflict
marker would ever flag (a clean three-way merge with a wrong resolution
produces no conflict at all).

INVARIANT (deliberately narrow — see below): a row present at BOTH the
branch's own merge-base AND on current origin/main — i.e. a row NEITHER
this branch NOR any other PR has touched since this branch was created —
must still be present on the branch's own HEAD. If it isn't, nothing on
either side asked for its removal, so its disappearance can only be an
artifact of how the branch's tree was produced (the exact "hand-resolved a
false conflict, kept one side's whole file" incident this check exists
for). A PR that doesn't touch the ledger at all is skipped entirely.

Why not simply "every row on origin/main must be in HEAD"? Because this
ledger's own header sanctions a real, intentional action: "Remove a line
ONLY when the arming is PROVEN live." A PR that legitimately closes an
existing, previously-untouched row is indistinguishable, by pure git
history, from one that accidentally dropped it — nothing in `git diff`
can carry that intent. Rather than either (a) blocking every legitimate
closure or (b) trusting intent no mechanical check can verify, this stays
a LOUD, NON-required signal (see the companion workflow) until it has been
observed over a dry-run window — the same promotion path this repo already
uses (`worktree_gc_universal`'s own history). Promoting it to a required
branch-protection check is a separate, later, operator-only action
(repo/branch-protection settings are explicitly outside session scope).

Identity is (opened_date, artifact-title), not the full raw line: the
ledger's own body fields (status, missing-step, owner, proof-of-armed) are
legitimately edited in place as work progresses on an ALREADY-open entry
(e.g. PR #3831, same day this check was written: the ReDoS-timing entry's
status text changed from "NOT fixed" to "FIXED in PR #3831" without the row
being a "different" entry) — keying on the full line would treat every such
edit as a silent removal-plus-addition and never distinguish it from a
genuine loss.

Pure signaler: reads three git refs (origin/main, merge-base, working tree),
prints a verdict, never writes anything.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pending_arms_report import (  # noqa: E402
    Entry,
    LedgerRefUnreadable,
    _default_ledger_path,
    _git,
    _parse_now,
    load_entries,
)

EntryKey = Tuple[Optional[date], str]


def entry_key(entry: Entry) -> EntryKey:
    return (entry.opened_date, entry.artifact.strip())


def entry_keys(entries: List[Entry]) -> Set[EntryKey]:
    return {entry_key(e) for e in entries}


def _format_key(key: EntryKey) -> str:
    opened, title = key
    opened_str = opened.isoformat() if opened else "????-??-??"
    return f"opened {opened_str} | {title}"


def ledger_touched_by_branch(
    ledger_path: Path, merge_base: str, head_ref: Optional[str] = None
) -> bool:
    rc, out, err = _git(
        ["diff", "--name-only", f"{merge_base}..{head_ref or 'HEAD'}", "--", str(ledger_path.name)],
        cwd=ledger_path.parent,
    )
    if rc != 0:
        # Can't tell -> do NOT assume untouched (that would silently skip the
        # one case this check exists for). Caller surfaces this as CANNOT-VERIFY.
        raise LedgerRefUnreadable(f"git diff --name-only failed: {err or rc}")
    return bool(out.strip())


def check(
    ledger_path: Path,
    now: date,
    base_ref: str = "origin/main",
    head_ref: Optional[str] = None,
) -> int:
    """head_ref=None reads the physical working tree (local/dev use — what's
    actually checked out IS the branch under test). CI passes an explicit SHA
    when the checkout strategy pins HEAD to something other than the PR's own
    branch tip (e.g. a base-anchored checkout, matching hot-zone-pr-gate.yml's
    convention of checking out base.sha and fetching head.sha separately)."""
    head_for_diff = head_ref or "HEAD"
    rc, merge_base, err = _git(["merge-base", base_ref, head_for_diff], cwd=ledger_path.parent)
    if rc != 0:
        print(f"CANNOT-VERIFY: git merge-base {base_ref} {head_for_diff} failed: {err or rc}")
        return 4

    try:
        touched = ledger_touched_by_branch(ledger_path, merge_base, head_ref=head_ref)
    except LedgerRefUnreadable as exc:
        print(f"CANNOT-VERIFY: {exc}")
        return 4

    if not touched:
        print(
            "OK: this branch does not touch "
            f"{ledger_path.name} — nothing for this check to verify."
        )
        return 0

    try:
        main_entries = load_entries(ledger_path, now, ref=base_ref)
        base_entries = load_entries(ledger_path, now, ref=merge_base)
        head_entries = load_entries(ledger_path, now, ref=head_ref)  # None = working tree
    except LedgerRefUnreadable as exc:
        print(f"CANNOT-VERIFY: {exc}")
        return 4

    main_keys = entry_keys(main_entries)
    base_keys = entry_keys(base_entries)
    head_keys = entry_keys(head_entries)

    # Untouched by ANYONE since this branch diverged: present at the branch's
    # own starting point AND still present on current main. Nothing on either
    # side has asked for these rows to go away.
    stable_keys = base_keys & main_keys
    missing = sorted(stable_keys - head_keys, key=lambda k: (k[0] or date.min, k[1]))

    if missing:
        print(
            f"FAIL (non-blocking, dry-run — see workflow): {len(missing)} open ledger row(s) "
            "untouched by any PR since this branch diverged (present at merge-base AND on "
            "current origin/main) are absent from this branch's HEAD:"
        )
        for key in missing:
            print(f"  - {_format_key(key)}")
        print(
            "\nIf this is a deliberate closure (arming PROVEN live — the ledger's own "
            "removal rule), ignore this signal; it cannot see intent, only content. If it "
            "is NOT deliberate, this is the exact loss the merge=union driver exists to "
            "prevent. If GitHub reported this PR as `mergeable: false` / DIRTY on "
            "PENDING-ARMS.md, that is EXPECTED (server-side mergeability does not apply "
            ".gitattributes drivers) and is NOT a real conflict — do not hand-resolve. Fix: "
            "`git merge origin/main` locally (the union driver applies correctly "
            "client-side), then push. See the PENDING-ARMS.md entry opened 2026-08-02 "
            "('merge=union on this ledger...') and docs/runbooks/merge-queue-discipline.md "
            "§6quinquies."
        )
        return 1

    print(
        f"OK: {len(head_keys)} open row(s) on HEAD, {len(main_keys)} on origin/main, "
        f"{len(stable_keys)} row(s) untouched-by-anyone all survived — no silent loss."
    )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=None, help="Path to PENDING-ARMS.md")
    parser.add_argument(
        "--now", type=str, default=None, help="Override 'today' as YYYY-MM-DD (deterministic runs/tests)."
    )
    parser.add_argument(
        "--base-ref",
        type=str,
        default="origin/main",
        help=(
            "Ref/SHA to treat as 'main' (default origin/main). CI passes the PR's exact "
            "base SHA — a symbolic origin/main may not be populated in a base-anchored "
            "shallow checkout."
        ),
    )
    parser.add_argument(
        "--head-ref",
        type=str,
        default=None,
        help=(
            "Ref/SHA to treat as the PR's HEAD. Default reads the physical working tree "
            "(local/dev use). CI passes the PR's exact head SHA when the checkout strategy "
            "doesn't leave HEAD pointed at the PR branch tip."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    ledger_path = args.ledger or _default_ledger_path()
    now = _parse_now(args.now)
    return check(ledger_path, now, base_ref=args.base_ref, head_ref=args.head_ref)


if __name__ == "__main__":
    raise SystemExit(main())
