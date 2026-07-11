#!/usr/bin/env bash
# start-one.sh — start ONE wa-mirror Node process for ONE employee.
# Isolated process = no Baileys connection_replaced collision.
#
# Usage:  bash start-one.sh <name>       (QR mode if no session yet, else silent)
#         bash start-one.sh <name> --qr  (force QR re-link)

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

NAME="${1:-}"
FORCE_QR="${2:-}"

if [ -z "$NAME" ]; then
    echo "Usage: bash start-one.sh <name> [--qr]"
    echo ""
    echo "Available employees:"
    list_accounts
    exit 1
fi

E164=$(validate_name "$NAME") || exit 1
PIDFILE="$(pid_file "$NAME")"
LOGFILE="$(log_file "$NAME")"
SESDIR="$(session_dir "$E164")"

# Kill any existing process for this employee
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "▸ Killing existing process PID $OLD_PID for $NAME..."
        kill -9 "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PIDFILE"
fi

# If --qr, wipe session to force fresh QR scan
if [ "$FORCE_QR" = "--qr" ]; then
    echo "▸ Wiping session $SESDIR (forcing fresh QR)..."
    rm -rf "$SESDIR" 2>/dev/null || true
fi

# Generate per-process env override
ACCOUNT_NAMES_JSON=$(get_account_names_for "$E164" "$NAME")
ACCOUNT_EMAILS_JSON=$(get_account_email_for "$E164")   # FIX 4 2026-05-26
WA_MIRROR_ACCOUNT_EMAILS_DEFAULT='{}'                  # FIX 5 2026-05-26 (escape bug)

echo "━━━ wa-mirror single-process launcher ━━━"
echo "  Employee:   $NAME"
echo "  E.164:      $E164"
echo "  Log:        $LOGFILE"
echo "  Session:    $SESDIR"
echo ""

if [ ! -d "$SESDIR" ] || [ -z "$(ls -A "$SESDIR" 2>/dev/null)" ]; then
    echo "🔑 First link — QR mode. Scan within 20s."
else
    echo "♻️  Existing session found — reconnecting silently."
fi
echo ""
sleep 1

# Build env: common from ~/.wa-mirror.env + override accounts to single E.164
cd "$WA_MIRROR_DIR"

# Spawn node process in background, redirect both stdout+stderr to log
WA_MIRROR_ACCOUNTS="$E164" \
WA_MIRROR_ACCOUNT_NAMES="$ACCOUNT_NAMES_JSON" \
WA_MIRROR_ACCOUNT_EMAILS="${ACCOUNT_EMAILS_JSON:-$WA_MIRROR_ACCOUNT_EMAILS_DEFAULT}" \
WA_MIRROR_DATABASE_URL="$(grep '^WA_MIRROR_DATABASE_URL=' "$HOME/.wa-mirror.env" | cut -d= -f2-)" \
WA_MIRROR_SESSION_LABEL="$(grep '^WA_MIRROR_SESSION_LABEL=' "$HOME/.wa-mirror.env" | cut -d= -f2- | tr -d '"')" \
WA_MIRROR_LOG_LEVEL="info" \
WA_MIRROR_MEDIA_ROOT="$HOME/wa-mirror-media" \
WA_MIRROR_ENV_FILE="$HOME/.wa-mirror.env" \
TELEGRAM_BOT_TOKEN="" \
TELEGRAM_OWNER_CHAT_ID="" \
TELEGRAM_ADMIN_CHAT_ID="" \
TELEGRAM_ZERO_CHAT_ID="" \
BALIZEROBOT_TOKEN="" \
TELEGRAM_CHAT_ID="" \
nohup node --enable-source-maps dist/bridge/index.js --employee="$NAME" > "$LOGFILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PIDFILE"

# Wait up to 15 sec for QR generation OR connection
echo "▸ Process spawned PID $NEW_PID. Waiting for QR or connection..."
for i in $(seq 1 30); do
    if grep -q "QR saved" "$LOGFILE" 2>/dev/null; then
        echo ""
        echo "📱 QR ready:"
        echo "   open /tmp/qr-${E164#+}.png"
        echo ""
        echo "Employee scans on phone:"
        echo "   WhatsApp Business → Settings → Linked Devices → Link a Device"
        echo ""
        break
    fi
    if grep -q "wa-mirror session connected" "$LOGFILE" 2>/dev/null; then
        echo ""
        echo "✅ Connected via persisted session (no QR needed)"
        echo ""
        break
    fi
    sleep 0.5
done

echo ""
echo "Watch logs:    tail -f $LOGFILE"
echo "Status:        bash $SCRIPT_DIR/status.sh"
echo "Stop:          bash $SCRIPT_DIR/stop-one.sh $NAME"
