#!/usr/bin/env bash
# wa_practices_replica_cron.sh — cron payload for cron-runner.sh, running
# scripts/wa_practices_replica.py --sync (T5 P4, one-way Fly -> Pro
# `practices` replica).
#
# cron-runner executes payloads with /bin/bash; this thin wrapper picks the
# right interpreter (the CLI needs asyncpg, which lives in
# apps/backend-rag/.venv, not any bare python3). It lives IN THE REPO and the
# crontab line points here directly — never a ~/scripts copy (superscar #1
# HOME-fork). Same pattern as scripts/wa_team_promises_scan_cron.sh.
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
#   0 * * * * /bin/bash /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/wa_practices_replica_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/wa-practices-replica.log 2>&1
#
# Exit-code mapping: whatever `wa_practices_replica.py --sync` returns (0 =
# ran, including "0 inserted/0 updated"; 1 = FAIL line on stderr; 2 =
# guard/argparse refusal) propagates as-is — cron-runner's receipt must see a
# real failure as a real failure, never a silent green (superscar #2).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ORGAN="$REPO/scripts/wa_practices_replica.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "wa_practices_replica_cron: organ not found at $ORGAN (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

if [ ! -x "$PYTHON" ]; then
    echo "wa_practices_replica_cron: interpreter missing at $PYTHON — asyncpg lives there" >&2
    exit 66
fi

"$PYTHON" "$ORGAN" --sync "$@"
rc=$?
echo "wa_practices_replica_cron: organ rc=$rc" >&2
exit "$rc"
