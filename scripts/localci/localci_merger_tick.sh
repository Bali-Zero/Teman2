#!/bin/bash
# pro.localci_merger — launchd tick of the localci shadow merger (scripts/localci/merger.py;
# docs/specs/localci-sovereign-2026-10-07.md, phases C-D). Live copy: ~/.nuzantara-cron/localci_merger_tick.sh (declared
# pair, node=pro). Runs merger.py and hosted_compare.py exactly as committed on origin/main, read at ONE resolved sha from
# the merger's own mirror — never from a working tree, which drifts (superscar #1). One-shot: launchd's StartInterval runs
# it again, there is no KeepAlive (#7). Every exit path writes the heartbeat ~/.organism/last_seen/pro.localci_merger.json
# (#2) through scripts/lib/heartbeat.sh: ok, error (a failure before Python starts writes no journal line, so this is where it
# shows), warning (B6: the host under the start floor, or a prune that failed) or disabled (the kill switch: an operator's
# stop, which the healer and the sentinel treat as exempt, not as a failure).
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
# B33: how many ticks this launchd instance has already chained (0 on a launchd start; the only thing that crosses the re-exec).
# Anything but digits means no chain at all, never a guess.
DEPTH="${MERGER_CHAIN_DEPTH:-0}"
CHAIN_OK=1
case "$DEPTH" in '' | *[!0-9]*) DEPTH=0; CHAIN_OK=0 ;; esac
WARN=""   # B6: the host under the floor, or a prune that failed: the tick is not an error, the organ says warning
# shellcheck disable=SC2329  # invoked indirectly, by `trap finish EXIT` below (shellcheck 0.11 does not follow it here)
finish() { finish_with "$?"; }
finish_with() {   # B33: a chained tick calls this by hand, with the tick's rc, before it re-execs
  local rc=$1
  if [ -n "$CODE" ]; then rm -rf "$CODE"; fi
  local code="${SHA:0:12}"
  if [ "$rc" -ne 0 ]; then heartbeat error "tick rc=$rc code=${code:-none} depth=$DEPTH"
  elif [ -n "$WARN" ]; then heartbeat warning "$WARN code=${code:-none} depth=$DEPTH"
  else heartbeat ok "tick rc=0 code=${code:-none} depth=$DEPTH"; fi
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
# a failed fetch is not fatal here: the tick fetches again and journals its own `error` line, so the journal sees the outage.
# The wrapper reads the code from ITS OWN ref, refs/merger/wrapper: refs/merger/base belongs to merger.py's fetch_base alone (F2:
# once phase F has pushed, that ref is the authority and a force-fetch here would rewind it before the divergence guard looks)
git -C "$STATE/repo.git" fetch --no-tags --quiet origin +refs/heads/main:refs/merger/wrapper \
  || echo "merger_tick: fetch failed — running the main fetched last; the tick journals its own fetch error" >&2
# a mirror from before this ref existed has only refs/merger/base: its code is what the last tick ran, read once and never written
SHA="$(git -C "$STATE/repo.git" rev-parse --verify --quiet 'refs/merger/wrapper^{commit}' \
  || git -C "$STATE/repo.git" rev-parse --verify 'refs/merger/base^{commit}')"
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-merger.XXXXXX")"
for f in merger.py hosted_compare.py; do
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f"
done
for f in prune.py runner.py contexts_matrix.yaml tick_chain.py; do   # B6's prune, its df probe and the BASE matrix whose stand-ins it keeps; B33's chain predicate (absent: no chain)
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f" 2>/dev/null || rm -f "$CODE/$f"
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
# B6: the host's free GB is read BEFORE the tick, which never starts a run under the floor (it journals the skip), and the
# prune runs AFTER it: the decision first, then the gate removes what it wrote and trims the VM when an image went
HOST_PATH="${MERGER_HOST_PATH:-/System/Volumes/Data}"
[ -d "$HOST_PATH" ] || HOST_PATH=/
FLOOR_GB="${MERGER_MIN_HOST_FREE_GB:-60}"   # B15: the START floor = Zero's 50 GB (2026-10-16, was 90) + 10 (merger.py HOST_FLOOR_GB + START_MARGIN_GB)
FREE="$(df -Pk "$HOST_PATH" 2>/dev/null | awk 'NR==2 && $4 ~ /^[0-9]+$/ { printf "%d", $4 * 1024 / 1000000000 }' || true)"
FREE_FLAG=""
FLOOR_FLAG=""
if [ -n "$FREE" ] && grep -q -- "--host-free-gb" "$CODE/merger.py"; then FREE_FLAG="--host-free-gb=$FREE"; FLOOR_FLAG="--min-host-free-gb=$FLOOR_GB"; fi
if [ -n "$FREE" ] && [ "$FREE" -lt "$FLOOR_GB" ]; then WARN="host_below_floor free_gb=$FREE start_floor_gb=$FLOOR_GB: no run started"; fi
if [ -z "$FREE" ]; then WARN="host free space unreadable (df -Pk $HOST_PATH): no run started"; fi   # a floor unread is not a floor met
echo "merger_tick: $(date -u +%FT%TZ) code=${SHA:0:12} host_free_gb=${FREE:-unread}"
TICK_RC=0
OFFSET="$(wc -c 2>/dev/null < "$STATE/decisions.jsonl" | tr -d '[:space:]' || true)"   # B33: the journal bytes before the tick
OFFSET="${OFFSET:-0}"
if [ -n "$WARN" ] && [ -z "$FREE_FLAG" ]; then
  echo "merger_tick: $WARN (not journalled: no reading, or a merger.py that cannot journal the skip)" >&2
else
  "$PY" -I "$CODE/merger.py" tick --node "$NODE" --state-dir "$STATE" --python "$PY" ${CODE_FLAG:+"$CODE_FLAG"} \
    ${FREE_FLAG:+"$FREE_FLAG"} ${FLOOR_FLAG:+"$FLOOR_FLAG"} || TICK_RC=$?
fi
if [ -f "$CODE/prune.py" ] && grep -q -- '"prune"' "$CODE/merger.py"; then
  PRUNE_RC=0
  "$PY" -I "$CODE/merger.py" prune --state-dir "$STATE" --fstrim ${CODE_FLAG:+"$CODE_FLAG"} || PRUNE_RC=$?
  if [ "$PRUNE_RC" -ne 0 ]; then WARN="${WARN:+$WARN; }prune rc=$PRUNE_RC"; fi
fi

# B33 S1: launchd re-arms StartInterval only when this job EXITS, so every tick was followed by 600 s of nothing (measured 601-603 s,
# 5 of 5 cycles). A tick that bore a verdict re-executes this script at once, in the same process: launchd still sees the one instance
# it started, the lease is taken and dropped inside merger.py so a parallel manual tick still excludes it, and the next tick is a WHOLE
# tick (fetch, code at the new sha, floor, lease, watchdog, prune). Any doubt is today's behaviour: exit, and StartInterval resumes.
CHAIN_MAX="${MERGER_CHAIN_MAX:-12}"
case "$CHAIN_MAX" in '' | *[!0-9]*) CHAIN_MAX=0 ;; esac
chain_why=""
if [ "$CHAIN_OK" -ne 1 ]; then chain_why="MERGER_CHAIN_DEPTH is not a number"
elif [ "${LOCALCI_MERGER_CHAIN:-1}" = "0" ]; then chain_why="LOCALCI_MERGER_CHAIN=0"
elif [ -e "$STATE/chain_off" ]; then chain_why="$STATE/chain_off exists"
elif [ "$DEPTH" -ge "$CHAIN_MAX" ]; then chain_why="depth cap $CHAIN_MAX reached"
elif [ -n "$WARN" ]; then chain_why="the tick warned: $WARN"
elif [ ! -f "$CODE/tick_chain.py" ]; then chain_why="no tick_chain.py at ${SHA:0:12}"
else
  CHAIN_OUT="$("$PY" -I "$CODE/tick_chain.py" "$STATE/decisions.jsonl" "$OFFSET" "$TICK_RC" 2>/dev/null || true)"
  case "$CHAIN_OUT" in
    "chain "*) ;;
    *) chain_why="${CHAIN_OUT#stop }"; chain_why="${chain_why:-the predicate gave no answer}" ;;
  esac
fi
if [ -z "$chain_why" ]; then
  echo "merger_tick: chain depth=$((DEPTH + 1)) after ${CHAIN_OUT#chain }"
  finish_with "$TICK_RC"
  trap - EXIT
  export MERGER_CHAIN_DEPTH=$((DEPTH + 1))
  shopt -s execfail
  exec "$BASH" "$0" || { heartbeat error "chain exec failed code=${SHA:0:12}"; exit 1; }
fi
echo "merger_tick: chain stop: $chain_why"
exit "$TICK_RC"
