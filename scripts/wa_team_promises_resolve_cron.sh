#!/usr/bin/env bash
# wa_team_promises_resolve_cron.sh — cron payload for cron-runner.sh, running
# scripts/wa_team_promises.py --resolve (T3 P2, the resolver).
#
# Same thin-wrapper pattern as wa_team_promises_judge_cron.sh: picks the venv
# interpreter (asyncpg lives in apps/backend-rag/.venv), sets PYTHONPATH, lives
# IN THE REPO (never a ~/scripts copy — superscar #1 HOME-fork). Hourly, at an
# offset minute from the scanner's and the judge's. The resolver is fill-only
# and idempotent, so overlapping runs cannot double-write; it takes no lock.
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
#   13 * * * * /bin/bash /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/wa_team_promises_resolve_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/wa-team-promises-resolve.log 2>&1
#
# Exit-code mapping: whatever `wa_team_promises.py --resolve` returns (0 = ran,
# including "0 scanned"; 1 = FAIL line on stderr; 2 = guard/argparse refusal)
# propagates as-is — a real failure must reach cron-runner's receipt as one
# (superscar #2).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ORGAN="$REPO/scripts/wa_team_promises.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "wa_team_promises_resolve_cron: organ not found at $ORGAN (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

if [ ! -x "$PYTHON" ]; then
    echo "wa_team_promises_resolve_cron: interpreter missing at $PYTHON — asyncpg lives there" >&2
    exit 66
fi

PYTHONPATH="$REPO/apps/backend-rag" "$PYTHON" "$ORGAN" --resolve "$@"
rc=$?
echo "wa_team_promises_resolve_cron: organ rc=$rc" >&2
exit "$rc"
