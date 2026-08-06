#!/usr/bin/env bash
# claude-settings-change-alert.sh — Gap 3 fix v2 (2026-05-25)
# Triggered by launchd WatchPaths on ~/.claude/settings.json change.
# Sends Telegram alert reminding session restart needed for hot-apply.
#
# Cicatrix: W1 T1.2 H1 — settings.json hooks NON hot-reload mid-session.
# v2: env-var passing to Python (no heredoc interpolation pitfall),
# state file written BEFORE alert (so dedup works even if alert fails).

set -uo pipefail

[[ -f "$HOME/.nuzantara-secrets.env" ]] && source "$HOME/.nuzantara-secrets.env" 2>/dev/null

STATE_DIR="$HOME/.agent/decisions"
STATE_FILE="$STATE_DIR/claude-settings-last-md5"
mkdir -p "$STATE_DIR"

CURRENT_MD5=$(/sbin/md5 -q "$HOME/.claude/settings.json" 2>/dev/null)
LAST_MD5=$(cat "$STATE_FILE" 2>/dev/null || echo "")

if [[ "$CURRENT_MD5" == "$LAST_MD5" ]]; then
    exit 0
fi

# Write state BEFORE alert so dedup works even if Telegram is down (W55-class)
echo "$CURRENT_MD5" > "$STATE_FILE"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S WITA')
MD5_SHORT="${CURRENT_MD5:0:12}"

# The CONDITION is "settings.json now has content <md5>", NOT "the clock read
# <timestamp>". Naming it keeps every genuine change audible while the gateway's
# escalating mute ladder still collapses a re-announcement of the SAME content.
#
# This matters here more than anywhere: with no name, tg_notify derives an
# identity from the message with digits stripped, and every change would share
# one identity. Measured on the 2026-07-14..08-06 spool, 6 of the 11 gaps
# between the 12 real changes are under the 6h first window — so the derived
# identity would have muted 6 genuine "restart your session" alerts, and the
# ladder would have escalated to 24h during the 17-18 July burst.
export ALERT_CONDITION="settings-json:${MD5_SHORT}"

# Pass message via env-var to Python (avoids heredoc interpolation breakage on UTF-8/quotes)
export ALERT_MSG="[settings.json] modified at ${TIMESTAMP}
md5: ${MD5_SHORT}

[!] Hot-reload NOT supported (cicatrix W1 T1.2 H1).
=> /quit + relogin Claude Code per attivare nuovo hook/config.

If intentional and no hot-apply needed, ignore."

/usr/bin/env python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/scripts"))
try:
    from sentinel_lib.alerter import send_alert
    msg = os.environ.get("ALERT_MSG", "settings.json modified — no msg env")
    try:
        ok = send_alert(msg, level="WARNING", condition=os.environ.get("ALERT_CONDITION", ""))
    except TypeError:
        # An older ~/scripts/sentinel_lib/alerter.py has no `condition` kwarg.
        # Without this the TypeError would fall into the outer handler and the
        # alert would be LOST — a version skew must degrade to an unnamed alert,
        # never to silence. Deploy order is alerter first, then this script.
        ok = send_alert(msg, level="WARNING")
    print(f"[alert] sent={ok}")
    sys.exit(0)
except Exception as e:
    print(f"[alert-error] {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)
PYEOF

exit 0
