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
    3  CANNOT-VERIFY — the payload was unreadable or carried no PR node; no
       verdict is emitted. `mq state` returns the same 3 when its own primary
       read fails.
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

# The ONLY thing that settles it — and it is asymmetric, which the text must
# say. If the PR is already armed the command REFUSES and nothing changes; if
# it is NOT armed the same command ARMS IT. So it is a probe in exactly the
# case you did not need one, and an action in the case you did. Calling it
# "harmless" would be true of one branch and a trap on the other.
DISAMBIGUATOR = (
    "`gh pr merge <PR> --auto` decides it, but ONLY RUN IT IF YOU INTEND TO ARM: "
    "'already queued to merge' proves it was ARMED and changes nothing, while any "
    "other outcome means it was not armed and you have just armed it"
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


def _context_nodes(pr):
    """The rollup contexts the query actually RETURNED — at most one page.

    `contexts(first:100)` is paginated while `totalCount` counts them all, so
    this list can be a strict subset. Anything derived from it is a statement
    about the page, never about the rollup, and the caller has to say which.

    CheckRun carries `name` + `conclusion` (None while running); StatusContext
    carries `context` + `state`. Both shapes are normalised into one list.
    """
    nodes = _dig(_rollup(pr), "contexts", "nodes", default=[]) or []
    out = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        out.append(
            {
                "name": str(n.get("name") or n.get("context") or ""),
                "state": str(n.get("conclusion") or n.get("state") or n.get("status") or "").upper(),
            }
        )
    return out


def judge(payload):
    """payload -> {verdict, sub_state, evidence: [...], warnings: [...]}

    `payload` keys:
      pr             the GraphQL `pullRequest` node (required)
      required_names list[str] | None — the NAMES branch protection requires on
                     the PR's own base branch. None means the probe could not
                     answer, which is not the same as "requires nothing"
      queue_runs     {matched, window, oldest} | None — queue-branch runs and the
                     DEPTH of the page they were counted in. A bare int is still
                     accepted (older callers), but then the window is unknown and
                     a zero is rendered with that uncertainty stated.
      armed_sha      str | None — the sha `mq arm` recorded, if any
      armed_sha_unreadable
                     bool — a state file exists but could not be parsed, so the
                     head-vs-armed comparison is unavailable rather than absent
    """
    pr = payload.get("pr")
    if not isinstance(pr, dict) or not pr:
        raise ValueError("payload.pr is missing or not an object")

    state = (pr.get("state") or "").upper()
    merged_at = pr.get("mergedAt") or ""
    entry = pr.get("mergeQueueEntry")
    amr = pr.get("autoMergeRequest")
    enabled_at = _dig(amr, "enabledAt", default="") if isinstance(amr, dict) else ""

    required_names = payload.get("required_names")
    required_count = len(required_names) if isinstance(required_names, list) else None
    queue_runs = payload.get("queue_runs")
    armed_sha = payload.get("armed_sha")
    armed_sha_unreadable = bool(payload.get("armed_sha_unreadable"))

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
        # NEITHER field yields an arm. This is trap #10's window and it is NOT
        # 'not armed'.
        #
        # ARMED keys on `enabledAt`, not on the presence of the object, because
        # `enabledAt` is a nullable DateTime — so `autoMergeRequest` CAN arrive
        # as a non-null object carrying a null timestamp. Saying "both absent"
        # there would assert the absence of an object we were just handed: a
        # measured falsehood inside the one tool whose entire value is that its
        # evidence is true. Say which of the two shapes actually arrived.
        verdict = "INDETERMINATE"
        if isinstance(amr, dict):
            evidence.append(
                "autoMergeRequest is PRESENT but carries no enabledAt, and there is no "
                "mergeQueueEntry — no arm can be read from either, which is the "
                "documented arm->entry window, NOT proof of disarmament (measured PR #5036)"
            )
        else:
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
    nodes = _context_nodes(pr)
    seen_names = {n["name"] for n in nodes if n["name"]}
    truncated = isinstance(total, int) and len(nodes) < total
    base_ref = pr.get("baseRefName") or ""

    evidence.append(
        f"rollup={rollup_state or '<none>'} over totalCount="
        f"{total if total is not None else '?'} context(s)"
        + (f"; {base_ref or 'the base branch'} requires {required_count}" if required_count is not None else "")
    )

    # A required check has an IDENTITY, not a cardinality. Sixty-eight green
    # OPTIONAL contexts do not satisfy eleven REQUIRED ones that are all
    # absent — and comparing the two counts says they do. That substitution
    # (a number standing in for a name set) is the same proxy-for-entity
    # mistake this whole verb exists to stop, so it is checked by NAME and the
    # count is kept only as the thing to print.
    if terminal:
        pass
    elif required_names is None:
        warnings.append(
            "required checks CANNOT-VERIFY: the base branch's protection did not answer with a "
            "check list (classic protection may be absent and the rules may live in a ruleset). "
            "A rollup=SUCCESS cannot be trusted without knowing WHICH checks had to be in it — "
            "and this is not the same as 'requires nothing'."
        )
    elif not required_names:
        evidence.append("the base branch declares no required status checks")
    elif not seen_names:
        warnings.append(
            f"{len(required_names)} required check(s) declared, but the rollup returned no context "
            "NAMES to match them against — presence cannot be verified from this read."
        )
    else:
        # No count-vs-count fallback lives here. Once every required NAME is
        # accounted for, `totalCount < len(required)` is unreachable by
        # construction (nodes are a subset of total), so such a branch would
        # be a guard that cannot fire — the shape this file exists to refuse.
        missing = sorted(n for n in required_names if n not in seen_names)
        if missing and truncated:
            warnings.append(
                f"{len(missing)} required check(s) are absent from the {len(nodes)} context(s) this "
                f"read returned, but the rollup has {total} and only one page was fetched — "
                f"CANNOT-VERIFY rather than missing. First: {', '.join(missing[:3])}"
            )
        elif missing:
            warnings.append(
                f"FALSE GREEN RISK: {len(missing)} of {len(required_names)} required check(s) are "
                f"ABSENT from the rollup entirely, whatever its state says — a green computed over "
                f"contexts that are not the required ones is not mergeable-green. "
                f"Missing: {', '.join(missing[:5])}"
                + (f" (+{len(missing) - 5} more)" if len(missing) > 5 else "")
            )

    if truncated and not terminal:
        warnings.append(
            f"only {len(nodes)} of {total} rollup contexts were fetched (the query asks for one "
            "page): any statement below about which contexts are present or CANCELLED is about "
            "that page, not about the rollup."
        )

    # --- evidence: CANCELLED is not 'fail', and not 'pass' either -----------
    cancelled = [n for n in nodes if n["state"] == "CANCELLED"]
    if cancelled:
        evidence.append(f"CANCELLED contexts: {len(cancelled)}")
        warnings.append(
            f"{len(cancelled)} context(s) CANCELLED. `gh pr checks` files these under bucket "
            "'cancel', never 'fail' — a caller filtering bucket=='fail' reads '0 reds' on a PR "
            "whose rollup may be FAILURE. The authority is statusCheckRollup.state."
        )

    # --- evidence: the arm rides the PR, not the sha ------------------------
    head = pr.get("headRefOid") or ""
    if armed_sha_unreadable:
        # Silence here would delete the HEAD-MOVED check without saying so —
        # an omission indistinguishable from "this PR was never armed", which
        # is the one thing this file refuses to imply anywhere else.
        warnings.append(
            "an armed-state file exists for this PR but could not be read, so the "
            "head-vs-armed comparison is CANNOT-VERIFY — not evidence that the head "
            "has held still since arming."
        )
    elif armed_sha:
        if head and head != armed_sha:
            warnings.append(
                f"HEAD MOVED since arm: armed {armed_sha[:12]}, head now {head[:12]}. "
                "The auto-merge request sits on the PR, not the SHA — this push inherited "
                "the arm WITHOUT re-passing the gate that judged it."
            )
        elif not head:
            warnings.append(
                f"an armed sha is on record ({armed_sha[:12]}) but this read returned no "
                "headRefOid, so head-vs-armed is CANNOT-VERIFY — silence here would have "
                "read as 'the head has held still'."
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


def render(result, pr_number, repo=""):
    lines = [f"== mq state — PR #{pr_number}" + (f" ({repo})" if repo else "") + " =="]
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
    ap.add_argument("--repo", default="", help="owner/name, for the header only")
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
    # A traceback is not a verdict, and rc 1 is not rc 3. Any shape the judge
    # cannot read — a list instead of an object, a string where a number was
    # promised — has to arrive as a labelled CANNOT-VERIFY, or the caller
    # reading only the exit code learns the wrong thing.
    try:
        if not isinstance(payload, dict):
            raise ValueError(f"payload must be a JSON object, got {type(payload).__name__}")
        result = judge(payload)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        print(f"CANNOT-VERIFY — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result, args.pr, args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
