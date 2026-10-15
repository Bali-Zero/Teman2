#!/usr/bin/env bash
# signal_merge_intent.sh <PR> — the one ship gesture: label first, then arm.
#
# The LocalCI merger merges only a PR carrying `localci:merge-shadow-ok`, applied by an
# admin/maintain User AFTER the head's push (scripts/localci/merger.py, B2a). GitHub
# auto-merge is armed on top of it ONLY while the base branch still has a `merge_queue`
# rule; after the phase-F flip the rule is gone and the arm is skipped (a skip, not an error).
#
# B31 — the label is never silently missing:
#   1. read it back first (scripts/localci/label_census.py verify = the merger's own check);
#      valid => nothing is written, no remove, no new event;
#   2. absent => add; present but not valid (its event predates the head) => remove, then add
#      (an add of a present label makes no event);
#   3. the add is retried with bounded backoff, then READ BACK again with the same bound;
#   4. a label that is not shown valid at the end is FATAL: exit 2, SIGNAL_INTENT_FAIL on stderr,
#      whatever the queue state (while the queue rule exists the arm is still attempted first —
#      it is what merges until the flip — and the exit stays 2).
#
# Output (one line): SIGNAL_INTENT pr=N label=applied|failed queue=present|absent|unknown arm=armed|skipped
# Exit: 0 ok, 1 usage, 2 label failed, 3 arm failed.
# Env: SIGNAL_INTENT_REPO (default Bali-Zero/Teman2), SIGNAL_INTENT_BASE (default main),
#      SIGNAL_INTENT_TRIES (default 4), SIGNAL_INTENT_BACKOFF_S (default 2, doubled each try),
#      SIGNAL_INTENT_VERIFY (a command run as `<cmd> <repo> <pr>`: 0 valid, other not; default label_census.py verify).
set -uo pipefail

REPO="${SIGNAL_INTENT_REPO:-Bali-Zero/Teman2}"
BASE="${SIGNAL_INTENT_BASE:-main}"
LABEL="localci:merge-shadow-ok"
TRIES="${SIGNAL_INTENT_TRIES:-4}"
BACKOFF="${SIGNAL_INTENT_BACKOFF_S:-2}"
HERE="$(dirname "${BASH_SOURCE[0]}")"

PR="${1:-}"
case "$PR" in
  ''|*[!0-9]*) echo "usage: signal_merge_intent.sh <PR-number>" >&2; exit 1 ;;
esac
case "$TRIES" in ''|*[!0-9]*|0) TRIES=4 ;; esac

queue="$(SIGNAL_INTENT_REPO="$REPO" SIGNAL_INTENT_BASE="$BASE" "$HERE/merge_queue_rule.sh")"

verify_label() {   # 0 valid; otherwise the reason is on stdout/stderr
  if [ -n "${SIGNAL_INTENT_VERIFY:-}" ]; then
    "$SIGNAL_INTENT_VERIFY" "$REPO" "$PR" 2>&1
  else
    python3 "$HERE/localci/label_census.py" verify --repo "$REPO" --pr "$PR" 2>&1
  fi
}

pause() { sleep "$BACKOFF"; BACKOFF=$((BACKOFF * 2)); }

apply_label() {   # sets $why on failure
  local has=0 i out rc
  if gh pr view "$PR" --repo "$REPO" --json labels --jq '.labels[].name' 2>/dev/null | grep -qxF "$LABEL"; then has=1; fi
  for ((i = 1; i <= TRIES; i++)); do
    rc=0; out=""
    if [ "$has" = 1 ]; then
      out="$(gh pr edit "$PR" --repo "$REPO" --remove-label "$LABEL" 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] && has=0
    fi
    if [ "$rc" -eq 0 ]; then
      out="$(gh pr edit "$PR" --repo "$REPO" --add-label "$LABEL" 2>&1)"; rc=$?
    fi
    [ "$rc" -eq 0 ] && break
    [ "$i" -lt "$TRIES" ] && pause
  done
  if [ "$rc" -ne 0 ]; then
    why="the label write failed $TRIES time(s) (rc=$rc): $(printf '%s' "$out" | tail -3 | tr '\n' ' ')"
    return 1
  fi
  for ((i = 1; i <= TRIES; i++)); do
    out="$(verify_label)" && return 0
    [ "$i" -lt "$TRIES" ] && pause
  done
  why="read-back after the write does not show a valid label: $(printf '%s' "$out" | tail -2 | tr '\n' ' ')"
  return 1
}

label=applied
why=""
if ! verify_label >/dev/null; then
  apply_label || label=failed
fi
if [ "$label" = failed ]; then
  echo "SIGNAL_INTENT_FAIL pr=$PR label=failed queue=$queue: $why" >&2
fi

if [ "$queue" = absent ]; then
  echo "SIGNAL_INTENT pr=$PR label=$label queue=absent arm=skipped"
  [ "$label" = applied ] && exit 0
  exit 2
fi

out="$(gh pr merge "$PR" --repo "$REPO" --auto 2>&1)"; rc=$?
if [ "$rc" -ne 0 ] && ! printf '%s' "$out" | grep -qi "already queued\|auto-merge enabled\|already enabled\|clean"; then
  echo "SIGNAL_INTENT_FAIL pr=$PR label=$label queue=$queue arm=failed (rc=$rc): $(printf '%s' "$out" | tail -3 | tr '\n' ' ')" >&2
  exit 3
fi
echo "SIGNAL_INTENT pr=$PR label=$label queue=$queue arm=armed"
[ "$label" = applied ] && exit 0
exit 2
