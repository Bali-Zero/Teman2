#!/usr/bin/env bash
# Lint all project LaunchAgents against VADEMECUM §11.
# Exit code = number of violations found (capped at 255).
#
# Project plist matched: ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist
#
# Rules enforced:
#   - Daemon (no StartInterval AND no StartCalendarInterval) MUST have KeepAlive=true
#     (or a non-empty conditional dict like {NetworkState=true})
#   - Cron-style (StartInterval OR StartCalendarInterval set) SHOULD NOT have
#     KeepAlive=true (mutually exclusive with schedule). Missing KeepAlive on cron
#     is OK (default = false).
#   - All plist MUST have EnvironmentVariables (PATH minimum).
#   - StandardOutPath / StandardErrorPath MUST NOT live under /tmp/ (lost on reboot).
#   - Each daemon MUST be registered in ~/.agent/decisions/job_registry.json
#     (so Sentinel monitors it).
#
# Disabled plist (Disabled=true at top-level) are skipped.

set -u

PLIST_DIR="$HOME/Library/LaunchAgents"
REGISTRY="$HOME/.agent/decisions/job_registry.json"
VIOLATIONS=0
DAEMON_COUNT=0
CRON_COUNT=0
DISABLED_COUNT=0
TOTAL=0

shopt -s nullglob
PLISTS=()
for pat in "$PLIST_DIR"/com.nuzantara.*.plist \
           "$PLIST_DIR"/com.balizero.*.plist \
           "$PLIST_DIR"/com.cell.*.plist; do
    [ -e "$pat" ] && PLISTS+=("$pat")
done

if [ "${#PLISTS[@]}" -eq 0 ]; then
    echo "[ERROR] No project plist found under $PLIST_DIR" >&2
    exit 2
fi

for plist in "${PLISTS[@]}"; do
    TOTAL=$((TOTAL+1))
    label=$(plutil -extract Label raw -- "$plist" 2>/dev/null)
    [ -z "$label" ] && label=$(basename "$plist" .plist)

    # --- Skip if Disabled=true at top level ----------------------------------
    disabled=$(plutil -extract Disabled raw -- "$plist" 2>/dev/null || echo "")
    if [ "$disabled" = "true" ]; then
        DISABLED_COUNT=$((DISABLED_COUNT+1))
        echo "[SKIP] $label: Disabled=true (not enforced)"
        continue
    fi

    # --- Classify daemon vs cron ---------------------------------------------
    has_interval=""
    has_calendar=""
    plutil -extract StartInterval raw -- "$plist" >/dev/null 2>&1 && has_interval=1
    plutil -extract StartCalendarInterval json -- "$plist" >/dev/null 2>&1 && has_calendar=1

    if [ -n "$has_interval" ] || [ -n "$has_calendar" ]; then
        is_cron=true
        CRON_COUNT=$((CRON_COUNT+1))
    else
        is_cron=false
        DAEMON_COUNT=$((DAEMON_COUNT+1))
    fi

    # --- KeepAlive checks ----------------------------------------------------
    # plutil -extract KeepAlive raw → "true" / "false" (bool); fails if absent or dict.
    # plutil -extract KeepAlive json → "true" / "false" / "{...}"; fails only if absent.
    keepalive_json=$(plutil -extract KeepAlive json -- "$plist" 2>/dev/null || echo "")

    if ! $is_cron; then
        if [ -z "$keepalive_json" ]; then
            echo "[VIOLATION] $label: daemon (no schedule) missing KeepAlive directive (must be true)"
            VIOLATIONS=$((VIOLATIONS+1))
        elif [ "$keepalive_json" = "false" ]; then
            echo "[VIOLATION] $label: daemon has KeepAlive=false (must be true; will not respawn)"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
        # KeepAlive=true OR conditional dict ({...}) → accepted
    else
        # Cron must NOT have KeepAlive=true (mutually exclusive with schedule).
        if [ "$keepalive_json" = "true" ]; then
            echo "[VIOLATION] $label: cron-style has KeepAlive=true (must be false or absent)"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi

    # --- EnvironmentVariables required --------------------------------------
    if ! plutil -extract EnvironmentVariables json -- "$plist" >/dev/null 2>&1; then
        echo "[VIOLATION] $label: missing EnvironmentVariables (PATH+HOME mandatory per VADEMECUM §11)"
        VIOLATIONS=$((VIOLATIONS+1))
    fi

    # --- Logs must NOT be in /tmp/ ------------------------------------------
    out=$(plutil -extract StandardOutPath raw -- "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw -- "$plist" 2>/dev/null || echo "")
    if [[ "$out" == /tmp/* ]] || [[ "$err" == /tmp/* ]]; then
        echo "[VIOLATION] $label: logs to /tmp/ (out=$out err=$err) — must use ~/logs/"
        VIOLATIONS=$((VIOLATIONS+1))
    fi

    # --- Daemon must be in job_registry.json --------------------------------
    if ! $is_cron && [ -f "$REGISTRY" ]; then
        if ! jq -e --arg lbl "$label" '.jobs[$lbl] // empty' "$REGISTRY" >/dev/null 2>&1; then
            echo "[VIOLATION] $label: daemon not registered in $REGISTRY"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi
done

echo ""
echo "Plist scanned: $TOTAL ($DAEMON_COUNT daemon, $CRON_COUNT cron-style, $DISABLED_COUNT disabled)"
echo "Total violations: $VIOLATIONS"

# Cap exit code at 255 so we can still distinguish 0 (clean) vs >0 (dirty).
[ "$VIOLATIONS" -gt 255 ] && exit 255
exit "$VIOLATIONS"
