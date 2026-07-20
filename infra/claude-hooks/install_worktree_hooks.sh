#!/bin/bash
# install_worktree_hooks.sh — install the two worktree-isolation hooks + the
# runtime-state allowlist data into ~/.claude/hooks/ from this repo dir, then
# SELF-VERIFY with the innocence vaccine.
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
declare -a NEW_FILES=()

install_file() {
    local name="$1"
    local mode="${2:-700}"   # .py hooks are executable (700); data files pass 644
    local src="$SRC/$name"
    local dst="$DST/$name"
    if [ ! -f "$src" ]; then
        echo "  SKIP $name (not in repo dir $SRC)"
        return 1
    fi
    if [ -f "$dst" ]; then
        if ! diff -q "$src" "$dst" >/dev/null 2>&1; then
            cp -p "$dst" "$dst.bak-pre-worktree-$TS"   # -p: backup keeps original mode
            BACKUPS+=("$dst.bak-pre-worktree-$TS:$dst")
            echo "  backed up existing $name -> $name.bak-pre-worktree-$TS"
        fi
    else
        # no prior version to back up → track so rollback removes it (not orphan it)
        NEW_FILES+=("$dst")
    fi
    cp "$src" "$dst"
    chmod "$mode" "$dst"
    echo "  installed $name (mode $mode)"
}

echo "== installing worktree-isolation hooks into $DST =="
for h in "${HOOKS[@]}"; do
    install_file "$h"
done

# runtime_state_allowlist.json is DATA read by worktree_isolation.py (the ff-only
# exception's per-machine allowlist), NOT an executable hook — install it too, as
# 644. Without this the JSON stays absent/stale live while the repo source moves:
# the exact gap that shut the Pro ff-only exception and stranded W91's path fix
# (superscar #1 applied to the guard's own data). Rolled back with the hooks.
install_file runtime_state_allowlist.json 644

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
# NOTE: guard every array value-expansion with a count test — macOS /bin/bash is
# 3.2, where `"${arr[@]}"` on an empty array aborts under `set -u` (would strand
# the rollback half-done). `${#arr[@]}` is safe on an empty declared array.
if [ ${#BACKUPS[@]} -gt 0 ]; then
    for pair in "${BACKUPS[@]}"; do
        bak="${pair%%:*}"; orig="${pair##*:}"
        cp -p "$bak" "$orig"   # -p: restore original content AND mode
        echo "  restored $orig from backup"
    done
fi
if [ ${#NEW_FILES[@]} -gt 0 ]; then
    for nf in "${NEW_FILES[@]}"; do
        rm -f "$nf"
        echo "  removed newly-installed $nf (had no prior version to restore)"
    done
fi
echo "== rollback complete. Investigate test_hook_innocence.py failures before retrying. =="
exit 1
