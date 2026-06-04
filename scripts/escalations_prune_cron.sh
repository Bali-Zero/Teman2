#!/bin/bash
# P1-8: daily cron wrapper for escalations SQLite mirror.
# Runs prune (deletes resolved >30d) then archive (gzip-archives unresolved >90d).
#
# Loaded via infra/launchd/com.nuzantara.escalations-prune.plist at 03:00 WITA.
set -u  # do NOT use -e: we want both subcommands to attempt even if one fails.

PYTHON="${PYTHON:-/usr/bin/env python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATE="${SCRIPT_DIR}/migrate_escalations_to_sqlite.py"

if [ ! -f "$MIGRATE" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ERROR: migrate script not found: $MIGRATE" >&2
    exit 2
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) escalations-prune: starting"

PRUNE_RC=0
$PYTHON "$MIGRATE" prune --older-than-days 30 || PRUNE_RC=$?
if [ "$PRUNE_RC" -ne 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN: prune exited $PRUNE_RC" >&2
fi

ARCHIVE_RC=0
$PYTHON "$MIGRATE" archive --older-than-days 90 || ARCHIVE_RC=$?
if [ "$ARCHIVE_RC" -ne 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN: archive exited $ARCHIVE_RC" >&2
fi

# S3 (2026-06-02): the two subcommands above only touch the out-of-tree SQLite
# mirror. The canonical git-tracked JSONL (shared/escalations_<machine>.jsonl)
# has no rotation of its own — a W61-class retry storm refilled it to >1MB once
# (4519 lines, hand-truncated by PR #972). escalations_rotate.py gzip-archives
# then truncates it when it crosses the size/line threshold. --commit is
# deliberately OFF (a cron must not git-commit a shared worktree mid-session —
# cicatrix W50/W51/W59 family); the empty file propagates via the normal commit
# flow / canonical node. Lossless: every line is also in the SQLite mirror.
ROTATE="${SCRIPT_DIR}/escalations_rotate.py"
ROTATE_RC=0
if [ -f "$ROTATE" ]; then
    $PYTHON "$ROTATE" || ROTATE_RC=$?
    if [ "$ROTATE_RC" -ne 0 ]; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN: rotate exited $ROTATE_RC" >&2
    fi
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN: rotate script not found: $ROTATE" >&2
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) escalations-prune: done (prune_rc=$PRUNE_RC archive_rc=$ARCHIVE_RC rotate_rc=$ROTATE_RC)"
# Exit non-zero only if BOTH SQLite subcommands failed — partial success keeps
# the LaunchAgent green. Rotation failure alone is a WARN (the SQLite mirror,
# the durable store, is unaffected).
if [ "$PRUNE_RC" -ne 0 ] && [ "$ARCHIVE_RC" -ne 0 ]; then
    exit 1
fi
exit 0
