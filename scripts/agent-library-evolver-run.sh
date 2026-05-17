#!/bin/bash
# Bali Zero Nuzantara agent-library-evolver — weekly wrapper
#
# Triggered by ~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist
# Schedule: Sunday 03:00 WITA (after wr2 Reflexion 02:30, before Mon SessionStart).
#
# Spec: docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md
# Status: Phase 0 SKELETON — exits 0 without real LLM call. Phase 1 will
# wire the actual 4-step pipeline (context, redact, evoskill run, gate).

set -euo pipefail

# ─── 0. Bootstrap ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_DATE="$(date +%Y-%m-%d)"
RUN_ID="agent-library-evolver-$(date +%Y%m%d-%H%M%S)"
TELEMETRY_DIR="${EVOSKILL_TELEMETRY_DIR:-/tmp/agent-library-evolver}/${RUN_DATE}"
mkdir -p "$TELEMETRY_DIR"
LOG="$TELEMETRY_DIR/${RUN_ID}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S WITA')] $*" | tee -a "$LOG"
}

# ─── 1. Source secrets (fail-closed on missing) ────────────────────────
SECRETS_FILE="${SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
if [ ! -r "$SECRETS_FILE" ]; then
    log "FATAL: secrets file not readable at $SECRETS_FILE"
    log "Copy config/agent-library-evolver-secrets.env.example to that path."
    exit 1
fi
set -a
# shellcheck source=/dev/null
. "$SECRETS_FILE"
set +a

BUDGET_USD="${BUDGET_USD:-1.00}"
log "Phase 0 smoke run — BUDGET_USD=$BUDGET_USD (no LLM call expected)"
log "Telemetry: $TELEMETRY_DIR"

# ─── 2. PG advisory lock (single-flight per spec §"Reflection loop") ───
# Phase 0: skip if psql missing — smoke test doesn't need it.
if command -v psql >/dev/null 2>&1 && [ -n "${PGURL:-}" ]; then
    LOCK_KEY="${EVOSKILL_LOCK_KEY:-1234567890}"
    LOCK_RESULT=$(psql "$PGURL" -tAc \
        "SELECT pg_try_advisory_lock($LOCK_KEY);" 2>&1 || echo "f")
    if [ "$LOCK_RESULT" != "t" ]; then
        log "WARN: previous run still active OR psql unreachable — skipping"
        exit 0
    fi
    trap "psql '$PGURL' -c 'SELECT pg_advisory_unlock($LOCK_KEY);' >/dev/null 2>&1 || true" EXIT
else
    log "INFO: psql / PGURL unavailable — skipping advisory lock (Phase 0 OK)"
fi

# ─── 3. Context gathering (Phase 1 — TODO) ─────────────────────────────
# Phase 0: skeleton-only, produces empty raw context to prove the dir
# structure works.
CONTEXT_RAW="$TELEMETRY_DIR/context-raw.md"
cat > "$CONTEXT_RAW" <<EOF
# Bali Zero Nuzantara agent-library-evolver — context raw (Phase 0 skeleton)
# Run: $RUN_ID
# Date: $RUN_DATE
#
# Phase 1 will populate this with:
#   - mem query "recent successes/failures last 7 days"
#   - git log --since=7days --oneline
#   - read agent-library/02-patterns.md + 03-lessons.md
#   - read recent cicatrix-scars.md additions
EOF
log "Context raw: $CONTEXT_RAW (Phase 0 skeleton — no real content)"

# ─── 4. Privacy redaction (Phase 1 — TODO) ─────────────────────────────
# Phase 0: NO LLM call planned, so redaction is no-op pass-through.
# Phase 1 will wire scripts/_redact_pii.py per
# agent-library/config/redaction-rules.yaml
CONTEXT_REDACTED="$TELEMETRY_DIR/context-redacted.md"
cp "$CONTEXT_RAW" "$CONTEXT_REDACTED"
log "Context redacted: $CONTEXT_REDACTED (Phase 0 no-op pass-through)"

# ─── 5. EvoSkill run (Phase 1 — TODO) ──────────────────────────────────
# Phase 0: only --help smoke. Real `uv run evoskill run` deferred.
VENDOR_DIR="${EVOSKILL_VENDOR_DIR:-$REPO_ROOT/vendor/evoskill}"
if [ ! -d "$VENDOR_DIR" ]; then
    log "FATAL: vendor dir missing at $VENDOR_DIR"
    exit 1
fi

# Phase 0 smoke: verify the CLI itself loads (no LLM call).
# Real run: uv run --directory "$VENDOR_DIR" evoskill run \
#     --config "$EVOSKILL_CONFIG_PATH"
if command -v uv >/dev/null 2>&1; then
    if (cd "$VENDOR_DIR" && uv run evoskill --help) >>"$LOG" 2>&1; then
        log "Phase 0 SMOKE: uv run evoskill --help OK"
    else
        log "Phase 0 SMOKE FAIL: uv run evoskill --help returned non-zero"
        log "See $LOG for the upstream CLI traceback"
        exit 1
    fi
else
    log "FATAL: uv not installed — install via brew install uv"
    exit 1
fi

# ─── 6. Telemetry persist (Phase 1 — TODO) ─────────────────────────────
# Phase 1 will write usage.total_cost_usd and proposals_passed counts.
TELEMETRY_JSON="$TELEMETRY_DIR/telemetry.json"
cat > "$TELEMETRY_JSON" <<EOF
{
  "run_id": "$RUN_ID",
  "phase": "0-smoke",
  "started_at_wita": "$(date '+%Y-%m-%d %H:%M:%S')",
  "budget_usd": "$BUDGET_USD",
  "usage": {
    "total_cost_usd": 0.0,
    "deepseek_calls": 0,
    "gemini_calls": 0,
    "notebooklm_calls": 0
  },
  "proposals": {
    "raw": 0,
    "passed_existence": 0,
    "passed_entailment": 0,
    "rejected": 0
  },
  "exit_code": 0,
  "phase_0_note": "Skeleton run — no real LLM call, no proposals generated."
}
EOF
log "Telemetry: $TELEMETRY_JSON"

# ─── 7. Telegram alert (Phase 1 — TODO) ────────────────────────────────
# Phase 1 will fire the alert per spec §"Telegram alert format".
log "Phase 0 alert SKIPPED (skeleton — no proposals to announce)"

log "DONE: Phase 0 smoke completed at $(date '+%Y-%m-%d %H:%M:%S WITA')"
exit 0
