#!/bin/sh
# Read-only integration check for Pro/Mini git sync wiring.

set -u

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT" 2>/dev/null || exit 1

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

ok() {
  printf 'OK: %s\n' "$*"
}

HOST=$(hostname)
case "$HOST" in
  Nuzantara)
    LOCAL_NODE="Pro"
    PEER_ALIAS="mini"
    PEER_REPO='~/Desktop/nuzantara'
    EXPECTED_PULL_SCRIPT="$HOME/Desktop/nuzantara/scripts/mini/mini-git-pull.sh"
    ;;
  Mini-Pro2|mini-pro2)
    LOCAL_NODE="Mini"
    PEER_ALIAS="pro"
    PEER_REPO='~/Desktop/nuzantara'
    EXPECTED_PULL_SCRIPT="$HOME/Desktop/nuzantara/scripts/mini/mini-git-pull.sh"
    ;;
  *)
    fail "unsupported host $(hostname)"
    ;;
esac

[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ] || fail "local branch is not main"
ok "$LOCAL_NODE on main"

LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null) || fail "cannot read local HEAD"
PEER_SHA=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$PEER_ALIAS" "cd $PEER_REPO && git rev-parse HEAD" 2>/dev/null || true)
[ -n "$PEER_SHA" ] || fail "cannot read peer HEAD via ssh $PEER_ALIAS"

if [ "$LOCAL_SHA" = "$PEER_SHA" ]; then
  ok "local and peer heads match $(printf '%s' "$LOCAL_SHA" | cut -c1-10)"
else
  fail "local and peer heads differ local=$(printf '%s' "$LOCAL_SHA" | cut -c1-10) peer=$(printf '%s' "$PEER_SHA" | cut -c1-10)"
fi

ORIGIN_SHA=$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}' || true)
[ -n "$ORIGIN_SHA" ] || fail "cannot read origin/main"
if [ "$LOCAL_SHA" = "$ORIGIN_SHA" ]; then
  ok "local and origin/main match $(printf '%s' "$ORIGIN_SHA" | cut -c1-10)"
else
  fail "local and origin/main differ local=$(printf '%s' "$LOCAL_SHA" | cut -c1-10) origin=$(printf '%s' "$ORIGIN_SHA" | cut -c1-10)"
fi

ssh -o BatchMode=yes -o ConnectTimeout=5 "$PEER_ALIAS" "cd $PEER_REPO && git rev-parse --is-inside-work-tree >/dev/null" \
  || fail "peer repo is not accessible"
ok "peer repo accessible"

if [ "$LOCAL_NODE" = "Pro" ]; then
  ssh -o BatchMode=yes -o ConnectTimeout=5 mini 'test -x ~/scripts/mini-git-pull.sh' \
    || fail "Mini deployed pull script is missing or not executable"
  ok "Mini deployed pull script executable"

  if ssh -o BatchMode=yes -o ConnectTimeout=5 mini 'cmp -s ~/Desktop/nuzantara/scripts/mini/mini-git-pull.sh ~/scripts/mini-git-pull.sh'; then
    ok "Mini deployed pull script matches repo copy"
  else
    fail "Mini deployed pull script differs from repo copy"
  fi

  ssh -o BatchMode=yes -o ConnectTimeout=5 mini 'cd ~/Desktop/nuzantara && git ls-remote pro refs/heads/main >/dev/null' \
    || fail "Mini cannot read Pro remote"
  ok "Mini can read Pro remote"
else
  [ -x "$EXPECTED_PULL_SCRIPT" ] || fail "repo Mini pull script missing or not executable"
  git ls-remote pro refs/heads/main >/dev/null 2>&1 || fail "Mini cannot read Pro remote"
  ok "Mini can read Pro remote"
fi

sh -n .husky/pre-push || fail ".husky/pre-push syntax"
sh -n scripts/pro-mini-git-sync-hook.sh || fail "sync hook syntax"
bash -n scripts/mini/mini-git-pull.sh || fail "Mini pull script syntax"
ok "hook and sync script syntax"

scripts/pro-mini-healthcheck.sh >/dev/null || fail "healthcheck failed"
ok "healthcheck passed"
