#!/usr/bin/env bash
# merge_queue_rule.sh — print `present`, `absent` or `unknown` for the base branch's
# `merge_queue` rule. The ONE probe shared by signal_merge_intent.sh and the
# queue watchers: while the rule exists the GitHub arm merges and a label alone is not
# armed; once it is gone the LocalCI label is the arm. A failed probe prints `unknown`
# and callers keep the arm-based behaviour.
# Env: SIGNAL_INTENT_REPO (default Bali-Zero/Teman2), SIGNAL_INTENT_BASE (default main).
REPO="${SIGNAL_INTENT_REPO:-Bali-Zero/Teman2}"
BASE="${SIGNAL_INTENT_BASE:-main}"
n="$(gh api "repos/$REPO/rules/branches/$BASE" --jq '[.[] | select(.type == "merge_queue")] | length' 2>/dev/null)" || n=""
case "$n" in
  0) echo absent ;;
  ''|*[!0-9]*) echo unknown ;;
  *) echo present ;;
esac
