#!/bin/bash
# pro.localci_merger — launchd tick of the localci shadow merger (scripts/localci/merger.py;
# docs/specs/localci-sovereign-2026-10-07.md, phases C-D). Live copy: ~/.nuzantara-cron/localci_merger_tick.sh (declared
# pair, node=pro). Runs merger.py and hosted_compare.py exactly as committed on origin/main, read at ONE resolved sha from
# the merger's own mirror — never from a working tree, which drifts (superscar #1). One-shot: launchd's StartInterval runs
# it again, there is no KeepAlive (#7). Every exit path writes the heartbeat ~/.organism/last_seen/pro.localci_merger.json
# (#2) through scripts/lib/heartbeat.sh: ok, error (a failure before Python starts writes no journal line, so this is where it
# shows) or disabled (the kill switch: an operator's stop, which the healer and the sentinel treat as exempt, not as a failure).
set -euo pipefail
ORGAN_ID="pro.localci_merger"
STATE="${MERGER_STATE_DIR:-$HOME/.nuzantara-pilots/local-ci/merger}"
# heartbeat.sh too is read from the mirror at the tick's sha, never from a working checkout: each tick refreshes the copy
# in the state dir, and an exit before that (kill switch, missing configuration) uses the copy the last tick extracted
HB_LIB="${MERGER_HEARTBEAT_LIB:-$STATE/heartbeat.sh}"
# the library runs in its OWN process (its CLI mode), never sourced: it cannot change this script's options, traps or exit status
heartbeat() { # $1 status, $2 note
  if [ -r "$HB_LIB" ] && [ -s "$HB_LIB" ]; then
    "$BASH" "$HB_LIB" "$ORGAN_ID" "$1" "$2" || echo "merger_tick: heartbeat not written by $HB_LIB" >&2
  else
    echo "merger_tick: no heartbeat library at $HB_LIB (absent or empty) — the organ will read stale" >&2
  fi
}

# kill switch: an operator stop without uninstalling; the disabled heartbeat keeps the healer from resurrecting it
if [ "${LOCALCI_MERGER_ENABLED:-true}" = "false" ]; then
  echo "merger_tick: LOCALCI_MERGER_ENABLED=false — not ticking"
  heartbeat disabled "kill switch LOCALCI_MERGER_ENABLED=false"
  exit 0
fi

CODE=""
SHA=""
finish() {
  local rc=$?
  if [ -n "$CODE" ]; then rm -rf "$CODE"; fi
  local code="${SHA:0:12}"
  if [ "$rc" -eq 0 ]; then heartbeat ok "tick rc=0 code=${code:-none}"; else heartbeat error "tick rc=$rc code=${code:-none}"; fi
}
trap finish EXIT

SEED="${MERGER_SEED:-$HOME/nuzantara}"
URL="${MERGER_REMOTE_URL:-https://github.com/Bali-Zero/Teman2.git}"
PY="${MERGER_PYTHON:-}"    # the interpreter that runs the BASE runner
NODE="${MERGER_NODE:-}"    # the only host allowed to decide
# an explicit exit, not ${VAR:?}: bash leaves an expansion error's status out of the EXIT trap, and the heartbeat would say ok
if [ -z "$PY" ] || [ -z "$NODE" ]; then
  echo "merger_tick: MERGER_PYTHON and MERGER_NODE are required" >&2
  exit 2
fi
if [ ! -x "$PY" ]; then
  echo "merger_tick: MERGER_PYTHON $PY is not an executable interpreter (the merger's venv: see scripts/localci/README.md)" >&2
  exit 2
fi
while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep '^GIT_' || true)   # no caller GIT_DIR, index or config
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_COUNT=3 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null GIT_CONFIG_KEY_1=core.fsmonitor \
  GIT_CONFIG_VALUE_1=false GIT_CONFIG_KEY_2=core.attributesFile GIT_CONFIG_VALUE_2=/dev/null

mkdir -p "$STATE"
if [ ! -f "$STATE/repo.git/HEAD" ]; then
  git clone --bare --quiet --no-tags "$SEED" "$STATE/repo.git"
  git -C "$STATE/repo.git" remote set-url origin "$URL"
fi
# a failed fetch is not fatal here: the tick fetches again and journals its own `error` line, so the journal sees the outage
git -C "$STATE/repo.git" fetch --no-tags --quiet origin +refs/heads/main:refs/merger/base \
  || echo "merger_tick: fetch failed — running the main fetched last; the tick journals its own fetch error" >&2
SHA="$(git -C "$STATE/repo.git" rev-parse --verify 'refs/merger/base^{commit}')"
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-merger.XXXXXX")"
for f in merger.py hosted_compare.py; do
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f"
done
HB_NEW="$(mktemp "$STATE/.heartbeat.sh.XXXXXX")"   # one temp file per run: a hand run beside launchd never shares it
if git -C "$STATE/repo.git" show "$SHA:scripts/lib/heartbeat.sh" > "$HB_NEW" && [ -s "$HB_NEW" ]; then
  mv -f "$HB_NEW" "$STATE/heartbeat.sh"
else
  rm -f "$HB_NEW"
  echo "merger_tick: no scripts/lib/heartbeat.sh at ${SHA:0:12} — keeping the copy the last tick extracted" >&2
fi
# provenance only when the extracted merger knows the flag: a newer wrapper beside an older main (or a stale mirror after a
# failed fetch) must still tick, never die on argparse
CODE_FLAG=""
if grep -q -- "--code-sha" "$CODE/merger.py"; then CODE_FLAG="--code-sha=$SHA"; fi
echo "merger_tick: $(date -u +%FT%TZ) code=${SHA:0:12}"
"$PY" -I "$CODE/merger.py" tick --node "$NODE" --state-dir "$STATE" --python "$PY" ${CODE_FLAG:+"$CODE_FLAG"}
