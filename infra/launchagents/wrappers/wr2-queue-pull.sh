#!/bin/bash
# wr2-queue-pull.sh — keeps the M5 copy of the WR2 queue in sync with Pro (source of truth).
# The native WR2 Control.app polls this file from disk; this is the only thing that makes
# its view track Pro. Pull-only (M5 never writes back). Blocking loop (not KeepAlive-oneshot, scar #7).
# Lives OUTSIDE ~/Desktop (W84: launchd loses TCC grant on ~/Desktop).
set -uo pipefail
LOG="$HOME/logs/wr2-queue-pull.log"
DEST_DIR="$HOME/Desktop/nuzantara/apps/war-room/output/queue"
SRC_DIR="/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/queue"
# WR2 Insights: the analyst reasoning (real findings) lives only on Pro under the skill dir.
AMEND_DEST="$HOME/.claude/skills/bali-zero-brand/_proposed-amendments"
AMEND_SRC="/Users/nuzantara/.claude/skills/bali-zero-brand/_proposed-amendments"
# Carousel render PNGs — synced from Pro (the renderer) from now on, so new caroselli
# show their cover in the app. Pull-only, additive (never deletes M5-local carousels).
CAROUSEL_DEST="$HOME/Desktop/nuzantara/apps/war-room/output/carousel"
CAROUSEL_SRC="/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/carousel"
INTERVAL="${WR2_QUEUE_PULL_INTERVAL:-300}"
mkdir -p "$DEST_DIR" "$AMEND_DEST" "$CAROUSEL_DEST"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

while true; do
  for f in human-review-queue.json queue-archive.json; do
    tmp="$DEST_DIR/.$f.pull.tmp"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes pro "cat '$SRC_DIR/$f'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
      # valida JSON prima di sostituire (mai clobberare con spazzatura)
      if python3 -c "import json,sys; json.load(open('$tmp'))" 2>/dev/null; then
        if ! cmp -s "$tmp" "$DEST_DIR/$f" 2>/dev/null; then
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
    tmp="$AMEND_DEST/.$bn.pull.tmp"
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
  if rsync -a --ignore-existing --ignore-errors \
       -e "ssh -o ConnectTimeout=10 -o BatchMode=yes" \
       "pro:$CAROUSEL_SRC/" "$CAROUSEL_DEST/" >/dev/null 2>>"$LOG"; then
    : # silent on success (rsync is chatty enough on error)
  else
    echo "[$(ts)] WARN carousel rsync failed (Pro unreachable?)" >> "$LOG"
  fi

  sleep "$INTERVAL"
done
