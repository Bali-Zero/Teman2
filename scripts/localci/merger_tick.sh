#!/bin/bash
# launchd tick of the localci shadow merger (scripts/localci/merger.py; docs/specs/localci-sovereign-2026-10-07.md, phases C-D).
# Runs merger.py and hosted_compare.py exactly as committed on origin/main, read from the merger's own mirror — never from
# a working tree, which drifts (superscar #1). One-shot: launchd's StartInterval runs it again, there is no KeepAlive (#7).
set -euo pipefail
STATE="${MERGER_STATE_DIR:-$HOME/.nuzantara-pilots/local-ci/merger}"
SEED="${MERGER_SEED:-$HOME/nuzantara}"
PY="${MERGER_PYTHON:?MERGER_PYTHON: the interpreter that runs the BASE runner}"
NODE="${MERGER_NODE:?MERGER_NODE: the only host allowed to decide}"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG_PARAMETERS
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null

mkdir -p "$STATE"
if [ ! -f "$STATE/repo.git/HEAD" ]; then
  git clone --bare --quiet --no-tags "$SEED" "$STATE/repo.git"
  git -C "$STATE/repo.git" remote set-url origin https://github.com/Bali-Zero/Teman2.git
fi
git -C "$STATE/repo.git" fetch --no-tags --quiet origin +refs/heads/main:refs/merger/base
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-merger.XXXXXX")"
trap 'rm -rf "$CODE"' EXIT
for f in merger.py hosted_compare.py; do
  git -C "$STATE/repo.git" show "refs/merger/base:scripts/localci/$f" > "$CODE/$f"
done
echo "merger_tick: $(date -u +%FT%TZ) code=$(git -C "$STATE/repo.git" rev-parse --short=12 refs/merger/base)"
"$PY" -I "$CODE/merger.py" tick --node "$NODE" --state-dir "$STATE" --python "$PY"
