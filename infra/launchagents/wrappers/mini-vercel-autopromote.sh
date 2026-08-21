#!/bin/bash
# mini.vercel_autopromote — promote the READY-but-STAGED Vercel production build so a merge reaches balizero.com without a human
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/mini-vercel-autopromote.sh
# Live:  ~/scripts/mini-vercel-autopromote.sh (declared pair, node=mini)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="mini.vercel_autopromote"
LOG_DIR="$HOME/logs/mini-vercel_autopromote"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-mini-vercel_autopromote.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${MINI_VERCEL_AUTOPROMOTE_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_VERCEL_AUTOPROMOTE_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
#
# WHAT THIS CLOSES
# On 2026-08-21 balizero.com served a ~22h-old build while three READY production builds sat
# on Vercel unaliased. The detector (frontend-live-sentinel.yml) had gone red 13 times in a
# row and DELIVERED its Telegram every time; the cure (vercel_prod_deploy.py) worked on
# demand. Nothing joined them, so every merge waited for a human. This is the join.
#
# WHY --promote-only AND NOT THE DEFAULT
# Left at its default the script CREATES a deployment when no READY build exists (~6 min +
# build minutes). Unattended at a 15-minute cadence that is a build loop nobody asked for.
# --promote-only promotes what is already built and refuses to build, returning 2 for "there
# was nothing to promote" — an anomaly that wants eyes, not an automatic rebuild.
#
# WHY THE PATH IS SET EXPLICITLY (W108)
# vercel_prod_deploy.py refreshes its OAuth token by shelling out to `vercel whoami`, and
# that token's lifetime is HOURS — so refreshing is the ORDINARY path, not the exception.
# launchd hands a job a minimal PATH: measured on this machine, `which vercel` under `env -i`
# finds NOTHING, while /opt/homebrew/bin/vercel answers. Without this line the organ would
# work for a few hours after any interactive login and then quietly stop curing anything,
# reporting only "vercel CLI not on PATH". The interpreter is absolute for the same reason:
# the reporter must not share a failure mode with the thing it reports.
PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

REPO="$HOME/nuzantara"
CURE="$REPO/scripts/vercel_prod_deploy.py"

log "run start"

if [ ! -f "$CURE" ]; then
    # Armed at nothing (W81): the plist fires, the payload is absent. Say so.
    log "cure script missing at $CURE"
    heartbeat "error" "cure script missing: $CURE"
    exit 0
fi

# Capture the exit code from the command itself, never through a pipe (W97), and
# errexit-immune (W101) even though this wrapper does not set -e — so that adding it later
# cannot silently decapitate the branch below, which is the only reason this line exists.
OUT=""
RC=0
OUT=$(cd "$REPO" && /usr/bin/python3 "$CURE" --promote-only 2>&1) || RC=$?

# Judge the OUTPUT, not only the code (W104): the log is what a human reads at 07:30.
printf '%s\n' "$OUT" >> "$LOG"

case "$RC" in
    0)
        # Both good outcomes: production was already current, or it just got promoted.
        if printf '%s' "$OUT" | grep -q 'promoted'; then
            heartbeat "ok" "promoted"
            log "PROMOTED — production moved"
        else
            heartbeat "ok" "already current"
        fi
        ;;
    2)
        # No READY build for the target commit. NOT a failure of this organ: Vercel either
        # skipped the commit or its build failed, and both want a human's eyes rather than
        # an unattended rebuild. Distinct status so a silence-watcher can tell them apart.
        heartbeat "warning" "no READY build to promote (rc=2)"
        log "NO READY BUILD — nothing promoted, deliberately did not build"
        ;;
    *)
        heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
        ;;
esac

log "run done rc=$RC"
exit 0
