#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if [[ -z "${VIRTUAL_ENV:-}" && "${CI:-}" != "true" ]]; then
  echo "Activate a Python virtualenv before running MCP coverage." >&2
  exit 2
fi

python -m pytest \
  --cov=nuzantara_mcp \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --junitxml=test-results-mcp.xml \
  tests
