#!/bin/bash
# wa-team-promises wrapper: T3 promise extractor tick (Pro-local, Law 2 — no
# secret/env-file needed, the DB is local nuzantara_dev on the loopback).
# Tracked here (scar #1: no HOME-only wrapper) so cron-runner.sh has a
# stable script path to invoke. crontab line (documented, NOT installed by
# this PR — see scripts/wa_team_promises.py docstring / PR body):
#   */15 * * * * $HOME/nuzantara/scripts/cron-runner.sh \
#     $HOME/nuzantara/infra/launchagents/wrappers/wa-team-promises-run.sh \
#     >> $HOME/logs/wa-team-promises.log 2>&1
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$HOME/nuzantara/apps/backend-rag/.venv/bin/python"
SCRIPT="$HOME/nuzantara/scripts/wa_team_promises.py"
exec env PYTHONPATH="$HOME/nuzantara/apps/backend-rag" "$PYBIN" -u "$SCRIPT" "$@"
