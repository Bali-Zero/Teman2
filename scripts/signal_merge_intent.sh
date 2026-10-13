#!/usr/bin/env bash
# signal_merge_intent.sh <PR> — the one ship gesture: label first, then arm.
#
# The LocalCI merger merges only a PR carrying `localci:merge-shadow-ok`,
# applied by an admin/maintain User (scripts/localci/merger.py). GitHub
# auto-merge is armed on top of it ONLY while the base branch still has a
# `merge_queue` rule; after the phase-F flip the rule is gone and the arm is
# skipped (a skip, not an error).
#
# Output (one line): SIGNAL_INTENT pr=N label=applied queue=present|absent|unknown arm=armed|skipped
# Exit: 0 ok, 1 usage, 2 label failed with the queue rule ABSENT (nothing to arm), 3 arm failed.
# While the queue rule is present/unknown a label failure only WARNs: the arm still runs and the
# exit code is the ARM result, as before the flip.
# Probe failure => queue=unknown => arm attempted, as before the flip.
# Env: SIGNAL_INTENT_REPO (default Bali-Zero/Teman2), SIGNAL_INTENT_BASE (default main).
set -uo pipefail

REPO="${SIGNAL_INTENT_REPO:-Bali-Zero/Teman2}"
BASE="${SIGNAL_INTENT_BASE:-main}"
LABEL="localci:merge-shadow-ok"

PR="${1:-}"
case "$PR" in
  ''|*[!0-9]*) echo "usage: signal_merge_intent.sh <PR-number>" >&2; exit 1 ;;
esac

queue="$(SIGNAL_INTENT_REPO="$REPO" SIGNAL_INTENT_BASE="$BASE" "$(dirname "${BASH_SOURCE[0]}")/merge_queue_rule.sh")"

label=applied
out="$(gh pr edit "$PR" --repo "$REPO" --add-label "$LABEL" 2>&1)"; rc=$?
if [ "$rc" -ne 0 ]; then
  msg="SIGNAL_INTENT_FAIL pr=$PR label=failed queue=$queue (rc=$rc): $(printf '%s' "$out" | tail -3 | tr '\n' ' ')"
  if [ "$queue" = absent ]; then
    echo "$msg" >&2
    exit 2
  fi
  # The queue still exists: the arm is what merges, so a label failure must not block it.
  echo "WARN $msg — arming anyway (the label is not load-bearing while merge_queue exists)" >&2
  label=failed
fi

if [ "$queue" = absent ]; then
  echo "SIGNAL_INTENT pr=$PR label=applied queue=absent arm=skipped"
  exit 0
fi

out="$(gh pr merge "$PR" --repo "$REPO" --auto 2>&1)"; rc=$?
if [ "$rc" -ne 0 ] && ! printf '%s' "$out" | grep -qi "already queued\|auto-merge enabled\|already enabled\|clean"; then
  echo "SIGNAL_INTENT_FAIL pr=$PR label=$label queue=$queue arm=failed (rc=$rc): $(printf '%s' "$out" | tail -3 | tr '\n' ' ')" >&2
  exit 3
fi
echo "SIGNAL_INTENT pr=$PR label=$label queue=$queue arm=armed"
