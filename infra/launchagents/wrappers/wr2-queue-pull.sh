#!/bin/bash
# wr2-queue-pull.sh — keeps the M5 copy of the WR2 queue in sync with Pro (source of truth).
# The native WR2 Control.app polls this file from disk; this is the only thing that makes
# its view track Pro. Pull-only (M5 never writes back). Blocking loop (not KeepAlive-oneshot, scar #7).
# Lives OUTSIDE ~/Desktop (W84: launchd loses TCC grant on ~/Desktop).
set -uo pipefail
LOG="$HOME/logs/wr2-queue-pull.log"
DEST_DIR="$HOME/nuzantara/apps/war-room/output/queue"
SRC_DIR="/Users/nuzantara/nuzantara/apps/war-room/output/queue"
# WR2 Insights: the analyst reasoning (real findings) lives only on Pro under the skill dir.
AMEND_DEST="$HOME/.claude/skills/bali-zero-brand/_proposed-amendments"
AMEND_SRC="/Users/nuzantara/.claude/skills/bali-zero-brand/_proposed-amendments"
# Carousel render PNGs — synced from Pro (the renderer) from now on, so new caroselli
# show their cover in the app. Pull-only, additive (never deletes M5-local carousels).
CAROUSEL_DEST="$HOME/nuzantara/apps/war-room/output/carousel"
CAROUSEL_SRC="/Users/nuzantara/nuzantara/apps/war-room/output/carousel"
INTERVAL="${WR2_QUEUE_PULL_INTERVAL:-300}"
mkdir -p "$DEST_DIR" "$AMEND_DEST" "$CAROUSEL_DEST"

# Re-render reconcile (verb leg 3): steady-state --ignore-existing skips a carousel
# whose PNGs were REPLACED IN PLACE on Pro (same filenames, new bytes) — after a
# re-render the M5 mirror would show the STALE slides forever. WR2_PULL_CHECKSUM=1
# swaps in --checksum: rsync compares content hashes and re-pulls changed files.
# Still additive (no --delete), still --ignore-errors. Hashing both sides is
# expensive — meant as a one-shot after a re-render (combine with --once), not
# as the steady-state default.
if [ "${WR2_PULL_CHECKSUM:-0}" = "1" ]; then
  RSYNC_MODE="--checksum"
else
  RSYNC_MODE="--ignore-existing"
fi
# --once: run a single pass and exit (one-shot reconcile instead of daemon loop).
ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1

# A4 (2026-07-16, optional / red-team gates independently — separate commit):
# WR2_PULL_CHECKSUM=1 above only forces --checksum for a MANUAL one-shot; the
# steady-state daemon loop otherwise runs --ignore-existing forever, so a
# carousel re-rendered IN PLACE on Pro (same filenames, new bytes) is skipped
# by filename and never re-pulled. Force a --checksum pass automatically every
# Nth loop iteration (default 12 * 300s interval ≈ 1h) so re-render-in-place
# drift self-heals without a human remembering to run the manual mode. Scoped
# to the carousel rsync only — the queue-file pull already re-fetches +
# byte-compares (cmp -s) every iteration regardless.
CHECKSUM_EVERY_N="${WR2_PULL_CHECKSUM_EVERY_N:-12}"
iter_n=0

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Merge helper (split-brain cure, 2026-07-13): the WR2 Control app writes
# publish transitions LOCALLY (QueueWriter.markPublished) and a blind replace
# reverted them within one poll cycle. The merge keeps Pro as SSOT but protects
# local published* entries and emits a push-back list replayed into Pro via the
# canonical wr2_queue_writer.py (exact ref-code, IG-URL validated writer-side).
MERGE_PY="$HOME/nuzantara/scripts/wr2_queue_pull_merge.py"

while true; do
  for f in human-review-queue.json queue-archive.json; do
    # PID-suffixed tmp: a WR2_PULL_CHECKSUM one-shot may run while the daemon
    # loop is live — a shared deterministic tmp path would interleave writes.
    tmp="$DEST_DIR/.$f.pull.tmp.$$"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes pro "cat '$SRC_DIR/$f'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
      # valida JSON prima di sostituire (mai clobberare con spazzatura)
      if python3 -c "import json,sys; json.load(open('$tmp'))" 2>/dev/null; then
        if [ "$f" = "human-review-queue.json" ] && [ -f "$MERGE_PY" ] && [ -f "$DEST_DIR/$f" ]; then
          # merge instead of clobber: local publish transitions survive the pull
          report=$(python3 "$MERGE_PY" --remote "$tmp" --local "$DEST_DIR/$f" --out "$tmp.merged" 2>>"$LOG")
          if [ -s "$tmp.merged" ]; then
            if ! cmp -s "$tmp.merged" "$DEST_DIR/$f" 2>/dev/null; then
              mv "$tmp.merged" "$DEST_DIR/$f"
              echo "[$(ts)] merged $f ($report)" >> "$LOG"
            else
              rm -f "$tmp.merged"
            fi
            rm -f "$tmp"
            # push protected publish transitions back to Pro (SSOT) via the
            # canonical writer. ref/url are shell-safe by construction (strict
            # regexes in the merge script); the writer re-validates on Pro.
            echo "$report" | python3 -c 'import json,sys
try: rep=json.load(sys.stdin)
except Exception: rep={}
for e in rep.get("push_back", []): print(e["ref_code"], e["ig_url"])' | \
            while read -r ref url; do
              if ssh -o ConnectTimeout=10 -o BatchMode=yes pro \
                   "cd ~/nuzantara && python3 scripts/wr2_queue_writer.py mark-published '$ref' '$url'" >>"$LOG" 2>&1; then
                echo "[$(ts)] pushed back $ref -> published on Pro" >> "$LOG"
              else
                echo "[$(ts)] WARN push-back $ref failed (state not publishable on Pro yet?)" >> "$LOG"
              fi
            done
          else
            # merge failed → keep old local file, log, fall back to nothing
            echo "[$(ts)] WARN merge of $f produced no output, kept old" >> "$LOG"
            rm -f "$tmp" "$tmp.merged"
          fi
        elif ! cmp -s "$tmp" "$DEST_DIR/$f" 2>/dev/null; then
          mv "$tmp" "$DEST_DIR/$f"
          echo "[$(ts)] updated $f" >> "$LOG"
        else
          rm -f "$tmp"   # no change
        fi
      else
        echo "[$(ts)] WARN $f pulled but invalid JSON, kept old" >> "$LOG"
        rm -f "$tmp"
      fi
    else
      echo "[$(ts)] WARN pull $f failed (Pro unreachable?)" >> "$LOG"
      rm -f "$tmp"
    fi
  done

  # Pull the latest REAL ig-insights amendment (the Insights view reads it). Exclude the
  # "insufficient-data" stubs. Take the newest by filename date.
  latest=$(ssh -o ConnectTimeout=10 -o BatchMode=yes pro \
    "ls -1 '$AMEND_SRC'/*-ig-insights.md 2>/dev/null | grep -v insufficient-data | sort | tail -1" 2>/dev/null)
  if [ -n "$latest" ]; then
    bn=$(basename "$latest")
    tmp="$AMEND_DEST/.$bn.pull.tmp.$$"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes pro "cat '$latest'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
      if ! cmp -s "$tmp" "$AMEND_DEST/$bn" 2>/dev/null; then
        mv "$tmp" "$AMEND_DEST/$bn"
        echo "[$(ts)] updated insights $bn" >> "$LOG"
      else
        rm -f "$tmp"
      fi
    else
      rm -f "$tmp"
    fi
  fi

  # Pull new carousel render dirs (PNGs) from Pro. Additive only:
  #  --ignore-existing  → never re-pull or overwrite a carousel M5 already has
  #  (no --delete)      → never remove M5-local carousels (M5 is a superset today)
  # So only carousels NEW on Pro land on M5; existing ones are untouched.
  # --ignore-errors: macOS tags some local carousel files with a com.apple.provenance
  # xattr (SIP-protected, cannot be stripped). Without this flag openrsync aborts
  # the ENTIRE batch on the first "open: Operation not permitted" it hits — and
  # there are dozens of tagged files scattered across the tree (not just one), so
  # a per-dir --exclude doesn't scale. --ignore-errors lets rsync skip the tagged
  # file and continue the rest of the batch (already-synced files are unaffected
  # by --ignore-existing regardless).
  iter_n=$((iter_n + 1))
  carousel_mode="$RSYNC_MODE"
  if [ "${WR2_PULL_CHECKSUM:-0}" != "1" ] && [ "$CHECKSUM_EVERY_N" -gt 0 ] \
       && [ $((iter_n % CHECKSUM_EVERY_N)) -eq 0 ]; then
    carousel_mode="--checksum"
    echo "[$(ts)] periodic checksum pass (iter $iter_n, every $CHECKSUM_EVERY_N) — checking for re-render-in-place drift" >> "$LOG"
  fi
  if rsync -a "$carousel_mode" --ignore-errors \
       -e "ssh -o ConnectTimeout=10 -o BatchMode=yes" \
       "pro:$CAROUSEL_SRC/" "$CAROUSEL_DEST/" >/dev/null 2>>"$LOG"; then
    : # silent on success (rsync is chatty enough on error)
  else
    echo "[$(ts)] WARN carousel rsync failed (Pro unreachable?)" >> "$LOG"
  fi

  if [ "$ONCE" = "1" ]; then
    echo "[$(ts)] one-shot pass done (mode $RSYNC_MODE), exiting" >> "$LOG"
    break
  fi
  sleep "$INTERVAL"
done
