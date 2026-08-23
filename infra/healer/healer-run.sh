#!/bin/bash
# healer-run.sh — the HEALER organ (autonomous cure loop, Mini-Pro2).
#
# Born 2026-07-06 on Zero's GO "guaritore in loop e piena autonomia".
# Loop: launchd StartInterval 4h → deterministic $0 pre-check over the three
# receptors (proprioception, PENDING-ARMS ledger, escalations board) → ONLY if
# something is actionable, spawn a headless claude (Sonnet 5) session with the
# standing mandate (HEALER-MANDATE.md) that cures IN-PERIMETER findings via
# worktree→PR→auto-merge→prove-live→ledger, and Telegram-alerts Zero for
# anything operator-gated. Healthy-idle runs cost zero LLM tokens.
#
# Safety rails (mirror of the mandate, enforced here):
#   - kill switch: HEALER_ENABLED=false in env or ~/.nuzantara-healer.env
#   - anti-overlap: pidfile lock (a 4h loop must never stack sessions)
#   - anti-loop: HEALER_RUN=1 exported (a healer session must never spawn
#     another healer; the mandate forbids it, this env makes it detectable)
#   - wall-clock watchdog: hard kill of the claude session after MAX_WALL_S
#   - W84 trampoline: TCC-denied launchd context re-execs via ssh-localhost
#     (key ~/.ssh/id_local_trampoline, from=127.0.0.1/::1 restricted)
#   - heartbeat sidecar EVERY run (~/.organism/last_seen/mini.healer.json) —
#     the healer itself must be observable (Esiste≠Armato applies to healers)
#
# Manual run:  bash ~/scripts/healer-run.sh
# Canon:       infra/healer/healer-run.sh (declared pair in infra/home-fork/)

set -u

LOG_DIR="$HOME/logs/healer"
LOG="$LOG_DIR/healer.log"
mkdir -p "$LOG_DIR"
REPO="${HEALER_REPO:-$HOME/nuzantara}"
TG_SOURCE="healer-mini"
SIDECAR_DIR="$HOME/.organism/last_seen"
SIDECAR="$SIDECAR_DIR/mini.healer.json"
PIDFILE="/tmp/nuzantara-healer.pid"
MANDATE="$HOME/scripts/HEALER-MANDATE.md"
MAX_WALL_S="${HEALER_MAX_WALL_S:-3300}"   # 55 min hard cap for the LLM session
# The cascade must finish before this wrapper's watchdog so its EXIT trap can
# reap the active provider group and remove temp files. A healer turn may
# legitimately need ~50 minutes; quota/auth failures return immediately, so a
# long per-attempt budget preserves useful work while still rotating dead seats.
CLAUDE_CASCADE_DEADLINE_SEC="${HEALER_CASCADE_DEADLINE_SEC:-$((MAX_WALL_S - 120))}"
CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC="${HEALER_CASCADE_ATTEMPT_TIMEOUT_SEC:-$((CLAUDE_CASCADE_DEADLINE_SEC - 60))}"
if [ "$MAX_WALL_S" -le 180 ] \
    || [ "$CLAUDE_CASCADE_DEADLINE_SEC" -ge "$MAX_WALL_S" ] \
    || [ "$CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC" -le 0 ] \
    || [ "$CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC" -gt "$CLAUDE_CASCADE_DEADLINE_SEC" ]; then
    echo "invalid healer/cascade timeout relationship" >&2
    exit 2
fi
export CLAUDE_CASCADE_DEADLINE_SEC CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC
# Canonical Claude-only cascade retries every isolated OAuth seat without
# crossing the provider boundary (the healer requires Claude agent semantics).
CASCADE_BIN="${HEALER_CASCADE_BIN:-$HOME/scripts/claude-cascade.sh}"
[ -x "$CASCADE_BIN" ] || CASCADE_BIN="$HOME/nuzantara/infra/launchagents/wrappers/claude-cascade.sh"
MODEL="${HEALER_MODEL:-claude-sonnet-5}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"organ":"mini.healer","status":"%s","note":"%s","ts":"%s"}\n' \
        "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$SIDECAR"
}

telegram() { # $1 tier, $2 dedup-key, $3 text — through the tg_notify gateway
    # Was a raw POST guarded by `[ -z "$TELEGRAM_BOT_TOKEN" ] && return 0` and
    # ending in `>/dev/null 2>&1 || true`: in the token-poor environment of
    # launchd it did nothing AND left no trace of doing nothing (W108). The
    # gateway owns credential resolution, the tier router and the dedup ladder,
    # so no secret passes through this script and a standing fault is one
    # message per window instead of one per run.
    local tier="$1" key="$2" text="$3" gateway py
    gateway="$(dirname "$0")/../../scripts/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
    if [ ! -f "$gateway" ]; then
        log "NO GATEWAY at $gateway — alert NOT sent: ${text:0:80}"
        return 0
    fi
    # Absolute interpreter, never PATH: this script heals a machine that is
    # already sick, so its alarm must not share a failure mode with what it
    # reports (W108).
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        [ -x "$py" ] || continue
        # Verdict on stderr — the gateway exits 0 by design, so an exit code
        # would read every refusal as a success (W104).
        log "tg_notify[$key]: $("$py" "$gateway" --tier "$tier" --source "$TG_SOURCE" \
            --dedup-key "$key" -- "$text" 2>&1 | tail -1)"
        return 0
    done
    log "no absolute python3 — alert NOT sent: ${text:0:80}"
}

# ---- kill switch -----------------------------------------------------------
[ -f "$HOME/.nuzantara-healer.env" ] && set -a && source "$HOME/.nuzantara-healer.env" && set +a
if [ "${HEALER_ENABLED:-true}" = "false" ]; then
    log "kill switch HEALER_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# ---- anti-loop guard -------------------------------------------------------
if [ -n "${HEALER_RUN:-}" ]; then
    log "HEALER_RUN already set — refusing nested healer (anti-loop)"
    exit 0
fi

# ---- anti-overlap lock -----------------------------------------------------
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous healer run still alive (pid $(cat "$PIDFILE")) — skipping this tick"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
# The declaration close is a FALLBACK stamp: any exit path that is not the
# explicit close below (an error return, a handled signal) still records that
# this runner came back. close is idempotent and keeps the FIRST outcome, so
# the precise stamp made after `wait` always wins over this generic one.
# A -9 leaves the declaration OPEN on purpose — that is a real abandonment and
# must stay visible (scripts/session_declaration.py).
trap 'rm -f "$PIDFILE"; [ -n "${DECL_RUN_ID:-}" ] && python3 "$REPO/scripts/session_declaration.py" close --run-id "$DECL_RUN_ID" --outcome failed >/dev/null 2>&1; true' EXIT

# ---- secrets (Telegram; claude on Mini auths via its own login) ------------
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

# ---- W84 trampoline: non-ssh contexts ALWAYS re-exec via ssh-localhost ------
# TCC grants are PER-BINARY: under launchd, bash/ls/python3 can read ~/Desktop
# (the pre-check ran fine) while the node binary behind `claude` blocks forever
# on an invisible consent prompt at exec time — tick-2 autopsy 2026-07-06:
# child pinned at 0:00.00 CPU under launchd, the SAME wrapper under sshd
# accrues CPU immediately (sshd holds FDA, children inherit). A probe with ls
# therefore proves NOTHING about the claude child: when not already under ssh,
# trampoline unconditionally.
if [ -z "${HEALER_TRAMPOLINED:-}" ] && [ -z "${SSH_CONNECTION:-}" ]; then
    if [ -f "$HOME/.ssh/id_local_trampoline" ]; then
        log "W84: non-ssh context — re-exec via ssh-localhost trampoline (TCC is per-binary)"
        rm -f "$PIDFILE"
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
            -i "$HOME/.ssh/id_local_trampoline" localhost "HEALER_TRAMPOLINED=1 bash '$0'"
    fi
    log "WARN: no trampoline key — staying in non-ssh context; claude child may TCC-hang (watchdog will reap)"
fi
# Residual TCC check for THIS shell (fail-visible, exit 78 like the cured crons)
if ! /bin/ls "$REPO/CLAUDE.md" >/dev/null 2>&1; then
    log "FATAL: TCC denies $REPO in this context — aborting"
    heartbeat "error" "TCC denied"
    exit 78
fi

# ---- deterministic pre-check (zero LLM cost when the organism is healthy) --
cd "$REPO" || { heartbeat "error" "repo missing"; exit 1; }
ACTIONABLE=0
REASONS=""

# Receptor 1: PENDING-ARMS ledger — overdue tech-debt (>48h)
if ! python3 scripts/pending_arms_report.py --strict >/dev/null 2>&1; then
    ACTIONABLE=1; REASONS="${REASONS}ledger-overdue "
fi

# Receptor 2: proprioception — boundary divergences on THIS machine
PROP_JSON=$(python3 scripts/proprioception.py --json --no-fetch 2>/dev/null)
DIVERGED=$(printf '%s' "$PROP_JSON" | python3 scripts/healer_run_checks.py count-diverged 2>/dev/null || echo 0)
if [ "${DIVERGED:-0}" -gt 0 ] 2>/dev/null; then
    ACTIONABLE=1; REASONS="${REASONS}proprioception:${DIVERGED}-diverged "
fi

# Receptor 3: escalations board — fresh HIGH pending entries
ESC_OUT=$(bash scripts/hooks/escalations_alert_sessionstart.sh 2>/dev/null)
if [ -n "$ESC_OUT" ]; then
    ACTIONABLE=1; REASONS="${REASONS}escalations-board "
fi

# Receptor 4: registry-driven dead-organ scan (DNA/GENOME 2026-07-06 — zero
# hardcoded organ lists: coverage auto-extends when a new organ merges with
# its genes. never-armed / disabled / stale organs do NOT trigger; a BROKEN
# receptor (exit 2) DOES — silent coverage loss is #2 Esiste≠Armato).
REG_OUT=$(python3 scripts/healer_receptor_registry.py --node mini --json 2>/dev/null)
REG_EXIT=$?
if [ "$REG_EXIT" -eq 1 ]; then
    REG_DEAD=$(printf '%s' "$REG_OUT" | python3 -c "
import json,sys
try:
    print(len(json.load(sys.stdin).get('dead',[])))
except Exception:
    print(1)
" 2>/dev/null)
    ACTIONABLE=1; REASONS="${REASONS}registry:${REG_DEAD:-?}-dead-organs "
elif [ "$REG_EXIT" -eq 2 ]; then
    ACTIONABLE=1; REASONS="${REASONS}registry-receptor-broken "
fi

# Receptor 5: arsenal seats (scripts/arsenal_probe.py) — the quota-cascade can
# silently thin to 2-deep (codex 401, agy keychain, glm 401/529, deepseek 402).
# Live-probe at most ~daily (self-throttled by report age — keeps the "healthy
# tick costs ~zero LLM" promise); every tick reads transitions. A NEW persistent
# seat-death (AUTH/BALANCE/MODEL/UNKNOWN) → ACTIONABLE + direct Telegram (the
# cure is almost always operator-gated: relogin/top-up).
ARSENAL_REPORT="$HOME/.organism/arsenal/last.json"
ARSENAL_AGE_H=999
if [ -f "$ARSENAL_REPORT" ]; then
    ARSENAL_AGE_H=$(( ( $(date +%s) - $(stat -f %m "$ARSENAL_REPORT" 2>/dev/null || echo 0) ) / 3600 ))
fi
if [ "$ARSENAL_AGE_H" -ge 20 ] && [ -f "scripts/arsenal_probe.py" ]; then
    log "arsenal probe: report ${ARSENAL_AGE_H}h old — refreshing (live seat probes)"
    python3 scripts/arsenal_probe.py --quiet >> "$LOG" 2>&1 || true
fi
if [ -f "$ARSENAL_REPORT" ]; then
    NEW_DEAD=$(python3 - <<'PY' 2>/dev/null
import json, os
try:
    d = json.load(open(os.path.expanduser("~/.organism/arsenal/last.json")))
    strict = {"AUTH_DEAD", "BALANCE_DEAD", "MODEL_ERR", "UNKNOWN_ERR"}
    print(",".join(f"{t['seat']}:{t['to']}" for t in d.get("transitions", [])
                   if t.get("to") in strict))
except Exception:
    pass
PY
)
    if [ -n "$NEW_DEAD" ]; then
        ACTIONABLE=1; REASONS="${REASONS}arsenal:${NEW_DEAD} "
        telegram p0 "healer-mini:arsenal-seat-dead" "🔌 ARSENALE (Mini): seat morto rilevato — ${NEW_DEAD}. Dettaglio: ~/.organism/arsenal/last.json (docs/runbooks/arsenal-probe.md)"
    fi
fi

# Receptor 6: fleet session VISIBILITY (scripts/fleet_sessions.py). Until
# 2026-08-23 no organ could see the Claude Code sessions running on the OTHER
# machines - the healer that is supposed to notice dead organs was blind to
# three quarters of them, and a fleet audit had to be done by hand.
#
# WHAT THIS RECEPTOR FIRES ON, and deliberately what it does NOT:
#   exit 2  = BLIND, no host answered at all -> the receptor itself lost its
#             senses, same semantics as receptor 4's exit 2. ACTIONABLE.
#   UNREACHABLE host = coverage lost on that machine. Deduped Telegram: a
#             sleeping laptop must not spawn an LLM session every 4h, but it
#             must not read as silence either.
#   DECLARED-SPAN-UNMET rows are REPORTED by the tool, never alerted on here.
#             Measured 2026-08-23: the detector returned 10 such rows and all
#             10 were HEALTHY healer ticks - this plist's own StartInterval is
#             14400s, so "loop 4h" in a mandate TITLE is the cron cadence, not
#             the session's runtime. Wiring an alarm to a signal with a
#             measured 10/10 false-positive rate is how an alarm gets muted.
if [ -f "scripts/fleet_sessions.py" ]; then
    # FLEET_HOSTS_OVERRIDE is a TEST SEAM, same family as HEALER_REPO /
    # HEALER_CASCADE_BIN above: it lets a session exercise this receptor's
    # coverage-loss path (and its Telegram ladder) without taking a real machine
    # down. Unset in production, where the tool's own default local,pro,air wins.
    FLEET_JSON=$(python3 scripts/fleet_sessions.py --json ${FLEET_HOSTS_OVERRIDE:+--hosts "$FLEET_HOSTS_OVERRIDE"} 2>/dev/null)
    FLEET_EXIT=$?
    if [ "$FLEET_EXIT" -eq 2 ]; then
        ACTIONABLE=1; REASONS="${REASONS}fleet-sessions-blind "
        telegram p0 "healer-mini:fleet-blind" "🛰 FLOTTA (Mini): fleet_sessions non ha sondato NESSUN host - visibilita cross-macchina persa. Dettaglio: python3 scripts/fleet_sessions.py --table"
    elif [ "$FLEET_EXIT" -eq 1 ]; then
        # Read the SAME keys the tool emits (W120: a probe that reads a key the
        # reporter never writes zeroes its own alarm, silently).
        FLEET_SUM=$(printf '%s' "$FLEET_JSON" | python3 -c "
import json, sys
try:
    s = json.load(sys.stdin).get('summary', {})
    print('%d %s' % (s.get('hosts_unreachable', 0),
                     ','.join(s.get('unreachable_hosts', [])) or '-'))
except Exception:
    print('0 -')
" 2>/dev/null)
        FLEET_UNREACH=$(printf '%s' "$FLEET_SUM" | cut -d' ' -f1)
        FLEET_HOSTS=$(printf '%s' "$FLEET_SUM" | cut -d' ' -f2)
        if [ "${FLEET_UNREACH:-0}" -gt 0 ] 2>/dev/null; then
            # No second routine alert line here, deliberately. This wrapper is
            # allowed exactly ONE routine summary message, and that summary
            # already carries REASONS verbatim: proven live, it read
            # "run completato su ... fleet:1-host-unreachable". A duplicate
            # would spam Zero AND trip the anti-regrowth gateway lint, which
            # counts routine senders per wrapper. The host names are folded
            # into REASONS instead, so the one message says everything.
            ACTIONABLE=1; REASONS="${REASONS}fleet:${FLEET_UNREACH}-host-unreachable(${FLEET_HOSTS}) "
        fi
    fi
fi

# ---- receptor 7: runs that started and never came back --------------------
# The REAL detector for "an autonomous run died and every gauge stayed green",
# replacing the prose-parsing verdict that measured 10/10 false positives.
# It is safe to alert on because it is an OBSERVATION, not an inference: the
# wrapper opened a declaration, the wrapper never stamped it, and the recorded
# process is gone from the OS process table (pid + start-time, so a recycled
# pid cannot resurrect a dead run).
#   exit 0 = nothing abandoned · exit 1 = at least one · exit 2 = store
#   unreadable, which is BLIND and must never read as clean (W97).
# This receptor CAN accuse this very wrapper's previous tick. That is correct:
# a healer that gets killed every run IS the failure it exists to report.
if [ -f "scripts/session_declaration.py" ]; then
    DECL_JSON=$(python3 scripts/session_declaration.py scan --json 2>/dev/null)
    DECL_EXIT=$?
    if [ "$DECL_EXIT" -eq 2 ]; then
        ACTIONABLE=1; REASONS="${REASONS}declarations-blind "
        telegram p0 "healer-mini:declarations-blind" "🛰 DICHIARAZIONI (Mini): lo store delle dichiarazioni di run non e leggibile - l'abbandono silenzioso non e piu rilevabile. Dettaglio: python3 scripts/session_declaration.py scan"
    elif [ "$DECL_EXIT" -eq 1 ]; then
        # Same key the tool emits (W120), and the SPAWNER names, because "one
        # run was abandoned" without saying whose is not actionable.
        DECL_SUM=$(printf '%s' "$DECL_JSON" | python3 -c "
import json, sys
try:
    s = json.load(sys.stdin).get('summary', {})
    print('%d %s' % (s.get('abandoned', 0),
                     ','.join(s.get('abandoned_spawners', [])) or '-'))
except Exception:
    print('0 -')
" 2>/dev/null)
        DECL_N=$(printf '%s' "$DECL_SUM" | cut -d' ' -f1)
        DECL_WHO=$(printf '%s' "$DECL_SUM" | cut -d' ' -f2)
        if [ "${DECL_N:-0}" -gt 0 ] 2>/dev/null; then
            # Folded into REASONS, no second routine line: this wrapper is
            # allowed exactly ONE routine digest and it already carries REASONS
            # verbatim (anti-regrowth gateway lint counts routine senders).
            ACTIONABLE=1; REASONS="${REASONS}abandoned:${DECL_N}-run(${DECL_WHO}) "
        fi
    fi
fi

if [ "$ACTIONABLE" -eq 0 ]; then
    # ---- CONVERGENCE mission (DNA/GENOME §CONVERGENCE v2, panel-hardened) ----
    # Receptors all quiet: instead of sleeping, bring ONE grandfathered organ
    # into the genome. Deterministic pre-gates keep idle ticks zero-LLM when
    # there is nothing eligible: picker exit 3 = no candidate; an open
    # genome-retrofit PR = lease held (Codex 9); cooldown file = last attempt
    # failed <8h ago. Kill switch: HEALER_CONVERGENCE_ENABLED=false.
    COOLDOWN="$HOME/.organism/healer-convergence.cooldown"
    if [ "${HEALER_CONVERGENCE_ENABLED:-true}" = "false" ]; then
        log "idle; convergence disabled by kill switch"
        heartbeat "ok" "idle: pre-check clean (convergence off)"
        exit 0
    fi
    if [ -f "$COOLDOWN" ] && [ $(( $(date +%s) - $(stat -f %m "$COOLDOWN" 2>/dev/null || echo 0) )) -lt 28800 ]; then
        log "idle; convergence in cooldown"
        heartbeat "ok" "idle: convergence cooldown"
        exit 0
    fi
    if ! python3 scripts/genome_convergence.py --pick >/dev/null 2>&1; then
        log "idle; no eligible convergence candidate (picker exit != 0)"
        heartbeat "ok" "idle: pre-check clean, no convergence candidate"
        exit 0
    fi
    OPEN_RETRO=$(gh pr list --state open --search "genome-retrofit in:title" --json number --jq 'length' 2>/dev/null || echo 1)
    if [ "${OPEN_RETRO:-1}" != "0" ]; then
        log "idle; convergence lease held (open retrofit PR or gh unavailable)"
        heartbeat "ok" "idle: convergence lease held"
        exit 0
    fi
    log "idle + eligible candidate — spawning CONVERGENCE session"
    heartbeat "running" "convergence mission"
    REASONS="genome-convergence "
    MANDATE_OVERRIDE="$REPO/infra/healer/CONVERGENCE-MANDATE.md"
fi

log "ACTIONABLE: ${REASONS}— spawning healer session (model $MODEL, cap ${MAX_WALL_S}s)"
heartbeat "running" "spawned: ${REASONS}"

# ---- spawn the headless healer session --------------------------------------
[ -f "$MANDATE" ] || MANDATE="$REPO/infra/healer/HEALER-MANDATE.md"
# convergence mission reads its own mandate from repo canon (Mini pulls main
# every 5min; no HOME pair needed for a file only read post-trampoline)
[ -n "${MANDATE_OVERRIDE:-}" ] && MANDATE="$MANDATE_OVERRIDE"
if [ ! -f "$MANDATE" ]; then
    log "FATAL: mandate file missing"
    heartbeat "error" "mandate missing"
    exit 1
fi

SESSION_LOG="$LOG_DIR/session-$(date +%Y%m%d-%H%M%S).log"
export HEALER_RUN=1
# Headless hardening (first-tick autopsy 2026-07-06, two OVERLAPPING silent
# hangs — 0 bytes out, 0 CPU): (a) --dangerously-skip-permissions has a
# ONE-TIME interactive acceptance; in -p/no-TTY it hangs invisibly — the
# machine needs `bypassPermissionsModeAccepted: true` in ~/.claude.json
# (armed on Mini 2026-07-06); (b) untrusted cwd triggers the folder-trust
# dialog, same invisible hang (tests from $HOME hung; from the repo they
# PONG) — the cd "$REPO" above is load-bearing, keep it before this spawn.
# Belt-and-suspenders: closed stdin and a zeroed MCP set (the healer's
# perimeter is git/bash/file work; every configured MCP server is a
# synchronous-init hang risk in -p mode). HEALER_CLAUDE_BIN remains a
# compatibility override for the cascade's default seat only.
if [ -n "${HEALER_CLAUDE_BIN:-}" ]; then
    export CLAUDE_CASCADE_DEFAULT_BIN="$HEALER_CLAUDE_BIN"
fi
if [ ! -x "$CASCADE_BIN" ]; then
    log "FATAL: canonical Claude cascade missing (env HEALER_CASCADE_BIN, ~/scripts, repo canon)"
    heartbeat "error" "claude cascade missing"
    exit 1
fi
# TWO-PHASE COMMIT (scripts/session_declaration.py). Opened here, stamped after
# `wait`. An open declaration past its own cap with a dead runner is the ONLY
# honest "this run died and nobody noticed" signal — the prose-parsing verdict
# it replaces accused ten healthy ticks out of ten (PR #4646).
# CADENCE IS READ FROM THE PLIST, never hardcoded: StartInterval is what
# actually schedules this wrapper, and a second copy of that number is exactly
# the drift that made "loop 4h" readable as a runtime in the first place.
DECL_CADENCE=$(/usr/libexec/PlistBuddy -c "Print :StartInterval" \
    "$HOME/Library/LaunchAgents/com.nuzantara.healer.4h.plist" 2>/dev/null || true)
DECL_RUN_ID=$(python3 "$REPO/scripts/session_declaration.py" open \
    --spawner "healer-run.sh" \
    --cap-sec "$MAX_WALL_S" \
    ${DECL_CADENCE:+--cadence-sec "$DECL_CADENCE"} \
    --mandate "$MANDATE" \
    --pid $$ 2>/dev/null) || DECL_RUN_ID=""
[ -n "$DECL_RUN_ID" ] || log "WARN: session declaration not opened — this run is invisible to the abandonment scan"

"$CASCADE_BIN" "$(cat "$MANDATE")

CONTESTO DI QUESTO TICK — receptor scattati: ${REASONS}" \
    --claude-only --model "$MODEL" -- \
    --dangerously-skip-permissions --strict-mcp-config \
    --mcp-config '{"mcpServers":{}}' \
    --max-budget-usd "${HEALER_MAX_BUDGET_USD:-10}" \
    </dev/null > "$SESSION_LOG" 2>&1 &
CPID=$!

# Single-process wall-clock watchdog (macOS has no timeout(1)). Python sleeps
# in-process so cancelling the watchdog cannot orphan an external sleep under
# PID 1 after a fast cascade return.
python3 -c '
import datetime
import os
import signal
import sys
import time

child_pid = int(sys.argv[1])
time.sleep(float(sys.argv[2]))
try:
    os.kill(child_pid, 0)
except ProcessLookupError:
    raise SystemExit(0)
try:
    os.kill(child_pid, signal.SIGTERM)
except ProcessLookupError:
    raise SystemExit(0)
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open(sys.argv[3], "a", encoding="utf-8") as handle:
    handle.write("[%s] WATCHDOG: %s\n" % (timestamp, sys.argv[4]))
' "$CPID" "$MAX_WALL_S" "$LOG" \
    "killed session after ${MAX_WALL_S}s" </dev/null >/dev/null 2>&1 &
WPID=$!
wait "$CPID"
CEXIT=$?
kill "$WPID" 2>/dev/null || true
wait "$WPID" 2>/dev/null || true

# 143 = 128+SIGTERM: the wall-clock watchdog above reaped the child. Recorded as
# its own outcome rather than folded into "failed" — a run the cap killed and a
# run that failed on its own need different cures.
if [ -n "${DECL_RUN_ID:-}" ]; then
    if [ "$CEXIT" -eq 0 ]; then DECL_OUTCOME=completed
    elif [ "$CEXIT" -eq 143 ]; then DECL_OUTCOME=killed-by-watchdog
    else DECL_OUTCOME=failed
    fi
    python3 "$REPO/scripts/session_declaration.py" close \
        --run-id "$DECL_RUN_ID" --outcome "$DECL_OUTCOME" --exit-code "$CEXIT" >/dev/null 2>&1 \
        || log "WARN: could not stamp declaration $DECL_RUN_ID"
fi

TAIL=$(tail -c 600 "$SESSION_LOG" 2>/dev/null | tr '\n' ' ' | tr -s ' ')
log "session exit=$CEXIT — tail: ${TAIL:0:300}"

if [ $CEXIT -eq 0 ]; then
    heartbeat "ok" "session done: ${REASONS}"
    telegram digest "healer-mini:run-complete" "🩹 HEALER (Mini): run completato su ${REASONS}. Esito: ${TAIL:0:400}"
else
    FAILURE_CLASS=$(printf '%s' "$TAIL" | python3 scripts/healer_run_checks.py classify-session-tail 2>/dev/null || echo session_error)
    if [ "$FAILURE_CLASS" = "rate_or_quota_limit" ]; then
        heartbeat "degraded" "claude quota/rate limit: ${REASONS}"
        telegram p0 "healer-mini:seats-exhausted" "⚠️ HEALER (Mini): tutti i seat Claude esauriti su ${REASONS}. Nessuna cascade cross-provider per policy; log: $SESSION_LOG"
    elif [ "$FAILURE_CLASS" = "auth_required" ]; then
        heartbeat "degraded" "claude auth required: ${REASONS}"
        telegram p0 "healer-mini:auth-failed" "⚠️ HEALER (Mini): autenticazione fallita su tutti i seat Claude per ${REASONS}. Nessuna cascade cross-provider per policy; log: $SESSION_LOG"
    else
        heartbeat "degraded" "session exit=$CEXIT"
        telegram p0 "healer-mini:session-exit" "⚠️ HEALER (Mini): sessione uscita $CEXIT su ${REASONS}. Log: $SESSION_LOG"
    fi
fi
exit 0
