#!/bin/bash
# intake_review_reader_run.sh — LaunchAgent wrapper for the Pro-side intake-review reader.
#
# WHY a wrapper (W65 / P0-3 scar): secrets must NOT live in the plist (world-readable plist
# leaks are a recurring P0). This wrapper sources a 0600 env-file, then execs uvicorn. The
# plist only points at this script; no secret value ever touches git or the plist.
#
# Env-file (chmod 0600, owner nuzantara only) — create it on the Pro, NEVER commit it:
#   ~/.cell-bridge-state/intake-review-reader.env
# with keys:
#   JWT_SECRET_KEY=<the Fly JWT_SECRET_KEY secret — must match Fly for cookie/Bearer JWT>
#   API_KEYS=<any non-empty value; settings requires it, reader is JWT-only in practice>
#   INTAKE_REVIEW_DATABASE_URL=postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev
#   INTAKE_REVIEW_BRIDGE_SECRET=<shared X-Bridge-Auth secret, added by the Fly proxy>
# (INTAKE_WRITER_ENABLED defaults to 0 — dry-run. FASE 5C go-live: set
#  INTAKE_WRITER_ENABLED=1 in this env-file + kickstart the LaunchAgent.)
set -euo pipefail

REPO_ROOT="${INTAKE_REVIEW_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
BACKEND_DIR="${REPO_ROOT}/apps/backend-rag"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
ENV_FILE="${INTAKE_REVIEW_ENV_FILE:-${HOME}/.cell-bridge-state/intake-review-reader.env}"
HOST="127.0.0.1"
PORT="18795"

# Main-repo venv fallback target (BUG 5 / py3.14 deep-root, see heal block below).
# DERIVED from the repo-root var pattern, never a hardcoded user path: when this wrapper
# runs FROM a deploy worktree whose REPO_ROOT differs from the canonical main checkout,
# MAIN_REPO_ROOT names the main checkout so a from-scratch deploy-venv install that is
# UNRESOLVABLE (py3.14 google-cloud matrix) can fall back to the known-good main venv.
# Overridable for tests; defaults to the canonical main checkout used by INTAKE_REVIEW_REPO_ROOT.
MAIN_REPO_ROOT="${INTAKE_REVIEW_MAIN_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
MAIN_VENV_PY="${MAIN_REPO_ROOT}/apps/backend-rag/.venv/bin/python"

# Heal coordination (BUG 2 — KeepAlive restart-storm guard, superscar #7).
HEAL_LOCK="${BACKEND_DIR}/.venv-heal.lock"
# Telegram alert rate-limit marker (BUG 4 — once-per-failure-window, anti-spam).
HEAL_ALERT_MARK="${BACKEND_DIR}/.venv-heal.alerted"
HEAL_ALERT_COOLDOWN_S="${HEAL_ALERT_COOLDOWN_S:-1800}"  # 30min between heal-failure pages
FALLBACK_NOTICE_MARK="${BACKEND_DIR}/.venv-heal.fellback"  # one-shot fallback notice

# --- Telegram helper (canonical pattern, identical to intake_review_reader_liveness.sh /
# supervisor_liveness_watchdog.sh). Reads the token from the 0600 secrets file — NEVER
# hardcodes it. No-ops cleanly if the token is unavailable so the heal never crashes on it. ---
send_telegram() {
  local msg="$1"
  if [[ -f "${HOME}/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${HOME}/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local TOKEN="${TELEGRAM_BOT_TOKEN:-${CELL_TELEGRAM_BOT_TOKEN:-}}"
  local CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-1125336968}}"
  if [[ -z "${TOKEN}" || -z "${CHAT_ID}" ]]; then
    echo "[intake-review-reader] telegram: skipped (no token/chat_id)" >&2
    return 0
  fi
  curl -fsS --max-time 5 -X POST \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    >/dev/null 2>&1 || echo "[intake-review-reader] telegram: send failed" >&2
}

# Send a heal-failure page AT MOST once per HEAL_ALERT_COOLDOWN_S window. KeepAlive would
# otherwise re-enter the heal every ThrottleInterval (10s) and spam the same page forever.
alert_heal_failed_once() {
  local detail="$1"
  local now last
  now="$(date +%s)"
  last=0
  if [[ -f "${HEAL_ALERT_MARK}" ]]; then
    last="$(cat "${HEAL_ALERT_MARK}" 2>/dev/null || echo 0)"
    [[ "${last}" =~ ^[0-9]+$ ]] || last=0
  fi
  if (( now - last < HEAL_ALERT_COOLDOWN_S )); then
    echo "[intake-review-reader] heal-alert suppressed (cooldown ${HEAL_ALERT_COOLDOWN_S}s)" >&2
    return 0
  fi
  echo "${now}" > "${HEAL_ALERT_MARK}" 2>/dev/null || true
  send_telegram "🚨 intake-review reader heal FAILED: ${detail} — venv on $(hostname -s) can't install deps. kita.balizero.com/review at risk. Check: tail ~/logs/intake-review-reader.log"
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[intake-review-reader] FATAL: env-file not found: ${ENV_FILE}" >&2
  echo "[intake-review-reader] create it 0600 with JWT_SECRET_KEY/API_KEYS/INTAKE_REVIEW_DATABASE_URL/INTAKE_REVIEW_BRIDGE_SECRET" >&2
  exit 78  # EX_CONFIG
fi

# Refuse a world-readable env-file (defence against the recurring plist-secret-644 class).
PERMS="$(stat -f '%Lp' "${ENV_FILE}" 2>/dev/null || echo '???')"
if [[ "${PERMS}" != "600" && "${PERMS}" != "400" ]]; then
  echo "[intake-review-reader] FATAL: ${ENV_FILE} is mode ${PERMS}, expected 600/400. chmod 600 it." >&2
  exit 78
fi

# Source the secrets, exporting every assignment.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# Writer flag: SAFE-OFF unless the operator explicitly enables it in the
# 0600 env-file (FASE 5C go-live = add INTAKE_WRITER_ENABLED=1 there + restart;
# no code change). Anything other than an explicit truthy value stays dry-run.
export INTAKE_WRITER_ENABLED="${INTAKE_WRITER_ENABLED:-0}"
if [[ "${INTAKE_WRITER_ENABLED}" == "1" ]]; then
  echo "[intake-review-reader] WARNING: INTAKE_WRITER_ENABLED=1 — approvals COMMIT to the local CRM (FASE 5C live)" >&2
fi

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}"

# Exec uvicorn from a given venv python (used both on the happy path and on fallback).
exec_uvicorn_from() {
  local py="$1"
  exec "${py}" -m uvicorn backend.app.intake_review_reader:app \
    --host "${HOST}" --port "${PORT}" --no-access-log
}

# ---------------------------------------------------------------------------------------
# Venv auto-heal — RESILIENT (5-bug chain, 2026-06-20). Scar #1546 follow-up / superscar
# #1 (HOME-fork deploy-worktree evaporation) + #2 (silent heal failure) + #7 (KeepAlive
# restart-storm). When the Pro rebooted (2026-06-19), the deploy-worktree .venv evaporated
# and the #1546 auto-heal hit a CHAIN of failures:
#   BUG 1 — requirements asked presidio>=2.2.362 (max on PyPI is 2.2.359) → impossible.
#   BUG 2 — the ~5min `pip install` ran under KeepAlive=true; launchd restarted the wrapper
#           every ThrottleInterval and KILLED the in-flight install, relaunching it →
#           observed runs=40 with the install never completing (superscar #7).
#   BUG 3 — the freshly-created deploy venv shipped pip 26.0, whose resolver dies with
#           `resolution-too-deep` on this requirements graph; the working main venv has
#           pip 26.1.1+.
#   BUG 4 — every failure was silent (log + exit 75, loop forever, no operator page).
#   BUG 5 — DEEP ROOT (NOT fixed here, see research/operations/2026-06-20-intake-reader-5bug-heal-chain.md):
#           on the deploy venv's Python 3.14, `pip install -r requirements.txt` is
#           `ResolutionImpossible` — requirements asks google-cloud-storage>=2.10.0 but
#           google-cloud-aiplatform>=1.151.0 requires google-cloud-storage>=3.10.0 on
#           py>=3.13, plus missing wheels. The main venv works only because it was built
#           (py3.11) before these constraints tightened. Resolving the google-cloud matrix
#           is risky (touches the RAG/Vertex stack) and out of scope for a wrapper fix.
#
# THE CURES (this wrapper):
#   #2 → a pid-file HEAL LOCK: only ONE heal runs at a time. A KeepAlive restart during a
#        live heal exits 0 cleanly and lets the in-flight install finish; the next cycle
#        finds deps present and execs uvicorn. (No flock on stock macOS → pid-file lock,
#        robust to a stale lock: a dead pid is reclaimed.)
#   #3 → upgrade pip itself to a resolver that works BEFORE the requirements install.
#   #4 → on heal-install failure, Telegram-page the operator (rate-limited, once/window).
#   #5 → if the deploy venv is UNRESOLVABLE, FALL BACK to the known-good main-repo venv
#        (if it can import uvicorn) and exec from there + notify once. The reader self-heals
#        to the working venv instead of looping. (The live plist was repointed to the main
#        checkout as the durable path; this fallback is the in-wrapper safety net.)
#
# CRITICAL: cwd MUST be BACKEND_DIR for the pip install — requirements.txt has
# `-e ../../packages/cell-core`, a path-relative editable that only resolves from
# apps/backend-rag/. We are already cd'd here.
# Idempotent + cheap on the happy path: the import probe short-circuits when deps exist,
# so a healthy boot adds one ~0.1s python invocation and never touches the lock or pip.
# ---------------------------------------------------------------------------------------

# Happy path: venv python present AND uvicorn importable → exec immediately, no lock/heal.
if [[ -x "${VENV_PY}" ]] && "${VENV_PY}" -c 'import uvicorn' 2>/dev/null; then
  exec_uvicorn_from "${VENV_PY}"
fi

# --- BUG 2: heal lock (pid-file, stale-safe) so KeepAlive can't storm the install ---
if [[ -f "${HEAL_LOCK}" ]]; then
  LOCK_PID="$(cat "${HEAL_LOCK}" 2>/dev/null || echo '')"
  if [[ "${LOCK_PID}" =~ ^[0-9]+$ ]] && kill -0 "${LOCK_PID}" 2>/dev/null; then
    echo "[intake-review-reader] a heal is already in progress (pid ${LOCK_PID}) — exit 0, let it finish (BUG 2 / superscar #7)" >&2
    exit 0
  fi
  echo "[intake-review-reader] reclaiming stale heal lock (pid '${LOCK_PID}' dead)" >&2
  rm -f "${HEAL_LOCK}" 2>/dev/null || true
fi
echo "$$" > "${HEAL_LOCK}" 2>/dev/null || true
# Release the lock on ANY exit of this heal attempt (success execs away before trap fires).
trap 'rm -f "${HEAL_LOCK}" 2>/dev/null || true' EXIT

# 1. venv shell gone -> recreate it.
if [[ ! -x "${VENV_PY}" ]]; then
  echo "[intake-review-reader] WARN: venv python missing at ${VENV_PY} — recreating (scar #1546)" >&2
  if ! python3 -m venv "${BACKEND_DIR}/.venv" >&2; then
    echo "[intake-review-reader] FATAL: venv shell creation failed" >&2
    alert_heal_failed_once "venv shell creation failed (python3 -m venv)"
    exit 75  # EX_OSERR
  fi
fi

# 2. deps unimportable -> heal: upgrade pip (BUG 3), then install requirements.
if ! "${VENV_PY}" -c 'import uvicorn' 2>/dev/null; then
  echo "[intake-review-reader] WARN: uvicorn unimportable — healing (pip-upgrade + install, cwd=${BACKEND_DIR}; scar #1546)" >&2

  # BUG 3: a stale resolver (pip 26.0 on a fresh venv) dies with resolution-too-deep on
  # this graph. Upgrade pip to a working resolver first. Cheap + idempotent.
  if ! "${VENV_PY}" -m pip install --upgrade 'pip>=26.1.2' >&2; then
    echo "[intake-review-reader] WARN: pip self-upgrade failed — continuing with existing pip" >&2
  fi

  # The heal install. Its stderr is captured so a failure can be paged + summarized (BUG 4).
  HEAL_ERR_LOG="${BACKEND_DIR}/.venv-heal.lasterr"
  if ! "${VENV_PY}" -m pip install -r requirements.txt 2> >(tee "${HEAL_ERR_LOG}" >&2); then
    LAST_ERR="$(grep -E 'ERROR|Could not|ResolutionImpossible|No matching distribution|resolution-too-deep' "${HEAL_ERR_LOG}" 2>/dev/null | tail -1)"
    [[ -z "${LAST_ERR}" ]] && LAST_ERR="pip install -r requirements.txt failed (see ${HEAL_ERR_LOG})"
    echo "[intake-review-reader] heal pip install FAILED: ${LAST_ERR}" >&2

    # BUG 5: the deploy venv may be UNRESOLVABLE (py3.14 google-cloud matrix). If the
    # known-good main-repo venv can import uvicorn, fall back to it instead of looping.
    if [[ "${MAIN_VENV_PY}" != "${VENV_PY}" && -x "${MAIN_VENV_PY}" ]] \
        && "${MAIN_VENV_PY}" -c 'import uvicorn' 2>/dev/null; then
      echo "[intake-review-reader] FALLBACK: deploy venv unresolvable — exec uvicorn from main venv ${MAIN_VENV_PY}" >&2
      if [[ ! -f "${FALLBACK_NOTICE_MARK}" ]]; then
        send_telegram "ℹ️ intake-review reader fell back to MAIN venv on $(hostname -s) — deploy venv unresolvable on py3.14 (google-cloud matrix). Reader stays UP. See research/operations/2026-06-20-intake-reader-5bug-heal-chain.md"
        echo "$(date +%s)" > "${FALLBACK_NOTICE_MARK}" 2>/dev/null || true
      fi
      rm -f "${HEAL_LOCK}" 2>/dev/null || true
      trap - EXIT
      cd "${MAIN_REPO_ROOT}/apps/backend-rag"
      export PYTHONPATH="${MAIN_REPO_ROOT}/apps/backend-rag"
      exec_uvicorn_from "${MAIN_VENV_PY}"
    fi

    # No fallback available — page the operator (rate-limited) and exit; KeepAlive retries.
    alert_heal_failed_once "${LAST_ERR}"
    echo "[intake-review-reader] FATAL: dependency install failed and no healthy main venv to fall back to" >&2
    exit 75  # EX_OSERR
  fi
fi

# Heal succeeded (deps now importable). Clear the fallback notice so a later genuine
# fallback re-notifies, and exec from the freshly-healed venv.
rm -f "${FALLBACK_NOTICE_MARK}" "${HEAL_ALERT_MARK}" 2>/dev/null || true
exec_uvicorn_from "${VENV_PY}"
