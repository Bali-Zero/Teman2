#!/usr/bin/env bash
#
# scar-replay-run.sh — induce the Scar-Replay Antibody Harness.
#
# This is the operational entrypoint for the redesigned agent-library-evolver
# (design: 3-LLM council 2026-06-04, decision_evolver_scar_replay_harness_2026_06_04.md).
#
# Symbiosis compliance baked into the SHELL layer (not just the Python):
#   - Law 4 graceful degradation: DeepSeek down / no key => --offline replay only.
#   - Law 5 alert-only-when-human-needed: a clean run (even 0 antibodies) is
#     SILENT. We alert ONLY when a human decision is genuinely required
#     (a probe went stale = a previously-fixed failure class regressed, OR the
#     harness itself crashed). A successful antibody is logged, not alerted.
#   - Self-healing worktree isolation: we NEVER run git-ops in the shared deploy
#     worktree. The harness probes use ephemeral mktemp sandboxes; this wrapper
#     additionally refuses to even cd into the shared deploy path.
#
# Induce on demand (no waiting for cron):
#   bash scar-replay-run.sh                      # online, all probes
#   bash scar-replay-run.sh --family shared_worktree_git_ops
#   bash scar-replay-run.sh --offline            # degraded mode
#   bash scar-replay-run.sh --cleanup --apply    # reap evolver-owned scories
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
HARNESS_DIR="${SCAR_REPLAY_DIR:-${SCRIPT_DIR}}"
LOG_DIR="${HOME}/logs"
LOG_FILE="${LOG_DIR}/scar-replay.log"
TELEMETRY_DIR="${HOME}/.agent/decisions/agent-library-evolver/scar-replay"
SHARED_DEPLOY="${HOME}/nuzantara-deploy"
mkdir -p "${LOG_DIR}" "${TELEMETRY_DIR}"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "${LOG_FILE}"; }

# --- self-heal: never operate inside the protected shared deploy worktree ---
_here="$(pwd -P)"
case "${_here}/" in
  "${SHARED_DEPLOY}/"*)
    log "REFUSE: cwd is inside the protected deploy worktree (${SHARED_DEPLOY}); the"
    log "        harness must run isolated. cd elsewhere. Aborting (no git-ops here)."
    exit 0
    ;;
esac

# --- alert only when a human decision is genuinely required (Law 5) ---
telegram_alert() {
  local msg="$1"
  # Resolve token + chat id from the sanctioned vaults (tolerate the
  # OWNER vs APPROVAL chat-id naming drift that silences the old evolver).
  local tok="${TELEGRAM_BOT_TOKEN:-}"
  local chat="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_APPROVAL_CHAT_ID:-}}"
  if [[ -z "${tok}" || -z "${chat}" ]]; then
    for f in "${HOME}/.nuzantara-secrets.env" "${HOME}/.openclaw/workspace/.env.master"; do
      [[ -f "$f" ]] || continue
      [[ -z "${tok}"  ]] && tok="$(grep -m1 -E '^TELEGRAM_BOT_TOKEN=' "$f" 2>/dev/null | cut -d= -f2- | tr -d '"')"
      [[ -z "${chat}" ]] && chat="$(grep -m1 -E '^TELEGRAM_(OWNER|APPROVAL)_CHAT_ID=' "$f" 2>/dev/null | cut -d= -f2- | tr -d '"')"
    done
  fi
  if [[ -z "${tok}" || -z "${chat}" ]]; then
    log "WARN: telegram creds unresolved — human-alert suppressed: ${msg}"
    return 0
  fi
  curl -sS --max-time 20 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
    -d "chat_id=${chat}" -d "text=🧬 scar-replay: ${msg}" >/dev/null 2>&1 || true
}

# Pass through cleanup verbatim.
if [[ "${1:-}" == "--cleanup" ]]; then
  shift
  apply_flag=""
  [[ "${1:-}" == "--apply" ]] && apply_flag="--apply-cleanup"
  log "cleanup (apply=${apply_flag:-no})"
  PYTHONPATH="${HARNESS_DIR}" python3 "${HARNESS_DIR}/scar_replay.py" \
    --cleanup ${apply_flag} --telemetry-dir "${TELEMETRY_DIR}" | tee -a "${LOG_FILE}"
  exit 0
fi

RUN_DATE="$(date '+%Y-%m-%d-%H%M%S')"
OUT_JSON="${TELEMETRY_DIR}/run-${RUN_DATE}.json"

log "=== scar-replay run ${RUN_DATE} (harness=${HARNESS_DIR}) ==="

set +e
PYTHONPATH="${HARNESS_DIR}" python3 "${HARNESS_DIR}/scar_replay.py" "$@" \
  --telemetry-dir "${TELEMETRY_DIR}" > "${OUT_JSON}" 2>>"${LOG_FILE}"
rc=$?
set -e

if [[ ${rc} -ne 0 ]]; then
  log "FAIL: harness crashed (rc=${rc}). This needs a human."
  telegram_alert "harness crashed rc=${rc} on ${RUN_DATE} — see ${LOG_FILE}"
  exit ${rc}
fi

# Parse the JSON for the two human-relevant conditions.
antibodies="$(python3 -c "import json,sys;print(json.load(open('${OUT_JSON}')).get('effective_antibodies',0))" 2>/dev/null || echo 0)"
stale="$(python3 - "${OUT_JSON}" <<'PY' 2>/dev/null || echo 0
import json,sys
d=json.load(open(sys.argv[1]))
# A probe whose baseline NO LONGER fails = a previously-fixed class regressed
# OR the probe drifted. Either way a human should look. (NOT an antibody success.)
stale=sum(1 for r in d.get("results",[]) if isinstance(r,dict) and r.get("baseline_failed") is False)
print(stale)
PY
)"

log "result: effective_antibodies=${antibodies} stale_probes=${stale} json=${OUT_JSON}"

# Law 5: alert ONLY on the human-needed condition (a stale/regressed probe),
# never on a successful or zero-antibody clean run.
if [[ "${stale}" -gt 0 ]]; then
  log "ALERT-WORTHY: ${stale} probe(s) no longer reproduce — a fixed failure class"
  log "             may have regressed, or the probe needs hardening. Human review."
  telegram_alert "${stale} probe(s) went stale on ${RUN_DATE} — baseline no longer fails. Review ${OUT_JSON}"
fi

log "DONE (effective_antibodies=${antibodies}) — exit 0"
exit 0
