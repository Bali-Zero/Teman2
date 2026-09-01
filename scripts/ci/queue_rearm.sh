#!/usr/bin/env bash
# queue_rearm.sh — find the pull requests the merge queue dropped and put back
# ONLY the ones whose red is infrastructural. DRY-RUN by default; --apply acts.
#
# WHY IT EXISTS (measured 2026-07-27, the day the queue went live): a required
# check can go red without the diff being at fault. `Tests & Coverage` failed
# inside `E2E Tests (Playwright)` at CONTAINER INITIALISATION —
# `registry-1.docker.io ... context deadline exceeded`, three back-offs, all
# timing out — so not a single test ran. GitHub removes that pull request from
# the queue and CONSUMES its auto-merge request, leaving it OPEN + MERGEABLE +
# CLEAN with `autoMergeRequest: null`, and nothing puts it back. Frequency,
# measured not guessed: 1 failure in 100 `merge_group` runs — a live fragility,
# not an epidemic. (Same sweep found four MERGEABLE pull requests that had
# never been armed at all, which this tool also surfaces.)
#
# WHY IT DOES NOT JUST RE-ARM EVERYTHING: re-arming without looking at the
# CLASS of the red turns the queue into a machine that retries until it passes
# — a disarmed gate that still looks armed (superscar #2). A code red gets
# fixed, never retried. The class decision lives in
# `queue_rearm_classify.sh`, a pure function with its own guilt+innocence
# corpus, precisely so this file's network plumbing can never quietly reinvent
# it.
#
# USAGE
#   scripts/ci/queue_rearm.sh              # dry-run: report, change nothing
#   scripts/ci/queue_rearm.sh --apply      # re-arm the INFRA/CANCELLED class
#   REPO=owner/name scripts/ci/queue_rearm.sh
#
# EXIT  0 nothing to do / dry-run completed · 2 at least one CODE red needs a
#       human fix · 3 a probe failed and no verdict was reached (fail-closed:
#       "could not check" is never "clean", superscar #2/W84).
set -uo pipefail

REPO="${REPO:-Bali-Zero/Teman2}"
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLASSIFY="$SCRIPT_DIR/queue_rearm_classify.sh"
[[ -x "$CLASSIFY" ]] || { echo "FATAL: $CLASSIFY missing or not executable"; exit 3; }
POPULATION="$SCRIPT_DIR/queue_rearm_population.sh"
[[ -x "$POPULATION" ]] || { echo "FATAL: $POPULATION missing or not executable"; exit 3; }

# Patterns that identify a red NOT attributable to the diff. Widen ONLY with a
# cause observed live, never by resemblance — every pattern here is a red this
# fleet actually produced.
# `gh-readonly-queue/.*not found` is the EJECTION'S OWN WAKE, added 2026-07-28 from a
# cause observed live on #3372 — never by resemblance, which this list forbids. Order of
# events, each measured: the P6 gate's `actions/checkout@v7` hung and was killed at 603s
# against a 600s budget -> `cancelled` -> the cancelled REQUIRED check ejected the entry ->
# the queue destroyed `gh-readonly-queue/main/pr-3372-<sha>` -> CodeQL, still running,
# finished cleanly ("scanned 5703 out of 5703 Python files") and then FAILED uploading its
# SARIF to a ref that no longer existed. Read without ordering, that reads as "Security
# Scanning failed" and sends you debugging security for an event twelve minutes earlier in
# a different workflow. It is a straggler tripping over the eject, and says nothing about
# the pull request's health — so it must not be scored as a CODE red that forbids the
# retry. Unanimity (rule 2 of the classifier) still protects this: one genuinely
# non-infrastructural failure anywhere in the set still forbids the re-arm.
#
# The ejection is NOT the only way that ref dies. Second attempt on the same pull request,
# also measured: P6 passed, the only red was `Snyk Docker Security` (NOT a required
# context, so it cannot eject) — and both CodeQL jobs still died on the identical missing
# ref. The queue also destroys the temporary branch when it REBUILDS the group after an
# entry ahead leaves. Same wake, two different upstream events, and neither is the diff.
#
# ANCHOR ON THE REF PATH, NOT ON THE SENTENCE. The first version of this pattern ended in
# `not found in the repository`; GitHub actually writes `not found in THIS repository`, so
# it matched nothing that the fleet had ever produced. It went undetected because the guilt
# fixture beside it was typed from memory instead of copied off the artifact — corpus and
# code wrong in the same direction, which is the one failure a corpus cannot catch about
# itself. The wording is form and belongs to GitHub; `refs/heads/gh-readonly-queue/…` +
# `not found` is the entity, and it is the entity that makes this red the queue's own.
INFRA_RE='registry-1\.docker\.io|Docker pull failed|context deadline exceeded|no space left on device|Runner has received a shutdown signal|The self-hosted runner.*lost communication|Failed to initialize container|ref .refs/heads/gh-readonly-queue/.*not found'

# ---------------------------------------------------------------------------
# 1. Who is IN the queue right now. Anyone inside is not orphaned, whatever
#    their fields say — `autoMergeRequest` goes null when the queue ACCEPTS
#    the request, not when the request failed.
# ---------------------------------------------------------------------------
inq=$(gh api graphql -f query="{repository(owner:\"$OWNER\",name:\"$NAME\"){mergeQueue(branch:\"main\"){entries(first:50){nodes{pullRequest{number}}}}}}" \
      --jq '[.data.repository.mergeQueue.entries.nodes[].pullRequest.number]|join(" ")' 2>/dev/null)
probe_rc=$?
if (( probe_rc != 0 )); then
  echo "🔌 queue probe FAILED (rc=$probe_rc) — stopping: without knowing who is inside, every 'orphan' verdict is blind."
  exit 3
fi
echo "in queue now: ${inq:-<empty>}"

# ---------------------------------------------------------------------------
# 2. Candidates: OPEN + MERGEABLE + no auto-merge request.
#
#    FETCH THE WHOLE POPULATION FIRST, then filter locally — and say how big
#    the population was. Learned by running this tool twice within seconds:
#    the first run printed "unarmed candidates: 0 / no orphaned pull request"
#    and the second, on the same world, printed 2. The `gh pr list` call had
#    returned an EMPTY list with rc=0, which the old code could not tell apart
#    from "nothing is orphaned" — a successful probe and a blind one produced
#    the identical clean verdict. So: an empty POPULATION is now a distinct,
#    fail-closed outcome (exit 3), and a real zero reads as "0 of N open",
#    which is a measurement instead of a shrug.
#    (memory: lesson_an_empty_set_impersonates_everything_and_nothing)
# ---------------------------------------------------------------------------
all_open=$(gh pr list --repo "$REPO" --state open --limit 100 \
           --json number,mergeable,autoMergeRequest,title 2>/dev/null)
probe_rc=$?
if (( probe_rc != 0 )); then
  echo "🔌 pull-request probe FAILED (rc=$probe_rc) — no verdict."
  exit 3
fi

open_count=$(printf '%s' "$all_open" | jq 'length' 2>/dev/null)
if [[ -z "$open_count" || ! "$open_count" =~ ^[0-9]+$ ]]; then
  echo "🔌 pull-request probe returned unparseable JSON — no verdict."
  exit 3
fi
if (( open_count == 0 )); then
  echo "🔌 the probe returned ZERO open pull requests. That is either a genuinely"
  echo "   empty repository or a probe that answered empty — indistinguishable from"
  echo "   here, so it is NOT reported as 'nothing orphaned'. No verdict."
  exit 3
fi

# ---------------------------------------------------------------------------
# 2b. Join the merge-queue snapshot from step 1 ($inq) onto every PR object as
#    `mergeQueueEntry` — the positive probe `queue_rearm_population.sh` now
#    requires before calling anything a candidate (scripts/lint_arm_probe.py;
#    proven live on PR #5422, which sat at `mergeQueueEntry {position: 1,
#    state: AWAITING_CHECKS}` while `autoMergeRequest` read null). No second
#    network call: $inq is already in hand from step 1, so this is one more
#    jq pass over data this script already fetched. Without this join,
#    `queue_rearm_population.sh` reporting "unarmed candidates: N" was
#    counting an already-armed PR — the per-item `$inq` cross-check below
#    (step 3) still kept the ACTION safe, but the printed COUNT was not.
# ---------------------------------------------------------------------------
inq_json=$(printf '%s\n' "$inq" | jq -R -c 'split(" ") | map(select(length > 0) | tonumber)')
all_open=$(printf '%s' "$all_open" | jq --argjson inq "$inq_json" '
  ($inq) as $inqnums
  | map(
      .number as $n
      | . + {mergeQueueEntry: (if ($inqnums | any(. == $n)) then {} else null end)}
    )
')
enriched_count=$(printf '%s' "$all_open" | jq 'length' 2>/dev/null)
if [[ -z "$enriched_count" || "$enriched_count" != "$open_count" ]]; then
  echo "🔌 merge-queue-entry join failed or changed the population size (before=$open_count after=${enriched_count:-<unparseable>}) — no verdict."
  exit 3
fi

cand=$(printf '%s' "$all_open" | "$POPULATION" --candidates)
total=$(printf '%s\n' "$cand" | grep -c .)

# THE THIRD VALUE — see the scar documented at the top of
# `queue_rearm_population.sh`. `mergeable` is not a boolean: GitHub answers
# UNKNOWN while it recomputes, and it recomputes for EVERY open pull request
# after every push to the base branch. So a merge to main opens a window in
# which genuine orphans read as not-MERGEABLE and quietly leave the candidate
# set — and a scheduled run is most likely to fire exactly then. An unresolved
# population must never be reported as an empty one.
undecidable=$(printf '%s' "$all_open" | "$POPULATION" --undecidable)
if [[ -z "$undecidable" || ! "$undecidable" =~ ^[0-9]+$ ]]; then
  echo "🔌 could not count undecided mergeable states — refusing to report a verdict on a partially-read set."
  exit 3
fi

echo "unarmed candidates: $total (of $open_count open pull request(s))"
if (( undecidable > 0 )); then
  echo "   ⏳ $undecidable unarmed pull request(s) have an UNDECIDED mergeable state — GitHub"
  echo "      recomputes mergeability after every push to the base branch, so this list is"
  echo "      INCOMPLETE right now. Re-run in a minute for the full picture."
fi

if (( total == 0 )); then
  if (( undecidable > 0 )); then
    echo "🔌 zero decidable candidates, but $undecidable await recomputation. That is"
    echo "   'ask again shortly', never 'nothing is orphaned'. No verdict."
    exit 3
  fi
  echo "✅ no orphaned pull request — every open one is armed, queued or conflicting."
  exit 0
fi

armed=0; needs_fix=0; undecided=0

while IFS=$'\t' read -r n title; do
  [[ -z "${n:-}" ]] && continue
  case " $inq " in *" $n "*) echo "  ⏭  #$n already in the queue"; continue ;; esac

  # 3. This pull request's most recent merge_group runs. `pr-<n>-` is how the
  #    queue names its temporary branches.
  #
  # NO `--arg`: `gh run list` does not accept it. It is a `jq` flag, and `gh`
  # only forwards the EXPRESSION to its embedded engine — passing it makes gh
  # exit 1 with `unknown command "n" for "gh run list"`. Measured 2026-07-28,
  # the day after this tool was armed: with `--arg` the query returned nothing
  # for EVERY pull request, so every candidate was filed "no merge_group run
  # found … LEAVING ALONE" and the tool could never reach a verdict on anything
  # — including a pull request that had 20 such runs at that very moment. The
  # re-armer was decorative by construction: the exact "exists != armed" disease
  # it was built to cure, living inside the cure (superscar #2).
  #
  # `$n` is interpolated into the expression instead. It comes from this script's
  # own jq extraction of `.number`, but it is re-asserted as digits below rather
  # than trusted, so nothing can be smuggled into the expression.
  if [[ ! "$n" =~ ^[0-9]+$ ]]; then
    echo "  ❓ #$n is not a pull-request number — refusing to build a query from it"
    undecided=$((undecided + 1))
    continue
  fi
  rows=$(gh run list --repo "$REPO" --event merge_group --limit 150 \
         --json databaseId,name,status,conclusion,headBranch,createdAt \
         --jq "[.[]|select(.headBranch|test(\"pr-${n}-\"))]|sort_by(.createdAt)|reverse|.[0:25][]|\"\(.databaseId)\t\(.status)\t\(.conclusion // \"\")\t\(.name)\"" 2>/tmp/qr_runs.err)
  runs_rc=$?

  # A FAILED probe is not an EMPTY one. Swallowing gh's stderr into an empty
  # string is precisely what let the `--arg` usage error masquerade as "this
  # pull request has no runs" for as long as it did.
  if (( runs_rc != 0 )); then
    echo "  🔌 #$n run probe FAILED (rc=$runs_rc): $(tr '\n' ' ' < /tmp/qr_runs.err | cut -c1-120)"
    echo "     no verdict for this pull request — a probe that could not read is never a clean read."
    undecided=$((undecided + 1))
    continue
  fi

  if [[ -z "$rows" ]]; then
    echo "  ❓ #$n no merge_group run found — never queued, or too old to see. LEAVING ALONE ($title)"
    undecided=$((undecided + 1))
    continue
  fi

  # 4. Classify each failure by reading its LOG, not its job name. The infra
  #    flag is computed here (network) and handed to the pure classifier.
  scored=""
  while IFS=$'\t' read -r rid status concl rname; do
    [[ -z "${rid:-}" ]] && continue
    hit=0
    case "${concl:-}" in
      failure|timed_out|startup_failure|action_required)
        if gh run view "$rid" --repo "$REPO" --log-failed 2>/dev/null | grep -qE "$INFRA_RE"; then
          hit=1
        fi
        ;;
    esac
    scored+="${rid}"$'\t'"${status}"$'\t'"${concl}"$'\t'"${hit}"$'\t'"${rname}"$'\n'
  done <<< "$rows"

  verdict=$(printf '%s' "$scored" | "$CLASSIFY")

  case "$verdict" in
    INFRA|CANCELLED)
      if (( APPLY )); then
        out=$(gh pr merge "$n" --repo "$REPO" --squash --auto 2>&1); arc=$?
        # Judge the REPLY, not only the exit code (W104): "already queued" is
        # success, and a zero rc on an unexpected message is not.
        if (( arc == 0 )) || printf '%s' "$out" | grep -qi "already queued"; then
          echo "  ♻️  #$n RE-ARMED [$verdict] — $title"
          armed=$((armed + 1))
        else
          echo "  ❌ #$n re-arm FAILED (rc=$arc): $(printf '%s' "$out" | head -1)"
          undecided=$((undecided + 1))
        fi
      else
        echo "  ♻️  #$n would re-arm [$verdict] — $title"
        armed=$((armed + 1))
      fi
      ;;
    CODE)
      echo "  🛑 #$n CODE red — not retried, it needs fixing: $title"
      needs_fix=$((needs_fix + 1))
      ;;
    *)
      echo "  ⏳ #$n not decidable yet (UNKNOWN) — leaving alone: $title"
      undecided=$((undecided + 1))
      ;;
  esac
done <<< "$cand"

echo "─── $armed re-armable · $needs_fix need a fix · $undecided undecided (of $total candidates)"
(( APPLY )) || echo "(dry-run — re-run with --apply to act)"
(( needs_fix > 0 )) && exit 2
exit 0
