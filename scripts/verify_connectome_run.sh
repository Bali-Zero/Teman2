#!/bin/bash
# verify_connectome_run.sh — cron wrapper for scripts/verify_connectome.py
#
# Runs the connectome drift-verifier against docs/connectome/edges/*.yaml,
# writes an alive-signal state JSON (deadman-family convention), and sends
# ONE Telegram alert when any edge REGRESSED (declared healthy, probe fails).
#
# Runtime homes (REPO_ROOT, overridable via env):
#   Pro : ~/nuzantara-deploy   (hourly-synced to origin/main — W71 rule)
#   M5  : ~/nuzantara          (main checkout; NEVER mutated here)
#
# Exit codes: 0 = no REGRESSED · 1 = REGRESSED (alert sent) · 2 = setup error.
# /bin/bash 3.2-compatible (macOS): no declare -A, no mapfile.
set -uo pipefail

LOG_PREFIX="[verify-connectome]"
STATE_DIR="$HOME/.agent/decisions/state"
STATE_FILE="$STATE_DIR/verify_connectome.json"
mkdir -p "$STATE_DIR"

# ── resolve repo root per machine ────────────────────────────────────────────
if [[ -z "${REPO_ROOT:-}" ]]; then
    if [[ "$(whoami)" == "balizero" ]]; then
        REPO_ROOT="$HOME/nuzantara"
    else
        REPO_ROOT="$HOME/nuzantara-deploy"
    fi
fi
if [[ ! -d "$REPO_ROOT/docs/connectome/edges" ]]; then
    echo "$LOG_PREFIX ERROR: edges dir missing under $REPO_ROOT (wrong branch or stale checkout?)" >&2
    exit 2
fi

# Read-only staleness note — never pull/checkout from a cron (scar:
# evolver/deploy-puller shared-worktree family).
BRANCH="$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo '?')"
if [[ "$BRANCH" != "main" && "$BRANCH" != "deploy/main" ]]; then
    echo "$LOG_PREFIX WARN: $REPO_ROOT on branch '$BRANCH' (not main) — verifier may be stale" >&2
fi

# Being ON main says nothing about being CURRENT with it, and that gap is not
# hypothetical: on 2026-07-29 the M5 checkout sat 248 commits behind while the
# census fix that cleared 5 false REGRESSED was already merged — so this cron
# would have kept reporting cured edges as regressions, with no line anywhere
# saying the map was old. The branch check above could never catch it: the
# branch was main the whole time. Read the DISTANCE, not the name.
#
# Report-only by construction. It never fetches (a cron that reaches the network
# to decide its own freshness is a new failure mode) and never pulls (the scar
# above). So the count is measured against the last-known origin/main in the
# local object store, which is itself a lower bound — say so rather than imply
# precision the measurement does not have.
BEHIND=""
if [[ "$BRANCH" == "main" || "$BRANCH" == "deploy/main" ]]; then
    BEHIND="$(git -C "$REPO_ROOT" rev-list --count HEAD..origin/main 2>/dev/null || echo "")"
fi
if [[ -z "$BEHIND" ]]; then
    # No origin/main ref locally, or git failed. CANNOT-VERIFY is not CLEAN:
    # never let "I could not check" read as "nothing to report" (W106b).
    echo "$LOG_PREFIX WARN: could not measure checkout distance from origin/main — verdicts below are of UNKNOWN freshness" >&2
elif (( BEHIND > 0 )); then
    echo "$LOG_PREFIX WARN: $REPO_ROOT is >= $BEHIND commits behind origin/main — every verdict below is judged against THAT vintage of the census, not today's. Do NOT pull here (sibling-race): refresh the checkout from an interactive session on this machine." >&2
fi

# ── python: backend venv first (PyYAML guaranteed), else system if yaml works ─
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python3"
if [[ ! -x "$PYBIN" ]]; then
    if python3 -c "import yaml" >/dev/null 2>&1; then
        PYBIN="python3"
    else
        echo "$LOG_PREFIX ERROR: no venv at $PYBIN and system python3 lacks PyYAML" >&2
        exit 2
    fi
fi

# ── run the verifier ─────────────────────────────────────────────────────────
cd "$REPO_ROOT" || exit 2
OUT="$("$PYBIN" scripts/verify_connectome.py --json "$STATE_FILE" 2>&1)"
RC=$?
echo "$OUT"

if [[ $RC -eq 2 ]]; then
    echo "$LOG_PREFIX ERROR: verifier setup failure (exit 2)" >&2
    exit 2
fi

# ── Telegram alert on REGRESSED (deadman convention — never hardcode token) ──
if [[ $RC -eq 1 ]]; then
    if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
        # shellcheck disable=SC1091
        source "$HOME/.nuzantara-secrets.env"
    fi
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
    TELEGRAM_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}}"
    REGRESSED_LINES="$(printf '%s\n' "$OUT" | grep -a 'REGRESSED ' | head -10)"
    if [[ -n "$TELEGRAM_BOT_TOKEN" && -n "$TELEGRAM_CHAT_ID" ]]; then
        MSG="connectome REGRESSED on $(hostname -s) $(date '+%Y-%m-%d %H:%M')
${REGRESSED_LINES}
state: ~/.agent/decisions/state/verify_connectome.json"
        curl -sS -m 15 -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${MSG}" >/dev/null \
            || echo "$LOG_PREFIX WARN: telegram send failed" >&2
    else
        echo "$LOG_PREFIX WARN: REGRESSED but no TELEGRAM_BOT_TOKEN — log-only" >&2
    fi
fi

exit $RC
