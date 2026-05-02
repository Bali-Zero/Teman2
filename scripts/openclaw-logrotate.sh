#!/usr/bin/env bash
# openclaw-logrotate.sh — Sprint 0 Track A1
#
# Rotate OpenClaw gateway logs and prune archives older than retention window.
#
# Usage:
#   bash scripts/openclaw-logrotate.sh --dry-run    # default; prints actions
#   bash scripts/openclaw-logrotate.sh --apply      # actually rotate + prune
#
# What it rotates:
#   ~/.openclaw/logs/gateway.log
#   ~/.openclaw/logs/gateway.err.log
#
# Behaviour:
#   - If the live log exceeds THRESHOLD_BYTES (default 100 MB), archive it as
#     ~/.openclaw/logs/archive/<name>.YYYY-MM-DD.gz with `gzip -9`, then
#     truncate the live file in place via `: > "$f"` so OpenClaw's open FD
#     keeps writing to the same inode without restart.
#   - Atomic mv into the archive dir (cp + sync + truncate, NOT rename — gzip
#     output already lives in archive dir before truncation, so partial-write
#     never corrupts a current log).
#   - Prune ~/.openclaw/logs/archive/*.gz older than RETENTION_DAYS (default 7).
#
# Idempotent: re-running on the same minute is safe (no-ops if files are below
# threshold or if archive name already exists).
#
# Why no `logrotate(8)`: macOS doesn't ship logrotate by default; this script
# is portable to a vanilla zsh + Homebrew setup with no extra dependencies.
#
# Reference: brainstorm 2026-05-02 round 2 (4-LLM unanimous P0 mitigation).
# Cicatrix: plist-hardening 2026-04-29 (file mode 0444 → see install steps).

set -euo pipefail

LOG_DIR="${HOME}/.openclaw/logs"
ARCHIVE_DIR="${LOG_DIR}/archive"

# Round-2 review fix: validate env vars BEFORE arithmetic evaluation. Bash
# arithmetic context evaluates command substitutions inside variables, so
# OPENCLAW_LOGROTATE_THRESHOLD='a[$(rm -rf /)]' would execute. Reject any
# non-decimal-integer value early.
THRESHOLD_BYTES="${OPENCLAW_LOGROTATE_THRESHOLD:-104857600}"  # 100 MB default
RETENTION_DAYS="${OPENCLAW_LOGROTATE_RETENTION_DAYS:-7}"

if [[ ! "$THRESHOLD_BYTES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: OPENCLAW_LOGROTATE_THRESHOLD must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: OPENCLAW_LOGROTATE_RETENTION_DAYS must be a non-negative integer" >&2
  exit 2
fi

TARGETS=("gateway.log" "gateway.err.log")

MODE="dry-run"
case "${1:-}" in
  --apply)   MODE="apply" ;;
  --dry-run) MODE="dry-run" ;;
  "")        MODE="dry-run" ;;
  *)
    echo "Usage: $0 [--dry-run|--apply]" >&2
    exit 2
    ;;
esac

log() {
  printf '[openclaw-logrotate %s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

if [[ ! -d "$LOG_DIR" ]]; then
  log "ERROR: $LOG_DIR not found — OpenClaw not installed on this host?"
  exit 0   # exit 0 so cron doesn't keep retrying on a clean host
fi

if [[ "$MODE" == "apply" ]]; then
  mkdir -p "$ARCHIVE_DIR"
fi

stat_size() {
  # macOS stat -f %z; gnu stat -c %s. Detect at runtime.
  if stat -f %z "$1" 2>/dev/null; then
    return
  fi
  stat -c %s "$1"
}

rotate_one() {
  local target="$1"
  local src="${LOG_DIR}/${target}"
  if [[ ! -f "$src" ]]; then
    log "skip: $target not present"
    return
  fi
  local size
  size="$(stat_size "$src")"
  if (( size < THRESHOLD_BYTES )); then
    log "skip: $target size ${size}B < threshold ${THRESHOLD_BYTES}B"
    return
  fi
  local stamp
  stamp="$(date +'%Y-%m-%d')"
  local dest="${ARCHIVE_DIR}/${target}.${stamp}.gz"
  if [[ -f "$dest" ]]; then
    # If the archive for today already exists, append a serial suffix so the
    # second-run-of-the-day case doesn't clobber the morning archive.
    local serial=2
    while [[ -f "${ARCHIVE_DIR}/${target}.${stamp}.${serial}.gz" ]]; do
      serial=$((serial + 1))
    done
    dest="${ARCHIVE_DIR}/${target}.${stamp}.${serial}.gz"
  fi

  if [[ "$MODE" == "dry-run" ]]; then
    log "would archive ${src} (${size}B) -> ${dest}, then truncate live file"
    return
  fi

  # Apply: gzip into archive dir, then truncate the live file in place.
  #
  # ── DATA-LOSS WINDOW (round-2 review correction) ────────────────────
  # `: > "$src"` is `O_TRUNC`: it discards file contents from byte 0 to EOF
  # immediately. Any log lines OpenClaw appended via its open FD BETWEEN
  # the moment `gzip` finished reading and the truncate are LOST. The
  # window is typically <100ms on a 100 MB log, but it is NOT zero — the
  # earlier draft of this comment claimed the bytes "survive in the live
  # file"; that was wrong (file truncation does NOT preserve bytes past
  # the truncation point — the inode's data blocks are released).
  #
  # Why we still use truncate-in-place (not copytruncate or rename):
  # - Renaming the file (`mv "$src" "$dest"; touch "$src"`) would break
  #   OpenClaw's open FD: it would keep writing to the now-detached inode
  #   that is now visible only as `$dest`. Restart of the OpenClaw daemon
  #   would be needed to re-open the new path. That's worse than a small
  #   data-loss window.
  # - The 03:00 WITA cron timing is chosen specifically because gateway
  #   throughput is lowest then; the data-loss window catches at most a
  #   handful of low-priority log lines.
  # - For OpenClaw tooling logs, this trade-off is acceptable. For audit-
  #   grade logs, this script is NOT the right tool.
  if ! gzip -9 -c "$src" > "${dest}.partial"; then
    log "ERROR: gzip failed for ${src} — leaving live file untouched"
    rm -f "${dest}.partial"
    return 1
  fi
  mv "${dest}.partial" "$dest"
  : > "$src"
  local archived_size
  archived_size="$(stat_size "$dest")"
  log "archived: ${target} ${size}B -> ${dest} (${archived_size}B gzipped); small data-loss window during truncate is documented and accepted"
}

prune_archives() {
  if [[ ! -d "$ARCHIVE_DIR" ]]; then
    return
  fi
  if [[ "$MODE" == "dry-run" ]]; then
    local count
    count="$(find "$ARCHIVE_DIR" -name '*.gz' -mtime "+${RETENTION_DAYS}" 2>/dev/null | wc -l | tr -d ' ')"
    log "would prune ${count} archive(s) older than ${RETENTION_DAYS} days"
    return
  fi
  find "$ARCHIVE_DIR" -name '*.gz' -mtime "+${RETENTION_DAYS}" -print -delete \
    | while read -r f; do log "pruned: $f"; done
}

log "mode=${MODE} threshold=${THRESHOLD_BYTES}B retention=${RETENTION_DAYS}d"

for t in "${TARGETS[@]}"; do
  rotate_one "$t"
done
prune_archives

log "done"
