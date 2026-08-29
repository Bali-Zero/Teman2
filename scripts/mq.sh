#!/usr/bin/env bash
# mq.sh — merge-queue operations tool (Merge-OS v2, Wave 0).
#
# Absorbs scripts/ci/queue_rearm.sh's arm/requeue reflex + a probe of its own,
# but NEVER reimplements queue_doctor.py's three-queue snapshot — it wraps it.
# Spec: research/operations/2026-08-10-merge-os-v2-submission-system.md §3
# ("`mq.sh` absorbs the probe") + §4 Wave 0.
#
# DESIGN RULES (blood-bought, cicatrix-superscar.md):
#   - Every external call's rc is captured errexit-immune (`|| var=$?`, never
#     a bare assignment under `set -e` — W101: a bare assignment aborts the
#     script BEFORE the caller can inspect the rc it was written to inspect).
#   - `gh`'s output is judged by CONTENT, never by exit code alone (W104):
#     `gh pr checks` returns 0/1/8 inconsistently across scenarios (measured
#     2026-08-10 on this repo — 0 was returned with pending checks present),
#     and `gh pr merge --auto` can print "already queued"/"already enabled"
#     on what looks like a non-zero failure. The JSON/text body decides.
#   - Never `... | tail` a command whose exit code matters (W97) — every rc
#     used downstream is captured directly off the command, not through a pipe.
#   - `mq arm` records the head SHA; `mq watch` is the POST-ARM watcher that
#     enforces "no push after arm" — arm itself is NOT a preflight guarantee
#     (Codex F13, spec §3): temporally, arm cannot see a push that happens
#     after it returns.
#
# VERBS
#   mq status [--all|PR...]            wrap queue_doctor.py, pass-through output
#   mq why-red <PR>                    name/bucket/link of each non-passing required check
#   mq arm <PR>                        record head sha, bare `gh pr merge --auto`, confirm
#   mq state <PR> [--json]             READ-ONLY queue-state oracle; never mutates, and has
#                                      no NOT_ARMED verdict (see scripts/mq_state_verdict.py)
#   mq watch <PR> [--timeout-mins N]   post-arm watcher (default ceiling 120m)
#   mq requeue <PR>                    disable-auto + re-arm (standing cure for ejections)
#   mq dequeue <PR>                    disable-auto + drop the local armed-state file
#   mq handoff                         queue snapshot + armed-state files, paste-ready
#
# State: $MQ_STATE_DIR/armed/<PR>.json (sha + timestamp recorded at arm time),
# dir created 0700 (armed-state is not a secret, but the discipline is cheap).
# Repo: $MQ_REPO, default Bali-Zero/Teman2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${MQ_REPO:-Bali-Zero/Teman2}"
MQ_STATE_DIR="${MQ_STATE_DIR:-$HOME/.nuzantara-mq}"
ARMED_DIR="$MQ_STATE_DIR/armed"
WATCH_INTERVAL_S="${MQ_WATCH_INTERVAL_S:-60}"  # test seam; real usage never sets this

MQ_TMP_ERR="$(mktemp "${TMPDIR:-/tmp}/mq-err.XXXXXX")"
trap 'rm -f "$MQ_TMP_ERR"' EXIT

_die() { echo "mq: $*" >&2; exit 1; }

_require_pr_number() {
  [[ "${1:-}" =~ ^[0-9]+$ ]] || _die "expected a PR number, got: '${1:-<empty>}'"
}

_now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

_state_dir_init() {
  mkdir -p "$ARMED_DIR"
  chmod 0700 "$MQ_STATE_DIR" "$ARMED_DIR" 2>/dev/null || true
}

_state_file() { printf '%s/%s.json' "$ARMED_DIR" "$1"; }

# Run `gh "$@"`, capturing stdout in MQ_OUT, stderr in MQ_ERR, rc in MQ_RC.
# Never trips `set -e` — every gh call in this script goes through here so a
# failure is DATA the caller inspects, not an abort the caller never sees.
_gh() {
  MQ_RC=0
  MQ_OUT="$(gh "$@" 2>"$MQ_TMP_ERR")" || MQ_RC=$?
  MQ_ERR="$(cat "$MQ_TMP_ERR" 2>/dev/null || true)"
  : > "$MQ_TMP_ERR"
}

_usage() {
  cat <<USAGE
mq.sh — merge-queue operations tool (Merge-OS v2 Wave 0)

  mq status [--all|PR...]            wrap queue_doctor.py (pass-through output)
  mq why-red <PR>                    name/bucket/link of each non-passing required check
  mq arm <PR>                        record head sha, bare 'gh pr merge --auto', confirm
  mq state <PR> [--json]             read-only queue-state oracle (never arms, never mutates)
  mq watch <PR> [--timeout-mins N]   post-arm watcher (default ceiling 120m)
  mq requeue <PR>                    disable-auto + re-arm
  mq dequeue <PR>                    disable-auto + drop the local armed-state file
  mq handoff                         queue snapshot + armed-state files, paste-ready

State: $ARMED_DIR/<PR>.json
Repo:  $REPO (override: MQ_REPO=owner/name)
USAGE
}

# ---------------------------------------------------------------------------
cmd_status() {
  local doctor="$SCRIPT_DIR/queue_doctor.py" rc=0
  [[ -f "$doctor" ]] || _die "queue_doctor.py not found at $doctor"
  # queue_doctor.py takes no arguments (no argparse) — any trailing args here
  # (--all, PR numbers) are accepted for the verb table's shape but currently
  # have no effect on its global 3-queue snapshot. Add nothing clever.
  python3 "$doctor" || rc=$?
  return "$rc"
}

# ---------------------------------------------------------------------------
cmd_why_red() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || _die "why-red requires a PR number"
  _require_pr_number "$pr"
  echo "== required checks — PR #$pr ($REPO) =="

  # 1. The names branch protection considers required RIGHT NOW (drifts as CI
  #    grows — docs/runbooks/merge-queue-discipline.md §2, never hardcode the
  #    count). This is what catches the "required check never reported" class
  #    (§6 Step 1 of the runbook): a name that never shows up in #2 below.
  _gh api "repos/$REPO/branches/main/protection" \
      --jq '.required_status_checks.checks[].context'
  local req_names="$MQ_OUT"
  if (( MQ_RC != 0 )); then
    echo "  CANNOT-VERIFY required-check name list (rc=$MQ_RC): ${MQ_ERR:0:160}"
    echo "  (degrading to reported-checks-only — same fallback merge-queue-watch.yml takes)"
    req_names=""
  fi

  # 2. What the PR itself reports, pre-filtered to required checks by gh's own
  #    isRequired-based logic (`--required`). The exit code is NOT the verdict
  #    (W104): gh docs list 0/1/8 for pass/fail/pending, but a live probe on
  #    this repo (2026-08-10) returned 0 with pending entries present — the
  #    JSON body is what gets judged, always.
  _gh pr checks "$pr" --repo "$REPO" --required \
      --json name,bucket,link,description,workflow
  if (( MQ_RC != 0 )) && [[ -z "$MQ_OUT" ]]; then
    echo "  CANNOT-VERIFY — gh pr checks produced no output (rc=$MQ_RC): ${MQ_ERR:0:200}"
    return 3
  fi
  local checks_json="${MQ_OUT:-[]}"

  python3 - "$checks_json" "$req_names" <<'PYEOF'
import json, sys

checks = json.loads(sys.argv[1] or "[]")
required_names = [l for l in sys.argv[2].splitlines() if l.strip()]

by_name = {c.get("name"): c for c in checks}
# gh's own bucket enum: pass, fail, pending, skipping, cancel. "skipping" is
# treated as pass by this repo's sentinel semantics (docs runbook §2/§4).
trouble = [c for c in checks if c.get("bucket") not in ("pass", "skipping")]
missing = [n for n in required_names if n not in by_name] if required_names else []

if not trouble and not missing:
    print("  clean — every required check GitHub reported is pass/skip")
else:
    for c in trouble:
        print(f"  [{c.get('bucket', '?').upper():8}] {c.get('name')}  ({c.get('workflow', '')})")
        if c.get("link"):
            print(f"           {c['link']}")
    for n in missing:
        print(f"  [MISSING ] {n}  — required by branch protection, absent from gh's reported set")
        print("           (\"required check never reported\" class — runbook §6 Step 1)")
PYEOF
}

# ---------------------------------------------------------------------------
_write_armed_state() {  # _write_armed_state <pr> <sha>
  local pr="$1" sha="$2" f
  f="$(_state_file "$pr")"
  python3 - "$f" "$pr" "$sha" "$(_now_iso)" <<'PYEOF'
import json, sys
path, pr, sha, ts = sys.argv[1:5]
with open(path, "w") as fh:
    json.dump({"pr": int(pr), "sha": sha, "armed_at": ts}, fh)
    fh.write("\n")
PYEOF
  chmod 0600 "$f"
}

cmd_arm() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || _die "arm requires a PR number"
  _require_pr_number "$pr"

  _gh pr view "$pr" --repo "$REPO" --json headRefOid
  (( MQ_RC == 0 )) || _die "could not read #$pr's head sha (rc=$MQ_RC): ${MQ_ERR:0:200}"
  local sha=""
  sha="$(printf '%s' "$MQ_OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("headRefOid",""))' 2>/dev/null || true)"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || _die "unexpected headRefOid in response: ${MQ_OUT:0:200}"

  _write_armed_state "$pr" "$sha"
  echo "recorded armed sha for #$pr: $sha"

  # Bare --auto only — the queue owns merge strategy. `--squash` now conflicts
  # with it and arms NOTHING silently (docs/runbooks/merge-queue-discipline.md,
  # measured live PR #3347: "The merge strategy for main is set by the merge
  # queue"). This is the post-arm-watcher design (Codex F13): arm cannot itself
  # guarantee no future push — mq watch is the guarantee.
  _gh pr merge "$pr" --repo "$REPO" --auto
  if (( MQ_RC != 0 )) && ! printf '%s%s' "$MQ_OUT" "$MQ_ERR" | grep -qi "already queued\|auto-merge enabled\|already enabled"; then
    _die "gh pr merge --auto failed (rc=$MQ_RC): $(printf '%s%s' "$MQ_OUT" "$MQ_ERR" | head -1)"
  fi
  echo "arm: ${MQ_OUT:-$MQ_ERR}"

  _gh pr view "$pr" --repo "$REPO" --json autoMergeRequest,mergeStateStatus,headRefOid
  if (( MQ_RC == 0 )); then
    echo "confirm: $MQ_OUT"
  else
    echo "  CANNOT-VERIFY confirm step (rc=$MQ_RC): ${MQ_ERR:0:160} — recorded sha stands, check manually"
  fi
  echo "ARMED #$pr @ $sha"
}

# ---------------------------------------------------------------------------
# mq state — READ-ONLY. Gathers three facts and hands them to the verdict
# module; judges nothing itself. It never calls `gh pr merge`, not even to
# disambiguate: that is a MUTATION, and this verb is what you run when you do
# NOT want to touch the PR. When the answer is INDETERMINATE it NAMES the
# mutation instead of performing it.
#
# Every read degrades to a labelled CANNOT-VERIFY rather than to a value that
# looks like a measurement (W106b: a probe that cannot answer must say so, not
# guess). Only the FIRST read is load-bearing; without it there is no verdict.
cmd_state() {
  local pr="" as_json=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json) as_json=1; shift ;;
      --repo) REPO="${2:-}"; shift 2 ;;
      -*) _die "state: unknown argument '$1'" ;;
      *) pr="$1"; shift ;;
    esac
  done
  [[ -n "$pr" ]] || _die "state requires a PR number"
  _require_pr_number "$pr"

  local owner name
  owner="${REPO%%/*}"; name="${REPO##*/}"
  [[ -n "$owner" && -n "$name" && "$owner" != "$REPO" ]] || _die "MQ_REPO must be owner/name, got '$REPO'"

  # (a) the per-PR node. `mergeQueueEntry` does NOT exist in `gh pr view --json`'s
  #     field list ("Unknown JSON field") — GraphQL is the only way to read it,
  #     which is exactly why CLI-only probes have concluded "not queued" about a
  #     PR sitting at position 1.
  local q
  q='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
        number state mergedAt isDraft mergeable mergeStateStatus headRefOid
        autoMergeRequest{enabledAt}
        mergeQueueEntry{state position}
        commits(last:1){nodes{commit{statusCheckRollup{state
          contexts(first:100){totalCount nodes{
            __typename
            ... on CheckRun{name conclusion status}
            ... on StatusContext{context state}}}}}}}}}}'
  _gh api graphql -f query="$q" -f o="$owner" -f r="$name" -F n="$pr" \
      --jq '.data.repository.pullRequest'
  if (( MQ_RC != 0 )) || [[ -z "$MQ_OUT" || "$MQ_OUT" == "null" ]]; then
    echo "CANNOT-VERIFY — the per-PR read failed (rc=$MQ_RC): ${MQ_ERR:0:200}" >&2
    echo "  no verdict is emitted: an unread state is not an absent one." >&2
    return 3
  fi
  local pr_json="$MQ_OUT"

  # (b) how many contexts branch protection actually requires. Without it a
  #     rollup=SUCCESS cannot be judged (it can be SUCCESS over 3 of 11).
  local required_count="null"
  _gh api "repos/$REPO/branches/main/protection" \
      --jq '(.required_status_checks.checks // .required_status_checks.contexts // [])|length'
  if (( MQ_RC == 0 )) && [[ "$MQ_OUT" =~ ^[0-9]+$ ]]; then
    required_count="$MQ_OUT"
  fi

  # (c) queue-branch runs. Their EXISTENCE is durable evidence that this PR has
  #     been built by the queue at least once — the queue deletes the branch on
  #     the way out, so the runs outlive the entry that produced them.
  #     The listing is a BOUNDED PAGE (100 runs ~= a dozen PRs). A zero here
  #     therefore means "not in this window", which is NOT the same claim as
  #     "never queued" — so the window's own depth travels with the count and
  #     the verdict module renders the difference instead of flattening it.
  local queue_runs="null"
  _gh api "repos/$REPO/actions/runs?event=merge_group&per_page=100" \
      --jq "{matched:([.workflow_runs[]?|select(.head_branch|test(\"gh-readonly-queue/.*/pr-${pr}-\"))]|length), window:(.workflow_runs|length), oldest:([.workflow_runs[]?.created_at]|sort|first)}"
  if (( MQ_RC == 0 )) && [[ "$MQ_OUT" == \{* ]]; then
    queue_runs="$MQ_OUT"
  fi

  # (d) the sha this tool recorded when it armed, if it ever did.
  local armed_sha="" f
  f="$(_state_file "$pr")"
  if [[ -f "$f" ]]; then
    armed_sha="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("sha",""))' "$f" 2>/dev/null || true)"
  fi

  local verdict_py="$SCRIPT_DIR/mq_state_verdict.py"
  [[ -f "$verdict_py" ]] || _die "mq_state_verdict.py not found at $verdict_py"

  local payload rc=0
  payload="$(python3 - "$pr_json" "$required_count" "$queue_runs" "$armed_sha" <<'MQSTATEPY'
import json, sys
pr_json, required_count, queue_runs, armed_sha = sys.argv[1:5]
def num(v):
    return int(v) if v.isdigit() else None
def obj(v):
    try:
        d = json.loads(v)
        return d if isinstance(d, dict) else None
    except Exception:
        return None
print(json.dumps({
    "pr": json.loads(pr_json),
    "required_count": num(required_count),
    "queue_runs": obj(queue_runs),
    "armed_sha": armed_sha or None,
}))
MQSTATEPY
)" || rc=$?
  if (( rc != 0 )) || [[ -z "$payload" ]]; then
    echo "CANNOT-VERIFY — could not assemble the payload (rc=$rc)" >&2
    return 3
  fi

  rc=0
  if (( as_json )); then
    printf '%s' "$payload" | python3 "$verdict_py" --pr "$pr" --json || rc=$?
  else
    printf '%s' "$payload" | python3 "$verdict_py" --pr "$pr" || rc=$?
  fi
  return "$rc"
}

# ---------------------------------------------------------------------------
cmd_watch() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || _die "watch requires a PR number"
  _require_pr_number "$pr"
  shift || true

  local timeout_mins=120
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --timeout-mins) timeout_mins="${2:-}"; shift 2 ;;
      *) _die "watch: unknown argument '$1'" ;;
    esac
  done
  [[ "$timeout_mins" =~ ^[0-9]+$ ]] || _die "--timeout-mins must be a positive integer"

  local f; f="$(_state_file "$pr")"
  [[ -f "$f" ]] || _die "no armed state for #$pr at $f — run 'mq arm $pr' first (this is a POST-ARM watcher, not a preflight)"
  local armed_sha=""
  armed_sha="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("sha",""))' "$f" 2>/dev/null || true)"
  [[ "$armed_sha" =~ ^[0-9a-f]{40}$ ]] || _die "state file $f does not carry a valid sha"

  echo "watching #$pr against armed sha $armed_sha (interval ${WATCH_INTERVAL_S}s, ceiling ${timeout_mins}m)"
  local start ceiling
  start=$(date +%s)
  ceiling=$(( timeout_mins * 60 ))

  while true; do
    local now elapsed
    now=$(date +%s)
    elapsed=$(( now - start ))
    if (( elapsed >= ceiling )); then
      echo "NO-VERDICT — ceiling (${timeout_mins}m) reached, #$pr still open/unresolved"
      exit 2
    fi

    _gh pr view "$pr" --repo "$REPO" --json state,mergedAt,headRefOid
    if (( MQ_RC != 0 )); then
      echo "  $(date -u +%H:%M:%S) probe failed (rc=$MQ_RC), not a verdict — retrying: ${MQ_ERR:0:120}"
      sleep "$WATCH_INTERVAL_S"
      continue
    fi

    local state="" merged_at="" head_sha=""
    # No backslash-escaped quotes inside an f-string {} part below — that is a
    # SyntaxError on Python <3.12 (caught live by the test corpus against this
    # repo's Python 3.11); plain string concatenation sidesteps it. And this
    # comment lives ABOVE the process substitution, never as its first line —
    # bash 3.2 (macOS's shipped /bin/bash) mis-parses a `#` comment as the
    # opening line of `< <( ... )` as an unterminated paren (reproduced in
    # isolation; moving the comment here is the fix, not the workaround).
    # Field delimiter is `|`, NEVER a tab: when IFS is made of ONLY
    # whitespace characters (space/tab/newline — POSIX "IFS whitespace"),
    # `read` COLLAPSES consecutive delimiters instead of yielding an empty
    # field, on every POSIX shell (reproduced on this repo's own bash 3.2,
    # not merely a version quirk) — a null `mergedAt` between two real
    # fields silently shifted every field after it by one.
    IFS='|' read -r state merged_at head_sha < <(
      printf '%s' "$MQ_OUT" | python3 -c '
import json, sys
d = json.load(sys.stdin)
state = d.get("state") or ""
merged_at = d.get("mergedAt") or ""
head_sha = d.get("headRefOid") or ""
print(state + "|" + merged_at + "|" + head_sha)
'
    )

    if [[ "$state" == "MERGED" || -n "$merged_at" ]]; then
      echo "MERGED — #$pr landed"
      exit 0
    fi
    if [[ "$state" == "CLOSED" ]]; then
      echo "CLOSED — #$pr closed without merging"
      exit 4
    fi
    if [[ -n "$head_sha" && "$head_sha" != "$armed_sha" ]]; then
      echo "!!! HEAD MOVED on #$pr while armed: was $armed_sha, now $head_sha — dequeuing"
      _gh pr merge "$pr" --repo "$REPO" --disable-auto
      echo "!!! disable-auto rc=$MQ_RC out=${MQ_OUT:-$MQ_ERR}"
      exit 3
    fi
    sleep "$WATCH_INTERVAL_S"
  done
}

# ---------------------------------------------------------------------------
cmd_requeue() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || _die "requeue requires a PR number"
  _require_pr_number "$pr"

  echo "disable-auto #$pr (standing cure for a queue ejection)"
  _gh pr merge "$pr" --repo "$REPO" --disable-auto
  echo "  rc=$MQ_RC out=${MQ_OUT:-$MQ_ERR}"

  cmd_arm "$pr"
}

# ---------------------------------------------------------------------------
cmd_dequeue() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || _die "dequeue requires a PR number"
  _require_pr_number "$pr"

  _gh pr merge "$pr" --repo "$REPO" --disable-auto
  echo "disable-auto #$pr: rc=$MQ_RC out=${MQ_OUT:-$MQ_ERR}"
  if printf '%s%s' "$MQ_OUT" "$MQ_ERR" | grep -qi "already queued"; then
    echo "  NOTE: 'already queued' is a documented no-op (runbook §Step 3b) — an entry"
    echo "  already BUILDING in the queue is not removed by --disable-auto. Use the"
    echo "  GraphQL dequeuePullRequest mutation in the runbook if it must come out now."
  fi

  local f; f="$(_state_file "$pr")"
  if [[ -f "$f" ]]; then
    rm -f "$f"
    echo "removed armed-state file for #$pr"
  fi
}

# ---------------------------------------------------------------------------
cmd_handoff() {
  echo "=== mq handoff — $(_now_iso) — $REPO ==="
  echo
  cmd_status || true
  echo
  echo "--- armed-state files ($ARMED_DIR) ---"
  local any=0 f
  for f in "$ARMED_DIR"/*.json; do
    [[ -e "$f" ]] || continue
    any=1
    echo "  $(cat "$f")"
  done
  (( any )) || echo "  (none)"
  echo "=== end handoff ==="
}

# ---------------------------------------------------------------------------
main() {
  _state_dir_init
  local verb="${1:-}"
  [[ -n "$verb" ]] || { _usage; exit 1; }
  shift || true
  case "$verb" in
    status)  cmd_status "$@" ;;
    why-red) cmd_why_red "$@" ;;
    arm)     cmd_arm "$@" ;;
    state)   cmd_state "$@" ;;
    watch)   cmd_watch "$@" ;;
    requeue) cmd_requeue "$@" ;;
    dequeue) cmd_dequeue "$@" ;;
    handoff) cmd_handoff "$@" ;;
    -h|--help|help) _usage ;;
    *) echo "mq: unknown verb '$verb'" >&2; _usage; exit 1 ;;
  esac
}

main "$@"
