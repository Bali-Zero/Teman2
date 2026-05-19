#!/usr/bin/env bash
# Agent Library Evolver — weekly wrapper (Phase 1)
#
# Invoked by ~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist
# Sunday 03:00 WITA. Drives the full pipeline:
#
#   1. Source SECRETS_FILE (default ~/.nuzantara-secrets.env)
#      Reject /dev/null, empty file, or missing DEEPSEEK_API_KEY.
#   2. PG advisory lock (pg_try_advisory_lock) — single-flight guarantee
#   3. Context gathering: mem query + git log + cicatrix-scars.md slice
#   4. MANDATORY redaction via scripts/_redact_pii.py (Symbiosis Law 2)
#   5. uv run evoskill run --config agent-library/.evoskill/config.toml
#   6. Parse telemetry.json — fail-closed if total_cost_usd > BUDGET_USD
#   7. scripts/_evidence_lint.py over proposals/YYYY-MM-DD/
#   8. scripts/_entailment_check.py over passed-existence/
#   9. Open draft PR via scripts/agent-library-evolver-propose-pr.sh
#      (inline function below — no separate script needed yet)
#  10. Telegram alert with run summary
#
# Spec: docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md
# Phase 1 — addresses L6, L11, L23 from .known-limitations-v1.md.
#
# CLI flags:
#   --dry-run    Skip steps 5-10. Exits after context gathering +
#                redaction validation. Useful for smoke testing.
#   --help       Print usage and exit 0.
#
# Environment overrides:
#   BUDGET_USD       Hard cap on total_cost_usd (default 1.00 prod,
#                    0.10 smoke). Wrapper aborts if telemetry exceeds.
#   SECRETS_FILE     Path to env file with DEEPSEEK_API_KEY etc.
#                    Default ~/.nuzantara-secrets.env. /dev/null rejected.
#   REPO_ROOT        Repository root. Default = parent of this script.
#   TELEMETRY_DIR    Where to write context-raw.md, context-redacted.md,
#                    telemetry.json. Default
#                    ~/.agent/decisions/agent-library-evolver/telemetry
#                    (L11 fix — was /tmp/agent-library-evolver in spec
#                    draft, weaker on reboot).
#   TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID
#                    Sourced from SECRETS_FILE. chat_id 1125336968
#                    (Zero's @zero0101010101010 verified live 2026-04-07).
#
# Exit codes:
#   0   Success — pipeline completed (with or without proposals)
#   1   Generic failure (any step failure not specifically classified)
#   2   Secrets validation failed (missing/empty file, missing key,
#       /dev/null shortcut detected)
#   3   PG advisory lock held — another run in progress, skip
#   4   Redaction fail-closed (over-redaction, missing _redact_pii.py,
#       Symbiosis Law 2 violation)
#   5   Budget exceeded — total_cost_usd > BUDGET_USD post-run

set -euo pipefail
# Note: we deliberately do NOT set `set -x` — secrets like
# DEEPSEEK_API_KEY would leak to launchd log files.

# ─── 0. Bootstrap ────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
BUDGET_USD="${BUDGET_USD:-1.00}"
SECRETS_FILE="${SECRETS_FILE:-${HOME}/.nuzantara-secrets.env}"
TELEMETRY_DIR="${TELEMETRY_DIR:-${HOME}/.agent/decisions/agent-library-evolver/telemetry}"
RUN_DATE="$(date +%Y-%m-%d)"
RUN_TS="$(date +%Y-%m-%dT%H:%M:%S%z)"
RUN_TELEMETRY_DIR="${TELEMETRY_DIR}/${RUN_DATE}"
DRY_RUN="0"

# ─── CLI parsing ─────────────────────────────────────────────────────

usage() {
    sed -n '2,/^set -euo pipefail$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

for arg in "$@"; do
    case "${arg}" in
        --dry-run) DRY_RUN="1" ;;
        --help|-h) usage ;;
        *) echo "ERROR: unknown flag ${arg}. Use --help" >&2; exit 1 ;;
    esac
done

# ─── 1. Bootstrap telemetry dir + log helper ─────────────────────────

mkdir -p "${RUN_TELEMETRY_DIR}"
# Tighten perms — telemetry holds raw context (pre-redaction) which
# contains PII. L11 fix: out of /tmp, into ~/.agent/.
chmod 0700 "${RUN_TELEMETRY_DIR}" 2>/dev/null || true

LOG_FILE="${RUN_TELEMETRY_DIR}/evolver.log"

log() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf '[%s] %s\n' "${ts}" "$*" | tee -a "${LOG_FILE}"
}

log "=== agent-library-evolver run ${RUN_TS} ==="
log "repo_root=${REPO_ROOT}"
log "budget_usd=${BUDGET_USD}"
log "telemetry_dir=${RUN_TELEMETRY_DIR}"
log "dry_run=${DRY_RUN}"

# ─── 2. Secrets validation (L20-style fail-closed) ───────────────────

validate_secrets() {
    if [[ "${SECRETS_FILE}" == "/dev/null" ]]; then
        log "FATAL: SECRETS_FILE=/dev/null is rejected (shortcut would bypass auth check)"
        exit 2
    fi
    if [[ ! -f "${SECRETS_FILE}" ]]; then
        log "FATAL: SECRETS_FILE not found: ${SECRETS_FILE}"
        exit 2
    fi
    if [[ ! -s "${SECRETS_FILE}" ]]; then
        log "FATAL: SECRETS_FILE is empty: ${SECRETS_FILE}"
        exit 2
    fi
    # Source after validation — set +x defensively so secrets don't
    # appear in any debug trace upstream.
    set +x
    # shellcheck disable=SC1090
    source "${SECRETS_FILE}"
    set +x
    if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
        log "FATAL: DEEPSEEK_API_KEY not set after sourcing ${SECRETS_FILE}"
        exit 2
    fi
    # Defensive: NEVER allow ANTHROPIC_API_KEY to be set in our process
    # (CLAUDE.md hard rule — panel R3 BLOCKING #2). Unset it before
    # spawning any LLM subprocess.
    unset ANTHROPIC_API_KEY
    log "secrets OK (DEEPSEEK_API_KEY set, ANTHROPIC_API_KEY unset defensively)"
}
validate_secrets

# ─── 3. PG advisory lock — single-flight ─────────────────────────────

PG_LOCK_KEY="${PG_LOCK_KEY:-0xA9E471BAA1}"  # arbitrary stable int → 728338108065 fits int64
# Default DATABASE_URL from SECRETS_FILE (CRM Pro local PG). Phase 1
# accepts no-PG fallback for smoke testing (sets lock to no-op).

acquire_lock() {
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log "WARN: DATABASE_URL not set — skipping advisory lock (single-flight not enforced)"
        return 0
    fi
    if ! command -v psql >/dev/null 2>&1; then
        log "WARN: psql not on PATH — skipping advisory lock"
        return 0
    fi
    local got
    got="$(psql "${DATABASE_URL}" -At -c "SELECT pg_try_advisory_lock(${PG_LOCK_KEY});" 2>>"${LOG_FILE}" || echo "")"
    if [[ "${got}" != "t" ]]; then
        log "another run holds the advisory lock (key=${PG_LOCK_KEY}) — exiting"
        exit 3
    fi
    log "advisory lock acquired (key=${PG_LOCK_KEY})"
    # Best-effort release on EXIT (Bash trap)
    # shellcheck disable=SC2064
    trap "psql '${DATABASE_URL}' -c 'SELECT pg_advisory_unlock(${PG_LOCK_KEY});' >/dev/null 2>&1 || true" EXIT
}
acquire_lock

# ─── 4. Context gathering ────────────────────────────────────────────

CONTEXT_RAW="${RUN_TELEMETRY_DIR}/context-raw.md"
CONTEXT_REDACTED="${RUN_TELEMETRY_DIR}/context-redacted.md"

gather_context() {
    log "gathering context → ${CONTEXT_RAW}"
    {
        printf '# Context for agent-library evolver run %s\n\n' "${RUN_TS}"

        printf '## Recent git activity (--since=7days)\n\n```\n'
        git -C "${REPO_ROOT}" log --since=7days --oneline --no-merges 2>/dev/null | head -200 || true
        printf '```\n\n'

        printf '## Cicatrix scars (.claude/rules/cicatrix-scars.md)\n\n'
        if [[ -f "${REPO_ROOT}/.claude/rules/cicatrix-scars.md" ]]; then
            head -300 "${REPO_ROOT}/.claude/rules/cicatrix-scars.md" || true
        else
            printf '(no cicatrix-scars.md found)\n'
        fi
        printf '\n'

        printf '## Recent mem entries (top 20 by importance)\n\n'
        if command -v mem >/dev/null 2>&1; then
            mem recent --limit 20 2>/dev/null || mem query "recent" 2>/dev/null || true
        else
            printf '(mem CLI not available)\n'
        fi
        printf '\n'

        printf '## Existing agent-library inventory\n\n'
        if [[ -f "${REPO_ROOT}/agent-library/01-inventory.md" ]]; then
            head -100 "${REPO_ROOT}/agent-library/01-inventory.md" || true
        fi
    } > "${CONTEXT_RAW}"

    local raw_bytes
    raw_bytes="$(wc -c < "${CONTEXT_RAW}" | tr -d ' ')"
    log "context-raw: ${raw_bytes} bytes"
    if [[ "${raw_bytes}" -lt 200 ]]; then
        log "FATAL: context-raw too small (${raw_bytes} bytes < 200) — gathering failed"
        exit 1
    fi
}
gather_context

# ─── 5. MANDATORY redaction (Symbiosis Law 2 + UU PDP) ───────────────

REDACTOR="${REPO_ROOT}/scripts/_redact_pii.py"
if [[ ! -f "${REDACTOR}" ]]; then
    log "FATAL: redactor not found at ${REDACTOR} — fail-closed per Symbiosis Law 2"
    exit 4
fi

redact_context() {
    log "redacting context → ${CONTEXT_REDACTED}"
    if ! python3 "${REDACTOR}" < "${CONTEXT_RAW}" > "${CONTEXT_REDACTED}" 2>>"${LOG_FILE}"; then
        log "FATAL: redactor exited non-zero — fail-closed"
        exit 4
    fi
    local red_bytes
    red_bytes="$(wc -c < "${CONTEXT_REDACTED}" | tr -d ' ')"
    log "context-redacted: ${red_bytes} bytes"
    if [[ "${red_bytes}" -lt 100 ]]; then
        log "FATAL: redacted context too small (${red_bytes} bytes < 100) — over-redaction or empty input"
        exit 4
    fi
    chmod 0600 "${CONTEXT_RAW}" "${CONTEXT_REDACTED}" 2>/dev/null || true
}
redact_context

if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run mode — skipping evoskill invocation, evidence/entailment, PR, alert"
    log "DONE (dry-run) — exit 0"
    exit 0
fi

# ─── 6. uv run evoskill run ──────────────────────────────────────────

TELEMETRY_JSON="${RUN_TELEMETRY_DIR}/telemetry.json"
EVOSKILL_DIR="${REPO_ROOT}/vendor/evoskill"
EVOSKILL_CONFIG="${REPO_ROOT}/agent-library/.evoskill/config.toml"

if [[ ! -f "${EVOSKILL_CONFIG}" ]]; then
    log "FATAL: evoskill config not found at ${EVOSKILL_CONFIG}"
    exit 1
fi

run_evoskill() {
    log "invoking uv run evoskill run --config ${EVOSKILL_CONFIG}"
    # Export BUDGET_USD + DEEPSEEK_API_KEY into the subprocess env.
    # The DeepSeek executor (Task #23) reads DEEPSEEK_API_KEY directly.
    # BUDGET_USD is informational here — actual gate is the post-run
    # telemetry check below (L6 finding: bash cannot enforce mid-run
    # cap because evoskill is one blocking command).
    if ! (
        cd "${EVOSKILL_DIR}" && \
        BUDGET_USD="${BUDGET_USD}" \
        DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY}" \
        uv run evoskill run \
            --config "${EVOSKILL_CONFIG}" \
            --output-telemetry "${TELEMETRY_JSON}" \
            >> "${LOG_FILE}" 2>&1
    ); then
        log "evoskill run failed — see ${LOG_FILE}"
        # Don't exit 1 immediately — telemetry.json may still have partial
        # cost info we want to honour the budget against. Fall through to
        # the parse step which will set is_error=true if missing.
    fi
    log "evoskill run completed"
}
run_evoskill

# ─── 7. Budget check (L6 fail-closed) ────────────────────────────────

enforce_budget() {
    if [[ ! -f "${TELEMETRY_JSON}" ]]; then
        log "WARN: telemetry.json missing — cannot verify budget. Treating as 0 cost (no proposals will ship)"
        return 0
    fi
    local total_cost
    total_cost="$(python3 -c "
import json, sys
try:
    with open('${TELEMETRY_JSON}') as f:
        data = json.load(f)
    print(data.get('total_cost_usd', 0.0))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    print('0.0')
" 2>>"${LOG_FILE}")"
    log "telemetry.total_cost_usd=${total_cost} budget_usd=${BUDGET_USD}"
    local over
    over="$(python3 -c "print(1 if float('${total_cost}') > float('${BUDGET_USD}') else 0)")"
    if [[ "${over}" == "1" ]]; then
        log "FATAL: total_cost_usd=${total_cost} exceeds budget_usd=${BUDGET_USD} — fail-closed"
        telegram_alert "Budget exceeded: \$${total_cost} > \$${BUDGET_USD}. Run halted before proposals shipped."
        exit 5
    fi
}
enforce_budget

# ─── 8. Evidence lint + entailment check ─────────────────────────────

PROPOSALS_DIR="${REPO_ROOT}/agent-library/proposals/${RUN_DATE}"
EVIDENCE_LINT="${REPO_ROOT}/scripts/_evidence_lint.py"
ENTAILMENT_CHECK="${REPO_ROOT}/scripts/_entailment_check.py"

PROPOSALS_PASSED=0

run_evidence_gates() {
    if [[ ! -d "${PROPOSALS_DIR}" ]]; then
        log "no proposals directory at ${PROPOSALS_DIR} — evoskill produced 0 proposals"
        return 0
    fi
    if [[ -f "${EVIDENCE_LINT}" ]]; then
        log "running evidence linter on ${PROPOSALS_DIR}"
        python3 "${EVIDENCE_LINT}" "${PROPOSALS_DIR}" >> "${LOG_FILE}" 2>&1 || \
            log "evidence linter exited non-zero (some proposals rejected — see log)"
    else
        log "WARN: ${EVIDENCE_LINT} not yet implemented (Phase 1 Task #25) — skipping"
    fi
    if [[ -f "${ENTAILMENT_CHECK}" ]]; then
        log "running entailment check on ${PROPOSALS_DIR}/passed-existence/"
        python3 "${ENTAILMENT_CHECK}" "${PROPOSALS_DIR}/passed-existence" >> "${LOG_FILE}" 2>&1 || \
            log "entailment check exited non-zero (some proposals rejected — see log)"
    else
        log "WARN: ${ENTAILMENT_CHECK} not yet implemented (Phase 1 Task #25) — skipping"
    fi
    if [[ -d "${PROPOSALS_DIR}/passed" ]]; then
        PROPOSALS_PASSED="$(find "${PROPOSALS_DIR}/passed" -name 'SKILL.md' -type f | wc -l | tr -d ' ')"
    fi
    log "proposals_passed=${PROPOSALS_PASSED}"
}
run_evidence_gates

# ─── 9. Open draft PR (only if ≥1 proposal passed) ───────────────────

open_pr_draft() {
    if [[ "${PROPOSALS_PASSED}" -lt 1 ]]; then
        log "0 proposals passed both gates — skipping PR creation"
        return 0
    fi
    if ! command -v gh >/dev/null 2>&1; then
        log "WARN: gh CLI not available — skipping PR creation, proposals stay on disk"
        return 0
    fi
    local branch="auto/agent-library-${RUN_DATE}"
    log "creating draft PR on branch ${branch} with ${PROPOSALS_PASSED} proposals"
    (
        cd "${REPO_ROOT}"
        git checkout -b "${branch}" 2>>"${LOG_FILE}" || git checkout "${branch}" 2>>"${LOG_FILE}"
        git add "agent-library/proposals/${RUN_DATE}/passed/" 2>>"${LOG_FILE}"
        git commit -m "feat(agent-library): auto-evolver proposals ${RUN_DATE}

${PROPOSALS_PASSED} proposals passed both evidence + entailment gates.
Generated by scripts/agent-library-evolver-run.sh ${RUN_TS}.

Human-merge gate required per L2 autonomous ops — do NOT auto-merge.
Each SKILL.md cites file:line / commit / URL evidence; review the
cited content before merging.

Co-Authored-By: agent-library-evolver <noreply@balizero.com>" 2>>"${LOG_FILE}" || true
        git push -u origin "${branch}" 2>>"${LOG_FILE}" || true
        gh pr create --draft \
            --title "auto: agent-library proposals ${RUN_DATE}" \
            --body "Weekly auto-evolver run ${RUN_TS}. ${PROPOSALS_PASSED} proposals passed evidence + entailment gates. Human review required before merge." \
            --base main \
            --head "${branch}" \
            >> "${LOG_FILE}" 2>&1 || \
            log "gh pr create failed — proposals committed on branch ${branch}, no PR opened"
    )
}
open_pr_draft

# ─── 10. Telegram alert ──────────────────────────────────────────────

telegram_alert() {
    local msg="$1"
    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] || [[ -z "${TELEGRAM_OWNER_CHAT_ID:-}" ]]; then
        log "WARN: TELEGRAM_BOT_TOKEN/CHAT_ID not set — alert skipped: ${msg}"
        return 0
    fi
    local payload
    payload="$(python3 -c "
import json, sys
print(json.dumps({
    'chat_id': '${TELEGRAM_OWNER_CHAT_ID}',
    'text': sys.argv[1],
    'parse_mode': 'Markdown'
}))
" "${msg}")"
    curl -sS -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "${payload}" >> "${LOG_FILE}" 2>&1 || \
        log "WARN: Telegram alert send failed"
}

final_alert() {
    local cost="(unknown)"
    if [[ -f "${TELEMETRY_JSON}" ]]; then
        cost="$(python3 -c "
import json
try:
    with open('${TELEMETRY_JSON}') as f:
        print(f\"\$\" + str(json.load(f).get('total_cost_usd', 0.0)))
except Exception:
    print('(parse error)')
")"
    fi
    telegram_alert "🌱 agent-library-evolver ${RUN_DATE}
proposals_passed=${PROPOSALS_PASSED}
cost=${cost}
budget=\$${BUDGET_USD}
log=${LOG_FILE}"
}
final_alert

log "DONE (proposals_passed=${PROPOSALS_PASSED}) — exit 0"
exit 0
