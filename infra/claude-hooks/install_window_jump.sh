#!/bin/bash
# install_window_jump.sh — install the WINDOW JUMP quartet into $HOME on a seat.
#
# The four DECLARED pairs of the jump, in the order the chain uses them:
#   context_window_guard.py  the PreToolUse gate that decides to jump — and where
#                            the gesture RETRY and the from_pid chain-walk live,
#                            so a seat installed without it gets v1 behaviour
#                            from a v2 checkout;
#   window_jump.sh           the AppleScript gesture;
#   nz-jump                  the one word typed into the new window;
#   context_jump_resume.py   the SessionStart injector that stamps to_session.
#
# #5987 shipped the files and DECLARED them in infra/home-fork/declared-
# pairs.json, but shipped no installer: each machine was armed by hand, which is
# cicatrix #1 (HOME-fork drift) waiting to happen — the repo moves, the live copy
# does not, and the guard fires on a seat whose window_jump.sh is the version
# that typed nothing. This script is the one gesture that closes the gap.
#
# This script reads the LIVE paths from declared-pairs.json, never hardcoding them:
# the declaration is the contract, and an installer that disagrees with it is
# just a second contract.
#
# Registers NOTHING in settings.json: the guard's own PreToolUse registration is
# a separate, deliberate act (see PENDING-ARMS.md) — this script only makes the
# four live copies match the checkout, which is cicatrix #1's cure, not #2's.
#
#   bash infra/claude-hooks/install_window_jump.sh          # install + self-verify
#   bash infra/claude-hooks/install_window_jump.sh --check   # report only, write nothing
#
# Kill switches after install: CONTEXT_JUMP_OFF=1 (no jump), CONTEXT_JUMP_NO_SPAWN=1
# (file but no gesture), CONTEXT_GUARD_OFF=1 (no guard at all).
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SRC/../.." && pwd)"
PAIRS="$REPO/infra/home-fork/declared-pairs.json"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

[ -f "$PAIRS" ] || { echo "FATAL: no declared-pairs.json at $PAIRS"; exit 2; }

# repo-relative source -> the live path DECLARED for it (tilde already expanded).
# A while-read loop, not mapfile: /bin/bash on macOS is 3.2 and has no mapfile.
PY_PAIRS='
import json, os, sys
want = {"infra/claude-hooks/context_window_guard.py",
        "infra/claude-hooks/window_jump.sh",
        "infra/claude-hooks/nz-jump.sh",
        "infra/claude-hooks/context_jump_resume.py"}
pairs = json.load(open(sys.argv[1]))["pairs"]
seen = set()
for p in pairs:
    repo = p.get("repo")
    if repo in want and repo not in seen:
        seen.add(repo)
        print(repo + chr(9) + os.path.expanduser(p["live"]))
for miss in sorted(want - seen):
    print("MISSING" + chr(9) + miss)
'

ROWS=()
while IFS= read -r line; do
    [ -n "$line" ] && ROWS+=("$line")
done < <(python3 -c "$PY_PAIRS" "$PAIRS")
[ "${#ROWS[@]}" -gt 0 ] || { echo "FATAL: declared-pairs.json unreadable or empty"; exit 2; }

for row in "${ROWS[@]}"; do
    [ "${row%%	*}" = "MISSING" ] && { echo "FATAL: not declared in declared-pairs.json: ${row#*	}"; exit 2; }
done
[ "${#ROWS[@]}" -eq 4 ] || { echo "FATAL: expected 4 declared pairs, got ${#ROWS[@]}"; exit 2; }

echo "== window jump: ${#ROWS[@]} declared pairs (guard + gesture + launcher + resume) =="
CHANGED=0
for row in "${ROWS[@]}"; do
    rel="${row%%	*}"; live="${row#*	}"
    from="$REPO/$rel"
    [ -f "$from" ] || { echo "FATAL: missing in repo: $rel"; exit 2; }
    if cmp -s "$from" "$live" 2>/dev/null; then
        echo "  = $live (already canon)"
        continue
    fi
    CHANGED=$((CHANGED+1))
    if [ "$CHECK_ONLY" = "1" ]; then
        echo "  ! $live DIFFERS from $rel (would install)"
        continue
    fi
    mkdir -p "$(dirname "$live")"
    cp "$from" "$live"
    chmod 0700 "$live"
    echo "  + $live <- $rel (0700)"
done

if [ "$CHECK_ONLY" = "1" ]; then
    echo "== check only: $CHANGED pair(s) would change, nothing written =="
    [ "$CHANGED" -eq 0 ] || exit 1
    exit 0
fi

echo "== self-verify: the gesture corpus against the INSTALLED window_jump.sh =="
INSTALLED_GESTURE="$(for row in "${ROWS[@]}"; do
    [ "${row%%	*}" = "infra/claude-hooks/window_jump.sh" ] && echo "${row#*	}"; done)"
if WINDOW_JUMP_SH="$INSTALLED_GESTURE" bash "$SRC/test_window_jump_gesture.sh"; then
    echo "== GREEN — the installed gesture types into the NEW window (osascript shimmed). =="
    echo "   The guard spawns it: nothing to register. Kill switch: CONTEXT_JUMP_OFF=1"
    exit 0
fi
echo "== RED — the INSTALLED copy fails its own corpus. Do not trust the jump on this seat:"
echo "   read infra/claude-hooks/test_window_jump_gesture.sh output above, fix the repo copy,"
echo "   re-run. CONTEXT_JUMP_OFF=1 disarms the jump meanwhile (the guard's deny stays)."
exit 1
