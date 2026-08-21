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
    # WARNING, not ok. A skip is not health: if a run ever wedges (a hung network call, a
    # stopped process), its pid stays alive and EVERY later tick lands here — an "ok"
    # heartbeat every 15 minutes while the organ cures nothing, which is the exact
    # green-over-dead shape of superscar #2. The organ that is skipping is not the organ
    # that is working, and the sidecar must not spell them the same way.
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "warning" "skipped: previous run still alive"
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

# The degraded-target marker is read on EVERY exit code, not only on rc=3. Measured live on
# 2026-08-21 against the real Vercel account with a poisoned fetch: main HEAD HAPPENED to have
# a READY build, so a run whose fetch was broken promoted it and exited 0 - and this wrapper,
# which only looked for the marker under rc=3, would have written a clean `ok` and hidden a
# dead fetch for as long as it stayed dead. The rc=3 comment below is right that Vercel skips
# main HEAD for all but a few merges a day; USUALLY is not NEVER, and superscar #2 is exactly
# the organ that stays green while blind. `if` and not `&&`, so no errexit can decapitate it
# (W101).
DEGRADED=0
if printf '%s' "$OUT" | grep -q 'main HEAD — git'; then DEGRADED=1; fi

case "$RC" in
    0)
        # Both good outcomes: production was already current, or it just got promoted.
        if [ "$DEGRADED" = 1 ]; then
            heartbeat "warning" "promoted a degraded target - git could not be asked"
            log "DEGRADED TARGET - promoted main HEAD; the fetch is broken, the promote was luck"
        elif printf '%s' "$OUT" | grep -q 'promoted'; then
            heartbeat "ok" "promoted"
            log "PROMOTED — production moved"
        else
            heartbeat "ok" "already current"
        fi
        ;;
    3)
        # FIRST, tell "there was nothing to promote" apart from "I could not work out WHAT to
        # promote". When `git fetch` fails, the cure falls back to main HEAD — a commit Vercel
        # skips for all but a few merges a day — so there is never a READY build for it and
        # this branch would repeat benignly forever while the organ promotes nothing. That is
        # a blind organ, not a quiet one (W106b: could-not-verify is never the same verdict as
        # nothing-to-do). The cure NAMES this in its own output, so read the output, not the
        # code alone (W104).
        if [ "$DEGRADED" = 1 ]; then
            heartbeat "error" "cure could not determine the target commit (git degraded)"
            log "DEGRADED TARGET — the cure fell back to main HEAD; it will never promote"
        else
            # No READY build for the target commit. NOT a failure of this organ: Vercel
            # either skipped the commit or its build failed, and both want a human's eyes
            # rather than an unattended rebuild. Distinct status so a watcher can tell them
            # apart. (if/else and not an early `break`: `break` outside a loop is a no-op in
            # bash, so the benign heartbeat below would have overwritten the error above.)
            heartbeat "warning" "no READY build to promote (rc=3)"
            log "NO READY BUILD — nothing promoted, deliberately did not build"
        fi
        ;;
    2)
        # argparse's own usage code: the cure REFUSED the command line — it does not know
        # --promote-only. Nothing ran and nothing was cured, so this must never wear the
        # benign colour of "nothing to promote". Measured on Mini before this landed: the
        # pre-merge copy of the script exits exactly here. This is the shape that would have
        # made the organ green over dead for as long as nobody looked (superscar #2).
        heartbeat "error" "cure rejected --promote-only (usage error, rc=2) — script too old?"
        log "USAGE ERROR — the cure does not know --promote-only; NOTHING was cured"
        ;;
    *)
        heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
        ;;
esac

log "run done rc=$RC"
exit 0
