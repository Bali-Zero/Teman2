#!/usr/bin/env python3
"""prepush_freshness.py — pure decision: is a branch's FIRST push stale
relative to origin/main?

Mandate (task #27, 2026-07-26): main moved `d5e5f9a755` -> `ee1bcbeb6a` ->
`8096fcd085` in under 30 minutes one night; four branches were cut from a
base that went stale before their first push landed, and each one hit the
"zero-check trap" — GitHub Actions never materialises `refs/pull/N/merge`
for a conflicting PR, so every `pull_request`-triggered workflow is silently
never created (not red, ABSENT), all 25 required contexts sit ABSENT, and
auto-merge sits armed and inert. Healthy PRs on this repo read 23-35
workflow runs on their head SHA; a trapped one reads 1. The only cure is
`merge origin/main; push` — re-running, re-arming, closing/reopening all
leave the merge ref uncomputable.

This is a CHEAP, DETERMINISTIC PROXY, not a conflict oracle: it warns when
origin/main has moved past the branch's fork point (merge-base(origin/main,
local_head) != origin/main's current tip), which is necessary but not
sufficient for an actual merge conflict — a branch can be behind main and
still merge clean if the changes are in disjoint files. That is deliberate:
a real conflict check needs a trial merge, which is heavier and has side
effects worth avoiding in a pre-push hook; the proxy over-warns on some
harmless staleness rather than under-warn on a real trap, and warn-only
(not block) means the cost of an over-warn is one ignorable line, not a
blocked push.

Scoped to the FIRST push of a branch only (git pre-push protocol's
`remote_sha == 0000...` case) — an already-pushed branch getting re-merged
before every SUBSEQUENT push is a different, more expensive anti-pattern
this repo already corrected away from (re-merging an already-pushed branch
widens `.husky/pre-push`'s diff range to `remote_sha..local_sha`, pulling
main's entire intervening churn into the path-aware classifier's file set
and escalating it to the FULL suite — and the long push it causes widens
the window for main to move again, which can manufacture the very conflict
it was meant to prevent). `gh pr view <N> --json mergeable,mergeStateStatus`
first; merge only on CONFLICTING/DIRTY, never proactively on an existing
push.

Usage (embedded in .husky/pre-push):
    python3 scripts/prepush_freshness.py "$RANGE_FROM" "$ORIGIN_MAIN_TIP"
    (prints WARN_MESSAGE to stdout iff stale, exits 0 unconditionally — this
    is warn-only by construction, never a push-blocking exit code, and the
    hook itself never captures this command's output into a variable: it is
    let through to the hook's own stdout directly, so a future edit here
    cannot reintroduce the W101/task-#39 bare-`$(...)`-under-`sh -e` failure
    mode on THIS line — there is nothing to capture).

ESCALATION CONDITION (stated 2026-07-26, task #27 ruling: warn-only without
a falsifiable trigger becomes wallpaper). Base rate the night this shipped:
4 branches hit the zero-check trap in well under an hour of main's normal
churn. If the trap recurs 3 MORE times after this warning is live —
measured by task #27's companion detection sweep (workflow-run count <=2 on
an open PR's head SHA, i.e. a branch that warned-and-was-ignored, or one
that somehow trapped without ever triggering this check) — this check
escalates from warn-only to a hard pre-push block on a stale first push.
That threshold must be tracked as an open PENDING-ARMS entry, not left to
memory: an unmonitored escalation condition is just a slower-motion version
of the "esiste ≠ armato" family this repo already has ten scars for.

Pure function, no git/subprocess state — same discipline as
prepush_classify.py's "THIS script owns zero git/subprocess state" (the bash
hook owns git plumbing; this owns the decision), which is what makes it fast
to test and impossible to fool with a crafted cwd.
"""

from __future__ import annotations

import sys

WARN_MESSAGE = (
    "⚠️  first push of this branch is based on a STALE origin/main "
    "— merging now avoids the zero-check trap (a conflicting first push "
    "gets ZERO workflow runs, not red ones: GitHub never materialises the "
    "merge ref, so no required context is ever created, and auto-merge sits "
    "armed and inert). Cure: `git fetch origin main && git merge origin/main "
    "&& git push` — re-running or re-arming after the fact does not work."
)


def is_stale_at_first_push(merge_base_sha: str, origin_main_sha: str) -> bool:
    """True iff origin/main has moved past this branch's fork point.

    `merge_base_sha` = `git merge-base origin/main <local_head>` (already
    computed by the caller for the diff-range decision; this function reuses
    it rather than asking for a second git call). `origin_main_sha` =
    `git rev-parse origin/main` after the caller's own fetch.

    Unknown state (either argument empty/falsy) never warns — the
    caller's own diff-range logic already fails closed to the FULL suite on
    a git-plumbing failure; this is an ADDITIONAL, non-blocking signal layered
    on top, and a signal with no data is not evidence of staleness.
    """
    if not merge_base_sha or not origin_main_sha:
        return False
    return merge_base_sha != origin_main_sha


def main(argv: list[str] | None = None) -> int:
    """CLI wrapper: `prepush_freshness.py <merge_base_sha> <origin_main_sha>`.

    Prints WARN_MESSAGE iff stale, prints nothing otherwise, and ALWAYS
    exits 0 — warn-only is enforced at this boundary too, not just in the
    pure function, so a malformed argv (wrong arg count, garbage SHA) fails
    open to silence rather than a non-zero exit the caller might treat as a
    push-blocking signal.
    """
    args = sys.argv[1:] if argv is None else argv
    merge_base_sha = args[0] if len(args) > 0 else ""
    origin_main_sha = args[1] if len(args) > 1 else ""
    if is_stale_at_first_push(merge_base_sha, origin_main_sha):
        print(WARN_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
