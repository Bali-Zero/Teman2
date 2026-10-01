#!/usr/bin/env bash
# wa_team_promises_audit_cron.sh — cron payload for cron-runner.sh, running
# scripts/wa_team_promises.py --audit-resolution (T3 P2 PR-C, the resolver's
# precision audit).
#
# Same thin-wrapper pattern as wa_team_promises_resolve_cron.sh: picks the venv
# interpreter (asyncpg lives in apps/backend-rag/.venv), sets PYTHONPATH, lives
# IN THE REPO (never a ~/scripts copy — superscar #1 HOME-fork). WEEKLY, Sunday
# 04:37, an hour no other wa_team_promises tick uses, because the audit makes up to
# 300 local-model calls and must not queue behind the judge. Read-only on
# team_promises; it writes only the int-only counts file the resolution digest
# quotes. The model endpoint is guarded to be local: the audit refuses (rc 2)
# on any other host.
#
# ── Crontab wiring (installed by the conductor after PROVE-LIVE, NOT here) ──
#
#   37 4 * * 0 /bin/bash /Users/nuzantara/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/nuzantara/scripts/wa_team_promises_audit_cron.sh \
#     >> /Users/nuzantara/logs/cron-tmp/wa-team-promises-audit.log 2>&1
#
# Exit-code mapping: whatever `wa_team_promises.py --audit-resolution` returns
# (0 = ran; 1 = FAIL line on stderr, e.g. Ollama down; 2 = guard/argparse
# refusal) propagates as-is — a real failure must reach cron-runner's receipt
# as one (superscar #2).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ORGAN="$REPO/scripts/wa_team_promises.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

if [ ! -f "$ORGAN" ]; then
    echo "wa_team_promises_audit_cron: organ not found at $ORGAN (checkout behind?)" >&2
    exit 66  # armed-to-nothing must be a loud receipt, never a silent green (W81)
fi

if [ ! -x "$PYTHON" ]; then
    echo "wa_team_promises_audit_cron: interpreter missing at $PYTHON — asyncpg lives there" >&2
    exit 66
fi

PYTHONPATH="$REPO/apps/backend-rag" "$PYTHON" "$ORGAN" --audit-resolution "$@"
rc=$?
echo "wa_team_promises_audit_cron: organ rc=$rc" >&2
exit "$rc"
