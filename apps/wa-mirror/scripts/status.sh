#!/usr/bin/env bash
# status.sh — show status of all wa-mirror per-employee processes.

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

ALL_NAMES=$(list_accounts | awk '{print $1}' | tr '[:upper:]' '[:lower:]')

printf "%-10s %-20s %-10s %-10s %s\n" "NAME" "E164" "STATUS" "PID" "LAST LOG"
echo "─────────────────────────────────────────────────────────────────────────────"
for NAME in $ALL_NAMES; do
    E164=$(get_e164 "$NAME")
    PIDFILE="$(pid_file "$NAME")"
    LOGFILE="$(log_file "$NAME")"
    SESDIR="$(session_dir "$E164")"

    # Session status
    # M4 (2026-07-20): a non-empty session dir does NOT mean linked — a 401
    # logged_out leaves the dir in place and the bridge stops retrying by
    # design, so status.sh used to show "🟢 RUNNING (linked)" for dead
    # accounts (sahira/krisna case). Cross-check the log: if the last
    # logged_out/401 event is newer than the last successful connect, the
    # account needs a QR re-link.
    if [ ! -d "$SESDIR" ] || [ -z "$(ls -A "$SESDIR" 2>/dev/null)" ]; then
        SES="no-link"
    else
        SES="linked"
        if [ -f "$LOGFILE" ]; then
            LAST_LOGOUT=$(grep -nE "logged_out|code 401" "$LOGFILE" 2>/dev/null | tail -1 | cut -d: -f1)
            LAST_CONN=$(grep -nE "session connected|session restored| connected:" "$LOGFILE" 2>/dev/null | tail -1 | cut -d: -f1)
            if [ -n "$LAST_LOGOUT" ] && [ "$LAST_LOGOUT" -gt "${LAST_CONN:-0}" ]; then
                SES="🔓LOGGED-OUT"
            fi
        fi
    fi

    # Process status
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            STATUS="🟢 RUNNING"
        else
            STATUS="🔴 DEAD"
            PID="-"
        fi
    else
        STATUS="⚪ STOPPED"
        PID="-"
    fi

    # Last log line
    LAST=""
    if [ -f "$LOGFILE" ]; then
        LAST=$(tail -1 "$LOGFILE" 2>/dev/null | head -c 60)
    fi

    printf "%-10s %-20s %-10s %-10s %s\n" "$NAME" "$E164 ($SES)" "$STATUS" "$PID" "$LAST"
done

echo ""
echo "Logs:  /tmp/wa-mirror-logs/<name>.log"
echo "DB count:  bash $SCRIPT_DIR/status.sh db"

# Show DB count if 'db' arg passed
if [ "${1:-}" = "db" ]; then
    echo ""
    echo "━━━ DB message counts ━━━"
    WA_MIRROR_DATABASE_URL="$(
        grep '^WA_MIRROR_DATABASE_URL=' "$HOME/.wa-mirror.env" \
            | cut -d= -f2- \
            | sed -E 's/^["'\'']|["'\'']$//g'
    )"
    if [ -z "$WA_MIRROR_DATABASE_URL" ]; then
        echo "(DB query failed — WA_MIRROR_DATABASE_URL missing in ~/.wa-mirror.env)"
        exit 1
    fi
    psql "$WA_MIRROR_DATABASE_URL" -c "
        SELECT
            team_member_phone,
            COUNT(*) as msgs,
            MAX(created_at) as last_msg
        FROM whatsapp_message_context
        WHERE team_member_phone IS NOT NULL
        GROUP BY team_member_phone
        ORDER BY MAX(created_at) DESC
    " 2>&1 || echo "(DB query failed — Postgres proxy down?)"
fi
