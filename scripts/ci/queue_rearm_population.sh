#!/usr/bin/env bash
# queue_rearm_population.sh — the PURE population reader behind the merge-queue
# re-arm tool. No network, no `gh`, no git: reads a JSON array on stdin (the
# `gh pr list --json number,mergeable,autoMergeRequest,title` shape, enriched
# by the caller with one more field, `mergeQueueEntry` — see below) and
# answers ONE question per invocation.
#
# WHY IT IS ITS OWN FILE: the same split as `queue_rearm_classify.sh`. The
# orchestrator has to talk to the GitHub API, which makes it untestable without
# a network and a live queue. Deciding WHO COUNTS AS ORPHANED is the part that
# must never be wrong, so it lives here as a pure function with a
# guilt+innocence corpus (`test_queue_rearm_population.sh`) that exercises THIS
# file — not a copy of its jq expressions pasted into a test, which would let
# the two drift while both stayed green.
#
# USAGE (stdin = the JSON array)
#   … | queue_rearm_population.sh --candidates    # TSV: <number>\t<title>
#   … | queue_rearm_population.sh --undecidable   # a single integer
#   … | queue_rearm_population.sh --open-count    # a single integer
#
# EXIT  0 answered · 3 the input could not be read (fail-closed: an unreadable
#       set is never an empty one).
#
# THE `autoMergeRequest==null` TRAP — `mergeQueueEntry` IS THE POSITIVE PROBE.
# `autoMergeRequest` reads `null` for a PR the queue has ACCEPTED (the request
# is CONSUMED, not disarmed), for one it EJECTED, and for one never armed —
# null in three different states, non-null in only one (`scripts/
# lint_arm_probe.py`, cicatrix W111/W123/#4756/#5012/#5275). Proven live on
# PR #5422: it sat in the queue at `mergeQueueEntry {position: 1, state:
# AWAITING_CHECKS}` — arming had SUCCEEDED — while simultaneously reading
# `mergeable=MERGEABLE, autoMergeRequest=null`. The OLD selectors below
# (mergeable + autoMergeRequest alone) picked that PR up as an "unarmed
# candidate", and `queue_rearm.sh` printed it in its "unarmed candidates: N"
# count even though its own later per-item loop correctly skipped RE-ARMING
# it via a separate `mergeQueue(...)` cross-check (`$inq`) — the ACTION was
# safe, the REPORTED COUNT was not. Both `--candidates` and `--undecidable`
# below therefore also require `mergeQueueEntry==null` — a PR already holding
# a live queue entry is never a candidate and never undecided-and-unarmed,
# regardless of what `mergeable`/`autoMergeRequest` say. Absent-key reads as
# null too (jq's normal missing-key behavior), which is deliberate: it keeps
# every caller/fixture that predates this field working exactly as before —
# `queue_rearm.sh` is the one caller in this tree and it MUST populate the
# field every time (fetched once via the branch-level `mergeQueue(branch:
# "main"){entries}` snapshot it already fetches for its own `$inq` cross-check,
# joined onto each PR object by `.number` before piping into this script) —
# see its own comment where that join happens.
#
# THE SCAR THIS FILE EXISTS FOR — `mergeable` HAS THREE VALUES, NOT TWO.
# GitHub computes it LAZILY and answers UNKNOWN while a background job runs,
# and every push to the base branch invalidates it for every open pull request.
# So each merge to main opens a window where genuine orphans read as
# not-MERGEABLE and silently leave the candidate set. Measured 2026-07-28:
# seconds after #3370 merged, the caller printed "unarmed candidates: 0 (of 17
# open pull request(s))" and declared "no orphaned pull request"; minutes later,
# same code and same world with nothing armed or closed in between, it printed
# 13. Only the recomputation had finished. A scheduled run is most likely to
# fire exactly in that window.
#
# Hence `--undecidable` is a FIRST-CLASS answer, not an implementation detail:
# the caller must be able to tell "nothing is orphaned" from "I cannot see yet".
# The old success line asserted a trichotomy — armed, queued or conflicting —
# that the MERGEABLE-only filter never established, so anything that was neither
# MERGEABLE nor CONFLICTING landed in the clean bucket while being none of the
# three. (Sibling rule, one level up: an empty POPULATION is already treated as
# fail-closed by the caller — memory
# lesson_an_empty_set_impersonates_everything_and_nothing.)
set -uo pipefail

MODE="${1:-}"

payload=$(cat)

# Fail-closed on anything unreadable. `jq -e` so a `null` input is a failure
# too, not a silent zero.
if ! printf '%s' "$payload" | jq -e 'type == "array"' > /dev/null 2>&1; then
  echo "queue_rearm_population: stdin is not a JSON array — no answer" >&2
  exit 3
fi

case "$MODE" in
  --candidates)
    # `mergeQueueEntry==null` is the positive probe: a PR already holding a
    # live queue entry is armed (the queue consumed the request), whatever
    # `autoMergeRequest` reads — see the module comment above for the #5422
    # proof this guards against.
    printf '%s' "$payload" \
      | jq -r '.[]|select(.mergeable=="MERGEABLE" and .autoMergeRequest==null and .mergeQueueEntry==null)|"\(.number)\t\(.title[0:70])"'
    ;;
  --undecidable)
    # Unarmed AND neither definitively mergeable nor definitively conflicting.
    # Deliberately written as "not one of the two known-terminal values" rather
    # than "== UNKNOWN": a value this script has never heard of must land here,
    # in the bucket that forces a re-run, never in the clean one.
    #
    # `mergeQueueEntry==null` guards this bucket too: a PR already in the
    # queue is armed regardless of a `mergeable` value still recomputing —
    # it must not be counted as an undecided orphan just because GitHub
    # hasn't finished recomputing mergeability for an already-queued PR.
    printf '%s' "$payload" \
      | jq '[.[]|select(.autoMergeRequest==null and .mergeQueueEntry==null and .mergeable!="MERGEABLE" and .mergeable!="CONFLICTING")]|length'
    ;;
  --open-count)
    printf '%s' "$payload" | jq 'length'
    ;;
  *)
    echo "queue_rearm_population: unknown mode '${MODE}' (want --candidates|--undecidable|--open-count)" >&2
    exit 3
    ;;
esac
