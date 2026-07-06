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
REPO="$HOME/Desktop/nuzantara"
SIDECAR_DIR="$HOME/.organism/last_seen"
SIDECAR="$SIDECAR_DIR/mini.healer.json"
PIDFILE="/tmp/nuzantara-healer.pid"
MANDATE="$HOME/scripts/HEALER-MANDATE.md"
MAX_WALL_S="${HEALER_MAX_WALL_S:-3300}"   # 55 min hard cap for the LLM session
CLAUDE_BIN="${HEALER_CLAUDE_BIN:-/opt/homebrew/bin/claude}"
MODEL="${HEALER_MODEL:-claude-sonnet-5}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"organ":"mini.healer","status":"%s","note":"%s","ts":"%s"}\n' \
        "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$SIDECAR"
}

telegram() { # $1 text — best-effort, never blocks the run
    [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OWNER_CHAT_ID:-}" ] && return 0
    curl -sS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" --data-urlencode text="$1" >/dev/null 2>&1 || true
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
trap 'rm -f "$PIDFILE"' EXIT

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
DIVERGED=$(printf '%s' "$PROP_JSON" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(sum(1 for p in d.get('probes',[]) if str(p.get('verdict','')).upper()=='DIVERGED'))
except Exception:
    print(0)
" 2>/dev/null)
if [ "${DIVERGED:-0}" -gt 0 ] 2>/dev/null; then
    ACTIONABLE=1; REASONS="${REASONS}proprioception:${DIVERGED}-diverged "
fi

# Receptor 3: escalations board — fresh HIGH pending entries
ESC_OUT=$(bash scripts/hooks/escalations_alert_sessionstart.sh 2>/dev/null)
if [ -n "$ESC_OUT" ]; then
    ACTIONABLE=1; REASONS="${REASONS}escalations-board "
fi

# Receptor 4: arsenal seats (scripts/arsenal_probe.py) — the quota-cascade can
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
        telegram "🔌 ARSENALE (Mini): seat morto rilevato — ${NEW_DEAD}. Dettaglio: ~/.organism/arsenal/last.json (docs/runbooks/arsenal-probe.md)"
    fi
fi

if [ "$ACTIONABLE" -eq 0 ]; then
    log "pre-check clean (0 diverged, ledger ok, board quiet) — no LLM spawn"
    heartbeat "ok" "idle: pre-check clean"
    exit 0
fi

log "ACTIONABLE: ${REASONS}— spawning healer session (model $MODEL, cap ${MAX_WALL_S}s)"
heartbeat "running" "spawned: ${REASONS}"

# ---- spawn the headless healer session --------------------------------------
[ -f "$MANDATE" ] || MANDATE="$REPO/infra/healer/HEALER-MANDATE.md"
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
# Belt-and-suspenders: MAX env token when available (Keychain reads can
# block under launchd/sshd, W84 family), closed stdin, and a zeroed MCP set
# (the healer's perimeter is git/bash/file work; every configured MCP server
# is a synchronous-init hang risk in -p mode).
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_1:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_1"
fi
"$CLAUDE_BIN" -p "$(cat "$MANDATE")

CONTESTO DI QUESTO TICK — receptor scattati: ${REASONS}" \
    --model "$MODEL" --dangerously-skip-permissions \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    </dev/null > "$SESSION_LOG" 2>&1 &
CPID=$!

# wall-clock watchdog (macOS has no timeout(1))
(
    sleep "$MAX_WALL_S"
    if kill -0 "$CPID" 2>/dev/null; then
        kill "$CPID" 2>/dev/null
        echo "[$(ts)] WATCHDOG: killed session after ${MAX_WALL_S}s" >> "$LOG"
    fi
) &
WPID=$!
wait "$CPID"
CEXIT=$?
kill "$WPID" 2>/dev/null

TAIL=$(tail -c 600 "$SESSION_LOG" 2>/dev/null | tr '\n' ' ' | tr -s ' ')
log "session exit=$CEXIT — tail: ${TAIL:0:300}"

if [ $CEXIT -eq 0 ]; then
    heartbeat "ok" "session done: ${REASONS}"
    telegram "🩹 HEALER (Mini): run completato su ${REASONS}. Esito: ${TAIL:0:400}"
else
    heartbeat "degraded" "session exit=$CEXIT"
    telegram "⚠️ HEALER (Mini): sessione uscita $CEXIT su ${REASONS}. Log: $SESSION_LOG"
fi
exit 0
