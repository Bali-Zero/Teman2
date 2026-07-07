#!/usr/bin/env bash
# organism_digest_sessionstart.sh — session-boot receptor for the organism digest.
#
# Third sibling of escalations_alert_sessionstart.sh / proprioception_sessionstart.sh.
# Renders "what changed in the organism in the last 24h" (regulatory deltas, dead AI
# seats, silent organs, overdue armings, main landings) INTO the session — the one
# channel Zero actually reads daily. Born 2026-07-06 from the mandate "Telegram non lo
# leggo: resoconti compatti al canale giusto".
#
# ANTI-CALM-LIAR CONTRACT: never silent — all-quiet prints a one-line heartbeat.
# Budget: the python receptor self-limits via SIGALRM (6s). Always exit 0.
# Kill switch: ORGANISM_DIGEST_ENABLED=false.

set -o pipefail
[[ "${ORGANISM_DIGEST_ENABLED:-true}" == "false" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." 2>/dev/null && pwd)"

OUT="$(python3 "$REPO_ROOT/scripts/organism_digest.py" 2>/dev/null)"
RC=$?
if [[ -n "$OUT" ]]; then
  echo "$OUT"
elif [[ $RC -ne 0 ]]; then
  echo "📰 organismo: receptor error (digest exit $RC) — run: python3 scripts/organism_digest.py"
else
  # Empty output with rc=0 should be impossible (anti-calm-liar) — make THAT visible too.
  echo "📰 organismo: receptor emitted nothing (contract breach) — check scripts/organism_digest.py"
fi
exit 0
