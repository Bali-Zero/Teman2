#!/usr/bin/env bash
# wa_team_promises_scan_cron.sh — cron payload for cron-runner.sh, running
# scripts/wa_team_promises.py --scan (T3 PR-2, the candidates scanner).
#
# cron-runner executes payloads with /bin/bash; this thin wrapper picks the
# right interpreter (the CLI needs asyncpg, which lives in
# apps/backend-rag/.venv, not any bare python3) and sets PYTHONPATH so the
# scanner's own sys.path self-insertion has a stable base to resolve against.
# It lives IN THE REPO and the crontab line points here directly — never a
# ~/scripts copy (superscar #1 HOME-fork). Same pattern as
# scripts/queue_stall_notify_cron.sh: a plain scripts/*_cron.sh payload, not
# an infra/launchagents/ LaunchAgent (this job has no plist and needs none).
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
#   */15 * * * * /bin/bash /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/wa_team_promises_scan_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/wa-team-promises-scan.log 2>&1
#
# Exit-code mapping: whatever `wa_team_promises.py --scan` returns (0 = ran,
# including "0 new candidates"; 1 = FAIL line on stderr; 2 = guard/argparse
# refusal) propagates as-is — cron-runner's receipt must see a real failure
# as a real failure, never a silent green (superscar #2).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ORGAN="$REPO/scripts/wa_team_promises.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "wa_team_promises_scan_cron: organ not found at $ORGAN (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

if [ ! -x "$PYTHON" ]; then
    echo "wa_team_promises_scan_cron: interpreter missing at $PYTHON — asyncpg lives there" >&2
    exit 66
fi

PYTHONPATH="$REPO/apps/backend-rag" "$PYTHON" "$ORGAN" --scan "$@"
rc=$?
echo "wa_team_promises_scan_cron: organ rc=$rc" >&2
exit "$rc"
