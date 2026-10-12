#!/bin/bash
set -u

PASS=0 FAIL=0 CANON_OK=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$ROOT/infra/launchagents/wrappers/mini-detect-secrets.sh"
SUITE="$(mktemp -d)"
FAKE_VALUE="FAKE_SECRET_SHAPED_VALUE_DO_NOT_USE_000000000000"
trap 'rm -rf "$SUITE"' EXIT
ok() { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
field() { sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p" "$1"; }
worktrees() { /usr/bin/git -C "$CASE_REPO" worktree list --porcelain | grep -c '^worktree '; }

setup_case() {
    CASE_DIR="$(mktemp -d "$SUITE/case.XXXXXX")"; CASE_HOME="$CASE_DIR/home"; CASE_REPO="$CASE_DIR/repo"
    mkdir -p "$CASE_HOME" "$CASE_REPO/scripts" "$CASE_DIR/bin" "$CASE_DIR/venv/bin"
    /usr/bin/git -C "$CASE_REPO" init -q -b main
    /usr/bin/git -C "$CASE_REPO" config user.email test@example.invalid
    /usr/bin/git -C "$CASE_REPO" config user.name "Detect secrets test"
    printf '{"version":"1.5.0","results":{}}\n' > "$CASE_REPO/.secrets.baseline"
    cat > "$CASE_REPO/scripts/detect_secrets_auto_triage.py" <<'PY'
#!/usr/bin/env python3
raise SystemExit(0)
PY
    cat > "$CASE_REPO/scripts/detect_secrets_check_unaudited.py" <<'PY'
#!/usr/bin/env python3
import json
b=json.load(open('.secrets.baseline'))
raise SystemExit(any('is_secret' not in h for hs in b.get('results',{}).values() for h in hs))
PY
    cat > "$CASE_REPO/scripts/tg_notify.py" <<'PY'
import json,os,sys
with open(os.path.join(os.environ['HOME'],'notify.log'),'a') as f:
    f.write(json.dumps({'routing':os.environ.get('TG_ACT_ROUTING_ENABLED'),'relay':os.environ.get('TG_RELAY_SSH'),'args':sys.argv[1:]})+'\n')
PY
    /usr/bin/git -C "$CASE_REPO" add . && /usr/bin/git -C "$CASE_REPO" commit -q -m fixture
    cat > "$CASE_DIR/venv/bin/detect-secrets" <<'SH'
#!/bin/bash
if [ "${1:-}" = --version ]; then printf '%s\n' "${FAKE_TOOL_VERSION:-1.5.0}"; exit 0; fi
case "${SCAN_CASE:-clean}" in
  error) exit 8 ;;
  hang) (sleep 31 & echo $! > "$HOME/child.pid"; wait) & wait ;;
  findings) printf '%s\n' '{"version":"1.5.0","results":{"src/obviously-fake.txt":[{"type":"Fake Detector","line_number":7,"hashed_secret":"FAKE_SECRET_SHAPED_VALUE_DO_NOT_USE_000000000000"}]}}' > .secrets.baseline ;;
  hostile) printf '%s\n' '{"version":"1.5.0","results":{"src/FAKE_SECRET_SHAPED_VALUE_DO_NOT_USE_000000000000\nspoof.txt":[{"type":"Fake Detector","line_number":7,"hashed_secret":"FAKE_SECRET_SHAPED_VALUE_DO_NOT_USE_000000000000"}]}}' > .secrets.baseline ;;
  *) printf '%s\n' '{"version":"1.5.0","results":{}}' > .secrets.baseline ;;
esac
SH
    cat > "$CASE_DIR/bin/hostname" <<'SH'
#!/bin/bash
printf '%s\n' "${HOST_CASE:-Mini-Pro2}"
SH
    cat > "$CASE_DIR/bin/git" <<'SH'
#!/bin/bash
printf '%s\n' "$*" >> "$GIT_CALLS"
exec /usr/bin/git "$@"
SH
    chmod +x "$CASE_DIR/venv/bin/detect-secrets" "$CASE_DIR/bin/hostname" "$CASE_DIR/bin/git"
}

run_case() {
    local scenario="$1" scan_case="${2:-clean}" host="${3:-Mini-Pro2}" enabled="${4:-true}" version="${5:-1.5.0}"
    setup_case
    if [ "$scenario" = tag ]; then
        /usr/bin/git -C "$CASE_REPO" checkout -q -b side
        printf '{"version":"9.9.9","results":{}}\n' > "$CASE_REPO/.secrets.baseline"
        /usr/bin/git -C "$CASE_REPO" commit -q -am side && /usr/bin/git -C "$CASE_REPO" tag main
        /usr/bin/git -C "$CASE_REPO" checkout -q main && /usr/bin/git -C "$CASE_REPO" branch -q -D side
    elif [ "$scenario" = stale ]; then
        mkdir -p "$CASE_DIR/tmp/run.dead"
        /usr/bin/git -C "$CASE_REPO" worktree add -q --detach "$CASE_DIR/tmp/run.dead/worktree" refs/heads/main
    elif [ "$scenario" = missing ]; then
        rm -f "$CASE_DIR/venv/bin/detect-secrets"
    fi
    BEFORE="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"
    env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" SCAN_CASE="$scan_case" HOST_CASE="$host" \
        FAKE_TOOL_VERSION="$version" MINI_DETECT_SECRETS_ENABLED="$enabled" \
        MINI_DETECT_SECRETS_TIMEOUT="${BOUND_CASE:-3600}" MINI_DETECT_SECRETS_REPO="$CASE_REPO" \
        MINI_DETECT_SECRETS_GIT="$CASE_DIR/bin/git" MINI_DETECT_SECRETS_PYTHON=/usr/bin/python3 \
        MINI_DETECT_SECRETS_HOSTNAME="$CASE_DIR/bin/hostname" MINI_DETECT_SECRETS_VENV="$CASE_DIR/venv" \
        MINI_DETECT_SECRETS_LOG_DIR="$CASE_HOME/logs" MINI_DETECT_SECRETS_SIDECAR_DIR="$CASE_HOME/sidecar" \
        MINI_DETECT_SECRETS_LOCKDIR="$CASE_DIR/lock" MINI_DETECT_SECRETS_TMP_BASE="$CASE_DIR/tmp" \
        GIT_CALLS="$CASE_HOME/git.log" /bin/bash "$WRAPPER" >/dev/null 2>&1
    AFTER="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"; [ "$BEFORE" = "$AFTER" ] || CANON_OK=0
    HB="$CASE_HOME/sidecar/mini.detect_secrets_fulltree.json"; CALLS="$CASE_HOME/notify.log"
}

run_case clean
MODE="$(/usr/bin/python3 -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777))' "$CASE_HOME/logs/run.log")"
if [ "$(field "$HB" status)" = ok ] && grep -q 'fulltree clean [0-9a-f]' "$HB" \
    && [ "$(worktrees)" -eq 1 ] && [ "$MODE" = 0o600 ]; then ok "clean scan is ok, private, and removes its worktree"; else bad "clean scan"; fi

run_case findings findings
if [ "$(field "$HB" status)" = warning ] && grep -q 'fulltree findings 1 ' "$HB" \
    && grep -q 'detect-secrets:findings:' "$CALLS" && grep -q 'src/obviously-fake.txt' "$CALLS" \
    && grep -q '1 finding(s) in 1 file(s)' "$CALLS" && grep -q '"p0"' "$CALLS" \
    && grep -q '"routing": "false"' "$CALLS" && grep -q '"relay": ""' "$CALLS" \
    && ! grep -R -F -q "$FAKE_VALUE" "$CASE_HOME/logs" "$CALLS"; then
    ok "findings warn and page with safe metadata only"
else bad "findings mapping or value redaction"; fi

run_case hostile hostile
if [ "$(field "$HB" status)" = warning ] && grep -q 'src/<redacted>' "$CALLS" \
    && ! grep -F -q "$FAKE_VALUE" "$CALLS" "$CASE_HOME/logs/run.log" \
    && [ "$(grep -c 'detect-secrets:findings:' "$CALLS")" -eq 1 ]; then
    ok "unsafe path content is redacted from logs and alerts"
else bad "unsafe path redaction"; fi

run_case missing
if [ "$(field "$HB" status)" = error ] && grep -q 'detect-secrets:broken:tool' "$CALLS" && grep -q 'detect-secrets==1.5.0' "$CALLS" && [ "$(worktrees)" -eq 1 ]; then ok "missing venv is a tool error"; else bad "missing venv"; fi
run_case mismatch clean Mini-Pro2 true 9.9.9
if [ "$(field "$HB" status)" = error ] && grep -q 'detect-secrets:broken:tool' "$CALLS" && [ "$(worktrees)" -eq 1 ]; then ok "version mismatch is a tool error"; else bad "version mismatch"; fi
run_case scan-error error
if [ "$(field "$HB" status)" = error ] && grep -q 'detect-secrets:broken:scan' "$CALLS" && [ "$(worktrees)" -eq 1 ]; then ok "scan errors page and clean up"; else bad "scan error"; fi
run_case wrong clean Air-M5
if [ "$(field "$HB" status)" = disabled ] && grep -q 'wrong-node air-m5' "$HB"; then ok "wrong node is disabled"; else bad "node guard"; fi
run_case off clean Mini-Pro2 false
if [ "$(field "$HB" status)" = disabled ] && grep -q 'kill switch' "$HB"; then ok "kill switch is disabled"; else bad "kill switch"; fi

BOUND_CASE=1 run_case bound hang
sleep 1; CHILD="$(sed -n '1p' "$CASE_HOME/child.pid" 2>/dev/null || echo 0)"
if [ "$CHILD" != 0 ] && ! kill -0 "$CHILD" 2>/dev/null && grep -q 'broken bound 1s' "$HB" \
    && grep -q 'detect-secrets:broken:bound' "$CALLS" && [ "$(worktrees)" -eq 1 ]; then ok "bound kills the scan process tree"; else bad "bound process-tree kill"; [ "$CHILD" = 0 ] || kill "$CHILD" 2>/dev/null || true; fi

setup_case
BEFORE="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"; t0=$(date +%s)
env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" SCAN_CASE=hang HOST_CASE=Mini-Pro2 FAKE_TOOL_VERSION=1.5.0 \
    MINI_DETECT_SECRETS_TIMEOUT=3600 MINI_DETECT_SECRETS_REPO="$CASE_REPO" MINI_DETECT_SECRETS_GIT="$CASE_DIR/bin/git" \
    MINI_DETECT_SECRETS_PYTHON=/usr/bin/python3 MINI_DETECT_SECRETS_HOSTNAME="$CASE_DIR/bin/hostname" \
    MINI_DETECT_SECRETS_VENV="$CASE_DIR/venv" MINI_DETECT_SECRETS_LOG_DIR="$CASE_HOME/logs" \
    MINI_DETECT_SECRETS_SIDECAR_DIR="$CASE_HOME/sidecar" MINI_DETECT_SECRETS_LOCKDIR="$CASE_DIR/lock" \
    MINI_DETECT_SECRETS_TMP_BASE="$CASE_DIR/tmp" GIT_CALLS="$CASE_HOME/git.log" /bin/bash "$WRAPPER" >/dev/null 2>&1 &
WPID=$!; for _ in $(seq 1 100); do [ -s "$CASE_HOME/child.pid" ] && break; sleep 0.1; done
kill -TERM "$WPID"; WRC=0; wait "$WPID" || WRC=$?; elapsed=$(( $(date +%s)-t0 )); sleep 1
CHILD="$(sed -n '1p' "$CASE_HOME/child.pid" 2>/dev/null || echo 0)"; AFTER="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"
HB="$CASE_HOME/sidecar/mini.detect_secrets_fulltree.json"
[ "$BEFORE" = "$AFTER" ] || CANON_OK=0
if [ "$WRC" -eq 143 ] && [ "$elapsed" -le 10 ] && [ "$CHILD" != 0 ] && ! kill -0 "$CHILD" 2>/dev/null \
    && [ "$(field "$HB" status)" = error ] && [ "$(worktrees)" -eq 1 ]; then ok "TERM to wrapper kills child tree within 10 seconds"; else bad "TERM forwarding"; [ "$CHILD" = 0 ] || kill "$CHILD" 2>/dev/null || true; fi

setup_case
BEFORE="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"; t0=$(date +%s)
env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" SCAN_CASE=hang HOST_CASE=Mini-Pro2 FAKE_TOOL_VERSION=1.5.0 \
    MINI_DETECT_SECRETS_TIMEOUT=3600 MINI_DETECT_SECRETS_REPO="$CASE_REPO" MINI_DETECT_SECRETS_GIT="$CASE_DIR/bin/git" \
    MINI_DETECT_SECRETS_PYTHON=/usr/bin/python3 MINI_DETECT_SECRETS_HOSTNAME="$CASE_DIR/bin/hostname" \
    MINI_DETECT_SECRETS_VENV="$CASE_DIR/venv" MINI_DETECT_SECRETS_LOG_DIR="$CASE_HOME/logs" \
    MINI_DETECT_SECRETS_SIDECAR_DIR="$CASE_HOME/sidecar" MINI_DETECT_SECRETS_LOCKDIR="$CASE_DIR/lock" \
    MINI_DETECT_SECRETS_TMP_BASE="$CASE_DIR/tmp" GIT_CALLS="$CASE_HOME/git.log" /bin/bash "$WRAPPER" >/dev/null 2>&1 &
WPID=$!; for _ in $(seq 1 100); do [ -s "$CASE_HOME/child.pid" ] && break; sleep 0.1; done
kill -USR1 "$WPID"; WRC=0; wait "$WPID" 2>/dev/null || WRC=$?; elapsed=$(( $(date +%s)-t0 )); sleep 1
CHILD="$(sed -n '1p' "$CASE_HOME/child.pid" 2>/dev/null || echo 0)"; AFTER="$(/usr/bin/git -C "$CASE_REPO" status --porcelain)"
HB="$CASE_HOME/sidecar/mini.detect_secrets_fulltree.json"
[ "$BEFORE" = "$AFTER" ] || CANON_OK=0
CHILD_ALIVE=0; [ "$CHILD" = 0 ] || kill -0 "$CHILD" 2>/dev/null && CHILD_ALIVE=1
HB_STATUS="$(field "$HB" status)"; WT_COUNT="$(worktrees)"
USR1_RC=$((128 + $(kill -l USR1)))
if [ "$WRC" -eq "$USR1_RC" ] && [ "$elapsed" -le 10 ] && [ "$CHILD" != 0 ] && [ "$CHILD_ALIVE" -eq 0 ] \
    && [ "$HB_STATUS" = error ] && [ "$WT_COUNT" -eq 1 ]; then ok "unexpected exit kills child tree within 10 seconds"; else bad "unexpected-exit cleanup (rc=$WRC elapsed=$elapsed child_alive=$CHILD_ALIVE heartbeat=$HB_STATUS worktrees=$WT_COUNT)"; [ "$CHILD" = 0 ] || kill "$CHILD" 2>/dev/null || true; fi

run_case stale
if [ ! -e "$CASE_DIR/tmp/run.dead" ] && [ "$(field "$HB" status)" = ok ] && [ "$(worktrees)" -eq 1 ]; then ok "stale run directory is swept"; else bad "stale sweep"; fi
run_case tag
if [ "$(field "$HB" status)" = ok ]; then ok "tag named main cannot shadow refs/heads/main"; else bad "tag shadow"; fi
BOUND_CASE=0 run_case invalid-bound
if [ "$(field "$HB" status)" = ok ] && grep -q 'timeout is not a positive integer' "$CASE_HOME/logs/run.log"; then ok "invalid bound falls back to 3600"; else bad "bound validation"; fi

if [ "$CANON_OK" -eq 1 ]; then ok "canonical checkout status is unchanged in every case"; else bad "canonical checkout changed"; fi
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
