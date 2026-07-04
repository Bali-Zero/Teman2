#!/bin/bash
# intake_archive_abort.sh — execute Zero's decision 2026-07-04 (option 4 + day-only):
#   1. abort the Dropbox-archive intake backlog (reject pending, delete blobs)
#   2. fast-forward the Drive cursor so the past never re-enters
#   3. rclone Dropbox->Drive becomes day-only (--max-age 24h)
#   4. re-arm the whole chain
# Run ON the Pro. Idempotent where possible. Never prints secrets.
set -uo pipefail

PSQL=/opt/homebrew/opt/postgresql@17/bin/psql
DB="postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
REPO=/Users/nuzantara/Desktop/nuzantara
UID_N=$(id -u)

echo "=== STEP 0: stop the feeders/consumer (reversible) ==="
launchctl bootout gui/$UID_N/com.balizero.dropbox-intake 2>/dev/null && echo "dropbox-intake: booted out" || echo "dropbox-intake: was not loaded"
pkill -f "rclone copy dropbox-bayu" && echo "rclone: killed" || echo "rclone: not running"
launchctl bootout gui/$UID_N/com.balizero.drive-intake-drain 2>/dev/null && echo "drain: booted out" || echo "drain: was not loaded (expected, paused earlier)"
launchctl bootout gui/$UID_N/com.nuzantara.intake-worker 2>/dev/null && echo "worker: booted out" || echo "worker: was not loaded"
sleep 2

echo "=== STEP 1: pre-checks ==="
NON_DRIVE=$($PSQL "$DB" -t -A -c "SELECT count(*) FROM intake_queue WHERE status='pending' AND source<>'drive';")
echo "pending non-drive rows: $NON_DRIVE (these are NOT touched)"
PENDING=$($PSQL "$DB" -t -A -c "SELECT count(*) FROM intake_queue WHERE status='pending' AND source='drive';")
echo "pending drive rows to reject: $PENDING"

echo "=== STEP 2: reject the archive backlog (rows stay = dedup registry) ==="
$PSQL "$DB" -c "UPDATE intake_queue SET status='rejected', updated_at=now(), last_error='operator abort 2026-07-04: Dropbox archive intake cancelled (Zero GO), blobs reclaimed' WHERE status='pending' AND source='drive';"

echo "=== STEP 3: fast-forward Drive cursor (past never re-enters) ==="
$PSQL "$DB" -c "UPDATE system_settings SET value='{}' WHERE key='intake_drive_page_token';"
$PSQL "$DB" -t -A -c "SELECT key, value FROM system_settings WHERE key='intake_drive_page_token';"

echo "=== STEP 4: reclaim blob bytes (existing organ, TTL=0) ==="
cd "$REPO"
INTAKE_BLOB_TTL_DAYS=0 apps/backend-rag/.venv/bin/python scripts/intake_blob_retention.py --apply 2>&1 | tail -5

echo "=== STEP 5: rclone day-only regime ==="
W=/Users/nuzantara/scripts/dropbox-intake-sync.sh
if grep -q -- "--max-age" "$W"; then
  echo "wrapper already day-only"
else
  sed -i.bak-pre-dayonly-20260704 's/--fast-list/--fast-list --max-age 24h/' "$W"
  grep -q -- "--max-age 24h" "$W" && echo "wrapper patched: --max-age 24h" || echo "PATCH FAILED - inspect $W"
fi

echo "=== STEP 6: re-arm the chain ==="
launchctl bootstrap gui/$UID_N ~/Library/LaunchAgents/com.nuzantara.intake-worker.plist && echo "worker: armed"
launchctl bootstrap gui/$UID_N ~/Library/LaunchAgents/com.balizero.drive-intake-drain.plist && echo "drain: armed"
launchctl bootstrap gui/$UID_N ~/Library/LaunchAgents/com.balizero.dropbox-intake.plist && echo "dropbox-intake: armed"

echo "=== STEP 7: prove ==="
df -h /System/Volumes/Data | tail -1
$PSQL "$DB" -t -A -c "SELECT status, count(*) FROM intake_queue GROUP BY status ORDER BY 2 DESC;"
du -sh /Users/nuzantara/.nuzantara/intake-blobs
echo "DONE — check drain tick in ~10min: tail ~/logs/drive-intake-drain.out.log"
