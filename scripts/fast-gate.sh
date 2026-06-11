#!/usr/bin/env bash
# fast-gate.sh — single fast local inner-loop gate (4-LLM panel ship-order #1, 2026-06-09).
#
# WHAT: ruff (lint+fix+format) + pytest-testmon (run ONLY tests impacted by the diff).
# WHY:  the panel's unanimous-ship item. Deterministic, $0, no LLM, no PII leak.
#       testmon uses coverage dependency-tracking to run just the tests touching the
#       changed code — real review-speed gain vs the full 10,500-test suite.
# SCOPE: this is a DEVELOPER inner-loop helper, NOT a replacement for .husky/pre-commit
#       (which stays the authoritative gate) nor for full CI (which still runs everything).
#
# Reference: research/operations/2026-06-09-dev-ai-stack-additions-4llm-panel.md §5 (#1).
#
# Usage:
#   bash scripts/fast-gate.sh            # lint+fix+format staged py, then impacted tests
#   bash scripts/fast-gate.sh --no-test  # lint/format only (fastest)
#   bash scripts/fast-gate.sh --all      # run full test suite instead of impacted-only
#
# Kill switch: none — it's opt-in (you run it). It never blocks a commit by itself.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$REPO_ROOT" ] && { echo "fast-gate: not in a git repo"; exit 1; }
BACKEND="$REPO_ROOT/apps/backend-rag"

# Resolve the venv python (matches .husky/pre-commit's resolution order).
if   [ -x "$BACKEND/.venv/bin/python" ]; then PY="$BACKEND/.venv/bin/python"
elif [ -x "$BACKEND/venv/bin/python" ];  then PY="$BACKEND/venv/bin/python"
else PY="python3"; fi

RUN_TESTS=1
TEST_MODE="--testmon"   # impacted-only by default
for arg in "$@"; do
  case "$arg" in
    --no-test) RUN_TESTS=0 ;;
    --all)     TEST_MODE="" ;;   # full suite (no testmon filter)
    *) echo "fast-gate: unknown arg '$arg' (use --no-test | --all)"; exit 2 ;;
  esac
done

# ── 1. ruff: lint+autofix+format on staged Python under apps/backend-rag ──────
STAGED_PY=$(git -C "$REPO_ROOT" diff --cached --name-only --diff-filter=d \
            | grep -E '^apps/backend-rag/.*\.py$' || true)
if [ -n "$STAGED_PY" ]; then
  REL=$(echo "$STAGED_PY" | sed 's|^apps/backend-rag/||')
  echo "🔧 ruff check --fix on $(echo "$REL" | wc -l | tr -d ' ') staged file(s)…"
  ( cd "$BACKEND" && echo "$REL" | xargs "$PY" -m ruff check --fix ) || {
    echo "❌ ruff found unfixable issues — resolve them, then re-stage."; exit 1; }
  echo "🎨 ruff format…"
  ( cd "$BACKEND" && echo "$REL" | xargs "$PY" -m ruff format )
  echo "   (ruff applied fixes/format — re-stage with: git add -u)"
else
  echo "ℹ️  no staged apps/backend-rag/*.py — skipping ruff."
fi

# ── 2. pytest-testmon: run only tests impacted by the change ──────────────────
if [ "$RUN_TESTS" -eq 1 ]; then
  if [ -n "$TEST_MODE" ]; then
    echo "🧪 pytest --testmon (impacted tests only; first run builds the map)…"
  else
    echo "🧪 pytest (FULL suite, --all)…"
  fi
  ( cd "$BACKEND" && PYTHONPATH=. "$PY" -m pytest $TEST_MODE -q ) || {
    echo "❌ tests failed."; exit 1; }
else
  echo "ℹ️  --no-test: skipping tests."
fi

echo "✅ fast-gate passed."
