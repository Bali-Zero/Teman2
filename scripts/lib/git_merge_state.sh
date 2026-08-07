#!/usr/bin/env bash
# git_merge_state.sh — "is a merge still open in this working tree?"
#
# Sourced by scripts/docs_inventory_regen.sh. Lives here, not inlined, for one
# reason: that script's first act is `cd "$SCRIPT_DIR/.."`, so it always
# operates on the real repo and a test can never put it in front of a fake one.
# A guard nobody can execute in a controlled world is a guard nobody has proven
# (scar #3: no guard ships without guilt AND innocence).
#
# WHY IT EXISTS, measured 2026-08-07 on PR #3750: the inventory was regenerated
# between `git merge` and `git commit`, while the merge was still conflicted.
# At that moment HEAD is still the BRANCH's own tip — the merged commits exist
# only in MERGE_HEAD, not in HEAD's history — so `git log -1 -- <path>`, which
# is where docs_audit.py reads `last_touched_date`, walked a history that did
# not contain what main had just landed and returned the older date. Two rows
# (docs/AI_ONBOARDING.md, docs/runbooks/README.md) went out a day stale and the
# `inventory-check` gate charged the PR for them. Nothing was broken: the
# ORDERING was wrong, and nothing said so.
#
# WARNING, NOT REFUSAL — deliberate. Resolving a DOCS_INVENTORY.md merge
# conflict by re-running the generator IS the correct workflow (a derived file
# has one authority, and it is not a hand-merge). A guard that refused would
# block the very path it is meant to support; it would also be the kind of
# obstacle whose documented escape is "disable the guard", which turns a
# usability complaint into a disarmed check (superscar #3 → #2). So it informs
# and gets out of the way: run the generator now to resolve the conflict, then
# run it AGAIN after the merge commit exists.

# Print a warning to stderr iff `repo` has an unfinished merge.
# ALWAYS returns 0: this is advice, never a verdict. A caller must not be able
# to fail because of it, and a future `set -e` in a caller must not turn advice
# into an abort.
warn_if_merge_in_progress() {
  local repo="${1:-.}"
  if ! git -C "$repo" rev-parse --verify -q MERGE_HEAD >/dev/null 2>&1; then
    return 0
  fi
  cat >&2 <<'EOF'
docs_inventory_regen: WARNING — a merge is still open in this working tree.

  Until you commit it, HEAD is your branch's own tip: the commits you are
  merging live in MERGE_HEAD and are NOT yet in the history `git log` walks.
  Commit dates computed now will therefore MISS whatever the other side just
  landed, and the rows for files that side touched will be written stale.

  Running the generator now to resolve a docs/DOCS_INVENTORY.md conflict is
  correct — that is what it is for. Just run it ONCE MORE after `git commit`,
  and commit that result too.
EOF
  return 0
}

# DECLARED LIMIT — what this deliberately does not look at:
#   * A rebase in progress is NOT flagged, and that is a claim about the
#     mechanism rather than an omission: while a rebase is stopped, the
#     upstream commits are already IN HEAD's history (that is what rebase
#     does), so the failure above cannot occur.
#   * CHERRY_PICK_HEAD / REVERT_HEAD are not flagged. They share the "not yet
#     in HEAD" property in principle, but neither has been measured biting this
#     pipeline, and a guard that names a case it has never seen invites the
#     reader to trust a coverage claim nobody checked. If one shows up, it gets
#     its own corpus row here.
