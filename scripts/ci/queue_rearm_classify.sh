#!/usr/bin/env bash
# queue_rearm_classify.sh — the PURE verdict function behind the merge-queue
# re-arm tool. No network, no `gh`, no git: reads pre-gathered rows on stdin
# and prints exactly one verdict on stdout.
#
# WHY IT IS ITS OWN FILE: the orchestrator (`queue_rearm.sh`) has to talk to
# the GitHub API, which makes it untestable without a network and a live
# queue. The DECISION — "may this PR be put back in the queue?" — is the part
# that must never be wrong, so it lives here as a pure function with a
# guilt+innocence corpus (`test_queue_rearm_classify.sh`), the same split as
# `hotzone_changed_files.sh` (pure enumeration) vs the gate that consumes it.
#
# INPUT (stdin), one merge_group check-run per line, TAB-separated:
#     <run_id>\t<status>\t<conclusion>\t<infra_hit>\t<name>
#   status      as GitHub reports it: completed | in_progress | queued | ...
#   conclusion  success | failure | cancelled | timed_out | "" (EMPTY = not
#               yet known — this is NOT "no failure", see SCAR below)
#   infra_hit   1 if this run's failing log matched the infra corpus, else 0.
#               Only meaningful on a failure row; the caller computes it.
#
# OUTPUT (stdout), exactly one of:
#     INFRA      every failure is infrastructural -> re-arm is legitimate
#     CANCELLED  no failure, at least one cancelled -> re-arm is legitimate
#     CODE       at least one failure is NOT infrastructural -> DO NOT retry
#     UNKNOWN    not decidable yet (or nothing to decide on) -> leave alone
#
# Exit code mirrors the verdict so a caller can branch on `$?` without
# parsing: 0=INFRA 1=CODE 2=CANCELLED 3=UNKNOWN. stdout stays the contract;
# the exit code is a convenience, and both are asserted by the corpus.
#
# THE THREE RULES, each one a scar:
#
#  1. An EMPTY conclusion is "I do not know yet", never "no failure".
#     2026-07-27: PR #3326 was read while `Tests & Coverage` was
#     `in_progress`/`conclusion=∅` and filed as "ejected with ZERO failures".
#     Re-read at terminal state it was `failure`. A snapshot is not a verdict
#     (cicatrix #2 lineage; memory
#     discovery_the_queue_ejects_on_an_infra_red_and_nothing_retries_it).
#
#  2. UNANIMITY. One non-infra failure forbids the retry even if nine others
#     are infrastructural. Re-arming on a code red turns the queue into a
#     machine that retries until it passes — a disarmed gate that still looks
#     armed (cicatrix #2).
#
#  3. An EMPTY input decides NOTHING. Zero rows is "no evidence", not "no
#     failures" — an empty set otherwise impersonates both everything and
#     nothing (memory lesson_an_empty_set_impersonates_everything_and_nothing).
set -uo pipefail

verdict() {
  printf '%s\n' "$1"
  case "$1" in
    INFRA)     exit 0 ;;
    CODE)      exit 1 ;;
    CANCELLED) exit 2 ;;
    *)         exit 3 ;;
  esac
}

rows=0
pending=0
failures=0
infra_failures=0
cancelled=0
malformed=0

while IFS=$'\t' read -r run_id status conclusion infra_hit name || [[ -n "${run_id:-}" ]]; do
  [[ -z "${run_id:-}" ]] && continue
  # A row that does not carry all five fields cannot be judged. Treat it as
  # evidence we cannot read rather than as a clean row (fail-closed).
  if [[ -z "${status:-}" || -z "${infra_hit+x}" ]]; then
    malformed=$((malformed + 1))
    continue
  fi
  rows=$((rows + 1))
  [[ "$status" != "completed" ]] && pending=$((pending + 1))
  case "${conclusion:-}" in
    failure|timed_out|startup_failure|action_required)
      failures=$((failures + 1))
      [[ "${infra_hit:-0}" == "1" ]] && infra_failures=$((infra_failures + 1))
      ;;
    cancelled)
      cancelled=$((cancelled + 1))
      ;;
  esac
done

# RULE 3 — nothing to decide on.
if (( rows == 0 )); then
  verdict UNKNOWN
fi

# A row we could not parse means the evidence is incomplete; never conclude
# "re-armable" from a partially-read set.
if (( malformed > 0 && failures == 0 )); then
  verdict UNKNOWN
fi

# RULE 1 — a run still in flight, with nothing decided against it yet, is not
# a verdict. Note the guard is `failures == 0`: once a failure IS known, a
# sibling still running cannot un-know it, so we go on to judge the failure.
if (( pending > 0 && failures == 0 )); then
  verdict UNKNOWN
fi

if (( failures > 0 )); then
  # RULE 2 — unanimity: every single failure must be infrastructural.
  if (( infra_failures == failures )); then
    verdict INFRA
  fi
  verdict CODE
fi

if (( cancelled > 0 )); then
  verdict CANCELLED
fi

# Every row terminal, none failed, none cancelled: the PR was not ejected by a
# red at all. Whatever removed it from the queue is not something this tool
# understands, so it does not act.
verdict UNKNOWN
