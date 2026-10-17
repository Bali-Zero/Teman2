#!/usr/bin/env bash
# signal_merge_intent.sh <PR> — the one ship gesture: label first, then arm.
#
# The LocalCI merger merges only a PR carrying `localci:merge-shadow-ok`, applied by an
# admin/maintain User (or a write-role author on its own same-repo PR, B42) AFTER the head's push (scripts/localci/merger.py, B2a). GitHub
# auto-merge is armed on top of it ONLY while the base branch still has a `merge_queue`
# rule; after the phase-F flip the rule is gone and the arm is skipped (a skip, not an error).
#
# B31'' — NO decision lives in this file: it is `exec python3 scripts/localci/label_intent.py`, whose pure `plan()` is the whole
# logic (exhaustively driven by scripts/localci/tests/test_label_intent.py). What the plan does, for the record:
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
# Exit: 0 ok, 1 usage, 2 label failed (also when the arm failed), 3 arm failed with a valid label.
# Env: SIGNAL_INTENT_REPO (default Bali-Zero/Teman2), SIGNAL_INTENT_BASE (default main),
#      SIGNAL_INTENT_TRIES (default 4), SIGNAL_INTENT_BACKOFF_S (default 2, doubled each try),
#      SIGNAL_INTENT_DEADLINE_S (default 45),
#      SIGNAL_INTENT_SHOW_CONFIG=1 (print the effective tries/deadline/backoff and exit 0 WITHOUT labelling anything: a diagnostic, never export it),
#      SIGNAL_INTENT_VERIFY (a command run as `<cmd> <repo> <pr>`: rc 0 valid, 1 not valid, ANY other rc unknown; default label_census.py verify).
HERE="$(dirname "${BASH_SOURCE[0]}")"
exec python3 "$HERE/localci/label_intent.py" "$@"
