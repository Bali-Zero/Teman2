#!/usr/bin/env bash
#
# sota_smoke_fase1.sh — end-to-end dry-run of Fase 1 Loop 90gg scaffolding.
#
# Validates without touching DB/launchd:
#   - Task 23: M13FeedbackLoop unit tests
#   - Task 24: m13_collect_post_metrics.py AST + plist lint
#   - Task 25: m13_weekly_report.py AST + plist lint
#   - Task 26: m13_monthly_retrain.py AST + plist lint
#   - Task 27: m13_checkpoint.py AST + plist lint
#   - Task 28: EditorialConfig unit tests (if present)
#   - Task 29: ToneCouncil persona_slug unit tests
#   - Task 30: research_control router unit tests + manifest import
#   - Task 31: Grafana dashboard JSON parse
#
# Exit codes:
#   0 = all 32 checks green
#   1 = any failure (first failure is fatal)
#
# Usage: bash scripts/sota_smoke_fase1.sh
#
# No side effects: does not install launchagents, does not start cron, does
# not hit the DB. All PG interactions are mocked in pytest via _FakePool.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${ROOT}/apps/backend-rag"
VENV="${BACKEND}/.venv"
# Fallback to the Pro repo venv if the worktree doesn't have its own
# (worktree venvs are often symlinked to /Users/nuzantara/Desktop/nuzantara/.../.venv).
if [[ ! -x "${VENV}/bin/python" ]] && [[ -x "/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python" ]]; then
  VENV="/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv"
fi
PY="${VENV}/bin/python"

cd "${ROOT}"

PASS=0
FAIL=0
STEP=0

_ok()   { STEP=$((STEP+1)); PASS=$((PASS+1)); printf "  [%02d] \033[32m✓\033[0m %s\n" "${STEP}" "$1"; }
_fail() { STEP=$((STEP+1)); FAIL=$((FAIL+1)); printf "  [%02d] \033[31m✗\033[0m %s\n" "${STEP}" "$1"; exit 1; }

_check_file() {
  local path="$1"; local label="$2"
  if [[ -f "${ROOT}/${path}" ]]; then _ok "${label}: ${path}"; else _fail "${label} MISSING: ${path}"; fi
}

_check_exec() {
  local path="$1"; local label="$2"
  if [[ -x "${ROOT}/${path}" ]]; then _ok "${label} executable: ${path}"; else _fail "${label} NOT executable: ${path}"; fi
}

_check_py_ast() {
  local path="$1"
  "${PY}" -c "import ast,sys; ast.parse(open('${ROOT}/${path}').read()); print('ok')" > /dev/null \
    && _ok "python AST parse: ${path}" \
    || _fail "python AST parse failed: ${path}"
}

_check_plist() {
  local path="$1"
  plutil -lint "${ROOT}/${path}" > /dev/null \
    && _ok "plist lint: ${path}" \
    || _fail "plist lint failed: ${path}"
}

_check_json() {
  local path="$1"
  "${PY}" -c "import json; json.load(open('${ROOT}/${path}'))" > /dev/null \
    && _ok "JSON parse: ${path}" \
    || _fail "JSON parse failed: ${path}"
}

_run_pytest() {
  local tests="$1"; local label="$2"
  (cd "${BACKEND}" && PYTHONPATH=. "${VENV}/bin/pytest" ${tests} -q --tb=line > /tmp/_smoke_pytest.log 2>&1) \
    && _ok "pytest ${label}" \
    || { cat /tmp/_smoke_pytest.log; _fail "pytest ${label}"; }
}

printf "\n== SOTA Fase 1 smoke ==\n"
printf "  root = %s\n  backend = %s\n\n" "${ROOT}" "${BACKEND}"

# ── Prereqs ─────────────────────────────────────────────────────────────
if [[ ! -x "${PY}" ]]; then
  echo "FATAL: venv python not found at ${PY}"
  exit 1
fi

# ── Task 23 — M13 feedback loop core ────────────────────────────────────
_check_file "apps/backend-rag/backend/services/measurer/m13_feedback_loop.py"      "T23 loop module"
_run_pytest "backend/tests/unit/services/measurer/test_m13_feedback_loop.py"       "T23 M13FeedbackLoop"

# ── Task 24 — collect every 6h ──────────────────────────────────────────
_check_file "apps/backend-rag/backend/services/sota_loop/m13_collect.py"            "T24 collect module"
_check_py_ast "apps/backend-rag/backend/services/sota_loop/m13_collect.py"
_check_plist "infra/launchagents/com.balizero.sota.m13-collect.plist"

# ── Task 25 — weekly report ─────────────────────────────────────────────
_check_file "apps/backend-rag/backend/services/sota_loop/m13_weekly.py"             "T25 weekly module"
_check_py_ast "apps/backend-rag/backend/services/sota_loop/m13_weekly.py"
_check_plist "infra/launchagents/com.balizero.sota.m13-weekly.plist"

# ── Task 26 — monthly retrain ───────────────────────────────────────────
_check_file "apps/backend-rag/backend/services/sota_loop/m13_monthly.py"            "T26 monthly module"
_check_py_ast "apps/backend-rag/backend/services/sota_loop/m13_monthly.py"
_check_plist "infra/launchagents/com.balizero.sota.m13-monthly.plist"

# ── Task 27 — checkpoint (30/60/90) ─────────────────────────────────────
_check_file "apps/backend-rag/backend/services/sota_loop/m13_checkpoint.py"         "T27 checkpoint module"
_check_py_ast "apps/backend-rag/backend/services/sota_loop/m13_checkpoint.py"
_check_plist "infra/launchagents/com.balizero.sota.m13-checkpoint.plist"

# ── Task 28 — EditorialConfig ───────────────────────────────────────────
_check_file "apps/backend-rag/backend/services/war_room/editorial_config.py"       "T28 editorial_config module"
_run_pytest "backend/tests/unit/services/war_room/test_editorial_config.py"        "T28 EditorialConfig"

# ── Task 29 — Council v2 persona_slug ───────────────────────────────────
_check_file "apps/backend-rag/backend/services/council/tone_council.py"            "T29 tone_council module"
_run_pytest "backend/tests/services/council/test_tone_council_persona.py"          "T29 persona_slug"

# ── Task 30 — Telegram kill-switch router ───────────────────────────────
_check_file "apps/backend-rag/backend/app/routers/research_control.py"             "T30 research_control router"
_run_pytest "backend/tests/services/war_room/test_research_control_router.py"      "T30 kill-switch endpoints"
_run_pytest "backend/tests/setup/test_router_manifest.py"                          "T30 manifest regression"

# ── Task 31 — Grafana dashboard ─────────────────────────────────────────
_check_file "docs/runbooks/grafana-sota-setup.md"                                  "T31 runbook"
_check_json "infra/grafana/social-sota-dashboard.json"

# ── Summary ─────────────────────────────────────────────────────────────
printf "\n== Smoke result ==\n"
printf "  checks = %d / %d pass\n" "${PASS}" "${STEP}"
if [[ "${FAIL}" -eq 0 ]]; then
  printf "  \033[32mALL GREEN\033[0m\n"
  exit 0
fi
printf "  \033[31mFAIL\033[0m\n"
exit 1
