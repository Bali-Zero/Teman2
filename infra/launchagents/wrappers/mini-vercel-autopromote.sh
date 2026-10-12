#!/bin/bash
# mini.vercel_autopromote — promote a READY build or build mouth from a local archive, then move production
# Default: --upload --auto-build. Set MINI_VERCEL_AUTOPROMOTE_MODE=promote-only for instant fallback.
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
PIDFILE_MAX_AGE_S=$((35 * 60))
BUSY_FILE="$LOG_DIR/lock-busy-ticks"
MODE="${MINI_VERCEL_AUTOPROMOTE_MODE:-autobuild}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] mode=$MODE $*" >> "$LOG"; }

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

# Mode is validated after the node guard and kill switch: a wrong node or a stopped organ
# reports that first, whatever the mode says.
case "$MODE" in
    autobuild) CURE_ARGS=(--upload --auto-build) ;;
    promote-only) CURE_ARGS=(--promote-only) ;;
    *)
        log "invalid MINI_VERCEL_AUTOPROMOTE_MODE — exiting"
        heartbeat "error" "invalid MINI_VERCEL_AUTOPROMOTE_MODE"
        exit 0
        ;;
esac

# G10_single_instance — pidfile + liveness probe + age threshold + trap cleanup
if [ -f "$PIDFILE" ]; then
    PREVIOUS_PID="$(cat "$PIDFILE" 2>/dev/null)"
    if [ -n "$PREVIOUS_PID" ] && kill -0 "$PREVIOUS_PID" 2>/dev/null; then
        # A normal upload takes about four minutes and therefore spans 2-3 launchd fires.
        # It stays healthy inside the 35-minute build-timeout margin. Past that boundary the
        # same live pid is a stuck run, not a green build forever (superscar #2).
        PIDFILE_MTIME="$(stat -f %m "$PIDFILE" 2>/dev/null)"
        case "$PIDFILE_MTIME" in
            ''|*[!0-9]*) PIDFILE_MTIME="$(stat -c %Y "$PIDFILE" 2>/dev/null)" ;;
        esac
        case "$PIDFILE_MTIME" in
            ''|*[!0-9]*) PIDFILE_AGE_S="" ;;
            *) PIDFILE_AGE_S=$(( $(date +%s) - PIDFILE_MTIME )) ;;
        esac
        if [ -n "$PIDFILE_AGE_S" ] && [ "$PIDFILE_AGE_S" -lt "$PIDFILE_MAX_AGE_S" ]; then
            log "previous run still building (pid $PREVIOUS_PID, age ${PIDFILE_AGE_S}s) — skipping"
            heartbeat "ok" "previous run still building"
        elif [ -n "$PIDFILE_AGE_S" ]; then
            log "previous run alive > 35 min (pid $PREVIOUS_PID, age ${PIDFILE_AGE_S}s) — skipping"
            heartbeat "warning" "previous run alive > 35 min"
        else
            log "previous run alive but pidfile age is unknown (pid $PREVIOUS_PID) — skipping"
            heartbeat "warning" "previous run age unknown"
        fi
        exit 0
    fi
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
#
# WHY EVERY 2 MINUTES AND NOT 15 (2026-09-09)
# Measured on the last mouth merge of the day (#6010): the PR left the merge queue and landed
# on main at 19:20:21 WITA, Vercel created the production build 4 seconds later and had it
# READY at 19:26:11 — and the 900s tick had run at 19:25:06, one minute too early, so the
# build sat STAGED until the 19:40 tick. Every one of the day's five mouth merges paid the
# same lottery (0-15 min after READY, promoted by hand each time by a session that would not
# wait), which is why "the organ works" and "a merge arrives live without a hand" were both
# true and both useless. At 120s the worst case after READY is 2 minutes. The price is
# nothing on the happy path: `vercel_prod_deploy.py` returns before touching the Vercel API
# when production already includes the target, so an idle tick is one `git fetch` and one
# GET on /api/health; the Vercel listing is only asked while a build is actually pending.
# A run may legitimately outlive a tick: a local upload build takes about four minutes, and
# a promote can probe for another ~2 minutes. launchd does not overlap one label, while the
# pidfile is the second line for manual runs. A young live pid therefore reports a healthy
# build in progress; after 35 minutes it turns warning so a wedged run cannot stay green.
#
# WHAT THIS CLOSES
# On 2026-08-21 balizero.com served a ~22h-old build while three READY production builds sat
# on Vercel unaliased. The detector (frontend-live-sentinel.yml) had gone red 13 times in a
# row and DELIVERED its Telegram every time; the cure (vercel_prod_deploy.py) worked on
# demand. Nothing joined them, so every merge waited for a human. This is the join.
#
# WHY AUTOBUILD IS NOW THE DEFAULT (2026-10-12)
# This organ originally used --promote-only because Vercel's Git integration made the build;
# creating another deployment at a 2-minute cadence would have been a build loop. The public
# repo is being removed, so that producer disappears. --upload --auto-build keeps the same
# promote-first decision and creates one serialized local-archive build only when none exists.
# MINI_VERCEL_AUTOPROMOTE_MODE=promote-only preserves the old behaviour as an instant fallback.
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

# At 120s the log grows ~7x faster than it did at 900s (a few lines per tick, ~4k lines a
# day). One generation of size-based rotation keeps `tail` useful and the disk bounded;
# `wc -c` rather than `stat` because the corpus runs this file on Linux CI too.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi

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
OUT=$(cd "$REPO" && /usr/bin/python3 "$CURE" "${CURE_ARGS[@]}" 2>&1) || RC=$?

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
#
# The pattern is the SHARED PREFIX of every fallback, not `main HEAD — git`. The cure degrades
# three ways and only two of them say "git": the third, "main HEAD — no commit in history
# touches a bundle path", falls back identically and was invisible to the narrower pattern --
# so widening the exit codes while leaving the pattern narrow closed one axis and left the
# other open, under a comment that claimed both. Raised by a cross-family refuter, which is
# how you find out that verifying ONE axis does not license a claim about the guard. The
# prefix names the entity (the cure fell back to main HEAD) rather than a wider form: the good
# path says "newest bundle-relevant commit on main" and cannot match it (superscar #3).
DEGRADED=0
if printf '%s' "$OUT" | grep -q 'main HEAD — '; then DEGRADED=1; fi

has_output_line() { # $1 anchored extended regexp
    printf '%s\n' "$OUT" | grep -Eq "$1"
}

safe_last_line() {
    local line
    line="$(printf '%s\n' "$OUT" | awk 'NF { line=$0 } END { print line }')"
    [ -n "$line" ] || line="rc=$RC"
    printf '%s' "$line" | LC_ALL=C tr -d '\000-\037\177' | sed -E \
        -e 's/([Tt][Oo][Kk][Ee][Nn]"?[[:space:]]*[:=][[:space:]]*"?)[^[:space:]",}]+/\1[REDACTED]/g' \
        -e 's/([Bb][Ee][Aa][Rr][Ee][Rr][[:space:]]+)[^[:space:]",}]+/\1[REDACTED]/g' \
        -e 's/[A-Za-z0-9_+\/=-]{32,}/[REDACTED]/g' \
        -e 's/\\/\\\\/g' \
        -e 's/"/\\"/g'
}

# Any outcome other than a busy lock resets the consecutive-busy counter.
if ! has_output_line '^upload already in progress — lock busy, skipping this tick$'; then
    rm -f "$BUSY_FILE"
fi

case "$RC" in
    0)
        if [ "$DEGRADED" = 1 ]; then
            # The note names the STATE, not an action. rc=0 covers two different histories —
            # it promoted main HEAD's build, or main HEAD was already what production served —
            # and this branch cannot tell them apart. Saying "promoted" here would be a
            # heartbeat that misdescribes what happened in the second case, which is the exact
            # defect class this whole organ keeps finding.
            heartbeat "warning" "degraded target — git could not be asked"
            log "DEGRADED TARGET — the cure fell back to main HEAD and exited 0; the fetch is broken"
        elif has_output_line '^upload already in progress — lock busy, skipping this tick$'; then
            # A lock held by a wedged or manual run must not read green forever (superscar #2):
            # count consecutive busy ticks; past 35 minutes of them it is a warning.
            BUSY="$(cat "$BUSY_FILE" 2>/dev/null)"
            # The counter's whole domain: written only by this wrapper, a decimal integer with no
            # leading zero and at most 5 digits. Anything else (empty, text, 08 read as octal,
            # an overflow) is corruption and restarts the count; it never aborts the run.
            case "$BUSY" in 0|[1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]|[1-9][0-9][0-9][0-9][0-9]) ;; *) BUSY=0 ;; esac
            BUSY=$(( BUSY + 1 ))
            printf '%s\n' "$BUSY" > "$BUSY_FILE"
            if [ $(( BUSY * 120 )) -lt "$PIDFILE_MAX_AGE_S" ]; then
                heartbeat "ok" "build in progress (lock held)"
            else
                heartbeat "warning" "upload lock held for $BUSY consecutive ticks"
            fi
            log "BUILD IN PROGRESS — upload lock held (consecutive busy ticks: $BUSY)"
        elif has_output_line '^OK - promoted dpl_[[:alnum:]_-]+; kita\.balizero\.com serves [[:xdigit:]]{9}$'; then
            heartbeat "ok" "built by upload and promoted"
            log "BUILT AND PROMOTED — upload moved production"
        elif has_output_line '^OK - kita\.balizero\.com already serves [[:xdigit:]]{9}; dpl_[[:alnum:]_-]+ stays staged, not promoted$'; then
            heartbeat "ok" "already current"
            log "ALREADY CURRENT — uploaded deployment stayed staged"
        elif has_output_line '^OK after promote — kita\.balizero\.com serves [[:xdigit:]]{9}$' \
            || has_output_line '^OK — kita\.balizero\.com serves [[:xdigit:]]{9} \(promoted dpl_[[:alnum:]_-]+, no rebuild(; newest bundle-relevant commit [[:xdigit:]]{9} still awaits its own build)?\)$'; then
            heartbeat "ok" "promoted"
            log "PROMOTED — production moved"
        elif has_output_line '^production already includes this commit — nothing to do$'; then
            heartbeat "ok" "already current"
            log "ALREADY CURRENT — nothing to do"
        else
            heartbeat "error" "unrecognized rc=0 outcome"
            log "UNRECOGNIZED SUCCESS — no exact outcome marker"
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
        elif [ "$MODE" = "promote-only" ]; then
            # No READY build for the target commit. NOT a failure of this organ: Vercel
            # either skipped the commit or its build failed, and both want a human's eyes
            # rather than an unattended rebuild. Distinct status so a watcher can tell them
            # apart. (if/else and not an early `break`: `break` outside a loop is a no-op in
            # bash, so the benign heartbeat below would have overwritten the error above.)
            heartbeat "warning" "no READY build to promote (rc=3)"
            log "NO READY BUILD — nothing promoted, deliberately did not build"
        else
            NOTE="$(safe_last_line)"
            heartbeat "error" "$NOTE"
            log "AUTOBUILD REFUSED — $NOTE"
        fi
        ;;
    2)
        # argparse's own usage code: the cure REFUSED the command line — it does not know
        # --promote-only. Nothing ran and nothing was cured, so this must never wear the
        # benign colour of "nothing to promote". Measured on Mini before this landed: the
        # pre-merge copy of the script exits exactly here. This is the shape that would have
        # made the organ green over dead for as long as nobody looked (superscar #2).
        heartbeat "error" "cure rejected $MODE arguments (usage error, rc=2) — script too old?"
        log "USAGE ERROR — the cure rejected the selected mode; NOTHING was cured"
        ;;
    4)
        SUSPENDED_SHA="$(printf '%s\n' "$OUT" | sed -nE 's/^SUSPENDED ([[:xdigit:]]{9}) — [0-9]+ failed upload builds; waiting for the target sha to change$/\1/p' | tail -n 1)"
        if [ -n "$SUSPENDED_SHA" ]; then
            heartbeat "error" "upload suspended for $SUSPENDED_SHA after repeated failed builds"
        else
            heartbeat "error" "upload suspended after repeated failed builds"
        fi
        log "UPLOAD SUSPENDED — failed-build limit reached"
        ;;
    1)
        NOTE="$(safe_last_line)"
        heartbeat "error" "$NOTE"
        log "CURE FAILED — $NOTE"
        ;;
    *)
        heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
        ;;
esac

log "run done rc=$RC"
exit 0
