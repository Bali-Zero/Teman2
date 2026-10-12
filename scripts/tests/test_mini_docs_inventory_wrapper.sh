#!/bin/bash
set -u

PASS=0; FAIL=0
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/mini-docs-inventory.sh"
SUITE_DIR="$(mktemp -d)"
trap 'rm -rf "$SUITE_DIR"' EXIT

ok() { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
field() { sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p" "$1"; }

setup_case() {
    CASE_DIR="$(mktemp -d "$SUITE_DIR/case.XXXXXX")"
    CASE_HOME="$CASE_DIR/home"
    CASE_REPO="$CASE_DIR/repo"
    mkdir -p "$CASE_HOME" "$CASE_REPO/scripts" "$CASE_DIR/bin"

    /usr/bin/git -C "$CASE_REPO" init -q -b main
    /usr/bin/git -C "$CASE_REPO" config user.email test@example.invalid
    /usr/bin/git -C "$CASE_REPO" config user.name "Docs inventory test"

    cat > "$CASE_REPO/scripts/docs_inventory_regen.sh" <<'EOF'
#!/bin/bash
set -u
case "${DOCS_CASE:-success}" in
  regen-fail) exit 9 ;;
  regen-hang) sleep 6 ;;
  regen-hang-tree) (sleep 31 & echo $! > "$HOME/child.pid"; wait) & sleep 6 ;;
  empty)
    printf '{}\n' > "$DOCS_DERIVED_OUTPUT_DIR/docs-sync.json"
    : > "$DOCS_DERIVED_OUTPUT_DIR/docs-audit.json"
    printf '# inventory\n' > "$DOCS_DERIVED_OUTPUT_DIR/DOCS_INVENTORY.md"
    ;;
  *)
    printf '{}\n' > "$DOCS_DERIVED_OUTPUT_DIR/docs-sync.json"
    printf '{}\n' > "$DOCS_DERIVED_OUTPUT_DIR/docs-audit.json"
    printf '# inventory\n' > "$DOCS_DERIVED_OUTPUT_DIR/DOCS_INVENTORY.md"
    ;;
esac
EOF
    cat > "$CASE_REPO/scripts/tg_notify.py" <<'EOF'
import json, os, sys
row = {"routing": os.environ.get("TG_ACT_ROUTING_ENABLED"),
       "relay": os.environ.get("TG_RELAY_SSH"), "args": sys.argv[1:]}
with open(os.path.join(os.environ["HOME"], "notify.log"), "a") as out:
    out.write(json.dumps(row, sort_keys=True) + "\n")
EOF
    chmod +x "$CASE_REPO/scripts/docs_inventory_regen.sh"
    /usr/bin/git -C "$CASE_REPO" add scripts
    /usr/bin/git -C "$CASE_REPO" commit -q -m fixture

    cat > "$CASE_DIR/bin/hostname" <<'EOF'
#!/bin/bash
printf '%s\n' "${HOST_CASE:-Mini-Pro2}"
EOF
    cat > "$CASE_DIR/bin/python-version" <<'EOF'
#!/bin/bash
if [ "${PY_CASE:-new}" = "old" ]; then
    echo 'Python 3.9.6' >&2
    exit 1
fi
echo 'Python 3.14.0' >&2
exit 0
EOF
    cat > "$CASE_DIR/bin/git" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$GIT_CALLS"
exec /usr/bin/git "$@"
EOF
    chmod +x "$CASE_DIR/bin/hostname" "$CASE_DIR/bin/python-version" "$CASE_DIR/bin/git"
}

run_case() {
    local docs_case="$1" host_case="${2:-Mini-Pro2}" enabled="${3:-true}" py_case="${4:-new}"
    setup_case
    if [ "$docs_case" = tag-shadow ]; then
        # An off-main commit whose regen fails, tagged `main`: bare `main` would resolve to it.
        /usr/bin/git -C "$CASE_REPO" checkout -q -b side
        printf '#!/bin/bash\nexit 9\n' > "$CASE_REPO/scripts/docs_inventory_regen.sh"
        /usr/bin/git -C "$CASE_REPO" commit -q -am off-main
        /usr/bin/git -C "$CASE_REPO" tag main
        /usr/bin/git -C "$CASE_REPO" checkout -q main
        /usr/bin/git -C "$CASE_REPO" branch -q -D side
        docs_case=success
    fi
    env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" \
        DOCS_CASE="$docs_case" HOST_CASE="$host_case" PY_CASE="$py_case" \
        MINI_DOCS_INVENTORY_REGEN_TIMEOUT="${REGEN_TIMEOUT_CASE:-1800}" \
        MINI_DOCS_INVENTORY_ENABLED="$enabled" \
        MINI_DOCS_INVENTORY_REPO="$CASE_REPO" \
        MINI_DOCS_INVENTORY_GIT="$CASE_DIR/bin/git" \
        MINI_DOCS_INVENTORY_PYTHON="$CASE_DIR/bin/python-version" \
        MINI_DOCS_INVENTORY_HOSTNAME="$CASE_DIR/bin/hostname" \
        MINI_DOCS_INVENTORY_LOG_DIR="$CASE_HOME/logs" \
        MINI_DOCS_INVENTORY_SIDECAR_DIR="$CASE_HOME/sidecar" \
        MINI_DOCS_INVENTORY_STATE_DIR="$CASE_HOME/state" \
        MINI_DOCS_INVENTORY_LOCKDIR="$CASE_DIR/lock" \
        MINI_DOCS_INVENTORY_TMP_BASE="$CASE_DIR/tmp" \
        GIT_CALLS="$CASE_HOME/git.log" \
        /bin/bash "$WRAPPER" >/dev/null 2>&1
    HB="$CASE_HOME/sidecar/mini.docs_inventory_refresh.json"
    CALLS="$CASE_HOME/notify.log"
    STATE="$CASE_HOME/state"
}

run_case success
if [ "$(field "$HB" status)" = "ok" ] && grep -q 'inventory [0-9a-f]' "$HB" \
    && [ -L "$STATE/latest" ] \
    && [ -s "$STATE/latest/docs-sync.json" ] \
    && [ -s "$STATE/latest/docs-audit.json" ] \
    && [ -s "$STATE/latest/DOCS_INVENTORY.md" ] \
    && [ "$(/usr/bin/git -C "$CASE_REPO" worktree list --porcelain | grep -c '^worktree ')" -eq 1 ] \
    && grep -q 'worktree remove --force' "$CASE_HOME/git.log" \
    && grep -q 'worktree prune' "$CASE_HOME/git.log"; then
    ok "success publishes latest and removes the detached worktree"
else
    bad "success bundle or worktree cleanup"
fi

run_case regen-fail
if [ "$(field "$HB" status)" = "error" ] && grep -q 'regen rc=9' "$HB" \
    && grep -q 'docs-inventory:broken:regen' "$CALLS" \
    && grep -q '"routing": "false"' "$CALLS" \
    && grep -q '"relay": ""' "$CALLS" \
    && grep -q '"digest"' "$CALLS" \
    && [ "$(/usr/bin/git -C "$CASE_REPO" worktree list --porcelain | grep -c '^worktree ')" -eq 1 ]; then
    ok "regen failure reports digest error and still removes the worktree"
else
    bad "regen failure mapping"
fi

run_case empty
if [ "$(field "$HB" status)" = "error" ] && grep -q 'payload-docs-audit.json' "$HB"; then
    ok "empty output is an error"
else
    bad "empty output mapping"
fi

run_case success Mini-Pro2 true old
if [ "$(field "$HB" status)" = "error" ] && grep -q 'python-version' "$HB" \
    && grep -q 'docs-inventory:broken:python-version' "$CALLS"; then
    ok "python 3.9 is rejected"
else
    bad "python version guard"
fi

run_case success Air-M5
if [ "$(field "$HB" status)" = "disabled" ] && grep -q 'wrong-node air-m5' "$HB"; then
    ok "wrong node is disabled"
else
    bad "node guard"
fi

run_case success Mini-Pro2 false
if [ "$(field "$HB" status)" = "disabled" ] && grep -q 'kill switch' "$HB"; then
    ok "kill switch is disabled"
else
    bad "kill switch"
fi

setup_case
mkdir -p "$CASE_HOME/state/old-bundle"
printf 'old\n' > "$CASE_HOME/state/old-bundle/docs-sync.json"
ln -s "$CASE_HOME/state/old-bundle" "$CASE_HOME/state/latest"
python3 -c 'import os,sys,time; p=sys.argv[1]; t=time.time()-31*86400; os.utime(p,(t,t))' \
    "$CASE_HOME/state/old-bundle"
env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" DOCS_CASE=success HOST_CASE=Mini-Pro2 PY_CASE=new \
    MINI_DOCS_INVENTORY_REPO="$CASE_REPO" MINI_DOCS_INVENTORY_GIT="$CASE_DIR/bin/git" \
    MINI_DOCS_INVENTORY_PYTHON="$CASE_DIR/bin/python-version" \
    MINI_DOCS_INVENTORY_HOSTNAME="$CASE_DIR/bin/hostname" \
    MINI_DOCS_INVENTORY_LOG_DIR="$CASE_HOME/logs" \
    MINI_DOCS_INVENTORY_SIDECAR_DIR="$CASE_HOME/sidecar" \
    MINI_DOCS_INVENTORY_STATE_DIR="$CASE_HOME/state" MINI_DOCS_INVENTORY_LOCKDIR="$CASE_DIR/lock" \
    MINI_DOCS_INVENTORY_TMP_BASE="$CASE_DIR/tmp" GIT_CALLS="$CASE_HOME/git.log" \
    /bin/bash "$WRAPPER" >/dev/null 2>&1
if [ ! -d "$CASE_HOME/state/old-bundle" ] && [ -L "$CASE_HOME/state/latest" ] \
    && [ -s "$CASE_HOME/state/latest/DOCS_INVENTORY.md" ]; then
    ok "30-day rotation removes stale bundles and preserves latest"
else
    bad "30-day rotation"
fi

if [ ! -e "$REPO_ROOT/.github/workflows/docs-inventory-refresh.yml" ] \
    && [ ! -e "$REPO_ROOT/.github/workflows/docs-inventory-refresh-liveness.yml" ] \
    && [ -e "$REPO_ROOT/infra/launchagents/com.nuzantara.docs-inventory-refresh.plist" ]; then
    ok "retired artifact publisher and liveness workflows stay replaced by launchd"
else
    bad "workflow retirement architecture pin"
fi

REGEN_TIMEOUT_CASE=1 run_case regen-hang
if [ "$(field "$HB" status)" = "error" ] && grep -q 'regen timed out after 1 s' "$HB" \
    && grep -q 'docs-inventory:broken:regen-timeout' "$CALLS" \
    && [ "$(/usr/bin/git -C "$CASE_REPO" worktree list --porcelain | grep -c '^worktree ')" -eq 1 ]; then
    ok "a hung regen is bounded, reported, and its worktree removed"
else
    bad "regen bound"
fi

REGEN_TIMEOUT_CASE=1 run_case regen-hang-tree
sleep 3
CHILD=$(cat "$CASE_HOME/child.pid" 2>/dev/null || echo 0)
if [ "$CHILD" != 0 ] && ! kill -0 "$CHILD" 2>/dev/null && grep -q 'regen timed out' "$HB"; then
    ok "the bound kills the regen's whole process tree"
else
    bad "regen tree kill (child $CHILD alive?)"
    [ "$CHILD" = 0 ] || kill "$CHILD" 2>/dev/null
fi

setup_case
/usr/bin/git -C "$CASE_REPO" worktree add -q --detach "$CASE_DIR/tmp/run.dead01/worktree" refs/heads/main
STALE_SETUP_DIR="$CASE_DIR"
env -i HOME="$CASE_HOME" PATH="/usr/bin:/bin" DOCS_CASE=success HOST_CASE=Mini-Pro2 PY_CASE=new \
    MINI_DOCS_INVENTORY_REPO="$CASE_REPO" MINI_DOCS_INVENTORY_GIT="$CASE_DIR/bin/git" \
    MINI_DOCS_INVENTORY_PYTHON="$CASE_DIR/bin/python-version" \
    MINI_DOCS_INVENTORY_HOSTNAME="$CASE_DIR/bin/hostname" \
    MINI_DOCS_INVENTORY_LOG_DIR="$CASE_HOME/logs" MINI_DOCS_INVENTORY_SIDECAR_DIR="$CASE_HOME/sidecar" \
    MINI_DOCS_INVENTORY_STATE_DIR="$CASE_HOME/state" MINI_DOCS_INVENTORY_LOCKDIR="$CASE_DIR/lock" \
    MINI_DOCS_INVENTORY_TMP_BASE="$CASE_DIR/tmp" GIT_CALLS="$CASE_HOME/git.log" \
    /bin/bash "$WRAPPER" >/dev/null 2>&1
HB="$CASE_HOME/sidecar/mini.docs_inventory_refresh.json"
if [ ! -e "$STALE_SETUP_DIR/tmp/run.dead01" ] && [ "$(field "$HB" status)" = "ok" ] \
    && [ "$(/usr/bin/git -C "$CASE_REPO" worktree list --porcelain | grep -c '^worktree ')" -eq 1 ]; then
    ok "a run killed without its trap is swept by the next run"
else
    bad "stale run sweep"
fi

run_case tag-shadow
if [ "$(field "$HB" status)" = "ok" ] && [ -s "$STATE/latest/DOCS_INVENTORY.md" ]; then
    ok "a tag named main does not shadow the main branch"
else
    bad "tag shadow"
fi

printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
