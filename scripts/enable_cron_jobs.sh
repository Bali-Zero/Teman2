#!/bin/bash
# enable_cron_jobs.sh — Zero activation script
#
# One-command launchctl load for the 4 cron jobs shipped in
# 2026-04-16 sprint: metabolic, council, curiosity, genome-decay.
#
# Usage (on Air, as antonellosiano):
#     bash scripts/enable_cron_jobs.sh [--unload|--status|--test]
#
# --unload  → launchctl unload all 4 (disable)
# --status  → list current state + last exit codes
# --test    → run all 4 in foreground (dry-run style) to validate

set -euo pipefail

REPO="/Users/antonellosiano/Projects/nuzantara"
LA_DIR="$HOME/Library/LaunchAgents"
PLIST_DIR="$REPO/docs/infra/launchagents"

JOBS=(
    "com.cell.metabolic-rollup"
    "com.matagaruda.council-weekly"
    "com.graph.curiosity-loop"
    "com.cell.genome-decay"
)

usage() {
    echo "Usage: $0 [--unload|--status|--test]"
    echo "  (no args) → symlink + launchctl load all 4"
    echo "  --unload  → launchctl unload all 4"
    echo "  --status  → show current state"
    echo "  --test    → dry-run all wrapper scripts in foreground"
}

status() {
    echo "Cron jobs status:"
    for job in "${JOBS[@]}"; do
        if launchctl list "$job" &>/dev/null; then
            local last_exit
            last_exit=$(launchctl list "$job" 2>/dev/null | awk -F= '/LastExitStatus/ {gsub(/[^0-9-]/,"",$2); print $2}')
            echo "  ✅ $job (LastExitStatus=${last_exit:-?})"
        else
            echo "  ❌ $job (not loaded)"
        fi
    done
}

load_all() {
    mkdir -p "$LA_DIR"
    for job in "${JOBS[@]}"; do
        local src="$PLIST_DIR/${job}.plist"
        local dst="$LA_DIR/${job}.plist"
        if [ ! -f "$src" ]; then
            echo "⚠️  $src missing — skip"
            continue
        fi
        if [ -L "$dst" ] || [ -f "$dst" ]; then
            launchctl unload "$dst" 2>/dev/null || true
            rm -f "$dst"
        fi
        ln -s "$src" "$dst"
        launchctl load "$dst"
        echo "✅ $job loaded"
    done
    echo ""
    status
}

unload_all() {
    for job in "${JOBS[@]}"; do
        local dst="$LA_DIR/${job}.plist"
        launchctl unload "$dst" 2>/dev/null && echo "✅ $job unloaded" || echo "⚠️  $job already unloaded"
        rm -f "$dst"
    done
}

test_all() {
    echo "Foreground test (each script runs once, logs to /tmp/<job>-test.log):"
    for job in "${JOBS[@]}"; do
        local plist="$PLIST_DIR/${job}.plist"
        # Extract first .sh path inside <string>...</string> tags
        local script
        script=$(grep -oE '<string>[^<]+\.sh</string>' "$plist" | head -1 | sed -E 's|<string>(.*)</string>|\1|')
        echo ""
        echo "── $job ── ($script)"
        if [ -z "$script" ]; then
            echo "  ⚠️  no .sh found in $plist"
            continue
        fi
        if [ ! -x "$script" ]; then
            echo "  ⚠️  $script not executable"
            continue
        fi
        if bash "$script" > "/tmp/${job}-test.log" 2>&1; then
            echo "  ✅ exit 0"
        else
            echo "  ❌ exit $? (see /tmp/${job}-test.log)"
        fi
    done
}

case "${1:-load}" in
    --unload) unload_all ;;
    --status) status ;;
    --test)   test_all ;;
    load|"")  load_all ;;
    *)        usage; exit 1 ;;
esac
