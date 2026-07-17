#!/bin/bash
# pro.log_rotate — Copytruncate rotation for logs over 50MB under ~/logs (5-generation retention)
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/log-rotate-run.sh
# Live:  ~/scripts/log-rotate-run.sh (declared pair, node=pro)
#
# Why (PENDING-ARMS ledger 2026-07-17): Pro logs grow unrotated — supervisor.err
# 182M, cron-log-sentinel.log 122M, mata-garuda-kg-api.err 111M,
# translate-hourly.log 100M, all live, contributing to Pro disk at 94%. No
# size-based rotation existed on Pro (com.nuzantara.log-prune.daily is a
# Mini-only AGE-based deleter — declared machines:["mini"] in
# infra/home-fork/declared-pairs.json, script absent on Pro — no conflict).
#
# What: recursively finds every file >50MB under ~/logs (any depth — the two
# biggest offenders live in subdirs: logs/organism/supervisor.err,
# logs/cell/organism.stderr.log), gzips it into ~/logs/archive/ with a
# provenance-preserving name (subdir path folded into the archive filename so
# two same-named files in different subdirs never collide), then truncates
# the LIVE file in place (`: > file`, never rm/mv — processes hold the fd
# open across truncate; W92-class rule: never rm/mv a live file mid-write).
# Idempotent: a same-day re-run only acts on files that regrew past the
# threshold; a same-day archive-name collision falls back to an HHMMSS
# suffix instead of silently clobbering the earlier archive.

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.log_rotate"
LOG_DIR="$HOME/logs/pro-log-rotate"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-log-rotate.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    log "node guard: $(hostname -s) != nuzantara — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${PRO_LOG_ROTATE_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_LOG_ROTATE_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
log "run start"

THRESHOLD_MB="${PRO_LOG_ROTATE_THRESHOLD_MB:-50}"
RETENTION="${PRO_LOG_ROTATE_RETENTION:-5}"
ARCHIVE_DIR="$HOME/logs/archive"
mkdir -p "$ARCHIVE_DIR"
DATE_TAG="$(date +%Y%m%d)"
ROTATED=0
ERRORS=0

# Every file >50MB under ~/logs, any depth, excluding anything already inside
# an "archive" dir (never re-rotate a .gz archive or a nested archive/ dir).
while IFS= read -r -d '' f; do
    case "$f" in
        */archive/*) continue ;;
    esac

    # Fold the subdir path into the archive filename so cross-subdir
    # basename collisions (e.g. two different "organism.stderr.log") never
    # overwrite each other in the flat archive/ dir.
    relpath="${f#"$HOME/logs/"}"
    reldir="$(dirname "$relpath")"
    base="$(basename "$relpath")"
    if [ "$reldir" = "." ]; then
        archname="$base"
    else
        archname="${reldir//\//_}_${base}"
    fi

    dest="$ARCHIVE_DIR/${archname}-${DATE_TAG}.log.gz"
    # Idempotency guard: a same-day second rotation of the same file must
    # never silently clobber the first archive — disambiguate with HHMMSS.
    if [ -e "$dest" ]; then
        dest="$ARCHIVE_DIR/${archname}-${DATE_TAG}-$(date +%H%M%S).log.gz"
    fi

    if gzip -c "$f" > "${dest}.tmp" 2>>"$LOG"; then
        mv "${dest}.tmp" "$dest"
        : > "$f"   # copytruncate — never rm/mv the live file, the writer's fd stays valid
        log "rotated: $f -> archive/$(basename "$dest") ($(du -h "$dest" 2>/dev/null | cut -f1))"
        ROTATED=$((ROTATED + 1))
    else
        rm -f "${dest}.tmp"
        log "ERROR: gzip failed for $f"
        ERRORS=$((ERRORS + 1))
    fi
done < <(find "$HOME/logs" -type f -size "+${THRESHOLD_MB}M" -print0 2>/dev/null)

# Retention: keep only the newest N generations per archived name-prefix.
if [ -d "$ARCHIVE_DIR" ]; then
    find "$ARCHIVE_DIR" -maxdepth 1 -name "*.log.gz" -print 2>/dev/null \
        | sed -E 's#.*/##; s/-[0-9]{8}(-[0-9]{6})?\.log\.gz$//' \
        | sort -u \
        | while IFS= read -r prefix; do
            [ -z "$prefix" ] && continue
            ls -t "$ARCHIVE_DIR/${prefix}-"*.log.gz 2>/dev/null \
                | tail -n "+$((RETENTION + 1))" \
                | while IFS= read -r stale; do
                    [ -z "$stale" ] && continue
                    rm -f "$stale" && log "retention: pruned $(basename "$stale")"
                done
        done
fi

log "run summary: rotated=$ROTATED errors=$ERRORS threshold=${THRESHOLD_MB}M retention=${RETENTION}"
if [ "$ERRORS" -eq 0 ]; then
    heartbeat "ok" "rotated=$ROTATED errors=0"
else
    heartbeat "error" "rotated=$ROTATED errors=$ERRORS"
fi
log "run done rc=0"
exit 0
