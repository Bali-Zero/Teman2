#!/usr/bin/env python3
"""mq_state_verdict.py — the pure verdict half of `mq state` (Merge-OS v2).

WHY THIS FILE EXISTS SEPARATELY FROM `mq.sh`
    The gathering (three `gh` calls) and the judging are different jobs with
    different failure modes. Split, the judgement can be driven by fixtures at
    the exact boundary the production code crosses (W114: a fake that shares
    the code's imagination proves nothing — here the fixture is the API's own
    JSON shape, and the production transformation runs over it unchanged).

WHAT THE QUEUE ACTUALLY LIES ABOUT (measured, MEMORY_MERGE_QUEUE_TRAPS.md)
    Arming CONSUMES `autoMergeRequest`. It goes null when the queue ACCEPTS
    the request — not when arming failed. And there is a window in which it is
    ALREADY null while `mergeQueueEntry` has NOT YET materialised: measured on
    PR #5036, where both fields read "not armed" while 32 queue-branch runs
    existed. Therefore:

        >>> NO INSTANTANEOUS READ OF THOSE TWO FIELDS, NOT EVEN JOINT,
        >>> CAN EVER PROVE "NOT ARMED".

    This module consequently has NO `NOT_ARMED` verdict. That is the design.
    The only thing that proves armed-ness is the REFUSAL TEXT of
    `gh pr merge --auto` ("already queued to merge") — and that is a MUTATION,
    so this read-only oracle never runs it; it NAMES it as the disambiguator
    when the verdict is INDETERMINATE.

ATTESTATION ORDER (the corpus's own, top = most reliable)
    1. the refusal text of `gh pr merge --auto`   [mutation — never run here]
    2. terminal state: `mergedAt` / `CLOSED`
    3. existence of `gh-readonly-queue/main/pr-<N>-*` runs
    4. `mergeQueueEntry` + `autoMergeRequest`, jointly, non-probative for "not armed"

EVIDENCE (never a verdict, always printed)
    - `mergeable`/`mergeStateStatus`: a DIRTY PR runs ZERO workflows, so its
      "0 pending checks" is not green, it is silence.
    - rollup state vs `contexts.totalCount` vs the branch's required count: a
      SUCCESS computed over 3 contexts when main requires 11 is a FALSE GREEN.
    - CANCELLED contexts: `gh pr checks` files CANCELLED under bucket `cancel`,
      never `fail`, so a caller filtering `bucket=="fail"` reads "0 reds" on a
      rollup whose state is FAILURE.
    - head sha vs the sha recorded at arm time: the arm rides the PR, not the
      SHA, so a push after arming inherits it without re-passing any gate.

EXIT CODES
    0  a verdict was produced (read `verdict` / `--json` for which)
    3  CANNOT-VERIFY — the primary read failed; no verdict is emitted
"""

from __future__ import annotations

import argparse
import json
import sys

# The verdicts this oracle can emit. `NOT_ARMED` is deliberately absent — see
# the module docstring. Adding it would re-commit the exact autogoal the
# corpus records twice (a background probe announcing a disarm that never
# happened, with the authority of an automated measurement).
VERDICTS = ("MERGED", "CLOSED", "IN_QUEUE", "ARMED", "INDETERMINATE")

DISAMBIGUATOR = (
    "run `gh pr merge <PR> --auto` (a MUTATION, but it refuses harmlessly): "
    "'already queued to merge' proves ARMED; anything else leaves it open"
)


def _dig(d, *path, default=None):
    """Walk a nested dict/list, returning `default` at the first missing step.

    GraphQL nulls arrive as None at any depth; `.get()` chains on None throw.
    """
    cur = d
    for key in path:
        if cur is None:
            return default
        if isinstance(key, int):
            if not isinstance(cur, list) or len(cur) <= key:
                return default
            cur = cur[key]
        else:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key)
    return default if cur is None else cur


def _rollup(pr):
    return _dig(pr, "commits", "nodes", 0, "commit", "statusCheckRollup", default={}) or {}


def _context_states(pr):
    """Every rollup context's state, normalised to upper-case strings.

    CheckRun carries `conclusion` (None while running); StatusContext carries
    `state`. Both shapes land in the same list.
    """
    nodes = _dig(_rollup(pr), "contexts", "nodes", default=[]) or []
    out = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        val = n.get("conclusion") or n.get("state") or n.get("status") or ""
        out.append(str(val).upper())
    return out


def judge(payload):
    """payload -> {verdict, sub_state, evidence: [...], warnings: [...]}

    `payload` keys:
      pr             the GraphQL `pullRequest` node (required)
      required_count int | None — branch protection's required-context count
      queue_runs     int | None — count of `gh-readonly-queue/.../pr-<N>-*` runs
      armed_sha      str | None — the sha `mq arm` recorded, if any
    """
    pr = payload.get("pr")
    if not isinstance(pr, dict) or not pr:
        raise ValueError("payload.pr is missing or not an object")

    state = (pr.get("state") or "").upper()
    merged_at = pr.get("mergedAt") or ""
    entry = pr.get("mergeQueueEntry")
    amr = pr.get("autoMergeRequest")
    enabled_at = _dig(amr, "enabledAt", default="") if isinstance(amr, dict) else ""

    required_count = payload.get("required_count")
    queue_runs = payload.get("queue_runs")
    armed_sha = payload.get("armed_sha")

    evidence, warnings = [], []
    sub_state = ""

    # --- signal 2: terminal states -----------------------------------------
    if merged_at or state == "MERGED":
        verdict = "MERGED"
        evidence.append(f"terminal: mergedAt={merged_at or '<unset>'} state={state or '?'}")
    elif state == "CLOSED":
        verdict = "CLOSED"
        evidence.append("terminal: state=CLOSED with no mergedAt — closed without merging")
    # --- signal 4: the two ambiguous fields, jointly ------------------------
    elif isinstance(entry, dict) and entry:
        verdict = "IN_QUEUE"
        sub_state = str(entry.get("state") or "")
        pos = entry.get("position")
        evidence.append(
            f"mergeQueueEntry present: state={sub_state or '?'}"
            + (f" position={pos}" if pos is not None else "")
        )
        evidence.append(
            "autoMergeRequest is null BY SUCCESS here — the queue consumes it on entry"
            if not enabled_at
            else f"autoMergeRequest.enabledAt={enabled_at}"
        )
        if sub_state.upper() == "UNMERGEABLE":
            warnings.append(
                "entry state UNMERGEABLE: the queue merges on top of the entries AHEAD, "
                "not on main — a clean 3-way against origin/main proves nothing. "
                "`RemovedFromMergeQueueEvent.reason` in the timeline is the only source for WHY."
            )
    elif enabled_at:
        verdict = "ARMED"
        evidence.append(f"autoMergeRequest.enabledAt={enabled_at}, no queue entry yet")
        evidence.append("will enter the queue when the required checks go green")
    else:
        # BOTH absent. This is trap #10's window and it is NOT 'not armed'.
        verdict = "INDETERMINATE"
        evidence.append(
            "autoMergeRequest AND mergeQueueEntry are both absent — this is the "
            "documented arm->entry window, NOT proof of disarmament (measured PR #5036)"
        )
        evidence.append(f"to decide: {DISAMBIGUATOR}")

    # --- signal 3: queue-branch runs (evidence, never a verdict on its own) --
    #
    # PRESENCE is sound: a run on gh-readonly-queue/.../pr-<N>-* proves the PR
    # reached the queue, and it outlives the entry (the queue deletes the branch
    # on the way out, the runs stay).
    #
    # ABSENCE IS NOT. The listing is one bounded page — measured 2026-08-29:
    # 100 merge_group runs spanned 13 PRs, because a queue build fires 8
    # workflows. A PR older than that window reads zero and has been queued a
    # dozen times. Rendering that zero as "never queued" would be this whole
    # file's own disease one level down: a bounded proxy read as the entity.
    matched = window = oldest = None
    if isinstance(queue_runs, dict):
        matched = queue_runs.get("matched")
        window = queue_runs.get("window")
        oldest = queue_runs.get("oldest")
    elif isinstance(queue_runs, int):
        matched = queue_runs

    if matched is None:
        evidence.append("queue-branch runs: CANNOT-VERIFY (run listing unavailable)")
    elif matched > 0:
        evidence.append(
            f"queue-branch runs: {matched} on gh-readonly-queue/.../pr-<N>-* "
            "— this PR HAS reached the queue at least once"
        )
        if verdict == "INDETERMINATE" and state == "OPEN":
            warnings.append(
                "still OPEN, not merged, no entry now, yet queue-branch runs exist: "
                "consistent with an EJECTION (which is silent and deletes its own branch). "
                "`RemovedFromMergeQueueEvent.reason` in the timeline is the only source for WHY."
            )
    else:
        span = ""
        if window is not None:
            span = f" (window: {window} merge_group run(s)"
            span += f", oldest {oldest})" if oldest else ")"
        evidence.append(
            f"queue-branch runs: 0 in the listed window{span} — this does NOT mean "
            "never queued: the listing is one bounded page, and an older PR falls off it"
        )

    # --- evidence: DIRTY runs nothing --------------------------------------
    # A merged/closed PR reports mergeable=UNKNOWN forever: warning about that
    # would be an over-match on a question that stopped existing (measured live
    # on #5214, which is MERGED and read UNKNOWN/UNKNOWN).
    terminal = verdict in ("MERGED", "CLOSED")
    mergeable = (pr.get("mergeable") or "").upper()
    mss = (pr.get("mergeStateStatus") or "").upper()
    evidence.append(f"mergeable={mergeable or '?'} mergeStateStatus={mss or '?'}")
    if terminal:
        pass
    elif mergeable == "CONFLICTING" or mss == "DIRTY":
        warnings.append(
            "DIRTY/CONFLICTING: a conflicted PR runs ZERO workflows, so '0 pending checks' "
            "here is silence, not green. Repoint the branch before reading any check state."
        )
    elif mergeable == "UNKNOWN":
        warnings.append(
            "mergeable=UNKNOWN: GitHub is still recomputing (it recomputes for EVERY open PR "
            "after every push to main). Not a verdict — re-read shortly."
        )

    # --- evidence: the rollup, and the count it was computed over -----------
    rollup_state = (_rollup(pr).get("state") or "").upper()
    total = _dig(_rollup(pr), "contexts", "totalCount")
    evidence.append(
        f"rollup={rollup_state or '<none>'} over totalCount="
        f"{total if total is not None else '?'} context(s)"
        + (f"; branch protection requires {required_count}" if required_count is not None else "")
    )
    if terminal:
        pass
    elif required_count is None:
        warnings.append(
            "required-context count CANNOT-VERIFY: a rollup=SUCCESS cannot be trusted without "
            "the number it was computed over."
        )
    elif rollup_state == "SUCCESS" and isinstance(total, int) and total < required_count:
        warnings.append(
            f"FALSE GREEN: rollup=SUCCESS was computed over {total} context(s) while main "
            f"requires {required_count}. A rerun detaches check-runs and third-party contexts "
            "alone can average to SUCCESS. This is not mergeable-green."
        )

    # --- evidence: CANCELLED is not 'fail', and not 'pass' either -----------
    states = _context_states(pr)
    cancelled = [s for s in states if s == "CANCELLED"]
    if cancelled:
        evidence.append(f"CANCELLED contexts: {len(cancelled)}")
        warnings.append(
            f"{len(cancelled)} context(s) CANCELLED. `gh pr checks` files these under bucket "
            "'cancel', never 'fail' — a caller filtering bucket=='fail' reads '0 reds' on a PR "
            "whose rollup may be FAILURE. The authority is statusCheckRollup.state."
        )

    # --- evidence: the arm rides the PR, not the sha ------------------------
    head = pr.get("headRefOid") or ""
    if armed_sha:
        if head and head != armed_sha:
            warnings.append(
                f"HEAD MOVED since arm: armed {armed_sha[:12]}, head now {head[:12]}. "
                "The auto-merge request sits on the PR, not the SHA — this push inherited "
                "the arm WITHOUT re-passing the gate that judged it."
            )
        else:
            evidence.append(f"head matches the sha recorded at arm time ({armed_sha[:12]})")

    if pr.get("isDraft"):
        evidence.append(
            "isDraft=true — a draft is a durable hold only BEFORE the entry exists; "
            "once queued it is cosmetic (measured: draft 13:21 -> merged 13:31)"
        )

    return {
        "verdict": verdict,
        "sub_state": sub_state,
        "state": state,
        "evidence": evidence,
        "warnings": warnings,
    }


def render(result, pr_number):
    lines = [f"== mq state — PR #{pr_number} =="]
    v = result["verdict"]
    sub = f" ({result['sub_state']})" if result.get("sub_state") else ""
    lines.append(f"VERDICT: {v}{sub}")
    for e in result["evidence"]:
        lines.append(f"  - {e}")
    for w in result["warnings"]:
        lines.append(f"  !! {w}")
    if v == "INDETERMINATE":
        lines.append(
            "  NOTE: this oracle has no NOT_ARMED verdict, on purpose — no instantaneous "
            "read of those fields can prove it."
        )
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="judge one PR's merge-queue state (read-only)")
    ap.add_argument("--pr", default="?", help="PR number, for the header only")
    ap.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    ap.add_argument(
        "--payload",
        default="-",
        help="path to the gathered payload JSON, or '-' for stdin (default)",
    )
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.payload == "-" else open(args.payload).read()
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        print(f"CANNOT-VERIFY — payload is not JSON: {exc}", file=sys.stderr)
        return 3
    try:
        result = judge(payload)
    except ValueError as exc:
        print(f"CANNOT-VERIFY — {exc}", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result, args.pr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
