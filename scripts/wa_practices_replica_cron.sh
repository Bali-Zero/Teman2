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
# Exit-code mapping: whatever `wa_practices_replica.py --sync` returns
# propagates as-is — cron-runner's receipt must see a real failure as a real
# failure, never a silent green (superscar #2):
#   0 = ran clean, including "0 inserted/0 updated", skipped_fk=0 and
#       skipped_invalid=0
#   1 = an exception aborted the run (FAIL line on stderr names the stage)
#   2 = the env guard or argparse refused before any I/O
#   3 = the sync COMPLETED and COMMITTED (every good row landed — not a
#       failure of the run itself) but skipped_fk>0 or skipped_invalid>0:
#       something in Fly's data could not be placed this run (added by the
#       gate's F3 finding, 2026-09-29 — a cron receipt that read rc=0
#       whatever the skip counts are is the exact silent-green this repo's
#       cron-runner discipline exists to prevent)

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
