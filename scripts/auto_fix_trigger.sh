#!/bin/bash
# Auto-Fix Trigger for Nuzantara
# ================================
# Questo script:
# 1. Controlla Sentry per nuovi errori
# 2. Se ci sono errori, lancia Claude Code per il fix automatico
# 3. Crea un commit locale (senza push)
#
# Uso:
#   ./scripts/auto_fix_trigger.sh           # Run once
#   ./scripts/auto_fix_trigger.sh --daemon  # Run as daemon (every 5 min)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_FILE="$PROJECT_ROOT/data/sentry_report.md"
LOCK_FILE="/tmp/nuzantara_autofix.lock"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        PID=$(cat "$LOCK_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "${YELLOW}Another instance is running (PID: $PID)${NC}"
            exit 1
        else
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $$ > "$LOCK_FILE"
    trap "rm -f $LOCK_FILE" EXIT
}

check_errors() {
    log "Checking Sentry for errors..."
    cd "$PROJECT_ROOT"

    # Run the Python monitor
    python scripts/sentry_monitor.py

    # Check if report was generated and has content
    if [ -f "$REPORT_FILE" ]; then
        ISSUE_COUNT=$(grep -c "^## \[" "$REPORT_FILE" 2>/dev/null || echo "0")
        if [ "$ISSUE_COUNT" -gt 0 ]; then
            log "${RED}Found $ISSUE_COUNT unresolved issues${NC}"
            return 0
        fi
    fi

    log "${GREEN}No errors to fix${NC}"
    return 1
}

run_claude_fix() {
    log "Running Claude Code auto-fix..."
    cd "$PROJECT_ROOT"

    # Create a branch for the fix
    BRANCH_NAME="auto/sentry-fix-$(date '+%Y%m%d-%H%M')"
    git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"

    # Run Claude Code with the sentry-fix command
    # This uses the /sentry-fix slash command we created
    claude --print "/sentry-fix" || {
        log "${YELLOW}Claude Code not available, showing manual instructions${NC}"
        echo ""
        echo "To fix manually:"
        echo "  1. cd $PROJECT_ROOT"
        echo "  2. claude /sentry-fix"
        echo ""
        return 1
    }

    # Check if there are changes to commit
    if ! git diff --quiet; then
        log "Creating commit with fixes..."
        git add -A
        git commit -m "fix(sentry): Auto-fix errors from Sentry

🤖 Generated with Claude Code (auto-fix)

Errors fixed from: $REPORT_FILE"

        log "${GREEN}Fix committed to branch: $BRANCH_NAME${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Review changes: git diff main...$BRANCH_NAME"
        echo "  2. Push branch and create merge request as needed"
    else
        log "${YELLOW}No changes made by Claude Code${NC}"
    fi
}

run_once() {
    check_lock

    if check_errors; then
        run_claude_fix
    fi
}

run_daemon() {
    INTERVAL=${1:-300}  # Default 5 minutes
    log "Starting daemon mode (interval: ${INTERVAL}s)"

    while true; do
        run_once || true
        log "Sleeping for ${INTERVAL}s..."
        sleep "$INTERVAL"
    done
}

# Main
case "${1:-}" in
    --daemon)
        run_daemon "${2:-300}"
        ;;
    --help)
        echo "Usage: $0 [--daemon [interval_seconds]]"
        echo ""
        echo "Options:"
        echo "  --daemon [interval]  Run continuously (default: 300s)"
        echo "  --help               Show this help"
        ;;
    *)
        run_once
        ;;
esac
