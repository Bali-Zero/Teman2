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
TG_SOURCE="healer-pro"
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

telegram() { # $1 tier, $2 dedup-key, $3 text — through the tg_notify gateway
    # Was a raw POST guarded by `[ -z "$TELEGRAM_BOT_TOKEN" ] && return 0` and
    # ending in `>/dev/null 2>&1 || true`: in the token-poor environment of
    # launchd it did nothing AND left no trace of doing nothing (W108). The
    # gateway owns credential resolution, the tier router and the dedup ladder,
    # so no secret passes through this script and a standing fault is one
    # message per window instead of one per run.
    local tier="$1" key="$2" text="$3" gateway py
    gateway="$(dirname "$0")/../../../scripts/tg_notify.py"
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
# Leave two minutes for the cascade trap and outer-wrapper bookkeeping. Healer
# turns are long-running by design; exhausted/auth-dead seats fail immediately,
# while a healthy seat keeps enough budget to complete a substantive repair.
CLAUDE_CASCADE_DEADLINE_SEC="${PRO_HEALER_CASCADE_DEADLINE_SEC:-$((MAX_WALL_S - 120))}"
CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC="${PRO_HEALER_CASCADE_ATTEMPT_TIMEOUT_SEC:-$((CLAUDE_CASCADE_DEADLINE_SEC - 60))}"
if [ "$MAX_WALL_S" -le 180 ] \
    || [ "$CLAUDE_CASCADE_DEADLINE_SEC" -ge "$MAX_WALL_S" ] \
    || [ "$CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC" -le 0 ] \
    || [ "$CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC" -gt "$CLAUDE_CASCADE_DEADLINE_SEC" ]; then
    echo "invalid pro-healer/cascade timeout relationship" >&2
    exit 2
fi
export CLAUDE_CASCADE_DEADLINE_SEC CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC
# Canonical Claude-only cascade retries every isolated OAuth seat without
# crossing the provider boundary (the healer requires Claude agent semantics).
CASCADE_BIN="${PRO_HEALER_CASCADE_BIN:-$HOME/scripts/claude-cascade.sh}"
[ -x "$CASCADE_BIN" ] || CASCADE_BIN="$HOME/nuzantara/infra/launchagents/wrappers/claude-cascade.sh"
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
# Task #70: --check now derives the repo side from origin/main (fetched)
# instead of the local checkout, so it has a THIRD exit outcome — 4
# (CANNOT-VERIFY: fetch/origin-main lookup failed) — that must not be
# folded into the same bucket as a real divergence. A collapsed `if !`
# would spawn a costly LLM healer session on the false premise "there is
# drift" when the true state is "could not check this tick"; Law 6 also
# makes a transient offline/fetch-refused state a natural condition, not
# a fault, so it must not be silently promoted to ACTIONABLE either — it
# is logged for visibility instead, never swallowed. The tool's own
# verdict text is captured, not discarded, in EITHER branch — a guard
# whose product is a verdict must not have that verdict thrown away by
# its only reader.
LHF_CHECK_OUT=$(python3 scripts/lint_home_fork.py --check 2>&1)
LHF_CHECK_RC=$?
if [ $(( LHF_CHECK_RC & 1 )) -ne 0 ]; then
    ACTIONABLE=1; REASONS="${REASONS}home-fork-drift "
    log "home-fork --check (rc=$LHF_CHECK_RC): $LHF_CHECK_OUT"
elif [ $(( LHF_CHECK_RC & 4 )) -ne 0 ]; then
    log "home-fork --check: CANNOT-VERIFY (rc=$LHF_CHECK_RC), not treated as drift: $LHF_CHECK_OUT"
fi

# Receptor D: arsenal seats (scripts/arsenal_probe.py) — the seat<->armed
# boundary was UNWATCHED on Pro: the boot receptor was re-serving a 193h-stale
# report that claimed claude NOT_INSTALLED on the machine where claude runs
# daily (S1 medico, 2026-07-18). Same self-throttled pattern as the Mini
# healer (infra/healer/healer-run.sh Receptor 5): live 1-token probes at most
# ~daily (report-age gate), transitions read every tick, a NEW persistent
# seat-death (AUTH/BALANCE/MODEL/UNKNOWN) → ACTIONABLE + direct Telegram —
# the cure is almost always operator-gated (relogin/top-up).
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
        telegram p0 "healer-pro:arsenal-seat-dead" "🔌 ARSENALE (Pro): seat morto rilevato — ${NEW_DEAD}. Dettaglio: ~/.organism/arsenal/last.json (docs/runbooks/arsenal-probe.md)"
    fi
fi

if [ "$ACTIONABLE" -eq 0 ]; then
    log "pre-check clean (pro organs alive, 0 diverged, pairs aligned) — no LLM spawn"
    heartbeat "ok" "idle: pre-check clean"
    exit 0
fi

# ---- G11_memoize: skip the LLM spawn when the organ-state fingerprint is
# unchanged AND the last verdict was "incurable" (D-004, ~/.tokenaudit/DECISIONS.md
# — measured 5/9 ticks in T3 spawning an identical $10-budget session against an
# already-incurable, unchanged organ set). Fail-open toward spawning: any error
# in the memo tooling below degrades to "spawn anyway", never to a silently
# skipped cure (#2 Esiste≠Armato) — MEMO_RC not in {0,3} falls through untouched.
export _HM_REG_OUT="$REG_OUT"
export _HM_PROP_JSON="$PROP_JSON"
export _HM_LHF_OUT="$LHF_CHECK_OUT"
export _HM_NEW_DEAD="${NEW_DEAD:-}"
export _HM_REASONS="$REASONS"
RECEPTOR_STATE_JSON=$(python3 - <<'PY'
import json, os

def _load(name):
    raw = os.environ.get(name, "")
    try:
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

reg = _load("_HM_REG_OUT")
prop = _load("_HM_PROP_JSON")
lhf_out = os.environ.get("_HM_LHF_OUT", "")
new_dead_raw = os.environ.get("_HM_NEW_DEAD", "")
reasons = os.environ.get("_HM_REASONS", "")

dead_organs = reg.get("dead") if isinstance(reg, dict) else []
if not isinstance(dead_organs, list):
    dead_organs = []

diverged_probes = []
for p in (prop.get("probes") if isinstance(prop, dict) else []) or []:
    if not isinstance(p, dict):
        continue
    verdict = str(p.get("status") or p.get("verdict") or "").upper()
    if verdict == "DIVERGED":
        diverged_probes.append(str(p.get("id", "")))

# lint_home_fork.py --check prints breach lines as "  - <text>"; a stale-checkout
# notice ("  ~ <text>") is NOT a breach and must not perturb the fingerprint.
drifted_pairs = [
    ln.strip()[2:].strip()
    for ln in lhf_out.splitlines()
    if ln.strip().startswith("- ")
]

arsenal_new_dead = [t for t in new_dead_raw.split(",") if t]

print(json.dumps({
    "dead_organs": dead_organs,
    "diverged_probes": diverged_probes,
    "drifted_pairs": drifted_pairs,
    "arsenal_new_dead": arsenal_new_dead,
    "reasons": reasons,
}))
PY
)
FINGERPRINT=$(printf '%s' "$RECEPTOR_STATE_JSON" | python3 scripts/healer_memo.py fingerprint 2>>"$LOG")
MEMO_STATE="$HOME/.organism/healer-pro/memo.json"
MEMO_RC=0
MEMO_OUT=$(python3 scripts/healer_memo.py check --state "$MEMO_STATE" --fingerprint "$FINGERPRINT" 2>&1) || MEMO_RC=$?
log "healer_memo check (rc=$MEMO_RC): $MEMO_OUT"
if [ "$MEMO_RC" -eq 3 ]; then
    log "memoized: same organ-state fingerprint as last spawn, last verdict incurable — LLM spawn skipped ($MEMO_OUT)"
    heartbeat "ok" "memoized: skipped LLM spawn ($MEMO_OUT)"
    exit 0
elif [ "$MEMO_RC" -ne 0 ]; then
    log "healer_memo check errored (rc=$MEMO_RC) — fail-open, spawning anyway: $MEMO_OUT"
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
if [ -n "${PRO_HEALER_CLAUDE_BIN:-}" ]; then
    export CLAUDE_CASCADE_DEFAULT_BIN="$PRO_HEALER_CLAUDE_BIN"
fi
if [ ! -x "$CASCADE_BIN" ]; then
    log "FATAL: canonical Claude cascade missing (env PRO_HEALER_CASCADE_BIN, ~/scripts, repo canon)"
    heartbeat "error" "claude cascade missing"
    exit 1
fi

SESSION_LOG="$LOG_DIR/session-$(date +%Y%m%d-%H%M%S).log"
SPAWN_TS_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export HEALER_RUN=1
"$CASCADE_BIN" "$(cat "$MANDATE")

CONTESTO DI QUESTO TICK — receptor scattati: ${REASONS}" \
    --claude-only --model "$MODEL" -- \
    --dangerously-skip-permissions --strict-mcp-config \
    --mcp-config '{"mcpServers":{}}' \
    --max-budget-usd "${HEALER_MAX_BUDGET_USD:-10}" \
    </dev/null > "$SESSION_LOG" 2>&1 &
CPID=$!
# Keep the watchdog single-process so fast cascade returns cannot orphan sleep.
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
    "killed after ${MAX_WALL_S}s" </dev/null >/dev/null 2>&1 &
WPID=$!
wait "$CPID"; RC=$?
kill "$WPID" 2>/dev/null || true
wait "$WPID" 2>/dev/null || true

TAIL=$(tail -c 600 "$SESSION_LOG" 2>/dev/null | tr '\n' ' ' | tr -s ' ')
log "session exit=$RC — tail: ${TAIL:0:300}"

# G11_memoize (continued): record this tick's outcome so the NEXT tick can
# memoize against it. The verdict comes from the healer's own escalation
# write (shared/escalations_pro.jsonl), never from $RC — a session can exit 0
# after concluding "0/N curable" (that IS success: the diagnosis is correct).
MEMO_VERDICT=$(python3 scripts/healer_memo.py verdict-from-escalations \
    --file shared/escalations_pro.jsonl --since "$SPAWN_TS_ISO" 2>>"$LOG")
[ -n "$MEMO_VERDICT" ] || MEMO_VERDICT="unknown"
if [ -n "${FINGERPRINT:-}" ]; then
    python3 scripts/healer_memo.py record --state "$MEMO_STATE" \
        --fingerprint "$FINGERPRINT" --verdict "$MEMO_VERDICT" \
        --spawned-at "$SPAWN_TS_ISO" >>"$LOG" 2>&1 \
        || log "WARN: healer_memo record failed (fingerprint=${FINGERPRINT:0:12}... verdict=$MEMO_VERDICT)"
else
    log "WARN: no fingerprint computed this tick — memo not recorded"
fi

if [ $RC -eq 0 ]; then
    heartbeat "ok" "session done: ${REASONS}"
    telegram digest "healer-pro:run-complete" "🩹 HEALER-PRO: run completato su ${REASONS}. Esito: ${TAIL:0:400}"
else
    heartbeat "degraded" "session exit=$RC"
    telegram p0 "healer-pro:session-exit" "⚠️ HEALER-PRO: sessione uscita $RC su ${REASONS}. Log: $SESSION_LOG"
fi
exit 0
