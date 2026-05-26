#!/usr/bin/env bash
# L5.2 Phase 2b trigger wrapper (LaunchAgent oneshot semantics via gate).
#
# Fires daily but EXITS SILENTLY before target date (2026-06-02).
# Once target date is reached:
#   1. Run l5_2_phase2b_auto_analyzer.py
#   2. Self-unload the LaunchAgent via launchctl bootout (oneshot complete)
#   3. Mark sentinel file so subsequent fires are no-ops
#
# Cron cadence: daily 09:00 WITA via StartCalendarInterval (no Year field
# support in plist → daily check + gate is the cleanest pattern).
#
# Reference: scripts/ci/l5_2_phase2b_auto_analyzer.py

set -u

TARGET_DATE="2026-06-02"
TODAY="$(date -u +%Y-%m-%d)"
SENTINEL="$HOME/.agent/l5-2-phase2b-fired.sentinel"
ANALYZER="$HOME/Desktop/nuzantara/scripts/ci/l5_2_phase2b_auto_analyzer.py"
LAUNCH_AGENT_LABEL="com.balizero.l5-2-phase2b-trigger"
LOG_DIR="$HOME/logs/l5-2-phase2b-analyzer"
mkdir -p "$(dirname "$SENTINEL")" "$LOG_DIR"

# Already fired? Self-cleanup if somehow still loaded.
if [ -f "$SENTINEL" ]; then
    echo "[$(date -Iseconds)] L5.2 Phase 2b already fired ($(cat "$SENTINEL"))"
    launchctl bootout "gui/$(id -u)/${LAUNCH_AGENT_LABEL}" 2>/dev/null || true
    exit 0
fi

# Before target date? Silent skip.
if [[ "$TODAY" < "$TARGET_DATE" ]]; then
    echo "[$(date -Iseconds)] gate: today=$TODAY < target=$TARGET_DATE — skip"
    exit 0
fi

# Past target → fire analyzer
echo "[$(date -Iseconds)] L5.2 Phase 2b GATE OPEN (today=$TODAY ≥ target=$TARGET_DATE)"

# Source secrets (Telegram tokens) if available
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env" || echo "WARN: secrets source failed (continuing)"
    set +a
fi

# Find Python (prefer pyenv 3.11, fall back to python3)
PYTHON_BIN=""
if [ -x "$HOME/.pyenv/versions/3.11.11/bin/python3" ]; then
    PYTHON_BIN="$HOME/.pyenv/versions/3.11.11/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "[$(date -Iseconds)] FATAL: no python3 found"
    exit 1
fi

# Ensure gh CLI is in PATH (Homebrew location)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v gh >/dev/null 2>&1; then
    echo "[$(date -Iseconds)] FATAL: gh CLI not in PATH"
    exit 1
fi

# Run analyzer
LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%dT%H%M%SZ).log"
echo "[$(date -Iseconds)] running analyzer, log: $LOG_FILE"
"$PYTHON_BIN" "$ANALYZER" > "$LOG_FILE" 2>&1
ANALYZER_EXIT=$?
echo "[$(date -Iseconds)] analyzer exit=$ANALYZER_EXIT"

# Mark fired (regardless of exit — we only want to run once)
echo "$(date -Iseconds) exit=$ANALYZER_EXIT" > "$SENTINEL"

# Self-unload (oneshot complete)
launchctl bootout "gui/$(id -u)/${LAUNCH_AGENT_LABEL}" 2>/dev/null || true
echo "[$(date -Iseconds)] LaunchAgent unloaded — oneshot complete"

exit "$ANALYZER_EXIT"
