#!/bin/zsh
# Auto-download NLM artifacts (BZ business analysis IT) to Desktop when ready.
# Idempotent: writes a .done marker per artifact so it never re-downloads.
# Self-unloads its LaunchAgent once BOTH artifacts are on disk.
set -u

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NB="361fcb85-c5ee-41ee-9e35-0535ca9b2198"
VID_ART="d01a590b-e5d4-4c3f-9a09-0bf3cd57835f"
SLD_ART="36048596-076f-4b77-9ac4-3a8a55161fcd"
DESK="$HOME/Desktop"
STATE="$HOME/.local/state/bz-nlm-autodl"
LOG="$STATE/autodl.log"
LABEL="com.balizero.nlm-autodownload"
mkdir -p "$STATE"

log() { print "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

STATUS=$(nlm studio status "$NB" 2>&1)

# --- VIDEO ---
if [[ ! -f "$STATE/video.done" ]]; then
  if print -r -- "$STATUS" | grep -iA4 "$VID_ART" | grep -qiE "completed|ready|status.*: *2[^0-9]|\.mp4"; then
    OUT="$DESK/BZ-Analisi-Business-Gen-Giu-2026-CINEMATIC-IT.mp4"
    if nlm download video "$NB" --id "$VID_ART" -o "$OUT" --no-progress >> "$LOG" 2>&1 && [[ -s "$OUT" ]]; then
      touch "$STATE/video.done"; log "VIDEO downloaded -> $OUT ($(du -h "$OUT" | cut -f1))"
    else
      log "VIDEO download attempt failed (will retry next tick)"
    fi
  else
    log "video not ready yet"
  fi
fi

# --- SLIDES ---
if [[ ! -f "$STATE/slides.done" ]]; then
  if print -r -- "$STATUS" | grep -iA4 "$SLD_ART" | grep -qiE "completed|ready|status.*: *2[^0-9]|\.pdf"; then
    OUT="$DESK/BZ-Analisi-Business-Gen-Giu-2026-SLIDE-IT.pdf"
    if nlm download slide-deck "$NB" --id "$SLD_ART" -o "$OUT" >> "$LOG" 2>&1 && [[ -s "$OUT" ]]; then
      touch "$STATE/slides.done"; log "SLIDES downloaded -> $OUT ($(du -h "$OUT" | cut -f1))"
    else
      log "SLIDES download attempt failed (will retry next tick)"
    fi
  else
    log "slides not ready yet"
  fi
fi

# --- self-unload when both done ---
if [[ -f "$STATE/video.done" && -f "$STATE/slides.done" ]]; then
  log "BOTH artifacts on Desktop — unloading LaunchAgent $LABEL"
  /bin/launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || /bin/launchctl unload "$HOME/Library/LaunchAgents/$LABEL.plist" 2>/dev/null
fi
