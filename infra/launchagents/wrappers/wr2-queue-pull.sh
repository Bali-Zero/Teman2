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
# Multi-path Pro ssh fallback (scar family #8, network flap — 2026-07-17):
# Tailscale (`pro`) and mDNS (`pro-lan`) alternate dying independently — a
# burst on one leaves the other reachable, and which one is dead flips
# without warning. Space-separated (bash 3.2, NO arrays) list of ssh
# aliases tried in order every tick; override for testing/ops via
# WR2_PRO_SSH_HOSTS.
PRO_HOSTS="${WR2_PRO_SSH_HOSTS:-pro pro-lan}"
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

# Returns the first reachable alias from $PRO_HOSTS on stdout (exit 0), or
# exit 1 if none answer. Short probe (ConnectTimeout=5) — the actual work
# calls below keep ConnectTimeout=10.
pick_pro_host() {
  for h in $PRO_HOSTS; do
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$h" true 2>/dev/null && { echo "$h"; return 0; }
  done
  return 1
}

# LOW #8 (Codex red-team, 2026-07-16): a non-numeric/negative override made
# the `[ "$CHECKSUM_EVERY_N" -gt 0 ]` test below throw "integer expression
# expected" on EVERY iteration (nonzero `[` exit, so the periodic checksum
# feature silently disabled itself) instead of failing loud once at startup.
case "$CHECKSUM_EVERY_N" in
  ''|*[!0-9]*)
    echo "[$(ts)] WARN WR2_PULL_CHECKSUM_EVERY_N='$CHECKSUM_EVERY_N' is not a non-negative integer — falling back to default 12" >> "$LOG"
    CHECKSUM_EVERY_N=12
    ;;
esac

# Merge helper (split-brain cure, 2026-07-13): the WR2 Control app writes
# publish transitions LOCALLY (QueueWriter.markPublished) and a blind replace
# reverted them within one poll cycle. The merge keeps Pro as SSOT but protects
# local published* entries and emits a push-back list replayed into Pro via the
# canonical wr2_queue_writer.py (exact ref-code, IG-URL validated writer-side).
MERGE_PY="$HOME/nuzantara/scripts/wr2_queue_pull_merge.py"

last_pro_host=""

while true; do
  # Pick a reachable Pro host THIS tick (scar #8) before any remote call.
  # Empty result: log ONE line and skip the whole tick (no per-call WARN
  # spam from every ssh/rsync below failing individually).
  PRO_HOST=$(pick_pro_host)
  if [ -z "$PRO_HOST" ]; then
    echo "[$(ts)] WARN no reachable Pro host this tick (tried: $PRO_HOSTS)" >> "$LOG"
    [ "$ONCE" = "1" ] && break
    sleep "$INTERVAL"
    continue
  fi
  if [ "$PRO_HOST" != "$last_pro_host" ]; then
    echo "[$(ts)] Pro host: $PRO_HOST (was: ${last_pro_host:-none})" >> "$LOG"
    last_pro_host="$PRO_HOST"
  fi

  # queue-archive.json pulled FIRST (2026-07-17, archive-blind resurrect fix):
  # the human-review-queue.json merge below needs THIS SAME iteration's fresh
  # archive to tell "archived on Pro" apart from "genuinely new local entry" —
  # a stale on-disk archive from last tick would resurrect an archived entry
  # for up to one more interval every time. archive_tmp is kept alive (not
  # rm'd) until the queue merge below has consumed it.
  archive_tmp=""
  archive_f="queue-archive.json"
  tmp="$DEST_DIR/.$archive_f.pull.tmp.$$"
  if ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" "cat '$SRC_DIR/$archive_f'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    if python3 -c "import json,sys; json.load(open('$tmp'))" 2>/dev/null; then
      archive_tmp="$tmp"
      if ! cmp -s "$tmp" "$DEST_DIR/$archive_f" 2>/dev/null; then
        # atomic swap (Codex red-team, 2026-07-17): a plain `cp` truncated by
        # a concurrent read or interrupted mid-write would still log
        # "updated" here and lose the good temp at end of tick — cp into a
        # sibling tmp then rename so the mirror is never observed partial.
        if cp "$tmp" "$DEST_DIR/$archive_f.tmp.$$" && mv "$DEST_DIR/$archive_f.tmp.$$" "$DEST_DIR/$archive_f"; then
          echo "[$(ts)] updated $archive_f" >> "$LOG"
        else
          echo "[$(ts)] WARN failed to atomically update $archive_f mirror, kept old" >> "$LOG"
          rm -f "$DEST_DIR/$archive_f.tmp.$$"
        fi
      fi
    else
      echo "[$(ts)] WARN $archive_f pulled but invalid JSON, kept old" >> "$LOG"
      rm -f "$tmp"
    fi
  else
    echo "[$(ts)] WARN pull $archive_f failed (Pro unreachable?)" >> "$LOG"
    rm -f "$tmp"
  fi

  f="human-review-queue.json"
  # PID-suffixed tmp: a WR2_PULL_CHECKSUM one-shot may run while the daemon
  # loop is live — a shared deterministic tmp path would interleave writes.
  tmp="$DEST_DIR/.$f.pull.tmp.$$"
  if ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" "cat '$SRC_DIR/$f'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    # valida JSON prima di sostituire (mai clobberare con spazzatura)
    if python3 -c "import json,sys; json.load(open('$tmp'))" 2>/dev/null; then
      if [ -f "$MERGE_PY" ] && [ -f "$DEST_DIR/$f" ]; then
        # merge instead of clobber: local publish transitions survive the pull.
        # NOTE: no bash arrays here — macOS ships bash 3.2, where an empty
        # array expanded as "${arr[@]}" under `set -u` throws "unbound
        # variable" (verified live), which would crash this loop every tick
        # the archive pull fails/is skipped.
        #
        # rm -f "$tmp.merged" FIRST (Codex red-team, 2026-07-17): the daemon
        # keeps the same PID (and thus the same $tmp path) across every tick
        # of this loop — a merge that failed mid-write on a PRIOR tick can
        # leave a stale non-empty .merged file that a LATER failed merge
        # (one that crashes before writing --out at all) would otherwise
        # re-install via the `[ -s "$tmp.merged" ]` check below, believing
        # it to be this tick's fresh output.
        rm -f "$tmp.merged"
        if [ -n "$archive_tmp" ]; then
          report=$(python3 "$MERGE_PY" --remote "$tmp" --local "$DEST_DIR/$f" --out "$tmp.merged" --remote-archive "$archive_tmp" 2>>"$LOG")
        else
          report=$(python3 "$MERGE_PY" --remote "$tmp" --local "$DEST_DIR/$f" --out "$tmp.merged" 2>>"$LOG")
        fi
        merge_rc=$?
        # gate on BOTH exit code 0 AND re-parseable JSON (Codex red-team,
        # 2026-07-17): ENOSPC mid-write can leave a partial-but-non-empty
        # JSON file that `[ -s ... ]` alone would accept — the next tick
        # would then treat the corrupt local queue as [] and wipe every
        # local-only entry.
        if [ "$merge_rc" -eq 0 ] && [ -s "$tmp.merged" ] \
             && python3 -c "import json,sys; json.load(open('$tmp.merged'))" 2>/dev/null; then
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
            if ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" \
                 "cd ~/nuzantara && python3 scripts/wr2_queue_writer.py mark-published '$ref' '$url'" >>"$LOG" 2>&1; then
              echo "[$(ts)] pushed back $ref -> published on Pro" >> "$LOG"
            else
              echo "[$(ts)] WARN push-back $ref failed (state not publishable on Pro yet?)" >> "$LOG"
            fi
          done
          # push external-manual entries back to Pro (§A/§B external-post feature,
          # 2026-07-17): each is a FULL JSON payload with operator-typed free-text
          # fields (topic/slug) — unlike ref/url above these are NOT regex-constrained,
          # so they must NEVER be shell-interpolated into the ssh command string (an
          # apostrophe in "Zero's post" would break a naive '$payload' embedding —
          # scar-family #3, substring-safety mistaken for shell-safety). Instead each
          # compact JSON line is piped over ssh's OWN stdin channel and the remote
          # reads it back with `"$(cat)"` — the payload never appears literally in any
          # shell command text on either side.
          echo "$report" | python3 -c 'import json,sys
try: rep=json.load(sys.stdin)
except Exception: rep={}
for e in rep.get("push_back_external", []):
    print(json.dumps(e, ensure_ascii=False))' | \
          while IFS= read -r payload_json; do
            item_id=$(printf '%s' "$payload_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("item_id","") or "")' 2>/dev/null)
            if [ -z "$item_id" ]; then
              echo "[$(ts)] WARN push-back-external: entry with no item_id, skipping" >> "$LOG"
              continue
            fi
            if printf '%s' "$payload_json" | ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" \
                 "cd ~/nuzantara && python3 scripts/wr2_queue_writer.py add-external \"\$(cat)\"" >>"$LOG" 2>&1; then
              # Pro confirmed the entry exists (added now OR already_present from a
              # prior retry — both are terminal success) — mark the LOCAL copy so
              # external_push_candidates never re-offers it (idempotent replay-safety).
              if python3 "$MERGE_PY" --mark-synced-item-id "$item_id" --mark-synced-file "$DEST_DIR/$f" >>"$LOG" 2>&1; then
                echo "[$(ts)] pushed back external $item_id -> Pro, marked synced_to_pro" >> "$LOG"
              else
                echo "[$(ts)] WARN pushed back external $item_id but failed to mark synced_to_pro locally (will retry next cycle)" >> "$LOG"
              fi
            else
              echo "[$(ts)] WARN push-back-external $item_id failed (ssh/add-external error, will retry next cycle)" >> "$LOG"
            fi
          done
        else
          # merge failed (rc) or produced empty/invalid output → keep old
          # local file, log, wipe both tmps.
          echo "[$(ts)] WARN merge of $f failed or produced invalid output (rc=$merge_rc), kept old" >> "$LOG"
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
  rm -f "$archive_tmp"

  # Pull the latest REAL ig-insights amendment (the Insights view reads it). Exclude the
  # "insufficient-data" stubs. Take the newest by filename date.
  latest=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" \
    "ls -1 '$AMEND_SRC'/*-ig-insights.md 2>/dev/null | grep -v insufficient-data | sort | tail -1" 2>/dev/null)
  if [ -n "$latest" ]; then
    bn=$(basename "$latest")
    tmp="$AMEND_DEST/.$bn.pull.tmp.$$"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$PRO_HOST" "cat '$latest'" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
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
  # LOW #8 (Codex red-team, 2026-07-16, comment corrected): --ignore-errors does
  # NOT make the batch "succeed" when files are skipped — rsync still exits
  # nonzero (23 = some file(s)/attrs could not be transferred; 24 = a source
  # file vanished mid-transfer, e.g. a concurrent render). Those two codes are
  # the EXPECTED/tolerated shape of "protected file skipped, rest of batch
  # continued", distinct from "Pro unreachable" — handled explicitly below.
  iter_n=$((iter_n + 1))
  carousel_mode="$RSYNC_MODE"
  if [ "${WR2_PULL_CHECKSUM:-0}" != "1" ] && [ "$CHECKSUM_EVERY_N" -gt 0 ] \
       && [ $((iter_n % CHECKSUM_EVERY_N)) -eq 0 ]; then
    carousel_mode="--checksum"
    echo "[$(ts)] periodic checksum pass (iter $iter_n, every $CHECKSUM_EVERY_N) — checking for re-render-in-place drift" >> "$LOG"
  fi
  if rsync -a "$carousel_mode" --ignore-errors \
       -e "ssh -o ConnectTimeout=10 -o BatchMode=yes" \
       "$PRO_HOST:$CAROUSEL_SRC/" "$CAROUSEL_DEST/" >/dev/null 2>>"$LOG"; then
    : # silent on success (rsync is chatty enough on error)
  else
    rsync_rc=$?
    if [ "$rsync_rc" = "23" ] || [ "$rsync_rc" = "24" ]; then
      # tolerated: protected/vanished files skipped, rest of the batch
      # continued (see the --ignore-errors comment above) — not "Pro
      # unreachable", so log quietly instead of alarming.
      echo "[$(ts)] carousel rsync rc=$rsync_rc (partial: protected/vanished files skipped, batch continued)" >> "$LOG"
    else
      echo "[$(ts)] WARN carousel rsync failed rc=$rsync_rc (Pro unreachable?)" >> "$LOG"
    fi
  fi

  if [ "$ONCE" = "1" ]; then
    echo "[$(ts)] one-shot pass done (mode $RSYNC_MODE), exiting" >> "$LOG"
    break
  fi
  sleep "$INTERVAL"
done
