#!/bin/bash
# pro.localci_shepherd — launchd tick of the LocalCI PR shepherd (scripts/localci/shepherd.py; docs/specs/localci-sovereign-2026-10-07.md,
# B34 P1: OBSERVE only, no write verb). Live copy: ~/.nuzantara-cron/localci_shepherd_tick.sh (declared pair, node=pro). Runs shepherd.py,
# merger.py and hosted_compare.py exactly as committed on origin/main, read at ONE resolved sha from the shepherd's OWN bare mirror
# (refs/shepherd/wrapper), never from a working tree (superscar #1). One-shot: StartInterval runs it again, no KeepAlive (#7). Every exit
# path writes the heartbeat ~/.organism/last_seen/pro.localci_shepherd.json (#2): ok, warning (skipped_quota), error, or disabled (the
# kill switch LOCALCI_SHEPHERD_ENABLED=false, or a host that is not SHEPHERD_NODE: an operator's choice, exempt from the healer).
set -euo pipefail
ORGAN_ID="pro.localci_shepherd"
STATE="${SHEPHERD_STATE_DIR:-$HOME/.nuzantara-pilots/local-ci/shepherd}"
HB_LIB="${SHEPHERD_HEARTBEAT_LIB:-$STATE/heartbeat.sh}"
heartbeat() { # $1 status, $2 note; the library runs in its own process, never sourced
  if [ -r "$HB_LIB" ] && [ -s "$HB_LIB" ]; then
    "$BASH" "$HB_LIB" "$ORGAN_ID" "$1" "$2" || echo "shepherd_tick: heartbeat not written by $HB_LIB" >&2
  else
    echo "shepherd_tick: no heartbeat library at $HB_LIB (absent or empty) — the organ will read stale" >&2
  fi
}

if [ "${LOCALCI_SHEPHERD_ENABLED:-true}" = "false" ]; then
  echo "shepherd_tick: LOCALCI_SHEPHERD_ENABLED=false — not ticking"
  heartbeat disabled "kill switch LOCALCI_SHEPHERD_ENABLED=false"
  exit 0
fi

CODE=""
SHA=""
OUT=""
HB_NEW=""
STATUS="ok"
NOTE=""
# shellcheck disable=SC2329  # invoked indirectly, by `trap finish EXIT`
finish() {
  local rc=$?
  # a failed cleanup must never end the trap before the heartbeat: `|| true` here, on the cleanup only
  if [ -n "$CODE" ]; then rm -rf "$CODE" || true; fi
  if [ -n "$OUT" ]; then rm -f "$OUT" || true; fi
  if [ -n "$HB_NEW" ]; then rm -f "$HB_NEW" || true; fi
  local code="${SHA:0:12}"
  if [ "$rc" -ne 0 ]; then heartbeat error "tick rc=$rc code=${code:-none}"
  elif [ "$STATUS" = "disabled" ]; then heartbeat disabled "$NOTE"
  elif [ "$STATUS" = "warning" ]; then heartbeat warning "$NOTE code=${code:-none}"
  else heartbeat ok "tick rc=0 ${NOTE:+$NOTE }code=${code:-none}"; fi
}
trap finish EXIT

URL="${SHEPHERD_REMOTE_URL:-https://github.com/Bali-Zero/Teman2.git}"
PY="${SHEPHERD_PYTHON:-}"
NODE="${SHEPHERD_NODE:-}"
# an explicit exit, not ${VAR:?}: bash leaves an expansion error's status out of the EXIT trap, and the heartbeat would say ok
if [ -z "$PY" ] || [ -z "$NODE" ]; then
  echo "shepherd_tick: SHEPHERD_PYTHON and SHEPHERD_NODE are required" >&2
  exit 2
fi
if [ ! -x "$PY" ]; then
  echo "shepherd_tick: SHEPHERD_PYTHON $PY is not an executable interpreter" >&2
  exit 2
fi
while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep '^GIT_' || true)
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_COUNT=3 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null GIT_CONFIG_KEY_1=core.fsmonitor \
  GIT_CONFIG_VALUE_1=false GIT_CONFIG_KEY_2=core.attributesFile GIT_CONFIG_VALUE_2=/dev/null

mkdir -p "$STATE"
chmod 700 "$STATE"
# The mirror BORROWS the merger's objects (clone --shared writes objects/info/alternates in OUR repo only; the merger's repo is never
# written): a full bare clone is ~2.8 GB on a host that must keep 100 GB free. Without a merger mirror, a blob-less partial clone.
MERGER_MIRROR="${SHEPHERD_MERGER_MIRROR:-$HOME/.nuzantara-pilots/local-ci/merger/repo.git}"
if [ ! -f "$STATE/repo.git/HEAD" ]; then
  if [ -f "$MERGER_MIRROR/HEAD" ]; then
    git clone --bare --shared --quiet --no-tags "$MERGER_MIRROR" "$STATE/repo.git"
  else
    git clone --bare --quiet --no-tags --filter=blob:none "$URL" "$STATE/repo.git"
  fi
  git -C "$STATE/repo.git" remote set-url origin "$URL"
fi
git -C "$STATE/repo.git" fetch --no-tags --quiet origin +refs/heads/main:refs/shepherd/wrapper \
  || echo "shepherd_tick: fetch failed — running the main fetched last" >&2
SHA="$(git -C "$STATE/repo.git" rev-parse --verify 'refs/shepherd/wrapper^{commit}')"
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-shepherd.XXXXXX")"
for f in shepherd.py merger.py hosted_compare.py; do
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f"
done
HB_NEW="$(mktemp "$STATE/.heartbeat.sh.XXXXXX")"
if git -C "$STATE/repo.git" show "$SHA:scripts/lib/heartbeat.sh" > "$HB_NEW" && [ -s "$HB_NEW" ]; then
  mv -f "$HB_NEW" "$STATE/heartbeat.sh"
else
  rm -f "$HB_NEW"
  echo "shepherd_tick: no scripts/lib/heartbeat.sh at ${SHA:0:12} — keeping the copy the last tick extracted" >&2
fi
echo "shepherd_tick: $(date -u +%FT%TZ) code=${SHA:0:12}"
OUT="$(mktemp "${TMPDIR:-/tmp}/localci-shepherd-out.XXXXXX")"
"$PY" -I "$CODE/shepherd.py" tick --node "$NODE" --state-dir "$STATE" | tee "$OUT"
LINE="$(grep -m1 '^status=' "$OUT" || true)"
STATUS="$(printf '%s' "$LINE" | sed -n 's/^status=\([a-z]*\).*/\1/p')"
NOTE="$(printf '%s' "$LINE" | sed -n 's/^status=[a-z]* *//p')"
STATUS="${STATUS:-ok}"
exit 0
