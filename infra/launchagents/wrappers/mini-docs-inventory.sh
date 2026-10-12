#!/bin/bash
# mini.docs_inventory_refresh — twice-daily volatile documentation bundle.
# Canon: infra/launchagents/wrappers/mini-docs-inventory.sh
# Live:  ~/scripts/mini-docs-inventory.sh (declared pair, node=mini)

set -u
umask 077

ORGAN_ID="mini.docs_inventory_refresh"
REPO="${MINI_DOCS_INVENTORY_REPO:-$HOME/nuzantara}"
GIT_BIN="${MINI_DOCS_INVENTORY_GIT:-/usr/bin/git}"
PYTHON_BIN="${MINI_DOCS_INVENTORY_PYTHON:-/opt/homebrew/bin/python3}"
HOSTNAME_BIN="${MINI_DOCS_INVENTORY_HOSTNAME:-/bin/hostname}"
GATEWAY="$REPO/scripts/tg_notify.py"
LOG_DIR="${MINI_DOCS_INVENTORY_LOG_DIR:-$HOME/logs/mini-docs-inventory}"
LOG="$LOG_DIR/run.log"
SIDECAR_DIR="${MINI_DOCS_INVENTORY_SIDECAR_DIR:-$HOME/.organism/last_seen}"
STATE_DIR="${MINI_DOCS_INVENTORY_STATE_DIR:-$HOME/.local/state/nuzantara/docs-derived-state}"
LOCKDIR="${MINI_DOCS_INVENTORY_LOCKDIR:-/tmp/nuzantara-mini-docs_inventory.lock}"
TMP_BASE="${MINI_DOCS_INVENTORY_TMP_BASE:-${TMPDIR:-$HOME/.cache}/mini-docs-inventory}"
PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

mkdir -p "$LOG_DIR" "$SIDECAR_DIR" "$STATE_DIR" "$TMP_BASE"
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }
# shellcheck disable=SC2329 # invoked by the EXIT-trap handler
heartbeat() {
    local tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    if printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$tmp" \
        && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json"; then
        return 0
    fi
    rm -f "$tmp"
    return 1
}
# shellcheck disable=SC2329 # invoked by the EXIT-trap handler
notify() {
    TG_ACT_ROUTING_ENABLED=false TG_RELAY_SSH='' /usr/bin/python3 "$GATEWAY" \
        --tier digest --source docs-inventory --dedup-key "$1" -- "$2" >> "$LOG" 2>&1
}

FINISHED=0
FINAL_STATUS="error"
FINAL_NOTE="inventory broken unexpected"
FAIL_KIND="unexpected"
ALERT=1
RUN_TMP=""
WORKTREE=""
BUNDLE=""
PUBLISHED=0
LOCK_HELD=0

# shellcheck disable=SC2329 # invoked by the EXIT trap
on_exit() {
    local rc=$?
    local cleanup_failed=0
    if [ -n "$WORKTREE" ]; then
        "$GIT_BIN" -C "$REPO" worktree remove --force "$WORKTREE" >> "$LOG" 2>&1 \
            || cleanup_failed=1
        "$GIT_BIN" -C "$REPO" worktree prune >> "$LOG" 2>&1 \
            || cleanup_failed=1
    fi
    [ -z "$RUN_TMP" ] || rm -rf "$RUN_TMP"
    if [ -n "$BUNDLE" ] && [ "$PUBLISHED" -ne 1 ]; then
        rm -rf "$BUNDLE"
    fi
    if [ "$FINISHED" -ne 1 ]; then
        FINAL_STATUS="error"
        FINAL_NOTE="inventory broken rc=$rc"
        FAIL_KIND="unexpected"
        ALERT=1
    elif [ "$cleanup_failed" -ne 0 ] && [ "$FINAL_STATUS" = "ok" ]; then
        FINAL_STATUS="error"
        FINAL_NOTE="inventory broken worktree-cleanup"
        FAIL_KIND="worktree-cleanup"
        ALERT=1
    fi
    heartbeat "$FINAL_STATUS" "$FINAL_NOTE" || true
    if [ "$ALERT" -eq 1 ]; then
        notify "docs-inventory:broken:$FAIL_KIND" "$FINAL_NOTE" \
            || log "broken alert failed or spooled"
    fi
    [ "$LOCK_HELD" -ne 1 ] || rm -rf "$LOCKDIR"
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

finish() {
    FINISHED=1
    FINAL_STATUS="$1"
    FINAL_NOTE="$2"
    FAIL_KIND="${3:-none}"
    ALERT="${4:-0}"
    exit 0
}

NODE="$($HOSTNAME_BIN -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
if [ "$NODE" != "mini-pro2" ]; then
    log "node guard: wrong node"
    finish "disabled" "wrong-node $NODE"
fi
if [ "${MINI_DOCS_INVENTORY_ENABLED:-true}" = "false" ]; then
    log "kill switch enabled"
    finish "disabled" "kill switch"
fi

if ! mkdir "$LOCKDIR" 2>/dev/null; then
    owner=$(cat "$LOCKDIR/pid" 2>/dev/null || true)
    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null \
        && ps -p "$owner" -o command= 2>/dev/null | grep -q "mini-docs-inventory.sh"; then
        # perl, not stat: BSD `stat -f %m` and GNU `stat -c %Y` disagree.
        mtime=$(/usr/bin/perl -e 'my @s = stat shift; print @s ? $s[9] : time' "$LOCKDIR" 2>/dev/null)
        case "$mtime" in ''|*[!0-9]*) mtime=$(date +%s) ;; esac
        age=$(( $(date +%s) - mtime ))
        if [ "$age" -lt 7200 ]; then
            finish "ok" "inventory already running"
        else
            finish "warning" "previous run alive for ${age}s"
        fi
    fi
    rm -rf "$LOCKDIR"
    mkdir "$LOCKDIR" 2>/dev/null || finish "error" "inventory broken lock" "lock" 1
fi
LOCK_HELD=1
echo $$ > "$LOCKDIR/pid"

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
    >> "$LOG" 2>&1; then
    finish "error" "inventory broken python-version" "python-version" 1
fi

RUN_TMP=$(mktemp -d "$TMP_BASE/run.XXXXXX") \
    || finish "error" "inventory broken tempdir" "tempdir" 1
WORKTREE="$RUN_TMP/worktree"
if ! "$GIT_BIN" -C "$REPO" worktree add --detach "$WORKTREE" refs/heads/main >> "$LOG" 2>&1; then
    finish "error" "inventory broken worktree-add" "worktree-add" 1
fi

SHORT_SHA="$($GIT_BIN -C "$WORKTREE" rev-parse --short HEAD 2>> "$LOG")" \
    || finish "error" "inventory broken revision" "revision" 1
BUNDLE="$STATE_DIR/$(date -u +%Y-%m-%dT%H%M)-$SHORT_SHA"
mkdir "$BUNDLE" 2>> "$LOG" \
    || finish "error" "inventory broken output-dir" "output-dir" 1

# Bounded: a hung regen would otherwise hold the lock and read only "warning" twice a day.
REGEN_TIMEOUT="${MINI_DOCS_INVENTORY_REGEN_TIMEOUT:-1800}"
REGEN_RC=0
(cd "$WORKTREE" && DOCS_DERIVED_OUTPUT_DIR="$BUNDLE" /usr/bin/perl -e 'alarm shift; exec @ARGV' \
    "$REGEN_TIMEOUT" bash scripts/docs_inventory_regen.sh --organ) >> "$LOG" 2>&1 || REGEN_RC=$?
if [ "$REGEN_RC" -eq 142 ]; then
    finish "error" "inventory broken regen timed out after ${REGEN_TIMEOUT} s" "regen-timeout" 1
elif [ "$REGEN_RC" -ne 0 ]; then
    finish "error" "inventory broken regen rc=$REGEN_RC" "regen" 1
fi

for name in docs-sync.json docs-audit.json DOCS_INVENTORY.md; do
    if [ ! -s "$BUNDLE/$name" ]; then
        finish "error" "inventory broken payload-$name" "payload" 1
    fi
done

TEMP_LINK="$STATE_DIR/.latest.$$"
rm -f "$TEMP_LINK"
ln -s "$BUNDLE" "$TEMP_LINK" \
    || finish "error" "inventory broken latest-link" "latest-link" 1
if [ "$(uname -s)" = "Darwin" ]; then
    mv -fh "$TEMP_LINK" "$STATE_DIR/latest" \
        || finish "error" "inventory broken latest-move" "latest-link" 1
else
    mv -fT "$TEMP_LINK" "$STATE_DIR/latest" \
        || finish "error" "inventory broken latest-move" "latest-link" 1
fi
PUBLISHED=1

LATEST_TARGET=$(readlink "$STATE_DIR/latest" 2>/dev/null || true)
find "$STATE_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -print | \
while IFS= read -r old_bundle; do
    [ "$old_bundle" = "$LATEST_TARGET" ] || rm -rf "$old_bundle"
done

log "run done sha=$SHORT_SHA"
finish "ok" "inventory $SHORT_SHA"
