#!/usr/bin/env bash
# pr_watch.sh — deterministic PR terminal-state watcher.
#
# Owner order (2026-08-21): 54% of a PR-session's output tokens were being
# spent AFTER `gh pr create` — babysitting CI by hand (14% of all Bash calls
# were `gh pr checks/view/run`). This replaces that manual poll loop: arm
# with `gh pr merge --auto`, run this in the background, and read its
# terminal-event lines instead of re-deriving PR state from scratch every
# few minutes.
#
# USAGE
#   scripts/pr_watch.sh [--repo OWNER/REPO] <PR#> [<PR#>...]
#
# Emits ONE line per event to stdout:
#   #N MERGED <mergedAt>
#   #N CLOSED
#   #N REQUIRED-FAILING: <name1,name2,...>   (once per NEW failing set)
#   #N MISSING-REQUIRED: <ctx1,ctx2,...>     (once per NEW missing set)
#   #N EJECTED-FROM-QUEUE                    (left the merge queue while
#                                              still OPEN — the ejection
#                                              class the runbook §6 Step 2b
#                                              describes)
# and exactly one final line: ALL_DONE (exit 0) or TIMEOUT (exit 1).
#
# DESIGN RULES (blood-bought, cicatrix-superscar.md — same discipline as
# scripts/mq.sh, which this script deliberately mirrors so the two tools
# read as one family):
#   - Every `gh` call's rc is captured errexit-immune (`|| var=$?`), never a
#     bare assignment under `set -e` (W101 — a bare assignment aborts the
#     script BEFORE the caller can inspect the rc it was written to inspect).
#   - `gh pr checks` is judged by CONTENT, not exit code alone (W104): its rc
#     is data-dependent (non-zero can mean "a check is failing", not "the
#     tool broke") — only rc!=0 WITH an empty body is a real transient
#     failure. `gh pr view` / `gh api` rc IS a straightforward tool-error
#     signal, so those are checked on rc alone.
#   - `autoMergeRequest` is NEVER read to infer queue state (W118): it reads
#     null both while a PR is healthily queued AND after it has been
#     ejected — indistinguishable from that one field. The only way to tell
#     "still queued" from "ejected while still open" apart is the GraphQL
#     `isInMergeQueue` truth source, which is what EJECTED-FROM-QUEUE below
#     is built on.
#   - MISSING-REQUIRED is computed via `comm -23` against the FULL reported
#     check-name set (not just the ones flagged isRequired) — this is what
#     catches a skipped matrix job: its suffixed required context never
#     shows up in the reported set at all, under any name (2026-08-21 scar,
#     `discovery_skipped_matrix_job_never_emits_its_required_contexts`).
#   - No arrays expanded when they might be empty (bash 3.2 on macOS raises
#     "unbound variable" under `set -u` on `"${empty_arr[@]}"` — reproduced
#     against this repo's shipped bash). Per-PR "done" state lives in a
#     state-dir file, not a shrinking array, so the main loop never expands
#     one.
#   - Field delimiter in every `IFS='|' read -r` below is `|`, never a tab:
#     under POSIX "IFS whitespace" rules `read` COLLAPSES consecutive
#     whitespace delimiters instead of yielding an empty field, and a blank
#     middle field would silently shift everything after it by one.
#
# No Telegram, no writes outside its own state dir. Poll interval
# PR_WATCH_INTERVAL (default 180s), ceiling PR_WATCH_MAX_MIN (default 120).
set -euo pipefail

PR_WATCH_INTERVAL="${PR_WATCH_INTERVAL:-180}"
PR_WATCH_MAX_MIN="${PR_WATCH_MAX_MIN:-120}"
PR_WATCH_REPO="${PR_WATCH_REPO:-}"

_usage() {
  cat <<USAGE
pr_watch.sh — deterministic PR terminal-state watcher

  scripts/pr_watch.sh [--repo OWNER/REPO] <PR#> [<PR#>...]

Env: PR_WATCH_INTERVAL (poll seconds, default 180)
     PR_WATCH_MAX_MIN  (ceiling minutes, default 120)
     PR_WATCH_REPO     (same as --repo)

Exits 0 on ALL_DONE, 1 on TIMEOUT, 2 on a usage/setup error.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  _usage
  exit 0
fi

if [[ "${1:-}" == "--repo" ]]; then
  [[ -n "${2:-}" ]] || { echo "pr_watch: --repo requires a value" >&2; exit 2; }
  PR_WATCH_REPO="$2"
  shift 2
fi

if [[ $# -eq 0 ]]; then
  _usage
  exit 2
fi

for _pr in "$@"; do
  [[ "$_pr" =~ ^[0-9]+$ ]] || { echo "pr_watch: not a PR number: '$_pr'" >&2; exit 2; }
done

PR_WATCH_TMP_ERR="$(mktemp "${TMPDIR:-/tmp}/pr_watch_err.XXXXXX")"
STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pr_watch.XXXXXX")"
trap 'rm -rf "$STATE_DIR" "$PR_WATCH_TMP_ERR"' EXIT

# Run `gh "$@"`, capturing stdout in GH_OUT, stderr in GH_ERR, rc in GH_RC.
# Never trips `set -e` on its own — every gh call in this script goes
# through here so a failure is DATA the caller inspects, not an abort.
_gh() {
  GH_RC=0
  GH_OUT="$(gh "$@" 2>"$PR_WATCH_TMP_ERR")" || GH_RC=$?
  GH_ERR="$(cat "$PR_WATCH_TMP_ERR" 2>/dev/null || true)"
  : > "$PR_WATCH_TMP_ERR"
}

if [[ -z "$PR_WATCH_REPO" ]]; then
  _gh repo view --json nameWithOwner --jq .nameWithOwner
  if (( GH_RC != 0 )) || [[ -z "$GH_OUT" ]]; then
    echo "pr_watch: could not resolve repo (rc=$GH_RC): ${GH_ERR:0:200} — pass --repo OWNER/REPO" >&2
    exit 2
  fi
  PR_WATCH_REPO="$GH_OUT"
fi
REPO="$PR_WATCH_REPO"
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
REPO_FLAGS=(--repo "$REPO")

_last() { [[ -f "$1" ]] && cat "$1" || true; }  # _last <file> -> content or ""

# _tick <pr> — one probe pass. Prints event lines as a side effect. Creates
# $STATE_DIR/<pr>.done when a terminal state is reached; the main loop reads
# that file's existence, never this function's return value, as the signal.
_tick() {
  local pr="$1"

  _gh pr view "$pr" "${REPO_FLAGS[@]}" --json state,mergedAt,mergeStateStatus
  if (( GH_RC != 0 )); then
    echo "  (transient) gh pr view #$pr failed rc=$GH_RC: ${GH_ERR:0:160}" >&2
    return 0
  fi
  local state="" merged_at=""
  IFS='|' read -r state merged_at < <(
    printf '%s' "$GH_OUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print((d.get("state") or "") + "|" + (d.get("mergedAt") or ""))
'
  )

  if [[ "$state" == "MERGED" || -n "$merged_at" ]]; then
    echo "#$pr MERGED $merged_at"
    : > "$STATE_DIR/$pr.done"
    return 0
  fi
  if [[ "$state" == "CLOSED" ]]; then
    echo "#$pr CLOSED"
    : > "$STATE_DIR/$pr.done"
    return 0
  fi

  # Still OPEN — everything below is advisory, never terminal.
  _gh pr checks "$pr" "${REPO_FLAGS[@]}" --json name,state,isRequired
  if (( GH_RC != 0 )) && [[ -z "$GH_OUT" ]]; then
    echo "  (transient) gh pr checks #$pr failed rc=$GH_RC: ${GH_ERR:0:160}" >&2
  else
    local checks_json="${GH_OUT:-[]}"
    _emit_required_failing "$pr" "$checks_json"
    _emit_missing_required "$pr" "$checks_json"
  fi

  _emit_queue_ejection "$pr"
  return 0
}

# _emit_required_failing <pr> <checks_json> — names every isRequired check
# NOT in {SUCCESS,SKIPPED,NEUTRAL}, deduped against the last-emitted set.
_emit_required_failing() {
  local pr="$1" checks_json="$2"
  local failing
  failing="$(printf '%s' "$checks_json" | python3 -c '
import json, sys
try:
    checks = json.load(sys.stdin) or []
except Exception:
    checks = []
ok_states = {"SUCCESS", "SKIPPED", "NEUTRAL"}
names = sorted(
    c.get("name", "") for c in checks
    if c.get("isRequired") and c.get("state") not in ok_states
)
print(",".join(names))
')"
  local last_file="$STATE_DIR/$pr.failing"
  local last; last="$(_last "$last_file")"
  if [[ -n "$failing" && "$failing" != "$last" ]]; then
    echo "#$pr REQUIRED-FAILING: $failing"
    printf '%s' "$failing" > "$last_file"
  elif [[ -z "$failing" && -n "$last" ]]; then
    : > "$last_file"   # silent reset on recovery — a later re-failure with
                        # the SAME names is a NEW set relative to "" and re-alerts
  fi
}

# _emit_missing_required <pr> <checks_json> — branch-protection required
# contexts absent from the reported name set entirely, via comm -23. This is
# what catches a skipped matrix job: its suffixed context never appears
# under ANY name in the reported set, required-flag or not — so the
# comparison set is every reported name, not just the required-flagged ones.
_emit_missing_required() {
  local pr="$1" checks_json="$2"
  _gh api "repos/$REPO/branches/main/protection" --jq '.required_status_checks.checks[].context'
  if (( GH_RC != 0 )); then
    echo "  (transient) branch-protection lookup failed for #$pr rc=$GH_RC: ${GH_ERR:0:160}" >&2
    return 0
  fi
  local req_names="$GH_OUT"
  [[ -n "$req_names" ]] || return 0

  local reported_names
  reported_names="$(printf '%s' "$checks_json" | python3 -c '
import json, sys
try:
    checks = json.load(sys.stdin) or []
except Exception:
    checks = []
print("\n".join(sorted(set(c.get("name", "") for c in checks))))
')"

  local req_sorted="$STATE_DIR/$pr.req_sorted.tmp" rep_sorted="$STATE_DIR/$pr.rep_sorted.tmp"
  printf '%s\n' "$req_names" | sort > "$req_sorted"
  printf '%s\n' "$reported_names" | sort > "$rep_sorted"
  local missing
  missing="$(comm -23 "$req_sorted" "$rep_sorted" | sed '/^$/d' | tr '\n' ',' | sed 's/,$//')"
  rm -f "$req_sorted" "$rep_sorted"

  local last_file="$STATE_DIR/$pr.missing"
  local last; last="$(_last "$last_file")"
  if [[ -n "$missing" && "$missing" != "$last" ]]; then
    echo "#$pr MISSING-REQUIRED: $missing"
    printf '%s' "$missing" > "$last_file"
  elif [[ -z "$missing" && -n "$last" ]]; then
    : > "$last_file"
  fi
}

# _emit_queue_ejection <pr> — GraphQL isInMergeQueue is the ONLY reliable
# signal here (W118): a transition true->false while the PR is still OPEN
# (already excluded from reaching this point when MERGED/CLOSED) means the
# queue dropped it, not that it landed.
_emit_queue_ejection() {
  local pr="$1"
  # shellcheck disable=SC2016  # GraphQL $vars, must stay single-quoted (unrelated to $OWNER/$NAME/$pr below)
  _gh api graphql -f query='
    query($owner:String!,$name:String!,$number:Int!) {
      repository(owner:$owner,name:$name) {
        pullRequest(number:$number) {
          isInMergeQueue
          mergeQueueEntry { state position }
        }
      }
    }' -F owner="$OWNER" -F name="$NAME" -F number="$pr"
  if (( GH_RC != 0 )); then
    echo "  (transient) merge-queue probe failed for #$pr rc=$GH_RC: ${GH_ERR:0:160}" >&2
    return 0
  fi
  local in_queue="0"
  in_queue="$(printf '%s' "$GH_OUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
pr = ((d.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
print("1" if pr.get("isInMergeQueue") else "0")
')"
  local last_file="$STATE_DIR/$pr.inqueue"
  local last; last="$(_last "$last_file")"
  [[ -n "$last" ]] || last="0"
  if [[ "$last" == "1" && "$in_queue" == "0" ]]; then
    echo "#$pr EJECTED-FROM-QUEUE"
  fi
  printf '%s' "$in_queue" > "$last_file"
}

start_ts=$(date +%s)
ceiling=$(( PR_WATCH_MAX_MIN * 60 ))

while :; do
  now=$(date +%s)
  if (( now - start_ts >= ceiling )); then
    echo "TIMEOUT"
    exit 1
  fi

  all_done=1
  for pr in "$@"; do
    [[ -f "$STATE_DIR/$pr.done" ]] && continue   # already terminal — skip, not re-probed
    all_done=0
    _tick "$pr"
  done

  if (( all_done )); then
    echo "ALL_DONE"
    exit 0
  fi

  sleep "$PR_WATCH_INTERVAL"
done
