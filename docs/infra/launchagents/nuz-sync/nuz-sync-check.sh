#!/bin/bash
#
# nuz-sync-check.sh — quick health probe for the sync daemon
# Called by Claude Code SessionStart hook (must be fast and silent on success).
#
# Exit 0 always (hook failure shouldn't block Claude Code).
# Prints one-line status to stdout only if something's off.
#
set -u

HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
case "$HOST" in
    Nuzantara|nuzantara)
        REPO="$HOME/Desktop/nuzantara"; NODE="Pro" ;;
    Nuzantara-9|nuzantara-9)
        REPO="$HOME/Projects/nuzantara"; NODE="Air" ;;
    *)
        exit 0 ;;
esac

HEARTBEAT="$HOME/logs/nuz-sync/last-run"
STALE_THRESHOLD=600  # 10 minutes

# Daemon running?
if [[ ! -f "$HEARTBEAT" ]]; then
    echo "⚠️  nuz-sync daemon never ran on $NODE — check 'launchctl list | grep nuz-sync'"
    exit 0
fi

last=$(cat "$HEARTBEAT" 2>/dev/null || echo 0)
now=$(date +%s)
age=$((now - last))

if (( age > STALE_THRESHOLD )); then
    mins=$((age / 60))
    echo "⚠️  nuz-sync daemon stale on $NODE (last run ${mins}m ago)"
fi

# Git divergence check (silent on clean)
if [[ -d "$REPO/.git" ]]; then
    branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [[ "$branch" == "main" ]]; then
        ahead=$(git -C "$REPO" rev-list --count origin/main..main 2>/dev/null || echo 0)
        behind=$(git -C "$REPO" rev-list --count main..origin/main 2>/dev/null || echo 0)
        if (( behind > 0 )); then
            echo "ℹ️  nuzantara main is $behind commits behind origin/main"
        fi
        if (( ahead > 0 )); then
            echo "ℹ️  nuzantara main is $ahead commits ahead of origin/main (unpushed)"
        fi
    fi
fi

exit 0
