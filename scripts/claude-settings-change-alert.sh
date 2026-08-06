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

# macOS ships /sbin/md5, Linux ships md5sum. This used to hardcode /sbin/md5,
# which is correct on Pro and silently yields an EMPTY hash anywhere else — so
# a test executing this script on a Linux runner would compare "" to "" and
# exit 0, measuring its own poverty rather than the script (W108).
_md5() {
    if [[ -x /sbin/md5 ]]; then /sbin/md5 -q "$1"
    else md5sum "$1" 2>/dev/null | cut -d' ' -f1
    fi
}

CURRENT_MD5=$(_md5 "$HOME/.claude/settings.json" 2>/dev/null)
LAST_MD5=$(cat "$STATE_FILE" 2>/dev/null || echo "")

if [[ "$CURRENT_MD5" == "$LAST_MD5" ]]; then
    exit 0
fi

# State is advanced AFTER a confirmed delivery, not before (changed 2026-08-06).
# The original comment claimed writing first meant "dedup works even if Telegram
# is down". What it actually bought was at-most-once: if the import failed, or
# the alerter raised, or the gateway refused the event, the next run compared
# equal hashes and exited — the alert was gone for good, silently, exit 0.
#
# Writing after is safe precisely BECAUSE this script is launchd WatchPaths, not
# a timer: it re-fires when settings.json CHANGES, so a stuck state file cannot
# produce a storm, only a retry of news nobody received. And a retry of the same
# transition carries the same key, so the gateway collapses it anyway.
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S WITA')
MD5_SHORT="${CURRENT_MD5:0:12}"

# The CONDITION is the TRANSITION <old>-><new>, not the clock and not the new
# state alone.
#
#   - the clock would move on every fire: a key that moves defeats every window;
#   - NO key lets tg_notify derive one, and with digits stripped every change
#     collapses into a single identity. Measured on the 2026-07-14..08-06 spool,
#     6 of the 11 gaps between the 12 real changes are under the 6h first
#     window, so 6 genuine "restart your session" alerts would have gone silent;
#   - the NEW STATE alone is a state, not an event, and the spool contains the
#     counter-example: md5 7af809… at 18:05, 2555ea… at 20:39, 7af809… again at
#     23:33. That third fire is a REAL change needing a real restart — the file
#     came back to a content your session has since stopped running — and a
#     state-keyed alert would have called it a duplicate of five hours earlier.
#
# A transition is not unique over TIME either: A->B, B->A, A->B reuses the
# first key on the third change, and that third change needs its own restart.
# So a sequence number rides along, and this producer OPTS OUT of the mute
# ladder by design.
#
# That is not the trauma repeating. The ladder exists to quieten a condition
# that STAYS TRUE while being re-measured; this producer emits DISCRETE EVENTS
# — each change is a separate fact that needs a separate restart — and there is
# nothing to quieten. The bound is the volume: 12 changes in the last month, at
# WARNING, so they arrive as lines inside the 2x/day digest, not as
# interruptions. A producer that opts out must be able to say why, and must be
# small enough that being wrong is cheap.
SEQ_FILE="$STATE_DIR/claude-settings-alert-seq"
SEQ=$(( $(cat "$SEQ_FILE" 2>/dev/null || echo 0) + 1 ))
echo "$SEQ" > "$SEQ_FILE"
export ALERT_CONDITION="settings-json:${LAST_MD5:0:12}->${MD5_SHORT}#${SEQ}"

# Pass message via env-var to Python (avoids heredoc interpolation breakage on UTF-8/quotes)
export ALERT_MSG="[settings.json] modified at ${TIMESTAMP}
md5: ${MD5_SHORT}

[!] Hot-reload NOT supported (cicatrix W1 T1.2 H1).
=> /quit + relogin Claude Code per attivare nuovo hook/config.

If intentional and no hot-apply needed, ignore."

DELIVERED=$(/usr/bin/env python3 - <<'PYEOF'
import inspect, sys, os
sys.path.insert(0, os.path.expanduser("~/scripts"))
try:
    from sentinel_lib.alerter import send_alert
    msg = os.environ.get("ALERT_MSG", "settings.json modified — no msg env")
    kwargs = {"level": "WARNING"}
    # Inspect the SIGNATURE; do not catch a TypeError from the call. Catching
    # the call cannot tell "this alerter predates the condition kwarg" from
    # "send_alert raised a TypeError inside" (a non-numeric ts in the local
    # dedup json does exactly that), and the retry would then paper over a real
    # bug while the outer handler exits 0.
    #
    # NOTE: on an older alerter the fallback is NOT an unnamed alert — that
    # alerter unconditionally sends `sentinel:<md5(message)>` of its own. The
    # fallback buys delivery, not identity. Deploy the alerter first.
    try:
        accepts = "condition" in inspect.signature(send_alert).parameters
    except (TypeError, ValueError):
        accepts = False
    if accepts:
        kwargs["condition"] = os.environ.get("ALERT_CONDITION", "")
    ok = send_alert(msg, **kwargs)
    print("DELIVERED" if ok else "NOT_DELIVERED")
except Exception as e:
    print(f"[alert-error] {type(e).__name__}: {e}", file=sys.stderr)
    print("NOT_DELIVERED")
sys.exit(0)
PYEOF
)

if [[ "$DELIVERED" == "DELIVERED" ]]; then
    echo "$CURRENT_MD5" > "$STATE_FILE"
else
    echo "[alert] not delivered — state NOT advanced, the next change retries" >&2
fi

exit 0
