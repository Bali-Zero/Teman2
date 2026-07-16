#!/bin/bash
# pro.healer — Node-scoped healer for Pro: cures Pro LOCAL runtime (kickstart dead organs, HOME-pair refresh from canon), NEVER writes the repo (single-writer stays mini.healer)
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-healer.sh
# Live:  ~/scripts/pro-healer.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.healer"
LOG_DIR="$HOME/logs/pro-healer"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-healer.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    log "node guard: $(hostname -s) != nuzantara — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${PRO_HEALER_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_HEALER_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# anti-loop guard — a healer session must never spawn another healer
if [ -n "${HEALER_RUN:-}" ]; then
    log "HEALER_RUN already set — refusing nested healer (anti-loop)"
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

telegram() { # $1 text — best-effort, never blocks the run
    [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OWNER_CHAT_ID:-}" ] && return 0
    curl -sS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" --data-urlencode text="$1" >/dev/null 2>&1 || true
}

# ---- G6_spawn_hardened: headless claude with the 4 gotchas cured ------------
# (1) bypass-acceptance: ~/.claude.json needs bypassPermissionsModeAccepted=true
#     on THIS machine (one-time, operator) — else silent hang at spawn.
# (2) folder-trust: cd into the repo BEFORE spawning — else trust-dialog hang.
# (3) TCC is PER-BINARY (W84): under launchd, bash may read ~/Desktop while the
#     node binary behind claude blocks on invisible consent. Cure: UNCONDITIONAL
#     ssh-localhost trampoline in non-ssh contexts (sshd holds FDA, children inherit).
# (4) hygiene: stdin </dev/null; empty MCP config (each server is a sync-init
#     hang risk in -p mode); OAuth token from env, Keychain can be LOCKED here.
REPO="$HOME/nuzantara"
MAX_WALL_S="${PRO_HEALER_MAX_WALL_S:-3300}"
# claude binary is NOT at the same path fleet-wide (Mini: /opt/homebrew symlink;
# Pro: ~/.local/bin only — first live tick died exit=127 on the homebrew default).
# Env override wins; otherwise probe known locations, then PATH.
CLAUDE_BIN="${PRO_HEALER_CLAUDE_BIN:-}"
if [ -z "$CLAUDE_BIN" ]; then
    for _c in /opt/homebrew/bin/claude "$HOME/.local/bin/claude" /usr/local/bin/claude; do
        if [ -x "$_c" ]; then CLAUDE_BIN="$_c"; break; fi
    done
fi
[ -n "$CLAUDE_BIN" ] || CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
MODEL="${PRO_HEALER_MODEL:-claude-sonnet-5}"

if [ -z "${PRO_HEALER_TRAMPOLINED:-}" ] && [ -z "${SSH_CONNECTION:-}" ]; then
    if [ -f "$HOME/.ssh/id_local_trampoline" ]; then
        log "W84: non-ssh context — re-exec via ssh-localhost trampoline (TCC is per-binary)"
        rm -f "$PIDFILE"
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
            -i "$HOME/.ssh/id_local_trampoline" localhost "PRO_HEALER_TRAMPOLINED=1 bash '$0'"
    fi
    log "WARN: no trampoline key — claude child may TCC-hang (watchdog will reap)"
fi
if ! /bin/ls "$REPO/CLAUDE.md" >/dev/null 2>&1; then
    log "FATAL: TCC denies $REPO in this context"; heartbeat "error" "TCC denied"; exit 78
fi
cd "$REPO" || { heartbeat "error" "repo missing"; exit 1; }

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_1:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_1"
fi

# ---- deterministic pre-check (zero LLM cost when Pro's runtime is healthy) --
# Receptors are PRO-scoped; the PENDING-ARMS ledger receptor stays MINI-ONLY
# (single consumer per receptor — two healers on one ledger = duplicated work).
ACTIONABLE=0
REASONS=""

# Receptor A: registry-driven dead-organ scan on THIS node (DNA/GENOME 4c)
REG_OUT=$(python3 scripts/healer_receptor_registry.py --node pro --json 2>/dev/null)
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

# Receptor B: proprioception — boundary divergences on THIS machine
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

# Receptor C: declared HOME pairs drift on pro (superscar #1)
if ! python3 scripts/lint_home_fork.py --check >/dev/null 2>&1; then
    ACTIONABLE=1; REASONS="${REASONS}home-fork-drift "
fi

if [ "$ACTIONABLE" -eq 0 ]; then
    log "pre-check clean (pro organs alive, 0 diverged, pairs aligned) — no LLM spawn"
    heartbeat "ok" "idle: pre-check clean"
    exit 0
fi

log "ACTIONABLE: ${REASONS}— spawning healer-pro session (model $MODEL, cap ${MAX_WALL_S}s)"
heartbeat "running" "spawned: ${REASONS}"

MANDATE="$HOME/scripts/HEALER-PRO-MANDATE.md"
[ -f "$MANDATE" ] || MANDATE="$REPO/infra/healer/HEALER-PRO-MANDATE.md"
if [ ! -f "$MANDATE" ]; then
    log "FATAL: mandate file missing"
    heartbeat "error" "mandate missing"
    exit 1
fi
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
    log "FATAL: no claude binary (env PRO_HEALER_CLAUDE_BIN, /opt/homebrew, ~/.local, /usr/local, PATH all empty)"
    heartbeat "error" "no claude binary"
    exit 1
fi

SESSION_LOG="$LOG_DIR/session-$(date +%Y%m%d-%H%M%S).log"
export HEALER_RUN=1
"$CLAUDE_BIN" -p "$(cat "$MANDATE")

CONTESTO DI QUESTO TICK — receptor scattati: ${REASONS}" \
    --model "$MODEL" --dangerously-skip-permissions \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --max-budget-usd "${HEALER_MAX_BUDGET_USD:-10}" \
    </dev/null > "$SESSION_LOG" 2>&1 &
CPID=$!
( sleep "$MAX_WALL_S"; kill -0 "$CPID" 2>/dev/null && kill "$CPID" && \
    echo "[$(ts)] WATCHDOG: killed after ${MAX_WALL_S}s" >> "$LOG" ) &
WPID=$!
wait "$CPID"; RC=$?
kill "$WPID" 2>/dev/null

TAIL=$(tail -c 600 "$SESSION_LOG" 2>/dev/null | tr '\n' ' ' | tr -s ' ')
log "session exit=$RC — tail: ${TAIL:0:300}"
if [ $RC -eq 0 ]; then
    heartbeat "ok" "session done: ${REASONS}"
    telegram "🩹 HEALER-PRO: run completato su ${REASONS}. Esito: ${TAIL:0:400}"
else
    heartbeat "degraded" "session exit=$RC"
    telegram "⚠️ HEALER-PRO: sessione uscita $RC su ${REASONS}. Log: $SESSION_LOG"
fi
exit 0
