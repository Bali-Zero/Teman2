#!/usr/bin/env bash
# lane_ship.sh — deterministic ship tail for an implementer-lane worktree.
#
# WHY THIS EXISTS (Zero, 2026-08-21): two Sonnet lanes finished with only an
# idle notification and no report — the orchestrator had no reliable signal
# that a lane's work had actually reached a PR, let alone an armed one. This
# script is the missing tail: refuse-if-not-ready -> push -> reuse-or-create
# PR -> arm -> GraphQL-verify, ending in exactly ONE machine-readable line
# (LANE_SHIP_OK / LANE_SHIP_FAIL) an orchestrator can grep for. See
# docs/runbooks/agent-worktree-broker.md "Lane report contract" for how a
# lane's final message is supposed to use this.
#
# Usage:
#   scripts/lane_ship.sh <worktree> "<PR title>" [--body-file <f>] [--no-arm]
#
# Steps:
#   1. refuse if <worktree> IS the main checkout, or has uncommitted changes
#      (prints them — never silently discards or decides for you)
#   2. git -C <worktree> push -u origin HEAD, judged by CAPTURED exit code
#   3. reuse the PR for this branch if one exists, else `gh pr create`
#      (body MUST carry a "## Adversarial review" section; a missing one
#      gets a placeholder appended, never silently dropped)
#   4. arm `gh pr merge --auto <N>` BARE — no strategy flag, the queue
#      refuses them (CLAUDE.md "Workflow rules" / feedback_arm_automerge_
#      default_not_leave_to_operator.md); "already queued"/clean is a
#      SUCCESS shape, not a failure (mq.sh precedent)
#   5. verify via GraphQL that autoMergeRequest.enabledAt is set OR
#      isInMergeQueue is true (W118: `autoMergeRequest` alone reads false
#      while a PR sits INSIDE the queue) and print the one verdict line
#
# DESIGN RULES (blood-bought, cicatrix-superscar.md — same discipline as
# scripts/mq.sh, which this script reuses conventions from but does not
# invoke, since mq.sh operates on PR numbers already known, and this script's
# job is to GET one):
#   - every external call's rc is captured errexit-immune (`|| var=$?`,
#     never a bare assignment under `set -e` — W101: the bare form aborts
#     the script BEFORE the caller can inspect the rc it exists to inspect)
#   - gh's answer is judged by CONTENT, never exit code alone (W104)
#   - a command whose exit code matters is never piped into `tail`/`grep`
#     directly (W97) — rc is captured on the command itself first
#   - the merge-queue verify step reads `isInMergeQueue` too, not only
#     `autoMergeRequest.enabledAt` (W118 — a PR can be armed and IN the
#     queue while the latter alone still reads false)
#   - the main-checkout / worktree-root check uses the SAME derivation as
#     infra/claude-hooks/worktree_isolation.py::_derive_repo_root()
#     (git rev-parse --path-format=absolute --git-common-dir) so this tool
#     and that hook never invent two different answers for "where is main"
#     (cicatrix family #3 lesson: two tools that must agree on a boundary
#     and don't are how an over/under-match pair is born)
#
# bash 3.2 compatible (macOS ships 3.2.57) — no arrays (an empty array under
# `set -u` on 3.2 raises "unbound variable"), no associative arrays, no
# process-substitution `<( )` with a `#` comment as its immediately-preceding
# line (mq.sh's own scar: bash 3.2 mis-parses that as an unterminated paren).
set -euo pipefail

REPO="${LANE_SHIP_REPO:-Bali-Zero/Teman2}"

_die() {  # _die <reason> [exit_code]
  echo "LANE_SHIP_FAIL reason=\"$1\"" >&2
  exit "${2:-1}"
}

_usage() {
  echo 'usage: lane_ship.sh <worktree> "<PR title>" [--body-file <f>] [--no-arm]' >&2
}

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
if [ "$#" -lt 2 ]; then
  _usage
  exit 1
fi
WORKTREE="$1"
PR_TITLE="$2"
shift 2

BODY_FILE=""
NO_ARM=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --body-file)
      [ "$#" -ge 2 ] || _die "--body-file requires a path"
      BODY_FILE="$2"
      shift 2
      ;;
    --no-arm)
      NO_ARM=1
      shift
      ;;
    *)
      _die "unknown argument '$1'"
      ;;
  esac
done

[ -d "$WORKTREE" ] || _die "worktree not found: $WORKTREE"

# ---------------------------------------------------------------------------
# Step 1 — refuse main checkout / dirty worktree
# ---------------------------------------------------------------------------
# Both sides below are resolved BY GIT (--path-format=absolute), never by
# shell `pwd`: on macOS $TMPDIR (and other spots) sit behind a symlink
# (/var/folders/... -> /private/var/folders/...) that `pwd` does not
# resolve but git's own realpath-based resolution does — mixing the two
# made an identical directory compare as two different ones (caught live
# by this script's own test corpus, not reasoned out in advance).
WT_ABS=""
WT_ABS="$(git -C "$WORKTREE" rev-parse --path-format=absolute --show-toplevel 2>/dev/null)" \
  || _die "not a git worktree (git rev-parse --show-toplevel failed): $WORKTREE"

COMMON_DIR=""
COMMON_DIR="$(git -C "$WT_ABS" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
  || _die "not a git worktree (git rev-parse --git-common-dir failed): $WT_ABS"
MAIN_ROOT="${COMMON_DIR%/.git}"

if [ "$WT_ABS" = "$MAIN_ROOT" ]; then
  _die "refusing: $WT_ABS IS the main checkout, not an isolated worktree (CLAUDE.md Agent Worktree Discipline — see scripts/agent_start.py)"
fi

DIRTY=""
DIRTY="$(git -C "$WT_ABS" status --porcelain 2>/dev/null)" \
  || _die "git status failed in $WT_ABS"
if [ -n "$DIRTY" ]; then
  {
    echo "LANE_SHIP_FAIL reason=\"uncommitted changes in $WT_ABS\""
    echo "$DIRTY"
  } >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 2 — push, judged by CAPTURED exit code (never by output alone, W97/W101)
# ---------------------------------------------------------------------------
PUSH_RC=0
PUSH_LOG="$(git -C "$WT_ABS" push -u origin HEAD 2>&1)" || PUSH_RC=$?
if [ "$PUSH_RC" -ne 0 ]; then
  {
    echo "LANE_SHIP_FAIL reason=\"git push failed (rc=$PUSH_RC)\""
    printf '%s\n' "$PUSH_LOG" | tail -40
  } >&2
  exit 2
fi

BRANCH=""
BRANCH="$(git -C "$WT_ABS" rev-parse --abbrev-ref HEAD 2>/dev/null)" \
  || _die "could not determine current branch in $WT_ABS" 2

# gh wrapper: every call runs FROM $WT_ABS (so gh resolves the right repo/
# remote unambiguously) and captures rc/stdout+stderr together — the caller
# always inspects $GH_RC before trusting $GH_OUT's shape (W104).
_gh() {
  GH_RC=0
  GH_OUT="$(cd "$WT_ABS" && gh "$@" 2>&1)" || GH_RC=$?
}

# ---------------------------------------------------------------------------
# Step 3 — reuse the PR for this branch, or create one
# ---------------------------------------------------------------------------
PR_NUMBER=""
PR_URL=""

_gh pr view "$BRANCH" --repo "$REPO" --json number,url
if [ "$GH_RC" -eq 0 ]; then
  PR_NUMBER="$(printf '%s' "$GH_OUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("number") or "")
except Exception:
    print("")
' 2>/dev/null || true)"
  PR_URL="$(printf '%s' "$GH_OUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("url") or "")
except Exception:
    print("")
' 2>/dev/null || true)"
fi

if [ -z "$PR_NUMBER" ]; then
  BODY_CONTENT=""
  if [ -n "$BODY_FILE" ]; then
    [ -f "$BODY_FILE" ] || _die "--body-file not found: $BODY_FILE"
    BODY_CONTENT="$(cat "$BODY_FILE")"
  fi
  if ! printf '%s' "$BODY_CONTENT" | grep -q '## Adversarial review'; then
    BODY_CONTENT="$BODY_CONTENT
## Adversarial review
_pending: orchestrating session re-verifies_"
  fi

  TMP_BODY="$(mktemp "${TMPDIR:-/tmp}/lane_ship_body.XXXXXX")"
  printf '%s\n' "$BODY_CONTENT" > "$TMP_BODY"

  _gh pr create --repo "$REPO" --title "$PR_TITLE" --body-file "$TMP_BODY"
  CREATE_RC="$GH_RC"
  CREATE_OUT="$GH_OUT"
  rm -f "$TMP_BODY"

  if [ "$CREATE_RC" -ne 0 ]; then
    _die "gh pr create failed (rc=$CREATE_RC): $(printf '%s' "$CREATE_OUT" | tail -5 | tr '\n' ' ')" 2
  fi

  # `gh pr create` prints the new PR's URL as its last stdout line.
  PR_URL="$(printf '%s' "$CREATE_OUT" | tail -1)"
  PR_NUMBER="${PR_URL##*/}"
fi

case "$PR_NUMBER" in
  ''|*[!0-9]*) _die "could not determine a numeric PR number (got '$PR_NUMBER')" 2 ;;
esac

# ---------------------------------------------------------------------------
# --no-arm: report success now, skip step 4 (arm) and step 5 (verify) —
# verifying "is it armed" after deliberately not arming would always read
# as a false failure.
# ---------------------------------------------------------------------------
if [ "$NO_ARM" -eq 1 ]; then
  LOCAL_HEAD="$(git -C "$WT_ABS" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "LANE_SHIP_OK pr=$PR_NUMBER url=$PR_URL head=$LOCAL_HEAD armed=skipped"
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 4 — arm: bare `gh pr merge --auto <N>`, NEVER a strategy flag (the
# queue refuses them — docs/runbooks/merge-queue-discipline.md). "already
# queued"/"already enabled"/"clean" is a SUCCESS shape even at non-zero rc
# (mq.sh cmd_arm precedent, same grep).
# ---------------------------------------------------------------------------
_gh pr merge "$PR_NUMBER" --repo "$REPO" --auto
if [ "$GH_RC" -ne 0 ] && ! printf '%s' "$GH_OUT" | grep -qi "already queued\|auto-merge enabled\|already enabled\|clean"; then
  _die "gh pr merge --auto failed on #$PR_NUMBER (rc=$GH_RC): $(printf '%s' "$GH_OUT" | tail -5 | tr '\n' ' ')" 2
fi

# ---------------------------------------------------------------------------
# Step 5 — verify via GraphQL (W118: `autoMergeRequest.enabledAt` alone can
# read unset while the PR sits INSIDE the merge queue — `isInMergeQueue` is
# the second, independent signal, and either one is sufficient).
# ---------------------------------------------------------------------------
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

# shellcheck disable=SC2016 # deliberate: $owner/$name/$number are GraphQL
# variable references sent literally via `gh api graphql -f/-F ...`, not
# bash variables — single-quoting is correct here, not a typo (same as
# .github/workflows/merge-queue-watch.yml's own query).
GQL_QUERY='
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      autoMergeRequest { enabledAt }
      isInMergeQueue
      headRefOid
      url
    }
  }
}'

_gh api graphql -f query="$GQL_QUERY" -f owner="$OWNER" -f name="$NAME" -F number="$PR_NUMBER"
if [ "$GH_RC" -ne 0 ]; then
  _die "GraphQL verify failed on #$PR_NUMBER (rc=$GH_RC): $(printf '%s' "$GH_OUT" | tail -5 | tr '\n' ' ')" 3
fi

# Comment intentionally NOT placed directly above the `< <( ... )` line below
# (bash 3.2 mis-parses a `#` there as an unterminated paren — mq.sh scar).
VERIFY_STATUS=""
ARMED_YN=""
HEAD_SHA=""
VERIFY_URL=""
IFS='|' read -r VERIFY_STATUS ARMED_YN HEAD_SHA VERIFY_URL < <(
  printf '%s' "$GH_OUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    pr = ((d.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
except Exception:
    print("parse_error|no||")
    raise SystemExit(0)
amr = pr.get("autoMergeRequest") or {}
enabled_at = amr.get("enabledAt")
in_queue = bool(pr.get("isInMergeQueue"))
head = pr.get("headRefOid") or ""
url = pr.get("url") or ""
if enabled_at:
    print("armed|yes|" + head + "|" + url)
elif in_queue:
    print("armed|queued|" + head + "|" + url)
else:
    print("not_armed|no|" + head + "|" + url)
'
)

FINAL_URL="${VERIFY_URL:-$PR_URL}"

if [ "$VERIFY_STATUS" = "armed" ]; then
  echo "LANE_SHIP_OK pr=$PR_NUMBER url=$FINAL_URL head=$HEAD_SHA armed=$ARMED_YN"
  exit 0
fi

_die "PR #$PR_NUMBER not armed after gh pr merge --auto (autoMergeRequest.enabledAt unset AND isInMergeQueue false)" 3
