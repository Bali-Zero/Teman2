#!/usr/bin/env bash
# wa-team-promises-scan-run.sh — wrapper cron per
# `scripts/wa_team_promises.py --scan` (T3 PR-2, the candidates scanner).
#
# Crontab line (NOT installed by this PR — activation is a separate,
# explicit step; see the PR body for the exact command):
#   */15 * * * * /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/infra/launchagents/wrappers/wa-team-promises-scan-run.sh \
#     >> /Users/nuzantara/logs/wa-team-promises-scan.log 2>&1
#
# Same three reasons this wrapper exists as wa-session-liveness.sh: pick the
# ABSOLUTE interpreter (never PATH — W108), never swallow the exit code
# under `set -e` on a bare pipeline (W101), and say CANNOT-VERIFY loudly
# instead of a silent 0 when the organ itself is missing (W81).
#
# Exit: whatever `wa_team_promises.py --scan` returns (0 = ran, including
# "0 new candidates"; 1 = FAIL line on stderr; 2 = guard/argparse refusal) ·
# 2 = this wrapper could not even find the organ or the interpreter.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ORGAN="$REPO/scripts/wa_team_promises.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "CANNOT-VERIFY: organo assente a $ORGAN (REPO derivata: $REPO)" >&2
    exit 2
fi

if [ ! -x "$PYTHON" ]; then
    echo "CANNOT-VERIFY: interprete assente a $PYTHON — asyncpg vive li dentro" >&2
    exit 2
fi

set +e
PYTHONPATH="$REPO/apps/backend-rag" "$PYTHON" "$ORGAN" --scan "$@"
RC=$?
set -e

echo "wa-team-promises-scan rc=$RC"
exit "$RC"
