#!/bin/bash
# install_worktree_hooks.sh — install the two worktree-isolation hooks into
# ~/.claude/hooks/ from this repo dir, then SELF-VERIFY with the innocence vaccine.
#
# Why this exists: install_phase_aware.sh deliberately skips worktree_isolation.py
# ("managed by W79"), so these two hooks had NO installer — which is exactly how
# they DRIFTED (the live copies got fixes the repo source lacked, and vice-versa;
# opus-mythos hooks TAC 2026-06-16). This installer closes that gap and refuses to
# leave a broken hook live: it runs test_hook_innocence.py after copying and rolls
# back if the vaccine goes red.
#
# Run on each machine after merging the vaccine PR:
#   bash infra/claude-hooks/install_worktree_hooks.sh
#
# Idempotent. Backs up any file it overwrites. Kill switch after install:
#   AGENT_WORKTREE_ENFORCEMENT=false (disables both hooks).
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HOME/.claude/hooks"
TS="$(date +%Y%m%d-%H%M%S)"
HOOKS=(worktree_isolation.py worktree_file_write_check.py)

mkdir -p "$DST"

declare -a BACKUPS=()

install_file() {
    local name="$1"
    local src="$SRC/$name"
    local dst="$DST/$name"
    if [ ! -f "$src" ]; then
        echo "  SKIP $name (not in repo dir $SRC)"
        return 1
    fi
    if [ -f "$dst" ] && ! diff -q "$src" "$dst" >/dev/null 2>&1; then
        cp "$dst" "$dst.bak-pre-worktree-$TS"
        BACKUPS+=("$dst.bak-pre-worktree-$TS:$dst")
        echo "  backed up existing $name -> $name.bak-pre-worktree-$TS"
    fi
    cp "$src" "$dst"
    chmod 700 "$dst"
    echo "  installed $name"
}

echo "== installing worktree-isolation hooks into $DST =="
for h in "${HOOKS[@]}"; do
    install_file "$h"
done

echo "== self-verify: running the innocence vaccine against installed hooks =="
# The vaccine copies the REPO hooks into a synthetic tempdir, so it validates the
# logic we just installed (repo == live after copy). A red vaccine = broken hook.
# test_arm_keep_hook.py covers the W80 arm-before-remove guard with REAL git
# worktrees (the synthetic vaccine can't, being a non-git repo) — both must pass.
if python3 "$SRC/test_hook_innocence.py" && python3 "$SRC/test_arm_keep_hook.py"; then
    echo "== VACCINE GREEN — hooks installed and proven to bite only the guilty. =="
    echo "   Reload with /hooks (or restart the session)."
    echo "   Kill switch: AGENT_WORKTREE_ENFORCEMENT=false"
    exit 0
fi

echo "== VACCINE RED — rolling back to avoid leaving a broken hook live =="
for pair in "${BACKUPS[@]}"; do
    bak="${pair%%:*}"; orig="${pair##*:}"
    cp "$bak" "$orig"
    echo "  restored $orig from backup"
done
echo "== rollback complete. Investigate test_hook_innocence.py failures before retrying. =="
exit 1
