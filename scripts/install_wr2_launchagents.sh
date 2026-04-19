#!/bin/bash
# install_wr2_launchagents.sh — copy + load War Room 2.0 LaunchAgents.
#
# Run ONCE from the worktree (or from ~/Desktop/nuzantara after merge):
#   ./scripts/install_wr2_launchagents.sh
#
# Supports two modes via the WR2_MODE env var:
#   load   (default)   copy plists to ~/Library/LaunchAgents and `launchctl load -w`
#   unload             `launchctl unload` + delete copies from ~/Library/LaunchAgents
#   dry-run            show what would happen, do not touch launchd
#
# Safety:
#   - Refuses to overwrite an existing plist with different content
#     unless WR2_FORCE=1 is set.
#   - Never touches the post-publish-poller / intel.nightly plists from the
#     legacy pipeline — those live under different labels.
#   - Before enabling, verify:
#       * DATABASE_URL_LOCAL is set in ~/.nuzantara-secrets.env (fly proxy or
#         equivalent exposing nuzantara-postgres to localhost)
#       * Telegram token + owner chat id in the secrets file
#       * apps/backend-rag/.venv is populated with runtime deps

set -euo pipefail

MODE="${WR2_MODE:-load}"
FORCE="${WR2_FORCE:-0}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_ROOT/infra/launchagents"
DST_DIR="$HOME/Library/LaunchAgents"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "ERROR: $SRC_DIR not found — run from repo root" >&2
    exit 1
fi

PLISTS=()
while IFS= read -r line; do
    PLISTS+=("$line")
done < <(cd "$SRC_DIR" && ls com.balizero.wr2.*.plist 2>/dev/null)
if [[ ${#PLISTS[@]} -eq 0 ]]; then
    echo "ERROR: no com.balizero.wr2.*.plist found in $SRC_DIR" >&2
    exit 1
fi

echo "War Room 2.0 LaunchAgent installer — mode=$MODE, ${#PLISTS[@]} agents"
echo "  source: $SRC_DIR"
echo "  target: $DST_DIR"
echo

case "$MODE" in
    load)
        mkdir -p "$DST_DIR"
        for P in "${PLISTS[@]}"; do
            SRC="$SRC_DIR/$P"
            DST="$DST_DIR/$P"
            if [[ -f "$DST" ]] && ! cmp -s "$SRC" "$DST"; then
                if [[ "$FORCE" != "1" ]]; then
                    echo "  ⚠️  $P already exists with different content — skip (set WR2_FORCE=1 to overwrite)"
                    continue
                fi
                echo "  ✓  overwriting $P"
            else
                echo "  ✓  installing $P"
            fi
            cp "$SRC" "$DST"
            launchctl unload -w "$DST" 2>/dev/null || true
            launchctl load   -w "$DST"
        done
        echo
        echo "Loaded. Verify with: launchctl list | grep com.balizero.wr2"
        ;;
    unload)
        for P in "${PLISTS[@]}"; do
            DST="$DST_DIR/$P"
            if [[ -f "$DST" ]]; then
                echo "  ✗  unloading $P"
                launchctl unload -w "$DST" 2>/dev/null || true
                rm "$DST"
            else
                echo "  -  $P not installed"
            fi
        done
        ;;
    dry-run)
        for P in "${PLISTS[@]}"; do
            echo "  would install: $P"
        done
        ;;
    *)
        echo "ERROR: unknown mode '$MODE' (use load|unload|dry-run)" >&2
        exit 64
        ;;
esac
