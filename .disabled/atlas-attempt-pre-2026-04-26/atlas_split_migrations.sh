#!/usr/bin/env bash
# atlas_split_migrations.sh — split Nuzantara migrations into Atlas-compatible pairs.
#
# The runtime migration runner (apps/backend-rag/backend/db/migration_manager.py)
# uses single SQL files with a `-- === ROLLBACK ===` marker separating the
# forward statements from the rollback statements. Atlas's `migrate lint`
# expects either golang-migrate-style _up.sql/_down.sql pairs or a versioned
# directory; this adapter produces the former from our format on the fly.
#
# Cutoff: only files whose numeric prefix is >= ROLLBACK_REQUIRED_FROM
# (default 114) are emitted. Older migrations are grandfathered (see
# LEGACY_NO_ROLLBACK_WHITELIST in migration_base.py); we skip them entirely.
#
# Usage: atlas_split_migrations.sh <src_dir> <dst_dir>
# Exit: 0 on success, non-zero on parse/IO error.

set -euo pipefail

ROLLBACK_REQUIRED_FROM="${ROLLBACK_REQUIRED_FROM:-114}"

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <src_dir> <dst_dir>" >&2
    exit 2
fi

src_dir="$1"
dst_dir="$2"

if [[ ! -d "$src_dir" ]]; then
    echo "error: src_dir '$src_dir' is not a directory" >&2
    exit 1
fi

mkdir -p "$dst_dir"

emitted=0
skipped=0

# Iterate sorted so generated _up.sql / _down.sql pairs land in the same
# numeric order Atlas will pick up (file system order matters for atlas.sum).
shopt -s nullglob
for src_file in $(ls "$src_dir"/*.sql 2>/dev/null | sort); do
    base="$(basename "$src_file" .sql)"

    # Numeric prefix at the start (e.g. "138_wr2_status_notify" -> "138").
    if [[ ! "$base" =~ ^([0-9]+)_ ]]; then
        echo "skip (unparseable name): $base" >&2
        skipped=$((skipped + 1))
        continue
    fi
    num="${BASH_REMATCH[1]}"
    # Strip leading zeros so 092 < 114 in arithmetic comparison.
    num=$((10#$num))

    if (( num < ROLLBACK_REQUIRED_FROM )); then
        skipped=$((skipped + 1))
        continue
    fi

    up_path="$dst_dir/${base}_up.sql"
    down_path="$dst_dir/${base}_down.sql"

    # awk splits the file at the rollback marker. Marker line itself is
    # excluded from both halves. Emits an exit code we read via $? so we
    # can detect "marker missing" vs "marker present but empty rollback".
    awk -v up="$up_path" -v down="$down_path" '
    BEGIN { phase = "up"; saw_marker = 0 }
    /^[[:space:]]*--[[:space:]]*===[[:space:]]*ROLLBACK[[:space:]]*===[[:space:]]*$/ {
        phase = "down"
        saw_marker = 1
        next
    }
    {
        if (phase == "up") {
            print > up
        } else {
            print > down
        }
    }
    END {
        # No-op marker file so down_path always exists; Atlas treats an
        # empty file as "no down migration" which is exactly what we want
        # to surface as a lint error.
        if (!saw_marker) {
            printf "" > down
        }
    }
    ' "$src_file"

    emitted=$((emitted + 1))
done

echo "atlas_split_migrations: emitted=$emitted skipped=$skipped src=$src_dir dst=$dst_dir"
