#!/usr/bin/env bash
# Auto-fix project LaunchAgents to satisfy VADEMECUM §11.
#
# Usage:
#   scripts/patch_launchagents.sh --dry-run           # default; print proposed changes
#   scripts/patch_launchagents.sh --apply             # write + launchctl unload/load
#   scripts/patch_launchagents.sh --apply --no-reload # write only, skip launchctl
#   scripts/patch_launchagents.sh --apply --only com.cell.organism,com.balizero.nlm-bridge
#
# Backups: each plist is copied to <plist>.pre-vademecum-audit on first apply.

set -u

DRY_RUN=true
RELOAD=true
ONLY_FILTER=""
ASSUME_YES=false
ADD_OBS_EMIT=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --apply)   DRY_RUN=false; shift ;;
        --add-observatory-emit) ADD_OBS_EMIT=true; shift ;;
        --no-reload) RELOAD=false; shift ;;
        --only)    ONLY_FILTER="$2"; shift 2 ;;
        --yes|-y)  ASSUME_YES=true; shift ;;
        --help|-h)
            sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "[ERROR] unknown arg: $1" >&2; exit 2 ;;
    esac
done

PLIST_DIR="${PLIST_DIR_OVERRIDE:-$HOME/Library/LaunchAgents}"
LOGS_DIR="$HOME/logs"
PATH_VAR="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.pyenv/shims:$HOME/.pyenv/bin"
HOME_VAR="$HOME"

mkdir -p "$LOGS_DIR"

# Helper: inject CELL_OBSERVATORY_EMIT=true into a plist that may be chmod 0444.
# Backs up to .pre-observatory-emit (first time only), unlocks, patches, re-locks.
add_observatory_emit_to_plist() {
    local plist="$1"
    local backup="${plist}.pre-observatory-emit"

    [ -f "$backup" ] || cp "$plist" "$backup"

    local original_mode
    original_mode=$(stat -f "%Lp" "$plist")
    chmod u+w "$plist"

    if /usr/bin/plutil -extract EnvironmentVariables xml1 -o - "$plist" 2>/dev/null | grep -q CELL_OBSERVATORY_EMIT; then
        /usr/bin/plutil -replace EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "true" "$plist"
    else
        /usr/bin/plutil -extract EnvironmentVariables xml1 -o - "$plist" 2>/dev/null >/dev/null \
            || /usr/bin/plutil -insert EnvironmentVariables -dictionary "$plist"
        /usr/bin/plutil -insert EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "true" "$plist"
    fi

    /usr/bin/plutil -lint "$plist" >/dev/null

    chmod "0$original_mode" "$plist"
    echo "[ok] $(basename "$plist")"
}

CHANGES_LOG="/tmp/p0-3-patch-changes.log"
: > "$CHANGES_LOG"

# Counters for summary
TOUCH_COUNT=0
KEEPALIVE_ADDED=0
ENV_ADDED=0
LOG_REWRITTEN=0
RUNATLOAD_AMBIGUOUS=()
DAEMONS_TOUCHED=()
CRONS_TOUCHED=()
SKIPPED_DISABLED=0

shopt -s nullglob
PLISTS=()
for pat in "$PLIST_DIR"/com.nuzantara.*.plist \
           "$PLIST_DIR"/com.balizero.*.plist \
           "$PLIST_DIR"/com.cell.*.plist; do
    [ -e "$pat" ] && PLISTS+=("$pat")
done

[ "${#PLISTS[@]}" -eq 0 ] && [ "$ADD_OBS_EMIT" = "false" ] && { echo "[ERROR] No project plist found" >&2; exit 2; }

# Prefix used by all log lines for grep-ability
PREFIX="[DRY]"
$DRY_RUN || PREFIX="[APPLY]"

log() { echo "$PREFIX $*" | tee -a "$CHANGES_LOG"; }

# Filter helper for --only
matches_filter() {
    local label="$1"
    [ -z "$ONLY_FILTER" ] && return 0
    local IFS=,
    for needle in $ONLY_FILTER; do
        [ "$label" = "$needle" ] && return 0
    done
    return 1
}

for plist in ${PLISTS[@]+"${PLISTS[@]}"}; do
    label=$(plutil -extract Label raw -- "$plist" 2>/dev/null)
    [ -z "$label" ] && label=$(basename "$plist" .plist)

    if ! matches_filter "$label"; then
        continue
    fi

    # Skip Disabled
    disabled=$(plutil -extract Disabled raw -- "$plist" 2>/dev/null || echo "")
    if [ "$disabled" = "true" ]; then
        SKIPPED_DISABLED=$((SKIPPED_DISABLED+1))
        continue
    fi

    # Classify
    has_interval=""
    has_calendar=""
    plutil -extract StartInterval raw -- "$plist" >/dev/null 2>&1 && has_interval=1
    plutil -extract StartCalendarInterval json -- "$plist" >/dev/null 2>&1 && has_calendar=1

    if [ -n "$has_interval" ] || [ -n "$has_calendar" ]; then
        is_cron=true
    else
        is_cron=false
    fi

    runatload=$(plutil -extract RunAtLoad raw -- "$plist" 2>/dev/null || echo "")
    keepalive_json=$(plutil -extract KeepAlive json -- "$plist" 2>/dev/null || echo "")

    # Compute proposed changes
    changes=()

    # 1. Daemon → KeepAlive=true if missing or false
    if ! $is_cron; then
        if [ -z "$keepalive_json" ]; then
            changes+=("ADD KeepAlive=true (was: absent)")
            if ! $is_cron && [ "$runatload" = "true" ]; then
                # Edge case: RunAtLoad=true + no schedule + no KeepAlive
                # → could be one-shot-on-load (e.g. boot script) or daemon
                RUNATLOAD_AMBIGUOUS+=("$label")
            fi
        elif [ "$keepalive_json" = "false" ]; then
            changes+=("REPLACE KeepAlive=true (was: false)")
        fi
        # KeepAlive=true / dict → already conformant
    else
        if [ "$keepalive_json" = "true" ]; then
            changes+=("REPLACE KeepAlive=false (was: true on cron-style)")
        fi
    fi

    # 2. Add EnvironmentVariables if missing (BOTH daemon and cron need PATH for hooks)
    if ! plutil -extract EnvironmentVariables json -- "$plist" >/dev/null 2>&1; then
        changes+=("ADD EnvironmentVariables{PATH=...,HOME=$HOME_VAR}")
    fi

    # 3. Rewrite /tmp/ log paths
    out=$(plutil -extract StandardOutPath raw -- "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw -- "$plist" 2>/dev/null || echo "")
    new_out=""
    new_err=""
    if [[ "$out" == /tmp/* ]]; then
        new_out="$LOGS_DIR/$(basename "$out")"
        changes+=("REWRITE StandardOutPath: $out → $new_out")
    fi
    if [[ "$err" == /tmp/* ]]; then
        new_err="$LOGS_DIR/$(basename "$err")"
        changes+=("REWRITE StandardErrorPath: $err → $new_err")
    fi

    [ "${#changes[@]}" -eq 0 ] && continue

    TOUCH_COUNT=$((TOUCH_COUNT+1))
    if $is_cron; then
        CRONS_TOUCHED+=("$label")
    else
        DAEMONS_TOUCHED+=("$label")
    fi

    log "─── $label  (path: $plist) ───"
    log "    classify: $($is_cron && echo 'cron-style' || echo 'daemon')${runatload:+ RunAtLoad=$runatload}"
    for ch in "${changes[@]}"; do
        log "    • $ch"
    done

    # Apply
    if ! $DRY_RUN; then
        backup="${plist}.pre-vademecum-audit"
        if [ ! -f "$backup" ]; then
            cp -p "$plist" "$backup"
            log "    backup: $backup"
        else
            log "    backup: $backup (already exists, kept)"
        fi

        # 1. KeepAlive
        if ! $is_cron; then
            if [ -z "$keepalive_json" ]; then
                plutil -insert KeepAlive -bool true -- "$plist" \
                    && KEEPALIVE_ADDED=$((KEEPALIVE_ADDED+1))
            elif [ "$keepalive_json" = "false" ]; then
                plutil -replace KeepAlive -bool true -- "$plist" \
                    && KEEPALIVE_ADDED=$((KEEPALIVE_ADDED+1))
            fi
        else
            if [ "$keepalive_json" = "true" ]; then
                plutil -replace KeepAlive -bool false -- "$plist"
            fi
        fi

        # 2. EnvironmentVariables
        if ! plutil -extract EnvironmentVariables json -- "$plist" >/dev/null 2>&1; then
            plutil -insert EnvironmentVariables -dictionary -- "$plist" \
                && plutil -insert EnvironmentVariables.PATH -string "$PATH_VAR" -- "$plist" \
                && plutil -insert EnvironmentVariables.HOME -string "$HOME_VAR" -- "$plist" \
                && ENV_ADDED=$((ENV_ADDED+1))
        fi

        # 3. log path rewrites
        if [ -n "$new_out" ]; then
            plutil -replace StandardOutPath -string "$new_out" -- "$plist" \
                && LOG_REWRITTEN=$((LOG_REWRITTEN+1))
        fi
        if [ -n "$new_err" ]; then
            plutil -replace StandardErrorPath -string "$new_err" -- "$plist" \
                && LOG_REWRITTEN=$((LOG_REWRITTEN+1))
        fi

        # 4. launchctl reload (skip with --no-reload)
        if $RELOAD; then
            log "    launchctl unload + load"
            launchctl unload "$plist" 2>/dev/null || true
            launchctl load "$plist" 2>/dev/null || \
                log "    [WARN] launchctl load returned non-zero — verify manually"
        else
            log "    (--no-reload: file changed, launchctl skipped)"
        fi
    fi
done

# Observatory emit injection (--add-observatory-emit)
if [ "$ADD_OBS_EMIT" = "true" ]; then
    for plist in "$PLIST_DIR"/com.cell.organism.plist \
                 "$PLIST_DIR"/com.balizero.seo-cell*.plist \
                 "$PLIST_DIR"/com.balizero.evaluator*.plist; do
        [ -f "$plist" ] || continue
        if [ "$DRY_RUN" = "true" ]; then
            echo "[dry-run] would add CELL_OBSERVATORY_EMIT=true to $(basename "$plist")"
        else
            add_observatory_emit_to_plist "$plist"
        fi
    done
fi

# Summary
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "SUMMARY ($($DRY_RUN && echo 'DRY-RUN' || echo 'APPLIED'))"
echo "════════════════════════════════════════════════════════════════"
echo "Plist proposed for change: $TOUCH_COUNT"
echo "  ├ daemons:       ${#DAEMONS_TOUCHED[@]}"
echo "  └ cron-style:    ${#CRONS_TOUCHED[@]}"
echo "Skipped (Disabled): $SKIPPED_DISABLED"
echo ""
if $DRY_RUN; then
    echo "Proposed actions:"
    echo "  KeepAlive add/fix:       (would patch ${#DAEMONS_TOUCHED[@]} daemon entries)"
    echo "  EnvironmentVariables:    (counted in dry-run; see [DRY] lines)"
    echo "  /tmp → ~/logs rewrites:  (counted in dry-run; see [DRY] lines)"
else
    echo "Actually applied:"
    echo "  KeepAlive=true:                $KEEPALIVE_ADDED"
    echo "  EnvironmentVariables added:    $ENV_ADDED"
    echo "  Log paths rewritten /tmp→logs: $LOG_REWRITTEN"
fi

if [ "${#DAEMONS_TOUCHED[@]}" -gt 0 ]; then
    echo ""
    echo "Daemons touched (KeepAlive impact):"
    printf '  - %s\n' "${DAEMONS_TOUCHED[@]}"
fi

if [ "${#RUNATLOAD_AMBIGUOUS[@]}" -gt 0 ]; then
    echo ""
    echo "⚠️  RunAtLoad=true + no schedule + no KeepAlive (AMBIGUOUS — review manually):"
    printf '  - %s\n' "${RUNATLOAD_AMBIGUOUS[@]}"
    echo "  Heuristic above classifies these as DAEMON. Confirm before --apply."
fi

if [ "${#CRONS_TOUCHED[@]}" -gt 0 ]; then
    echo ""
    echo "Cron-style touched:"
    printf '  - %s\n' "${CRONS_TOUCHED[@]}"
fi

echo ""
echo "Full change log: $CHANGES_LOG"
echo ""
$DRY_RUN && echo "Re-run with --apply to actually patch."
exit 0
