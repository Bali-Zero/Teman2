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
#      valid => nothing is written, no remove, no new event; UNREADABLE (rc other than 0/1) is
#      unknown, not invalid: the read is retried with the same bound and nothing is ever removed on unknown;
#   2. absent => add; present but not valid (its event predates the head) => remove, then add
#      (an add of a present label makes no event);
#   3. the add is retried with bounded backoff, then READ BACK again with the same bound (each phase
#      starts its backoff afresh: the SLEEP budget is 3 phases x (2+4+8)s = 42s) under a WALL-CLOCK deadline
#      (SIGNAL_INTENT_DEADLINE_S, default 45) checked before EVERY network call of the label phase
#      (the first read, the view, the remove, the add, every read-back) and before every sleep, which is
#      itself capped at the time left; hitting it is the same FATAL exit 2 with the deadline named. The
#      poller kills the helper at 60s: the 45s deadline, one in-flight call and the arm must stay below it
#      (pinned by test);
#   4. a label that is not shown valid at the end is FATAL: exit 2, SIGNAL_INTENT_FAIL on stderr,
#      whatever the queue state (while the queue rule exists the arm is still attempted first —
#      it is what merges until the flip — and the exit stays 2).
#
# Output (one line): SIGNAL_INTENT pr=N label=applied|failed queue=present|absent|unknown arm=armed|skipped
# Exit: 0 ok, 1 usage, 2 label failed, 3 arm failed.
# Env: SIGNAL_INTENT_REPO (default Bali-Zero/Teman2), SIGNAL_INTENT_BASE (default main),
#      SIGNAL_INTENT_TRIES (default 4), SIGNAL_INTENT_BACKOFF_S (default 2, doubled each try),
#      SIGNAL_INTENT_DEADLINE_S (default 45),
#      SIGNAL_INTENT_SHOW_CONFIG=1 (print the effective tries/deadline/backoff and exit 0: how the defaults are pinned),
#      SIGNAL_INTENT_VERIFY (a command run as `<cmd> <repo> <pr>`: 0 valid, other not; default label_census.py verify).
set -uo pipefail

SECONDS=0   # bash imports SECONDS from the environment: the deadline counts from HERE, whatever the caller exported
REPO="${SIGNAL_INTENT_REPO:-Bali-Zero/Teman2}"
BASE="${SIGNAL_INTENT_BASE:-main}"
LABEL="localci:merge-shadow-ok"
DEADLINE_DEFAULT=45
TRIES="${SIGNAL_INTENT_TRIES:-}"
DEADLINE="${SIGNAL_INTENT_DEADLINE_S:-}"
BACKOFF_START="${SIGNAL_INTENT_BACKOFF_S:-}"
deadline_hit=0
HERE="$(dirname "${BASH_SOURCE[0]}")"

PR="${1:-}"
case "$PR" in
  ''|*[!0-9]*) echo "usage: signal_merge_intent.sh <PR-number>" >&2; exit 1 ;;
esac
case "$TRIES" in *[!0-9]*) TRIES=0 ;; esac
TRIES=$((10#${TRIES:-0}))
[ "$TRIES" -ge 1 ] || TRIES=4
case "$DEADLINE" in ''|*[!0-9]*) DEADLINE=$DEADLINE_DEFAULT ;; esac
DEADLINE=$((10#$DEADLINE))
case "$BACKOFF_START" in ''|*[!0-9]*) BACKOFF_START=2 ;; esac
BACKOFF_START=$((10#$BACKOFF_START))
if [ "${SIGNAL_INTENT_SHOW_CONFIG:-}" = 1 ]; then echo "tries=$TRIES deadline=$DEADLINE backoff=$BACKOFF_START"; exit 0; fi
BACKOFF=$BACKOFF_START

queue="$(SIGNAL_INTENT_REPO="$REPO" SIGNAL_INTENT_BASE="$BASE" "$HERE/merge_queue_rule.sh")"

verify_label() {   # 0 valid; otherwise the reason is on stdout/stderr
  if [ -n "${SIGNAL_INTENT_VERIFY:-}" ]; then
    "$SIGNAL_INTENT_VERIFY" "$REPO" "$PR" 2>&1
  else
    python3 "$HERE/localci/label_census.py" verify --repo "$REPO" --pr "$PR" 2>&1
  fi
}

deadline_note() { if [ "$deadline_hit" = 1 ]; then printf ' (deadline %ss reached)' "$DEADLINE"; fi; }

budget_ok() {   # 1 once the wall-clock deadline is spent; asked before every network call of the label phase
  if [ $((DEADLINE - SECONDS)) -le 0 ]; then deadline_hit=1; return 1; fi
}

pause() {   # no sleep once the deadline is spent, and none past it; every call after it is refused by budget_ok anyway
  budget_ok || return 0
  local left=$((DEADLINE - SECONDS))
  if [ "$BACKOFF" -lt "$left" ]; then sleep "$BACKOFF"; else sleep "$left"; fi
  BACKOFF=$((BACKOFF * 2))
}

apply_label() {   # sets $why on failure
  local has=0 i out="" rc=1
  BACKOFF=$BACKOFF_START
  if budget_ok && gh pr view "$PR" --repo "$REPO" --json labels --jq '.labels[].name' 2>/dev/null | grep -qxF "$LABEL"; then has=1; fi
  for ((i = 1; i <= TRIES; i++)); do
    rc=0; out=""
    if [ "$has" = 1 ]; then
      if budget_ok; then out="$(gh pr edit "$PR" --repo "$REPO" --remove-label "$LABEL" 2>&1)"; rc=$?; else rc=1; fi
      [ "$rc" -eq 0 ] && has=0
    fi
    if [ "$rc" -eq 0 ]; then
      if budget_ok; then out="$(gh pr edit "$PR" --repo "$REPO" --add-label "$LABEL" 2>&1)"; rc=$?; else rc=1; fi
    fi
    [ "$rc" -eq 0 ] && break
    if [ "$i" -lt "$TRIES" ]; then pause; fi
  done
  if [ "$rc" -ne 0 ]; then
    why="the label write failed (rc=$rc)$(deadline_note): $(printf '%s' "$out" | tail -3 | tr '\n' ' ')"
    return 1
  fi
  BACKOFF=$BACKOFF_START
  for ((i = 1; i <= TRIES; i++)); do
    budget_ok || break
    out="$(verify_label)" && return 0
    if [ "$i" -lt "$TRIES" ]; then pause; fi
  done
  why="read-back after the write does not show a valid label$(deadline_note): $(printf '%s' "$out" | tail -2 | tr '\n' ' ')"
  return 1
}

label=applied
why=""
vrc=2
for ((i = 1; i <= TRIES; i++)); do
  budget_ok || break
  verify_label >/dev/null; vrc=$?
  [ "$vrc" -eq 0 ] || [ "$vrc" -eq 1 ] && break
  if [ "$i" -lt "$TRIES" ]; then pause; fi
done
case "$vrc" in
  0) ;;
  1) apply_label || label=failed ;;
  *) label=failed; why="the label could not be read (rc=$vrc)$(deadline_note): nothing was changed" ;;
esac
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
