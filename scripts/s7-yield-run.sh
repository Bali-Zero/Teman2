#!/usr/bin/env bash
# s7-yield-run.sh — LaunchAgent wrapper for S7, the CRM yield draft generator.
#
# S7 (scripts/s7_yield_draft_local.py) replaces com.balizero.yield-optimizer.weekly,
# retired 2026-08-20: that agent queried `crm_clients`, a table that does not exist
# in production (real table is `clients`), and depended on a 5-tier Claude cascade
# with no cross-family fallback for a print-mode agent — its last run (16/8/2026)
# had ALL FIVE Claude seats fail and the wrapper still `exit 0`'d (cron-theater,
# superscar family #2). S7 queries the real schema and is fully local/fail-closed.
#
# PII contract (UU PDP / SYMBIOSIS Law 2), enforced by s7_yield_draft_local.py itself,
# not by this wrapper:
#   - DB access: read-only role `nuzantara_readonly` via pg-proxy localhost:15432,
#     password from macOS Keychain (service nuzantara-postgres-readonly). Proven
#     readable from THIS exact GUI-launchd context by the sibling LaunchAgent
#     com.nuzantara.cost-ledger-export (30-min interval, live since before 2026-08-20,
#     same `security find-generic-password` call) — see PENDING-ARMS 2026-08-20 s7-cutover.
#   - Drafting LLM: Ollama qwen3.5:9b LOCAL only. If Ollama is down, the script itself
#     aborts non-zero with NO cloud fallback — this wrapper must never weaken that.
#   - stdout/stderr carry client_id + aggregate counts ONLY (script's own privacy-log
#     rule) — safe for this wrapper, cron-runner.sh's receipt, and the Telegram alert
#     to capture verbatim on failure.
#   - Drafts (which DO contain client PII) are written under $HOME, gitignored,
#     outside the repo tree, and are NEVER printed by this wrapper.
#
# Run via cron-runner.sh (not invoked directly by the plist) so failures get a
# Cell-readable receipt AND a deduped Telegram P0 through the proven gateway
# (tg_notify.py) — a wrapper that alarms for itself outside that path tends to go
# mute unheard (superscar W107/W108: 19 of 20 sibling wrappers failed silently this way).
#
# Kill-switch: S7_YIELD_OFF=1.

set -uo pipefail
unset ANTHROPIC_API_KEY

if [[ "${S7_YIELD_OFF:-0}" == "1" ]]; then
    echo "s7-yield-run: disabled via S7_YIELD_OFF=1" >&2
    exit 0
fi

# Absolute PATH — never rely on a resolved-after-the-fact interpreter (W108: an
# alerting path that shares the failure mode of the thing it reports on is worse
# than no alert).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="${HOME:-/Users/nuzantara}"

REPO_ROOT="${S7_YIELD_REPO_ROOT:-$HOME/nuzantara}"
SCRIPT="$REPO_ROOT/scripts/s7_yield_draft_local.py"
LIMIT="${S7_YIELD_LIMIT:-10}"

PY="/opt/homebrew/bin/python3"
[[ -x "$PY" ]] || PY="/usr/bin/python3"

if [[ ! -f "$SCRIPT" ]]; then
    echo "s7-yield-run: FATAL — $SCRIPT not found" >&2
    exit 1
fi

exec "$PY" "$SCRIPT" --all --limit "$LIMIT"
