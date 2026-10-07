#!/bin/bash
# launchd tick of the localci shadow merger (scripts/localci/merger.py; docs/specs/localci-sovereign-2026-10-07.md, phases C-D).
# Runs merger.py and hosted_compare.py exactly as committed on origin/main, read at ONE resolved sha from the merger's own
# mirror — never from a working tree, which drifts (superscar #1). One-shot: launchd's StartInterval runs it again, there is
# no KeepAlive (#7). A failure before Python starts (no git, no mirror) writes no journal line: it lands in the launchd
# err log, and `merger.py report` shows the gap as `longest_silence`.
set -euo pipefail
STATE="${MERGER_STATE_DIR:-$HOME/.nuzantara-pilots/local-ci/merger}"
SEED="${MERGER_SEED:-$HOME/nuzantara}"
URL="${MERGER_REMOTE_URL:-https://github.com/Bali-Zero/Teman2.git}"
PY="${MERGER_PYTHON:?MERGER_PYTHON: the interpreter that runs the BASE runner}"
NODE="${MERGER_NODE:?MERGER_NODE: the only host allowed to decide}"
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
trap 'rm -rf "$CODE"' EXIT
for f in merger.py hosted_compare.py; do
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f"
done
echo "merger_tick: $(date -u +%FT%TZ) code=${SHA:0:12}"
"$PY" -I "$CODE/merger.py" tick --node "$NODE" --state-dir "$STATE" --python "$PY"
