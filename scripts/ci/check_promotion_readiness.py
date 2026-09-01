#!/usr/bin/env python3
"""check_promotion_readiness.py — the precondition to promoting a check
context to `main`'s required-status-checks: how many currently-open PRs
would become newly BLOCKED if these contexts were required today?

WHY THIS EXISTS. Wiring a workflow so it CAN be a required context
(`on.pull_request` with no top-level `paths:`, plus `merge_group:` — see
`scripts/ci/check_required_workflow_conformance.py`) and being SAFE TO
PROMOTE it today are two different states, and until this script existed
nothing in the repo could tell them apart. Three wiring PRs merged
2026-08-30/31 (#5325, #5329, #5332) made four job contexts conformant —
`VOA probe organ tests`, `Restore drill wiring tests`,
`Canary self-test + incremental mutation`, `PR collision check corpus` —
but conformance only proves a NEW push would report the context. It says
nothing about PRs that are already open: their head commit was fixed before
these workflows existed or before their `paths:` filters were removed, and
promoting a context does not retroactively trigger a run on an unrelated
head SHA. A context absent from a PR's rollup shows "Expected — waiting for
status" forever (cicatrix W69) — so three individually-correct wiring PRs
could still stall the fleet-wide merge queue if "conformance green" were
read as "promotable". Zero's constraint on this whole wave, verbatim:
"abbiamo lavorato tanto per velocizzarla, non voglio regressioni".

WHAT IT DOES. For each candidate context, for every currently-open PR
against `--base` (default `main`): read that PR's OWN `statusCheckRollup`
(never a repo-wide run listing — see fetch_pr_rollup's docstring for why
that distinction is load-bearing) and classify it PASS / SKIPPED / NEUTRAL
/ PENDING / FAIL / ABSENT (classify()'s docstring has the full state table).
A PR is "newly blocked" if ANY candidate resolves to a blocking state for
it. Exit code answers the gate question directly (see EXIT CODES).

TRAPS THIS SCRIPT IS BUILT NOT TO FALL INTO, each one measured against this
repo's own live state on 2026-08-31 (not merely asserted):

  - workflow_dispatch check-suite trap: a context can be reported by a run
    whose check-run lands in a check suite that never enters a PR's
    rollup. fetch_pr_rollup() reads EXCLUSIVELY `gh pr view <n> --json
    statusCheckRollup` — never `gh run list` / `gh api .../actions/runs`.
    test_check_promotion_readiness.py enforces this by mocking subprocess
    and asserting every invocation's argv.
  - skipped-is-satisfied trap: a job-level `if:` that evaluates false still
    reports a completed run with conclusion SKIPPED, and GitHub treats a
    skipped required check as satisfied — classify() gives it its own
    state (STATE_SKIPPED) rather than folding it into PASS or ABSENT, so
    the table always shows WHICH kind of non-blocking outcome a PR relies
    on. NEUTRAL gets the identical non-blocking treatment (GitHub's
    documented Checks API conclusion semantics: success/neutral/skipped
    all satisfy a required check; only failure/cancelled/timed_out/
    action_required/stale/startup_failure block one) and its own state for
    the same reason — measured live in this repo 2026-08-31: CodeQL and
    "Vercel Agent Review" both report NEUTRAL on real open PRs, so this is
    not a hypothetical shape.
  - job-name-vs-workflow-name trap: the reported context is the JOB's
    `name:` (or job id), not the workflow's top-level `name:` — confirmed
    live, not assumed: "PR collision check corpus" reports under
    workflowName "PR collision check (advisory)", and "Canary self-test +
    incremental mutation" reports under workflowName "P1 STRATO-2
    incremental mutation gate". This script matches on the rollup's own
    `name`/`context` field, never on a workflow filename or its `name:`.
  - hardcoded-candidates trap: candidates are CLI input (--context,
    repeatable, or --candidates-file), never literals in this module.
    `--contexts-file` (default infra/required.d/contexts.json) is read
    only to ANNOTATE a candidate already present in that advisory snapshot
    — never to supply or validate the candidate list itself, and never
    fatal if the file is missing/stale (that snapshot is known to have
    drifted: 11 entries against 12 live contexts at authoring time).
  - empty-sweep-reads-clean trap: examining zero PRs or zero candidates
    must never exit 0 — see EXIT CODES. Found twice in this repo's own
    corpora before this rule existed, per the mandate that commissioned
    this script.
  - bulk-query trap (measured, not a hypothetical the module works around
    speculatively): `gh pr list --json statusCheckRollup` across this
    repo's ~44 open PRs returned HTTP 504 on every attempt on 2026-08-31 —
    each PR here carries 40-70+ check entries, and the underlying GraphQL
    query for all of them at once is too expensive. fetch_pr_rollup() below
    fetches ONE PR at a time (measured reliable, ~1s/call) and
    fetch_all_rollups() parallelizes that with a bounded thread pool
    instead of ever retrying the bulk shape.

EXIT CODES (mirrors this repo's own sibling-script convention — see
scripts/evidence_pack_lint.py / scripts/ci/check_required_workflow_conformance.py):
  0  examined >=1 PR and >=1 candidate, every fetch succeeded, and the
     newly-blocked PR count is <= --max-newly-blocked (PROMOTABLE)
  1  examined successfully but the newly-blocked PR count exceeds
     --max-newly-blocked (NOT PROMOTABLE today — this is the gate firing,
     not a tool failure)
  2  CANNOT-VERIFY: a gh/network call failed after retries, OR the
     examined set (PRs or, transitively, their rollups) came back empty —
     an empty sweep must never be silently read as "clean" (W84)
  3  usage error (no --context/--candidates-file given, or a negative
     --max-newly-blocked)

Usage:
    python3 scripts/ci/check_promotion_readiness.py \\
        --context "VOA probe organ tests" \\
        --context "Restore drill wiring tests" \\
        --context "Canary self-test + incremental mutation" \\
        --context "PR collision check corpus" \\
        [--base main] [--repo OWNER/NAME] [--max-newly-blocked 0] \\
        [--only-blocking] [--json]

No mutation of GitHub state anywhere in this module — read-only `gh pr
list` / `gh pr view` / `gh repo view` calls only. Never arms, promotes, or
edits infra/required.d/contexts.json or branch protection; this tool
MEASURES, a human/conductor PROMOTES.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONTEXTS_FILE = REPO_ROOT / "infra" / "required.d" / "contexts.json"

DEFAULT_LIMIT = 500
DEFAULT_CONCURRENCY = 6
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 2.0

# gh's GraphQL query for `gh pr view --json statusCheckRollup` pages the
# rollup's `contexts` connection at `contexts(first:100)` — confirmed live
# 2026-08-31 (see fetch_pr_rollup's docstring). A rollup landing at or above
# this size is treated as possibly-truncated, never trusted as complete.
_ROLLUP_PAGE_SIZE = 100

STATE_PASS = "PASS"
STATE_SKIPPED = "SKIPPED"
STATE_NEUTRAL = "NEUTRAL"
STATE_PENDING = "PENDING"
STATE_FAIL = "FAIL"
STATE_ABSENT = "ABSENT"
_STATE_DISPLAY_ORDER = (
    STATE_PASS, STATE_SKIPPED, STATE_NEUTRAL, STATE_PENDING, STATE_FAIL, STATE_ABSENT,
)

# CheckRun conclusions GitHub treats as SATISFYING a required check when the
# job has COMPLETED. Only reachable when status == "COMPLETED"; a still-
# running job is STATE_PENDING regardless of what (if anything) this dict
# would say about its (empty) conclusion. See the module docstring's
# "skipped-is-satisfied trap" for the citation.
_NONBLOCKING_CHECKRUN_CONCLUSIONS: dict[str, str] = {
    "SUCCESS": STATE_PASS,
    "SKIPPED": STATE_SKIPPED,
    "NEUTRAL": STATE_NEUTRAL,
}


class CannotVerify(RuntimeError):
    """Raised whenever this tool cannot trust its own answer: a gh/network
    failure after retries, or a response missing an expected field/shape.
    Every raiser of this is a place this module refuses to guess — per the
    mandate, 'Network failure => CANNOT-VERIFY and a non-zero exit. Never a
    guess, never a silent skip.' main() turns an uncaught one into exit 2."""


# --------------------------------------------------------------------- gh IO


def _gh_run(args: list[str], *, timeout: int, retries: int, backoff: float) -> str:
    """Retrying subprocess wrapper around the `gh` CLI. Every OTHER caller in
    this module (fetch_open_prs, fetch_pr_rollup) passes --repo explicitly
    on every invocation — this checkout's cwd is NOT trusted to resolve the
    target repo for THOSE calls (this repo's own lesson, 'la shell ti
    mente': a harness-level cwd reset between tool calls is a measured, live
    behavior on this fleet, not a hypothetical). The one deliberate
    exception is repo_slug() itself: its entire job is discovering the repo
    from cwd when the caller did not supply --repo at all, so it is the one
    _gh_run call with no --repo flag by design, not an oversight (docstring
    corrected 2026-08-31 — cross-family review, kimi-code/k3 and
    codex-gpt-5.6-sol both independently flagged the previous unqualified
    wording as inaccurate for this one caller)."""
    last_error = "gh call never attempted"
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = f"gh {' '.join(args)} raised {exc!r}"
        else:
            if proc.returncode == 0:
                return proc.stdout
            last_error = (
                f"gh {' '.join(args)} exited {proc.returncode}: "
                f"{proc.stderr.strip()[:500] or '(no stderr)'}"
            )
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise CannotVerify(last_error)


def _gh_json(args: list[str], *, timeout: int, retries: int, backoff: float) -> Any:
    raw = _gh_run(args, timeout=timeout, retries=retries, backoff=backoff)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CannotVerify(f"gh {' '.join(args)} returned non-JSON output: {exc}") from exc


def repo_slug(
    *, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES, backoff: float = DEFAULT_BACKOFF
) -> str:
    data = _gh_json(
        ["repo", "view", "--json", "nameWithOwner"], timeout=timeout, retries=retries, backoff=backoff
    )
    slug = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not slug:
        raise CannotVerify("gh repo view did not return nameWithOwner")
    return slug


_PR_LIST_FIELDS = "number,headRefName,headRefOid,isDraft,baseRefName,url"


def fetch_open_prs(
    repo: str,
    base: str,
    *,
    limit: int = DEFAULT_LIMIT,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> list[dict]:
    """Cheap call — PR identities only, no statusCheckRollup. Deliberately
    separate from fetch_pr_rollup(): see the module docstring's 'bulk-query
    trap' for why combining them in one `gh pr list ...,statusCheckRollup`
    call is not just slower but measured to fail outright on this repo.

    `--base` is passed to `gh` itself, not applied as a Python-side filter
    after the fact (found by cross-family review, codex-gpt-5.6-sol,
    2026-08-31): `--limit` bounds the RAW `gh pr list` result across every
    base branch in the repo, so filtering by base only afterward means
    `--limit` can silently exhaust itself on PRs against OTHER bases before
    ever returning enough `--base`-matching PRs — an incomplete sweep that
    still exits 0. Server-side `--base` makes `--limit` bound the right
    universe."""
    data = _gh_json(
        [
            "pr", "list", "--repo", repo, "--state", "open", "--base", base,
            "--limit", str(limit), "--json", _PR_LIST_FIELDS,
        ],
        timeout=timeout,
        retries=retries,
        backoff=backoff,
    )
    if not isinstance(data, list):
        raise CannotVerify("gh pr list did not return a JSON array")
    return data


def fetch_pr_rollup(
    repo: str,
    number: int,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> list[dict]:
    """The ONLY function in this module allowed to read check-run state,
    and it reads it exclusively from `gh pr view <n> --json
    statusCheckRollup` — this PR's own rollup, never a repo-wide run
    listing (mandate trap #1: a workflow_dispatch run's check-run lands in
    a DIFFERENT check suite and never enters a PR's rollup at all, so a
    tool reading `gh run list` / `gh api .../actions/runs` instead could
    report a context PRESENT when the PR's own merge decision would never
    see it). test_check_promotion_readiness.py enforces this boundary by
    mocking subprocess.run and asserting every captured argv starts with
    ["pr", "view", ...] or ["pr", "list", ...] — never ["run", ...] or a
    literal "actions/runs" anywhere in the args."""
    data = _gh_json(
        ["pr", "view", str(number), "--repo", repo, "--json", "number,statusCheckRollup"],
        timeout=timeout,
        retries=retries,
        backoff=backoff,
    )
    if not isinstance(data, dict) or not isinstance(data.get("statusCheckRollup"), list):
        raise CannotVerify(f"gh pr view {number} did not return a statusCheckRollup array")
    rollup = data["statusCheckRollup"]
    if len(rollup) >= _ROLLUP_PAGE_SIZE:
        # gh's own underlying GraphQL query pages statusCheckRollup contexts
        # at `contexts(first:100)` (confirmed live 2026-08-31 via `gh issue
        # view 12904 --repo cli/cli`, which dumped gh's actual query text
        # including this literal page size). Whether the `gh` CLI itself
        # follows `pageInfo.hasNextPage` to fetch subsequent pages before
        # emitting `--json statusCheckRollup` is NOT confirmed one way or
        # the other — found by cross-family review (codex-gpt-5.6-sol,
        # 2026-08-31), and this repo's own live PRs currently top out at 81
        # entries (measured same day), so it cannot be tested empirically
        # here either. Per the mandate ('never a guess, never a silent
        # skip'): a rollup landing AT the page size is exactly the shape a
        # silent truncation would produce, so it is treated as CANNOT-VERIFY
        # rather than trusted as complete — a false ABSENT on a truncated
        # candidate is precisely the failure mode this instrument exists to
        # prevent.
        raise CannotVerify(
            f"gh pr view {number} returned {len(rollup)} statusCheckRollup entries — "
            f"at or above the {_ROLLUP_PAGE_SIZE}-entry GraphQL page size, so completeness "
            "cannot be trusted (see fetch_pr_rollup's docstring)"
        )
    return rollup


def fetch_all_rollups(
    repo: str,
    pr_numbers: list[int],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> tuple[dict[int, list[dict]], dict[int, str]]:
    """Bounded-parallel fan-out over fetch_pr_rollup(). Returns
    (number -> rollup, number -> error) — a PR that failed after retries
    lands in the second dict, NEVER silently dropped from the first (a
    caller that ignored failures could under-count 'absent' contexts and
    report a falsely clean promotion verdict)."""
    rollups: dict[int, list[dict]] = {}
    failures: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        future_to_pr = {
            pool.submit(fetch_pr_rollup, repo, n, timeout=timeout, retries=retries, backoff=backoff): n
            for n in pr_numbers
        }
        for future in as_completed(future_to_pr):
            n = future_to_pr[future]
            try:
                rollups[n] = future.result()
            except CannotVerify as exc:
                failures[n] = str(exc)
    return rollups, failures


def load_already_required(path: Path) -> list[str]:
    """Best-effort, informational only — NEVER raises, NEVER affects the
    exit code. infra/required.d/contexts.json is an ADVISORY snapshot
    (scripts/ci/snapshot_required_contexts.py's own docstring) known to
    drift from live branch protection (mandate: '11 entries against 12
    live' measured before this script existed); this exists only so the
    report can flag a candidate that already appears there, never to
    resolve that drift or to supply/validate the candidate list itself."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    contexts = data.get("contexts") if isinstance(data, dict) else None
    if not isinstance(contexts, list):
        return []
    # `isinstance(c.get("name"), str)` — not the bare truthy `c.get("name")`
    # this used to be. A JSON `"name": 1` is truthy but not a string, and
    # `sorted({...})` over a set mixing str and int raises TypeError,
    # breaking this function's own "NEVER raises" contract on a file that IS
    # valid JSON, just malformed in a way this function is supposed to
    # tolerate. Found by cross-family review (codex-gpt-5.6-sol, 2026-08-31).
    names = {
        c["name"] for c in contexts
        if isinstance(c, dict) and isinstance(c.get("name"), str) and c["name"].strip()
    }
    return sorted(names)


# ------------------------------------------------------------ classification


def _entry_name(entry: dict) -> str | None:
    """A rollup node's context-identifying field differs by __typename: a
    CheckRun (GitHub Actions / GitHub Apps) reports `name`; a StatusContext
    (the legacy commit-status API — confirmed live 2026-08-31 on this
    repo's own PRs: {"__typename": "StatusContext", "context": "Vercel",
    "state": "SUCCESS", ...}) reports `context` and has no `name` key."""
    if entry.get("__typename") == "StatusContext":
        return entry.get("context")
    return entry.get("name")


def _is_settled(entry: dict) -> bool:
    """True when `entry` represents a resolved (non-in-flight) result.
    CheckRun: status == "COMPLETED". StatusContext: state != "PENDING" —
    the legacy Status API has no separate status/conclusion split, `state`
    alone carries both "is it done" and "what happened"."""
    if entry.get("__typename") == "StatusContext":
        return entry.get("state") != "PENDING"
    return entry.get("status") == "COMPLETED"


def _pick_authoritative(entries: list[dict]) -> dict:
    """Defensive tie-break for the (unexpected — a well-formed rollup
    already carries at most one node per context name) case of >1 entry
    matching the same context: prefer a SETTLED entry over an in-flight
    one, then the most recently resolved by completedAt/startedAt/
    createdAt (whichever the node type carries)."""
    settled = [e for e in entries if _is_settled(e)]
    pool = settled or entries
    if len(pool) == 1:
        return pool[0]
    return max(pool, key=lambda e: e.get("completedAt") or e.get("startedAt") or e.get("createdAt") or "")


def classify(rollup: list[dict], context_name: str) -> dict:
    """The single source of truth for "does this PR's head commit already
    carry a completed run of this context, and does that satisfy it?" —
    the exact question the mandate poses. Returns
    {"state", "blocks", "typename", "raw_status", "raw_outcome", "details_url"}.

    STATE TABLE (every branch is deliberate, not merely whatever GitHub
    happened to return — see the module docstring's TRAPS section for the
    live evidence behind each non-obvious row):
      ABSENT   no rollup entry names this context at all — the classic
               "Expected — waiting for status" trap; blocks=True.
      PENDING  an entry exists but has not yet settled (CheckRun status !=
               COMPLETED, or StatusContext state == PENDING) — the mandate
               asks whether a completed run already exists, and by that
               literal test a still-running one does not yet satisfy the
               context; blocks=True. (This is a MOMENT-IN-TIME reading: a
               re-run shortly after is likely to reclassify these as PASS/
               FAIL once the run settles — the table labels this state so
               a reader is never confused about which kind of "not yet
               satisfied" a PR is in.)
      PASS     CheckRun COMPLETED/SUCCESS, or StatusContext SUCCESS;
               blocks=False.
      SKIPPED  CheckRun COMPLETED/SKIPPED — GitHub treats a skipped
               required check as satisfied; blocks=False, own state so the
               table shows which non-blocking outcome a PR relies on.
      NEUTRAL  CheckRun COMPLETED/NEUTRAL — same non-blocking treatment as
               SKIPPED per GitHub's documented Checks API semantics, kept
               as a distinct state for the same reason; blocks=False.
      FAIL     Everything else that has settled: CheckRun
               FAILURE/CANCELLED/TIMED_OUT/ACTION_REQUIRED/STARTUP_FAILURE/
               STALE/any unrecognized conclusion, or StatusContext
               FAILURE/ERROR/any unrecognized state — fail CLOSED (treated
               as blocking) rather than silently assuming an unknown
               outcome is harmless; blocks=True.
    """
    matches = [e for e in rollup if _entry_name(e) == context_name]
    if not matches:
        return {
            "state": STATE_ABSENT,
            "blocks": True,
            "typename": None,
            "raw_status": None,
            "raw_outcome": None,
            "details_url": None,
        }

    entry = _pick_authoritative(matches)
    typename = entry.get("__typename")
    details_url = entry.get("detailsUrl") or entry.get("targetUrl")

    if typename == "StatusContext":
        state = entry.get("state")
        if state == "PENDING":
            mapped, blocks = STATE_PENDING, True
        elif state == "SUCCESS":
            mapped, blocks = STATE_PASS, False
        else:
            mapped, blocks = STATE_FAIL, True  # FAILURE, ERROR, or unrecognized
        return {
            "state": mapped,
            "blocks": blocks,
            "typename": typename,
            "raw_status": state,
            "raw_outcome": state,
            "details_url": details_url,
        }

    # CheckRun — or an unrecognized __typename, handled identically to an
    # unrecognized CheckRun conclusion below (this rollup has exactly two
    # documented node types today; a third is unproven, not assumed safe).
    status = entry.get("status")
    conclusion = entry.get("conclusion")
    if status != "COMPLETED":
        mapped, blocks = STATE_PENDING, True
    else:
        mapped = _NONBLOCKING_CHECKRUN_CONCLUSIONS.get(conclusion)
        if mapped is None:
            mapped, blocks = STATE_FAIL, True
        else:
            blocks = False
    return {
        "state": mapped,
        "blocks": blocks,
        "typename": typename,
        "raw_status": status,
        "raw_outcome": conclusion,
        "details_url": details_url,
    }


def evaluate(prs: list[dict], candidates: list[str]) -> dict:
    """Pure aggregation, no I/O — every guilt/innocence test in
    test_check_promotion_readiness.py exercises this function directly.
    `prs`: list of {"number", "isDraft"?, "rollup": [...]} (extra keys
    ignored). Returns {"rows", "newly_blocked_prs", "per_context_totals"}."""
    rows: list[dict] = []
    blocked_numbers: set[int] = set()
    totals: dict[str, dict[str, int]] = {c: {} for c in candidates}

    for pr in prs:
        number = pr["number"]
        rollup = pr.get("rollup") or []
        for context in candidates:
            verdict = classify(rollup, context)
            rows.append({"pr": number, "is_draft": bool(pr.get("isDraft")), "context": context, **verdict})
            totals[context][verdict["state"]] = totals[context].get(verdict["state"], 0) + 1
            if verdict["blocks"]:
                blocked_numbers.add(number)

    return {
        "rows": rows,
        "newly_blocked_prs": sorted(blocked_numbers),
        "per_context_totals": totals,
    }


# ------------------------------------------------------------------ reports


def format_table(rows: list[dict], *, only_blocking: bool = False) -> str:
    filtered = [r for r in rows if r["blocks"]] if only_blocking else rows
    if not filtered:
        return "(no blocking rows — nothing would newly block)" if only_blocking else "(no rows)"
    header = f"{'PR':>6}  {'CONTEXT':<42}  {'PRESENT':<8}  {'STATE':<8}  {'BLOCKS':<6}  DRAFT"
    lines = [header, "-" * len(header)]
    for r in sorted(filtered, key=lambda row: (row["pr"], row["context"])):
        present = "no" if r["state"] == STATE_ABSENT else "yes"
        lines.append(
            f"{r['pr']:>6}  {r['context'][:42]:<42}  {present:<8}  {r['state']:<8}  "
            f"{'YES' if r['blocks'] else 'no':<6}  {'draft' if r.get('is_draft') else ''}"
        )
    return "\n".join(lines)


def format_totals(
    report: dict,
    candidates: list[str],
    *,
    prs_examined: int,
    max_newly_blocked: int,
    already_required: list[str],
    fetch_failures_count: int = 0,
) -> str:
    lines = [f"PRs examined: {prs_examined}", ""]
    for c in candidates:
        totals = report["per_context_totals"].get(c, {})
        parts = ", ".join(f"{s}={totals[s]}" for s in _STATE_DISPLAY_ORDER if totals.get(s))
        note = "  [NOTE: already in infra/required.d/contexts.json — verify vs live branch protection]" if c in already_required else ""
        lines.append(f"  {c}: {parts or '(no data)'}{note}")
    newly_blocked = report["newly_blocked_prs"]
    lines.append("")
    lines.append(
        f"newly-blocked PRs (>=1 candidate not satisfied): {len(newly_blocked)} "
        f"(threshold --max-newly-blocked={max_newly_blocked})"
    )
    if newly_blocked:
        lines.append(f"  {newly_blocked}")
    if fetch_failures_count:
        # Found by cross-family review (codex-gpt-5.6-sol, 2026-08-31): this
        # verdict line used to be computed from newly_blocked/max_newly_blocked
        # ALONE, with no awareness of fetch_failures_count — so a run with
        # zero blocked PRs among the ones it COULD fetch, but one or more
        # fetches that failed, printed "verdict: PROMOTABLE TODAY" even
        # though the true status is CANNOT-VERIFY (exit 2). The brief
        # mandates pasting this exact table into the PR body verbatim, so a
        # misleading PROMOTABLE label here is a live hazard, not cosmetic.
        # fetch_failures_count always wins over the newly-blocked computation.
        verdict = (
            f"CANNOT-VERIFY — {fetch_failures_count} PR(s) unmeasured (see below), "
            "not a real promotable/not-promotable answer"
        )
    else:
        verdict = "PROMOTABLE TODAY" if len(newly_blocked) <= max_newly_blocked else "NOT PROMOTABLE TODAY"
    lines.append(f"verdict: {verdict}")
    return "\n".join(lines)


# ---------------------------------------------------------------------- CLI


class _UsageErrorParser(argparse.ArgumentParser):
    """Every CLI syntax error (a bad --max-newly-blocked value, an unknown
    flag, a missing value) SHALL exit 3 per this script's own documented
    contract — but bare argparse.ArgumentParser always calls self.exit(2,
    ...) on error, unconditionally, and `exit_on_error=False` (the
    documented way to opt out) only intercepts type=/choices= conversion
    failures: "unrecognized arguments" bypasses that flag entirely via a
    SEPARATE direct self.error() call in parse_args() itself — verified
    empirically 2026-08-31 (found by cross-family review, codex-gpt-5.6-sol)
    across every error shape on this repo's actual Python 3.11.11: type=int
    failure, missing value, unknown flag, and missing append-value all
    called self.exit(2, ...) before this override existed. Overriding
    error() itself (which every argparse error path funnels through, unlike
    exit_on_error) is the one interception point that actually covers all
    of them."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, f"{self.prog}: usage error: {message}\n")


def _load_candidates_file(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        return [str(x) for x in data if str(x).strip()]
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = _UsageErrorParser(
        description="How many currently-open PRs would become newly BLOCKED if these "
        "contexts were required today?"
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Candidate required-status-check context name — the JOB name as it lands in a "
        "PR's rollup, NOT the workflow's top-level name:. Repeatable.",
    )
    parser.add_argument(
        "--candidates-file", help="JSON array or newline-delimited file of additional candidate names"
    )
    parser.add_argument("--repo", default=None, help="OWNER/NAME (default: gh repo view in this checkout)")
    parser.add_argument("--base", default="main", help="PR base branch to examine (default: main)")
    parser.add_argument(
        "--contexts-file",
        default=str(DEFAULT_CONTEXTS_FILE),
        help="Advisory already-required snapshot, informational only (default: %(default)s)",
    )
    parser.add_argument("--max-newly-blocked", type=int, default=0)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument(
        "--pr",
        action="append",
        type=int,
        default=[],
        help="Restrict to this PR number (repeatable) instead of every open PR against --base",
    )
    parser.add_argument(
        "--only-blocking", action="store_true", help="Print only rows where blocks=true"
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # _UsageErrorParser.error() calls self.exit(3, ...), which is
        # argparse's own sys.exit(status) — a RAISED SystemExit, not a
        # returned value. Caught here so main()'s contract stays what every
        # other branch already promises: always RETURNS an int (0/1/2/3),
        # never raises. Real CLI usage is unaffected — `sys.exit(main())`
        # still exits 3 either way — this only matters for callers (tests,
        # or any future programmatic caller) that invoke main() directly
        # and expect a return value, not an exception.
        return exc.code if isinstance(exc.code, int) else 3

    candidates: list[str] = []
    for c in args.context:
        if c not in candidates:
            candidates.append(c)
    if args.candidates_file:
        try:
            file_candidates = _load_candidates_file(args.candidates_file)
        except OSError as exc:
            # A missing/unreadable --candidates-file is a caller mistake, not
            # a network/API failure — usage error (exit 3), not CANNOT-VERIFY
            # (exit 2). Found by cross-family review (agy, 2026-08-31): the
            # bare Path.read_text() in _load_candidates_file was unguarded,
            # so this path used to raise an unhandled FileNotFoundError out
            # of main() — a Python traceback with Python's default exit code
            # 1, outside the documented 0/1/2/3 contract entirely.
            print(f"usage error: --candidates-file {args.candidates_file!r}: {exc}", file=sys.stderr)
            return 3
        for c in file_candidates:
            if c not in candidates:
                candidates.append(c)

    if not candidates:
        print(
            "usage error: at least one --context NAME (or --candidates-file) is required — "
            "the candidate list must be data the caller supplies, never hardcoded in this script",
            file=sys.stderr,
        )
        return 3
    if args.max_newly_blocked < 0:
        print("usage error: --max-newly-blocked must be >= 0", file=sys.stderr)
        return 3

    try:
        repo = args.repo or repo_slug(timeout=args.timeout, retries=args.retries, backoff=DEFAULT_BACKOFF)
    except CannotVerify as exc:
        print(f"CANNOT-VERIFY: could not resolve repo slug: {exc}", file=sys.stderr)
        return 2

    already_required = load_already_required(Path(args.contexts_file))

    try:
        pr_list = fetch_open_prs(
            repo, args.base, limit=args.limit, timeout=args.timeout, retries=args.retries, backoff=DEFAULT_BACKOFF
        )
    except CannotVerify as exc:
        print(f"CANNOT-VERIFY: could not list open PRs for {repo}: {exc}", file=sys.stderr)
        return 2

    # Belt-and-suspenders: --base is now passed to `gh pr list` itself (see
    # fetch_open_prs' docstring), so this should already be a no-op filter —
    # kept anyway as defense-in-depth against a `gh` version/flag surprise,
    # never trusted as the ONLY thing bounding the result to the right base.
    pr_list = [p for p in pr_list if p.get("baseRefName") == args.base]
    if args.pr:
        wanted = set(args.pr)
        pr_list = [p for p in pr_list if p.get("number") in wanted]

    if not pr_list:
        print(
            f"CANNOT-VERIFY: examined ZERO open PRs against base {args.base!r} in {repo} — "
            "refusing to report a promotion verdict against an empty examined-set (a gate that "
            "passes having examined nothing is the defect class this instrument exists to kill)",
            file=sys.stderr,
        )
        return 2

    pr_numbers = [p["number"] for p in pr_list]
    rollups, fetch_failures = fetch_all_rollups(
        repo,
        pr_numbers,
        concurrency=args.concurrency,
        timeout=args.timeout,
        retries=args.retries,
        backoff=DEFAULT_BACKOFF,
    )
    # PRs whose rollup fetch failed must NOT be silently treated as "measured
    # and found absent" — that conflates CANNOT-VERIFY with a real negative
    # finding. Found by cross-family review (kimi-code/k3, 2026-08-31): the
    # old `rollups.get(p["number"], [])` fallback fed a failed PR into
    # evaluate() with an empty rollup, indistinguishable from a genuine
    # ABSENT — so the table/per-context totals/newly_blocked_prs (exactly
    # what this brief instructs pasting into the PR body verbatim) carried
    # phantom rows for PRs that were never actually measured, and the
    # printed verdict line was computed partly from that phantom data. The
    # overall exit code was already safely forced to 2 by `fetch_failures`
    # below regardless, so this was a report-integrity defect, not a
    # gate-bypass — but a corrupted report is still the artifact this whole
    # instrument exists to keep honest. Fetch-failed PRs are now excluded
    # from evaluation entirely; they remain fully named in the CANNOT-VERIFY
    # block further down, never silently merged into either PASS or ABSENT.
    measured_pr_list = [p for p in pr_list if p["number"] not in fetch_failures]
    for p in measured_pr_list:
        p["rollup"] = rollups.get(p["number"], [])

    report = evaluate(measured_pr_list, candidates)

    # --json means "stdout is JSON, full stop" (this repo's own `gh --json`
    # convention, and what lets the output go straight into `jq`) — the
    # human-readable table/totals still print, just to stderr, so a
    # `--json` run stays legible on a terminal without corrupting a pipe.
    report_stream = sys.stderr if args.json else sys.stdout

    print(format_table(report["rows"], only_blocking=args.only_blocking), file=report_stream)
    print(file=report_stream)
    print(
        format_totals(
            report,
            candidates,
            prs_examined=len(pr_list),
            max_newly_blocked=args.max_newly_blocked,
            already_required=already_required,
            fetch_failures_count=len(fetch_failures),
        ),
        file=report_stream,
    )

    if fetch_failures:
        print(
            f"\nCANNOT-VERIFY: {len(fetch_failures)}/{len(pr_list)} PR(s) could not be fetched "
            "after retries — the table/totals above are PARTIAL and must not be trusted as a "
            "full sweep:",
            file=sys.stderr,
        )
        for n, msg in sorted(fetch_failures.items()):
            print(f"  PR #{n}: {msg}", file=sys.stderr)

    exit_code = 1 if len(report["newly_blocked_prs"]) > args.max_newly_blocked else 0

    if args.json:
        print(
            json.dumps(
                {
                    "repo": repo,
                    "base": args.base,
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "candidates": candidates,
                    "already_required": already_required,
                    "prs_examined": len(pr_list),
                    "max_newly_blocked": args.max_newly_blocked,
                    "newly_blocked_count": len(report["newly_blocked_prs"]),
                    "newly_blocked_prs": report["newly_blocked_prs"],
                    "per_context_totals": report["per_context_totals"],
                    "rows": report["rows"],
                    "fetch_failures": fetch_failures,
                    "exit": 2 if fetch_failures else exit_code,
                },
                indent=2,
            )
        )

    return 2 if fetch_failures else exit_code


if __name__ == "__main__":
    sys.exit(main())
