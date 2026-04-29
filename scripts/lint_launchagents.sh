#!/usr/bin/env bash
# Lint all project LaunchAgents against VADEMECUM §11 + Renaissance PR-B1.
# Exit code = number of violations found (capped at 255).
#
# Project plist matched: ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist
#
# Rules enforced (VADEMECUM §11 baseline):
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
# Rules added by Renaissance PR-B1 (audit 2026-04-29):
#   - If ProgramArguments references "claude" CLI, EnvironmentVariables.PATH
#     MUST include $HOME/.local/bin or $HOME/.claude/local (where the OAuth
#     CLI shim lives). Caught by audit chunk3 P0: dlq_autopilot couldn't
#     reach the binary because PATH was hardcoded to /opt/homebrew only.
#   - Pyenv version pinned in ProgramArguments (e.g. .pyenv/versions/3.11.9/)
#     MUST match an installed pyenv version (`pyenv versions`). Caught by
#     audit chunk1: intel-radar-daily-digest pinned 3.11.9, only 3.11.11
#     installed → dead daemon.
#   - First positional argument of ProgramArguments (the script path) MUST
#     exist on disk. Caught by audit chunk1: wr2_fact_checker.py +
#     wr2_fact_extractor.py referenced but not in repo.
#   - A plist labelled X MUST NOT have a duplicate cron entry on the same
#     command — the launchd<->cron pair causes double-fire and confused
#     state. Caught by audit chunk3: fly-restart-loop-detector ran from
#     both cron */15 AND LaunchAgent.
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
    label=$(plutil -extract Label raw -o - -- "$plist" 2>/dev/null)
    [ -z "$label" ] && label=$(basename "$plist" .plist)

    # --- Skip if Disabled=true at top level ----------------------------------
    disabled=$(plutil -extract Disabled raw -o - -- "$plist" 2>/dev/null || echo "")
    if [ "$disabled" = "true" ]; then
        DISABLED_COUNT=$((DISABLED_COUNT+1))
        echo "[SKIP] $label: Disabled=true (not enforced)"
        continue
    fi

    # --- Classify daemon vs cron ---------------------------------------------
    has_interval=""
    has_calendar=""
    plutil -extract StartInterval raw -o - -- "$plist" >/dev/null 2>&1 && has_interval=1
    plutil -extract StartCalendarInterval json -o - -- "$plist" >/dev/null 2>&1 && has_calendar=1

    if [ -n "$has_interval" ] || [ -n "$has_calendar" ]; then
        is_cron=true
        CRON_COUNT=$((CRON_COUNT+1))
    else
        is_cron=false
        DAEMON_COUNT=$((DAEMON_COUNT+1))
    fi

    # --- KeepAlive checks ----------------------------------------------------
    # On macOS (>=Sequoia, plutil 1.x) `-extract X json` rejects bool/string
    # leaves with "Invalid object for JSON format" — works only for dict/array.
    # We use `raw` (which prints booleans as "true"/"false") for the leaf
    # case and fall back to `json` only to detect the dict shape.
    keepalive_raw=$(plutil -extract KeepAlive raw -o - -- "$plist" 2>/dev/null || echo "__absent__")
    if [ "$keepalive_raw" = "__absent__" ]; then
        # Either truly absent OR present-as-dict (raw rejects dicts). Probe
        # via json — success means dict/array, failure means truly absent.
        if plutil -extract KeepAlive json -o - -- "$plist" >/dev/null 2>&1; then
            keepalive_kind="dict"   # {NetworkState=true, ...} — accepted as conditional KeepAlive
        else
            keepalive_kind="absent"
        fi
    elif [ "$keepalive_raw" = "true" ]; then
        keepalive_kind="true"
    elif [ "$keepalive_raw" = "false" ]; then
        keepalive_kind="false"
    else
        keepalive_kind="other"  # shouldn't happen; treat as present
    fi

    if ! $is_cron; then
        case "$keepalive_kind" in
            absent)
                echo "[VIOLATION] $label: daemon (no schedule) missing KeepAlive directive (must be true)"
                VIOLATIONS=$((VIOLATIONS+1))
                ;;
            false)
                echo "[VIOLATION] $label: daemon has KeepAlive=false (must be true; will not respawn)"
                VIOLATIONS=$((VIOLATIONS+1))
                ;;
            true|dict|other) : ;;  # accepted
        esac
    else
        # Cron must NOT have KeepAlive=true (mutually exclusive with schedule).
        if [ "$keepalive_kind" = "true" ]; then
            echo "[VIOLATION] $label: cron-style has KeepAlive=true (must be false or absent)"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi

    # --- EnvironmentVariables required --------------------------------------
    if ! plutil -extract EnvironmentVariables json -o - -- "$plist" >/dev/null 2>&1; then
        echo "[VIOLATION] $label: missing EnvironmentVariables (PATH+HOME mandatory per VADEMECUM §11)"
        VIOLATIONS=$((VIOLATIONS+1))
    fi

    # --- ProgramArguments parsing (cached for subsequent checks) ------------
    prog_args_json=$(plutil -extract ProgramArguments json -o - -- "$plist" 2>/dev/null || echo "[]")
    # Flatten args to a single space-separated string for substring search.
    # We do this in python for safe JSON parsing (some plist embed long
    # /bin/zsh -lc "<long shell>" strings with quotes).
    prog_args_flat=$(python3 -c "
import json, sys
try:
    args = json.loads(sys.argv[1])
    print(' '.join(str(a) for a in args))
except Exception:
    pass
" "$prog_args_json" 2>/dev/null)

    # First positional arg = the script (or interpreter for shell-shim plist).
    first_arg=$(python3 -c "
import json, sys
try:
    args = json.loads(sys.argv[1])
    print(args[0] if args else '')
except Exception:
    pass
" "$prog_args_json" 2>/dev/null)

    # --- claude CLI requires PATH to include the OAuth shim ----------------
    # Audit chunk3 P0: dlq_autopilot.plist had PATH without ~/.local/bin, so
    # subprocess(["claude",...]) failed FileNotFoundError on every entry.
    if echo " $prog_args_flat " | grep -qE '[^a-zA-Z0-9_/\.-]claude[^a-zA-Z0-9_/\.-]'; then
        env_path=$(plutil -extract EnvironmentVariables.PATH raw -o - -- "$plist" 2>/dev/null || echo "")
        if [ -n "$env_path" ]; then
            if ! echo "$env_path" | grep -qE "(\.local/bin|\.claude/local)"; then
                echo "[VIOLATION] $label: invokes 'claude' CLI but PATH lacks \$HOME/.local/bin or \$HOME/.claude/local"
                VIOLATIONS=$((VIOLATIONS+1))
            fi
        fi
    fi

    # --- Pyenv pin must match installed versions ----------------------------
    # Audit chunk1 P0: intel-radar-daily-digest pinned 3.11.9, only 3.11.11
    # installed → daemon dead. Catch any reference to a pyenv version path.
    pyenv_pin=$(echo "$prog_args_flat" | grep -oE '\.pyenv/versions/[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's|.*/||')
    if [ -n "$pyenv_pin" ]; then
        if command -v pyenv >/dev/null 2>&1; then
            if ! pyenv versions --bare 2>/dev/null | grep -qx "$pyenv_pin"; then
                echo "[VIOLATION] $label: pinned Python $pyenv_pin not installed (have: $(pyenv versions --bare 2>/dev/null | tr '\n' ',' | sed 's/,$//'))"
                VIOLATIONS=$((VIOLATIONS+1))
            fi
        elif [ ! -d "$HOME/.pyenv/versions/$pyenv_pin" ]; then
            echo "[VIOLATION] $label: pinned Python $pyenv_pin not at \$HOME/.pyenv/versions/$pyenv_pin"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi

    # --- Referenced script must exist on disk -------------------------------
    # Audit chunk1 P0: wr2_fact_checker.py + wr2_fact_extractor.py referenced
    # but not on disk → silent fail every fire. We resolve the script path
    # by inspecting the first non-shell-shim positional arg.
    script_to_check=""
    if [ -n "$first_arg" ]; then
        case "$first_arg" in
            /bin/sh|/bin/bash|/bin/zsh|/usr/bin/env)
                # Shell shim: only the simplest pattern is reliably parseable
                # — `<shell> <flags?> <script>` (i.e. ProgramArguments has 2-3
                # entries with the last being a single .sh/.py absolute path).
                # Anything more complex (long shell strings with `&&`, multiple
                # cd's, conditional blocks, etc.) we skip — too noisy and the
                # supervisor/wrapper pattern means most invocations are
                # multi-line shell embeds. Risk: we miss validating those
                # scripts; benefit: zero false positives on the simple cases
                # we DO validate.
                arg_count=$(python3 -c "
import json, sys
try: print(len(json.loads(sys.argv[1])))
except: print(0)
" "$prog_args_json" 2>/dev/null)
                if [ "${arg_count:-0}" -le 3 ]; then
                    last_arg=$(python3 -c "
import json, sys
try:
    args = json.loads(sys.argv[1])
    print(args[-1] if args else '')
except Exception: pass
" "$prog_args_json" 2>/dev/null)
                    if [[ "$last_arg" == /* && ("$last_arg" == *.sh || "$last_arg" == *.py) ]]; then
                        script_to_check="$last_arg"
                    fi
                fi
                # else: complex shell-embed — skip script-existence check.
                ;;
            */python|*/python3|*/python3.*)
                # Python interpreter: next arg is the script.
                script_to_check=$(python3 -c "
import json, sys
try:
    args = json.loads(sys.argv[1])
    for a in args[1:]:
        if not a.startswith('-'):
            print(a); break
except Exception: pass
" "$prog_args_json" 2>/dev/null)
                ;;
            /*)
                # Direct absolute path.
                script_to_check="$first_arg"
                ;;
        esac
    fi
    if [ -n "$script_to_check" ] && [[ "$script_to_check" == /* ]]; then
        if [ ! -f "$script_to_check" ]; then
            echo "[VIOLATION] $label: referenced script does not exist: $script_to_check"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi

    # --- Cron+LA duplication check ------------------------------------------
    # Audit chunk3 P1: fly-restart-loop-detector ran from cron */15 AND a
    # LaunchAgent — double-fire. If a referenced script is also invoked
    # from the user's crontab, flag it.
    if [ -n "$script_to_check" ] && [[ "$script_to_check" == /* ]]; then
        if crontab -l 2>/dev/null | grep -F "$script_to_check" | grep -qv '^[[:space:]]*#'; then
            echo "[VIOLATION] $label: script also invoked from crontab — pick one (LA OR cron, not both)"
            VIOLATIONS=$((VIOLATIONS+1))
        fi
    fi

    # --- Logs must NOT be in /tmp/ ------------------------------------------
    out=$(plutil -extract StandardOutPath raw -o - -- "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw -o - -- "$plist" 2>/dev/null || echo "")
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
