#!/bin/bash
# Domain mesh Phase 1 (B1 setup_team) — daily 06:00 WITA pipeline.
#
# Mirrors infra/scripts/domain-mesh-foundations-cron.sh:
# - Absolute venv python (no system fallback)
# - Atomic snapshot via tmp + mv
# - Kill switch via SETUP_TEAM_CRON_ENABLED
# - Bali calendar guard: skip Galungan/Kuningan ±1
#
# What it does:
#   1. should_skip_today() -> if true, exit 0 with note logged
#   2. fetch_recent_regulations() — pasal.id + JDIHN + setkab
#   3. fetch_recent_immigration() — imigrasi + kemenkumham + tempo
#   4. fetch_recent_regulation_bali() — 4 jdih portals (probe-gated)
#   5. extract_obligations(reg) for each new Regulation (mocked
#      claude_runner via env var if SETUP_TEAM_DRY_RUN=true)
#   6. match_obligations_to_clients(obl) for each new Obligation
#   7. check_sla_and_alert() + auto_approve_tier1_after_sla()
#   8. Snapshot summary JSON to ~/.cache/setup-team/snapshots/YYYYMMDD.json
set -uo pipefail

# Kill switch.
if [ "${SETUP_TEAM_CRON_ENABLED:-true}" = "false" ]; then
    echo "$(date) setup-team cron disabled via SETUP_TEAM_CRON_ENABLED=false" >&2
    exit 0
fi

LOG_DIR="$HOME/logs/setup-team"
SNAPSHOT_DIR="$HOME/.cache/setup-team/snapshots"
mkdir -p "$LOG_DIR" "$SNAPSHOT_DIR"

LOG_FILE="$LOG_DIR/setup-team-daily-$(date +%Y%m%d).log"
SNAPSHOT_FILE="$SNAPSHOT_DIR/setup-team-$(date +%Y%m%d).json"
SNAPSHOT_TMP="${SNAPSHOT_FILE}.tmp.$$"

REPO_ROOT="${SETUP_TEAM_REPO_ROOT:-${HOME}/Desktop/nuzantara}"
cd "$REPO_ROOT/apps/mata-garuda" || {
    echo "$(date) FAILED: cannot cd to $REPO_ROOT/apps/mata-garuda" >> "$LOG_FILE"
    exit 1
}

VENV_PY="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo "$(date) FAILED: venv python not executable at $VENV_PY" >> "$LOG_FILE"
    exit 2
fi

# Pipeline runner. Captures all sub-steps in one Python invocation so we
# don't pay the ~300ms cold-start penalty per stage. Atomic snapshot mv
# at the end — partial pipeline = no snapshot file.
"$VENV_PY" -c "
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# Lazy direct imports — no transformers/torch at module load.
from mata_garuda.domains.setup_team.feeders.nb_intel_regulation import fetch_recent_regulations
from mata_garuda.domains.setup_team.feeders.nb_intel_immigration import fetch_recent_immigration
from mata_garuda.domains.setup_team.feeders.nb_intel_regulation_bali import fetch_recent_regulation_bali
from mata_garuda.domains.setup_team.obligation_engine import extract_obligations
from mata_garuda.domains.setup_team.client_match import match_obligations_to_clients
from mata_garuda.domains.setup_team.promotion_gate import (
    auto_approve_tier1_after_sla,
    check_sla_and_alert,
    propose_promotion,
)
from mata_garuda.domains.setup_team.scheduler import should_skip_today

DRY_RUN = os.environ.get('SETUP_TEAM_DRY_RUN', 'false').lower() == 'true'

skip, reason = should_skip_today()
if skip:
    sys.stdout.write(json.dumps({
        'skipped': True,
        'reason': reason,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    sys.exit(0)


async def run_feeders():
    regs = []
    for fetcher, name in [
        (fetch_recent_regulations, 'regulation'),
        (fetch_recent_immigration, 'immigration'),
        (fetch_recent_regulation_bali, 'regulation_bali'),
    ]:
        try:
            batch = await fetcher(days=30)
            regs.extend(batch)
        except Exception as exc:
            sys.stderr.write(f'feeder {name} failed: {exc}\n')
    return regs


def dry_runner(_prompt):
    return '[]'  # no obligations extracted in dry run


regs = asyncio.run(run_feeders())
n_new_obligations = 0
n_matches = 0
runner = dry_runner if DRY_RUN else None
for r in regs:
    try:
        # Propose promotion for tier <= 2
        if r.tier <= 2:
            propose_promotion(
                intel_source_id=r.source_id,
                target_authority_nb=f'NB-AUTHORITY-{r.domain}',
                owner='Adit',
                tier=r.tier,
            )
        if runner is not None:
            obls = extract_obligations(r, claude_runner=runner)
        else:
            obls = extract_obligations(r)
        n_new_obligations += len(obls)
        for obl in obls:
            if obl.id is None:
                continue
            n_matches += len(match_obligations_to_clients(obl.id))
    except Exception as exc:
        sys.stderr.write(f'pipeline step failed for {r.source_id}: {exc}\n')

alerts = check_sla_and_alert()
n_auto_approved = auto_approve_tier1_after_sla()

summary = {
    'skipped': False,
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'dry_run': DRY_RUN,
    'feeder_total': len(regs),
    'feeder_by_domain': {
        d: sum(1 for r in regs if r.domain == d)
        for d in ('regulation', 'immigration', 'regulation_bali')
    },
    'new_obligations': n_new_obligations,
    'client_matches': n_matches,
    'sla_alerts': len(alerts),
    'sla_alerts_by_kind': {
        k: sum(1 for a in alerts if a.kind == k)
        for k in (
            'sla_warning',
            'sla_reached_tier1_auto_approve',
            'sla_reached_tier2_escalate',
        )
    },
    'auto_approved_tier1': n_auto_approved,
}
sys.stdout.write(json.dumps(summary, indent=2))
" > "$SNAPSHOT_TMP" 2>>"$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    rm -f "$SNAPSHOT_TMP"
    echo "$(date) FAILED setup-team daily pipeline (exit $EXIT_CODE)" >> "$LOG_FILE"
    exit $EXIT_CODE
fi

# Atomic publish
mv "$SNAPSHOT_TMP" "$SNAPSHOT_FILE"

# Concise summary line for log
SUMMARY=$(SNAPSHOT_FILE="$SNAPSHOT_FILE" "$VENV_PY" -c "
import json, os
d = json.load(open(os.environ['SNAPSHOT_FILE']))
if d.get('skipped'):
    print(f\"skipped ({d['reason']})\")
else:
    print(f\"feeders={d['feeder_total']} new_obligations={d['new_obligations']} \"
          f\"matches={d['client_matches']} alerts={d['sla_alerts']} \"
          f\"auto_approved={d['auto_approved_tier1']}\")
")
echo "$(date) setup-team summary: $SUMMARY" >> "$LOG_FILE"

exit 0
