#!/usr/bin/env bash
# claude-settings-change-alert.sh — Gap 3 fix v2 (2026-05-25)
# Triggered by launchd WatchPaths on ~/.claude/settings.json change.
# Sends Telegram alert reminding session restart needed for hot-apply.
#
# Cicatrix: W1 T1.2 H1 — settings.json hooks NON hot-reload mid-session.
# v2: env-var passing to Python (no heredoc interpolation pitfall).
# v3 (2026-08-06): state file written AFTER a confirmed delivery — see the long
# comment at the write site. The v2 line here said the opposite and was still
# describing v2 behaviour after the code changed; a header that narrates the
# body is one more thing that can go stale, so it now points at the body.

set -uo pipefail

[[ -f "$HOME/.nuzantara-secrets.env" ]] && source "$HOME/.nuzantara-secrets.env" 2>/dev/null

STATE_DIR="$HOME/.agent/decisions"
STATE_FILE="$STATE_DIR/claude-settings-last-md5"
HEARTBEAT_DIR="$HOME/.organism/last_seen"     # G2 gene
mkdir -p "$STATE_DIR" "$HEARTBEAT_DIR"

_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Fire log — every invocation, INCLUDING the ones that exit early. This used to
# live in the plist as `bash -c 'echo …; exec …'`, which made the launchd payload
# an inline shell string: the organ-conformance gate then read THAT two-command
# string as the organ's body and found no heartbeat, no kill switch and no
# `set -u` — genes that were all one level down, in a file it never opened. A
# wrapper thin enough to look harmless still decides what the guard is allowed
# to see, so the diagnostic moved here and the plist now names the script.
echo "[$(_ts)] watcher-fire pid=$$" >> "$HOME/logs/claude-settings-watcher.log" 2>/dev/null || true

# G5 gene — kill switch. A WatchPaths organ cannot be quietened by a schedule;
# without this the only way to stop it is unloading the plist, which is exactly
# the "unarm to silence" move that turns a noisy organ into a dead one nobody
# remembers to revive.
if [[ "${CLAUDE_SETTINGS_WATCHER_ENABLED:-true}" == "false" ]]; then
    exit 0
fi

# G2 gene — heartbeat. Load-bearing for THIS organ in a way it is not for a
# timer: launchd fires it on a file event, so "it has not run in 3 days" is
# indistinguishable from "settings.json has not changed in 3 days" and its
# silence can never be read as a fault. The heartbeat is written on every fire,
# so proof-of-life is decoupled from the news.
_heartbeat() {
    printf '{"organ":"claude-settings-watcher","host":"%s","ts":"%s","status":"%s"}\n' \
        "$(hostname -s)" "$(_ts)" "${1:-ok}" \
        > "$HEARTBEAT_DIR/claude-settings-watcher.json" 2>/dev/null || true
}
_heartbeat "ok"

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
# produce a storm.
#
# Be exact about what this buys, because the first draft of this comment
# overclaimed it: recovery is NOT guaranteed, it is CONDITIONAL ON THE NEXT
# CHANGE. If delivery fails and settings.json is never touched again, this alert
# is still lost. What changes is the failure mode — at-most-once lost it
# unconditionally and silently; at-least-once-on-next-change loses it only when
# no further change ever arrives, and says so on stderr meanwhile. Strictly
# better, not sufficient. (A timer would close the gap and open a storm; the
# storm is the worse trade for a producer nobody is paged by.)
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
# nothing to quieten.
#
# The bound is NOT "12 changes last month" — that is an observation, and an
# observation is not a limit (a config manager rewriting this file every 30s
# would emit ~2880 unique keys/day). The limit is STRUCTURAL and lives one layer
# down: this producer is WARNING, so tg_notify spools it to the digest tier, and
# tg_digest_flush groups records BY SOURCE (`by_source[r["source"]]`, printed as
# `source ×N — <last>`). 12 events and 2880 events both cost exactly one line in
# one of the 2 daily digests. Unique keys buy spool rows, never interruptions.
# A producer that opts out of the ladder must be able to say why AND name what
# bounds it instead.
SEQ_FILE="$STATE_DIR/claude-settings-alert-seq"
# Read the counter as DIGITS or not at all. `$(( $(cat file) + 1 ))` on a
# corrupt/hand-edited counter is not a wrong number, it is a dead script: a
# value like `1 2` or `(` makes bash's arithmetic fail, SEQ never gets assigned,
# and `set -u` then kills the script on the expansion below — permanently, on
# every future change, exit before the alert. A guard that can be killed by its
# own state file is a #2 (exists ≠ armed) waiting to happen.
SEQ_RAW=$(cat "$SEQ_FILE" 2>/dev/null || echo 0)
[[ "$SEQ_RAW" =~ ^[0-9]+$ ]] || SEQ_RAW=0
SEQ=$(( SEQ_RAW + 1 ))
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
    _heartbeat "error"
    echo "[alert] not delivered — state NOT advanced, the next change retries" >&2
fi

exit 0
