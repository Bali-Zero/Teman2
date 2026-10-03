#!/usr/bin/env bash
# wa_team_promises_judge_cron.sh — cron payload for cron-runner.sh, running
# scripts/wa_team_promises.py --judge (T3 PR-3, the local Ollama judge).
#
# Same thin-wrapper pattern as wa_team_promises_scan_cron.sh: picks the venv
# interpreter (asyncpg lives in apps/backend-rag/.venv, not any bare
# python3), sets PYTHONPATH so the judge's own sys.path self-insertion has a
# stable base, lives IN THE REPO (never a ~/scripts copy — superscar #1
# HOME-fork). Own crontab line at an OFFSET minute from the scanner's, so
# the two never fire in the same wall-clock minute even though they hold
# SEPARATE lock files and would not block each other anyway.
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
#   7-59/15 * * * * /bin/bash /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/wa_team_promises_judge_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/wa-team-promises-judge.log 2>&1
#
# Exit-code mapping: whatever `wa_team_promises.py --judge` returns (0 = ran,
# including "0 selected"; 1 = FAIL line on stderr, e.g. an Ollama outage;
# 2 = guard/argparse refusal) propagates as-is — cron-runner's receipt must
# see a real failure as a real failure, never a silent green (superscar #2).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ORGAN="$REPO/scripts/wa_team_promises.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "wa_team_promises_judge_cron: organ not found at $ORGAN (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

if [ ! -x "$PYTHON" ]; then
    echo "wa_team_promises_judge_cron: interpreter missing at $PYTHON — asyncpg lives there" >&2
    exit 66
fi

PYTHONPATH="$REPO/apps/backend-rag" "$PYTHON" "$ORGAN" --judge "$@"
rc=$?
echo "wa_team_promises_judge_cron: organ rc=$rc" >&2
exit "$rc"
