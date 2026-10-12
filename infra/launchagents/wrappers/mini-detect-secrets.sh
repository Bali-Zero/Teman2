#!/bin/bash
# mini.detect_secrets_fulltree — daily read-only report from a detached main worktree.
set -u
umask 077

ORGAN_ID="mini.detect_secrets_fulltree"
REPO="${MINI_DETECT_SECRETS_REPO:-$HOME/nuzantara}"
GIT_BIN="${MINI_DETECT_SECRETS_GIT:-/usr/bin/git}"
PYTHON_BIN="${MINI_DETECT_SECRETS_PYTHON:-/opt/homebrew/bin/python3}"
HOSTNAME_BIN="${MINI_DETECT_SECRETS_HOSTNAME:-/bin/hostname}"
VENV="${MINI_DETECT_SECRETS_VENV:-$HOME/.local/share/nuzantara/detect-secrets-venv}"
LOG_DIR="${MINI_DETECT_SECRETS_LOG_DIR:-$HOME/logs/mini-detect-secrets}"
SIDECAR_DIR="${MINI_DETECT_SECRETS_SIDECAR_DIR:-$HOME/.organism/last_seen}"
LOCKDIR="${MINI_DETECT_SECRETS_LOCKDIR:-/tmp/nuzantara-mini-detect-secrets.lock}"
TMP_BASE="${MINI_DETECT_SECRETS_TMP_BASE:-${TMPDIR:-$HOME/.cache}/mini-detect-secrets}"
LOG="$LOG_DIR/run.log"
GATEWAY="$REPO/scripts/tg_notify.py"
PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

mkdir -p "$LOG_DIR" "$SIDECAR_DIR" "$TMP_BASE"
touch "$LOG"
if [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then mv -f "$LOG" "$LOG.1"; fi
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
heartbeat() {
    local tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$tmp" \
        && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json"
}
notify() {
    TG_ACT_ROUTING_ENABLED=false TG_RELAY_SSH='' "$PYTHON_BIN" "$GATEWAY" \
        --tier p0 --source detect-secrets --dedup-key "$1" -- "$2" >> "$LOG" 2>&1
}

FINISHED=0 FINAL_STATUS=error FINAL_NOTE="fulltree broken unexpected" FAIL_KIND=unexpected ALERT=1
RUN_TMP="" WORKTREE="" CHILD_PID="" LOCK_HELD=0
finish() { FINISHED=1; FINAL_STATUS="$1"; FINAL_NOTE="$2"; FAIL_KIND="${3:-none}"; ALERT="${4:-0}"; exit 0; }
stop_child() {
    local pid="$CHILD_PID"
    [ -n "$pid" ] || return 0
    CHILD_PID=""
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}
on_exit() {
    local rc=$? cleanup_failed=0
    stop_child
    if [ -n "$WORKTREE" ]; then
        "$GIT_BIN" -C "$REPO" worktree remove --force "$WORKTREE" >> "$LOG" 2>&1 || cleanup_failed=1
        "$GIT_BIN" -C "$REPO" worktree prune >> "$LOG" 2>&1 || cleanup_failed=1
    fi
    [ -z "$RUN_TMP" ] || rm -rf "$RUN_TMP"
    if [ "$FINISHED" -ne 1 ]; then
        FINAL_STATUS=error; FINAL_NOTE="fulltree broken rc=$rc"; FAIL_KIND=unexpected; ALERT=1
    fi
    if [ "$cleanup_failed" -ne 0 ]; then
        FINAL_STATUS=error; FINAL_NOTE="fulltree broken worktree cleanup"; FAIL_KIND=worktree; ALERT=1
    fi
    heartbeat "$FINAL_STATUS" "$FINAL_NOTE" || true
    [ "$ALERT" -ne 1 ] || notify "detect-secrets:broken:$FAIL_KIND" "$FINAL_NOTE" || log "alert failed or spooled"
    [ "$LOCK_HELD" -ne 1 ] || rm -rf "$LOCKDIR"
}
on_signal() {
    FINISHED=1; FINAL_STATUS=error; FINAL_NOTE="fulltree broken signal"; FAIL_KIND=signal; ALERT=1
    stop_child
    exit "$1"
}
trap on_exit EXIT
trap 'on_signal 143' TERM
trap 'on_signal 130' INT
trap 'on_signal 129' HUP

NODE="$($HOSTNAME_BIN -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
[ "$NODE" = mini-pro2 ] || finish disabled "wrong-node $NODE"
[ "${MINI_DETECT_SECRETS_ENABLED:-true}" != false ] || finish disabled "kill switch"

if ! mkdir "$LOCKDIR" 2>/dev/null; then
    owner=$(sed -n '1p' "$LOCKDIR/pid" 2>/dev/null || true)
    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null \
        && ps -p "$owner" -o command= 2>/dev/null | grep -q 'mini-detect-secrets.sh'; then
        mtime=$(/usr/bin/perl -e 'my @s=stat shift; print @s ? $s[9] : time' "$LOCKDIR" 2>/dev/null)
        case "$mtime" in ''|*[!0-9]*) mtime=$(date +%s) ;; esac
        age=$(( $(date +%s) - mtime ))
        [ "$age" -lt 7200 ] && finish ok "fulltree already running"
        finish warning "fulltree previous run alive ${age}s"
    fi
    rm -rf "$LOCKDIR"
    mkdir "$LOCKDIR" 2>/dev/null || finish error "fulltree broken lock" lock 1
fi
LOCK_HELD=1
printf '%s\n' $$ > "$LOCKDIR/pid"
for stale in "$TMP_BASE"/run.*; do
    [ -d "$stale" ] || continue
    "$GIT_BIN" -C "$REPO" worktree remove --force "$stale/worktree" >> "$LOG" 2>&1 || true
    rm -rf "$stale"
    log "removed stale run dir ${stale##*/}"
done
"$GIT_BIN" -C "$REPO" worktree prune >> "$LOG" 2>&1 || true

RUN_TMP=$(mktemp -d "$TMP_BASE/run.XXXXXX") || finish error "fulltree broken worktree tempdir" worktree 1
WORKTREE="$RUN_TMP/worktree"
"$GIT_BIN" -C "$REPO" worktree add --detach "$WORKTREE" refs/heads/main >> "$LOG" 2>&1 \
    || finish error "fulltree broken worktree add" worktree 1
SHORT_SHA="$($GIT_BIN -C "$WORKTREE" rev-parse --short HEAD 2>> "$LOG")" \
    || finish error "fulltree broken worktree revision" worktree 1
VERSION="$($PYTHON_BIN -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$WORKTREE/.secrets.baseline" 2>/dev/null)" \
    || finish error "fulltree broken tool baseline-version" tool 1
# The version reaches the heartbeat JSON and the alert: digits and dots only.
case "$VERSION" in ''|*[!0-9.]*) finish error "fulltree broken tool baseline-version" tool 1 ;; esac
SCAN_BIN="$VENV/bin/detect-secrets"
INSTALL="$HOME/.local/bin/uv venv --python /opt/homebrew/bin/python3 $VENV && $HOME/.local/bin/uv pip install --python $VENV/bin/python detect-secrets==$VERSION"
if [ ! -x "$SCAN_BIN" ]; then finish error "fulltree broken tool; install: $INSTALL" tool 1; fi
TOOL_VERSION="$($SCAN_BIN --version 2>/dev/null | awk 'END {print $NF}')"
if [ "$TOOL_VERSION" != "$VERSION" ]; then finish error "fulltree broken tool version; install: $INSTALL" tool 1; fi

BOUND="${MINI_DETECT_SECRETS_TIMEOUT:-3600}"
case "$BOUND" in ''|*[!0-9]*|0*) log "timeout is not a positive integer; using 3600"; BOUND=3600 ;; esac
SCAN_RC=0
(cd "$WORKTREE" && exec /usr/bin/perl -e '
    my ($t,$pid)=(shift,0); my $stop=sub { if($pid){ kill "TERM",-$pid; kill "TERM",$pid; sleep 2; kill "KILL",-$pid; kill "KILL",$pid; waitpid($pid,0) } exit shift };
    @SIG{qw(ALRM TERM INT HUP)}=(sub{$stop->(142)},sub{$stop->(143)},sub{$stop->(130)},sub{$stop->(129)});
    $pid=fork; die "fork: $!" unless defined $pid;
    if(!$pid){ @SIG{qw(ALRM TERM INT HUP)}=("DEFAULT") x 4; setpgrp(0,0); exec @ARGV or exit 127 }
    setpgrp($pid,$pid); alarm $t; waitpid($pid,0); exit(($?&127) ? 128+($?&127) : $?>>8);
' "$BOUND" /bin/bash -c '
    scan=$1; py=$2
    "$scan" scan --baseline .secrets.baseline --exclude-files "node_modules/.*" --exclude-files "\.venv/.*" --exclude-files "venv/.*" --exclude-files "\.git/.*" >/dev/null 2>&1 || exit 20
    "$py" scripts/detect_secrets_auto_triage.py --apply >/dev/null 2>&1 || exit 21
    "$py" scripts/detect_secrets_auto_triage.py --report >/dev/null 2>&1 || exit 22
    "$py" scripts/detect_secrets_check_unaudited.py >/dev/null 2>&1; rc=$?
    [ "$rc" -eq 0 ] && exit 0; [ "$rc" -eq 1 ] && exit 10; exit 23
' _ "$SCAN_BIN" "$PYTHON_BIN") &
CHILD_PID=$!
wait "$CHILD_PID" || SCAN_RC=$?
CHILD_PID=""

case "$SCAN_RC" in
    142) finish error "fulltree broken bound ${BOUND}s" bound 1 ;;
    20) finish error "fulltree broken scan" scan 1 ;;
    21|22) finish error "fulltree broken triage" triage 1 ;;
    23) finish error "fulltree broken gate" gate 1 ;;
    0|10) ;;
    *) finish error "fulltree broken scan rc=$SCAN_RC" scan 1 ;;
esac

# At most 30 paths: a mass-residue page must stay under Telegram's 4096-character limit, or the
# gateway records the dedup key for a message Telegram rejected.
"$PYTHON_BIN" -c 'import hashlib,json,re,sys
b=json.load(open(sys.argv[1])); rows=sorted({(f,str(h.get("type","?")),int(h.get("line_number",0))) for f,hs in b.get("results",{}).items() for h in hs if "is_secret" not in h})
files=sorted({r[0] for r in rows}); raw=json.dumps(rows,ensure_ascii=True,separators=(",",":")).encode(); digest=hashlib.sha256(raw).hexdigest()[:12]
def safe_path(path):
    parts=re.split(r"([/\\\\])",path)
    return "".join("<redacted>" if any(ord(c)<32 or ord(c)==127 for c in p) or re.search(r"[A-Za-z0-9_+=-]{24,}",p) else p for p in parts)
shown=[safe_path(f) for f in files[:30]]+([f"... and {len(files)-30} more file(s)"] if len(files)>30 else [])
open(sys.argv[2],"w").write(f"{digest} {len(rows)}\n"); open(sys.argv[3],"w").write(f"{len(rows)} finding(s) in {len(files)} file(s):\n"+"\n".join(shown)+"\n")' \
    "$WORKTREE/.secrets.baseline" "$RUN_TMP/meta" "$RUN_TMP/summary" \
    || finish error "fulltree broken gate metadata" gate 1
read -r FINDING_HASH FINDING_COUNT < "$RUN_TMP/meta"
if [ "$SCAN_RC" -eq 0 ] && [ "$FINDING_COUNT" -eq 0 ]; then
    log "fulltree clean $SHORT_SHA"
    finish ok "fulltree clean $SHORT_SHA"
fi
if [ "$SCAN_RC" -eq 10 ] && [ "$FINDING_COUNT" -gt 0 ]; then
    SUMMARY=$(<"$RUN_TMP/summary")
    log "$SUMMARY"
    notify "detect-secrets:findings:$FINDING_HASH" "$SUMMARY" || log "findings alert failed or spooled"
    finish warning "fulltree findings $FINDING_COUNT $SHORT_SHA"
fi
finish error "fulltree broken gate inconsistent" gate 1
