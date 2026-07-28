#!/bin/sh
# Did the branch move under the gate while the gate was running?
#
# THE DEFECT THIS EXISTS TO CATCH (measured 2026-07-28, M5, PR #3399):
#
#   1. `git push origin <branch>` started with the local tip at f3bf563244.
#   2. The pre-push hook was handed f3bf563244 on stdin — the only two SHAs
#      anywhere in its 439-line log are 418d187ccf (the old remote tip) and
#      f3bf563244 — and ran the full suite against it for ~15 minutes, green.
#   3. At 04:19:39Z, WHILE the hook was still running, a commit d45c116e45
#      landed on the same branch.
#   4. git printed `418d187ccf..f3bf563244  <branch> -> <branch>`.
#   5. GitHub recorded exactly ONE PushEvent on that ref: 418d187c -> d45c116e.
#   6. The remote tip is d45c116e45, per three independent probes
#      (`git ls-remote`, `GET /git/ref/heads/…`, `GET /commits/<sha>`).
#
# So what landed was neither what the gate validated nor what git reported.
# That is the observation. The MECHANISM is deliberately not named here: from
# outside the process I cannot distinguish late refspec re-resolution from
# anything else, and naming a mechanism I cannot see is the phantom-citation
# failure the scars file exists to punish (W78).
#
# It does not matter which mechanism it is. This check compares the two things
# that must agree — "the SHA the gate judged" and "the SHA this ref points at
# now" — and refuses when they diverge. If some other explanation is the true
# one, the comparison simply never fires; it accuses nothing on its own.
#
# WHY REFUSE RATHER THAN WARN. The neighbouring "backend suite was REQUIRED but
# never ran" branch at the end of the hook deliberately only downgrades its
# CLAIM instead of blocking, because that condition is environmental (a machine
# without local PG can do nothing about it) and walling those machines off would
# be worse. This one is the opposite: it is always the pusher's own action, it
# is always fixable in one step (push again — the new tip then gets gated), and
# leaving it unblocked means the pre-push gate, plus the `prepush-guards`
# REQUIRED context built on top of it, can be bypassed by an entirely ordinary
# accident whose window is as wide as the suite's runtime.
#
# CONTRACT
#   argv[1]  file holding the git pre-push protocol lines, verbatim:
#              <local_ref> <local_sha> <remote_ref> <remote_sha>
#   exit 0   every pushed ref still points where the gate judged it
#   exit 1   at least one ref DRIFTED — the push must not proceed
#   exit 2   cannot verify (no file, unreadable, or zero usable lines).
#            An empty read is never a clean read (W84): the caller decides
#            what to do with "I could not look", but it is never "all clear".
#
# Refs whose local_sha is the all-zero SHA are deletions: no commit to compare,
# skipped, and they do NOT count towards the "zero usable lines" test on their
# own — a delete-only push is legitimately unverifiable by this check and says
# so with exit 2 rather than pretending.

ZERO_SHA="0000000000000000000000000000000000000000"

REFS_FILE="${1:-}"

if [ -z "$REFS_FILE" ] || [ ! -r "$REFS_FILE" ]; then
    echo "tip-drift: no readable pre-push ref file ('${REFS_FILE:-<unset>}') — CANNOT VERIFY" >&2
    exit 2
fi

comparable=0
drifted=0

# `sh -e` may be in force in the caller's context; every command substitution
# below is written errexit-immune on purpose. A bare `now=$(git rev-parse …)`
# aborts the whole script the moment the ref does not resolve — which is W101,
# the exact scar that produced the sibling fix this check ships alongside. The
# guard against a decapitated guard is to never write the decapitating form.
while read -r local_ref local_sha _remote_ref _remote_sha; do
    [ -z "$local_ref" ] && continue
    [ -z "$local_sha" ] && continue
    [ "$local_sha" = "$ZERO_SHA" ] && continue   # deletion: nothing to compare

    now=""
    now=$(git rev-parse --verify --quiet "$local_ref" 2>/dev/null) || now=""

    if [ -z "$now" ]; then
        # The ref vanished locally between the push starting and now. That is
        # not evidence of drift, and accusing on it would be an over-match on
        # absence. Report it, do not count it as verified.
        echo "tip-drift: '$local_ref' no longer resolves locally — not verified" >&2
        continue
    fi

    comparable=$((comparable + 1))

    if [ "$now" != "$local_sha" ]; then
        drifted=$((drifted + 1))
        echo "tip-drift: $local_ref"
        echo "    gate judged : $local_sha"
        echo "    now points  : $now"
    fi
done < "$REFS_FILE"

if [ "$comparable" -eq 0 ]; then
    echo "tip-drift: zero comparable refs in '$REFS_FILE' — CANNOT VERIFY" >&2
    exit 2
fi

if [ "$drifted" -gt 0 ]; then
    echo ""
    echo "❌ The branch moved while the pre-push gate was running."
    echo "   The suite that just passed judged a DIFFERENT tree than the one git"
    echo "   is about to send, and git's own summary line names the OLD sha — so"
    echo "   the push log would confirm a commit that is not what lands."
    echo ""
    echo "   Fix: run the push again. The new tip gets gated on its own merits."
    echo "   Rule: never commit on a branch while a push from it is in flight."
    exit 1
fi

echo "tip-drift: $comparable ref(s) still at the sha the gate judged"
exit 0
