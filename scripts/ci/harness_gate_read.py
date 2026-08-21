#!/usr/bin/env python3
"""harness_gate_read.py — READ-ONLY verdict mirror for the `harness/fable-gate` commit status.

WHY THIS EXISTS (research/operations/2026-08-21-fable-gate-required-promotion.md): the
`harness/fable-gate` commit status posted by scripts/harness_fable_gate.py cannot itself be a
GitHub required status check, for two independent reasons documented in
.github/workflows/harness-floor.yml's own header ("ARMING NOTE", as of 2026-08-10):

  (a) SYNTHETIC-SHA RELAY. It is a classic commit status, always posted against the PR's real
      HEAD sha (`--sha` is a required, never-guessed CLI arg). GitHub's native merge queue tests
      every entry on a SYNTHETIC test-merge commit (`merge_group.head_sha`) that this status is
      never posted against — requiring the context would deadlock the queue forever.

  (b) FORK-PR WRITE PERMISSION. On a public repo, a fork PR's default GITHUB_TOKEN is read-only.
      A workflow step that WRITES a commit status (`gh api .../statuses/<sha>` with `-f state=`)
      fails silently for external contributors today; once the context is required, that same
      failure becomes a hard, permanent block on every fork PR that isn't declaring a Gear-3 brief.

THE FIX this script is the READ half of: harness-floor.yml no longer WRITES `harness/fable-gate`
for the "not applicable" (no brief / gear<3 / kill-switch) cases — those are now expressed purely
as the WORKFLOW JOB'S OWN exit code (a native GitHub Actions check-run, auto-associated with
whatever SHA the job runs against — real PR head, workflow_dispatch ref, OR the merge queue's
synthetic SHA; no relay needed, (a) is moot by construction). For the one case that genuinely
needs an external, human-decided verdict (Gear-3, floor satisfied, evidence/pack.yml conformant),
this script READS whether scripts/harness_fable_gate.py already posted a verdict on the PR's REAL
head sha, and mirrors that verdict as ITS OWN exit code. Reading a public commit-status needs no
elevated token scope at all — (b) is moot by construction too, because this script NEVER calls
`gh api` with a write verb. Verified by this file's own test corpus
(scripts/tests/test_harness_gate_read.py::test_script_never_shells_a_write_verb and
::test_script_exposes_no_publish_or_verdict_cli_flag) — a change that made this script capable of
publishing would fail that corpus, not just this docstring's claim.

scripts/harness_fable_gate.py is UNCHANGED by this design: it remains the durable, timestamped,
audit-trail record of the gate session's verdict (harness-v2-teman2.md §6 "meccanizzazione") —
this script only reads that record back.

WHAT "PENDING" LOOKS LIKE: a completed GitHub Actions job has no native "pending forever, waiting
for a human" state distinct from "failed" — so a Gear-3 PR with no verdict yet posted fails this
job exactly like a REWORK/BLOCK verdict would (same red X), with a message that says which case it
is. The cure is to re-run this job once the verdict exists — and WHICH command depends on the
case, because the obvious one does not work here.

CORRECTED 2026-08-21: this docstring, and the PENDING message below, used to say
`gh workflow run harness-floor.yml --ref <branch>` and forbid `gh run rerun` outright. That
deadlocked #4543. (#4549 hit the same PENDING red but was cured by a rerun without ever taking
the dispatch path -- 9 `pull_request` runs on its branch, zero `workflow_dispatch`. It confirms the
REMEDY a second time, not the deadlock.) A `workflow_dispatch` run creates its check-run in a DIFFERENT
CHECK SUITE from the `pull_request` event's, and that check-run does not enter the PR's
statusCheckRollup AT ALL — an ABSENT entry, not a superseded one. Measured on #4543: the rollup
holds exactly ONE `Harness floor recompute` entry, pointing at the pull_request run; the dispatch
run appears nowhere. So the dispatch goes green while the PR keeps the old failure.

On an open PR, re-run the ORIGINAL `pull_request` run: `gh run rerun <that run id>`. Same head SHA,
same check suite, verdict now posted — the rollup clears. This does not repeal W111 (whose hazard
is a ref that resolves through a MOVING base): on the pull_request path this workflow checks out
`github.event.pull_request.base.sha`, a pinned SHA, never `refs/pull/N/merge`. The
`workflow_dispatch:` trigger remains for the case where there is no PR to unblock. Full procedure,
including the escapes when no rerunnable run exists:
docs/runbooks/merge-queue-discipline.md section 6quinquies; CLAUDE.md Agent PR Contract rule 3.

EVENT-TO-SHA RESOLUTION:
  - pull_request  : the PR's real head sha is already directly on the event payload.
  - workflow_dispatch : `github.sha` already resolves to the dispatched ref's tip — no PR
    indirection needed, this IS the real head sha.
  - merge_group   : the synthetic `merge_group.head_sha` is NOT the PR's real head. The PR
    NUMBER is recoverable from `merge_group.head_ref`
    (`refs/heads/gh-readonly-queue/<base>/pr-<N>-<sha>` — a looser version of
    scripts/queue_ejection_attribution.py::PR_SHA_RE that anchors only the PR-number group, since
    the trailing sha in that ref is the BASE commit at queue-time, per
    scripts/ci/vercel_should_build.sh's own verified comment — NOT useful here, and not captured).
    The PR's live head sha is then fetched via
    `gh pr view <N> --json headRefOid` (a READ). GitHub ejects a queue entry the instant new
    commits land on its PR, so a merge_group run that is still executing (not superseded/
    cancelled) is guaranteed to see the PR's CURRENT head sha equal to what is being tested.

CLI:
  python3 scripts/ci/harness_gate_read.py --event-name <pull_request|merge_group|workflow_dispatch>
      --repo <owner/repo>
      [--pr-head-sha <sha>]        # pull_request: github.event.pull_request.head.sha
      [--merge-group-head-ref <ref>]  # merge_group: github.event.merge_group.head_ref
      [--dispatch-sha <sha>]       # workflow_dispatch: github.sha
      [--gh-bin gh]                # override for tests

Exit codes:
  0  harness/fable-gate == success on the resolved real head sha
  1  anything else: no verdict yet (pending), REWORK/BLOCK verdict, unresolvable sha, gh failure
     — always fail CLOSED, never silently pass on "could not check".
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

CONTEXT = "harness/fable-gate"

# A looser version of scripts/queue_ejection_attribution.py::PR_SHA_RE (which also anchors the
# trailing 40-hex sha) — only the PR-number group is needed here, since that trailing sha is the
# BASE commit at queue time, not the PR's head (see the module docstring). Deliberately does NOT
# require a real queue-ref shape after the number (e.g. matches inside "feature/pr-12-refactor"
# too) — harmless here because merge_group.head_ref is GitHub-minted, never attacker-supplied.
PR_NUMBER_RE = re.compile(r"pr-(\d+)-")


class GhCallError(RuntimeError):
    """A `gh` invocation failed or returned something this script cannot parse.
    Always caught and turned into a fail-closed exit — never treated as 'no data'."""


def extract_pr_number(head_ref: str | None) -> int | None:
    if not head_ref:
        return None
    match = PR_NUMBER_RE.search(head_ref)
    return int(match.group(1)) if match else None


def _run_gh(gh_bin: str, args: list[str]) -> str:
    """Every call this script ever makes to `gh` goes through here — a single choke point a
    source-scan test can audit for write verbs (-X, -f, --method, POST/PATCH/PUT/DELETE)."""
    try:
        proc = subprocess.run(
            [gh_bin, *args], capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GhCallError(f"gh {' '.join(args)} failed (rc={exc.returncode}): {exc.stderr.strip()[:300]}") from exc
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise GhCallError(f"gh {' '.join(args)} could not run: {exc}") from exc
    return proc.stdout


def resolve_real_head_sha(
    *,
    event_name: str,
    repo: str,
    pr_head_sha: str | None,
    merge_group_head_ref: str | None,
    dispatch_sha: str | None,
    gh_bin: str,
) -> tuple[str | None, str]:
    """Returns (sha_or_None, human-readable source/reason). Pure orchestration over `_run_gh` —
    every branch is independently testable by injecting a fake gh_bin (see test corpus)."""
    if event_name == "pull_request":
        if pr_head_sha and re.fullmatch(r"[0-9a-f]{40}", pr_head_sha):
            return pr_head_sha, "pull_request.head.sha"
        return None, f"pull_request event but --pr-head-sha is missing/malformed: {pr_head_sha!r}"

    if event_name == "workflow_dispatch":
        if dispatch_sha and re.fullmatch(r"[0-9a-f]{40}", dispatch_sha):
            return dispatch_sha, "workflow_dispatch ref tip (github.sha)"
        return None, f"workflow_dispatch event but --dispatch-sha is missing/malformed: {dispatch_sha!r}"

    if event_name == "merge_group":
        pr_number = extract_pr_number(merge_group_head_ref)
        if pr_number is None:
            return None, f"could not parse a PR number out of head_ref={merge_group_head_ref!r}"
        try:
            out = _run_gh(gh_bin, ["pr", "view", str(pr_number), "--repo", repo, "--json", "headRefOid"])
        except GhCallError as exc:
            return None, f"gh pr view #{pr_number} failed: {exc}"
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            return None, f"gh pr view #{pr_number} returned unparseable JSON: {exc}"
        sha = data.get("headRefOid") if isinstance(data, dict) else None
        if not sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
            return None, f"gh pr view #{pr_number} returned no usable headRefOid: {data!r}"
        return sha, f"live headRefOid of PR #{pr_number} (parsed from queue ref)"

    return None, f"unsupported --event-name {event_name!r}"


def read_fable_gate_state(*, sha: str, repo: str, gh_bin: str) -> tuple[str | None, str | None]:
    """Returns (state, description) for the `harness/fable-gate` context on `sha`, or
    (None, None) if no such status has EVER been posted there (genuinely pending, not a defect).
    Raises GhCallError if the read itself could not be completed — the caller must NOT conflate
    that with (None, None); "could not verify" is never "verified absent" (cicatrix W88/W106).

    Uses the COMBINED status endpoint (`commits/{sha}/status`), which GitHub already dedupes to
    the single most-recent entry per context — avoids re-implementing that ourselves against the
    raw per-status log (`commits/{sha}/statuses`), which is newest-first but not deduped."""
    out = _run_gh(gh_bin, ["api", f"repos/{repo}/commits/{sha}/status"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise GhCallError(f"commits/{sha}/status returned unparseable JSON: {exc}") from exc
    statuses = data.get("statuses") if isinstance(data, dict) else None
    if not isinstance(statuses, list):
        raise GhCallError(f"commits/{sha}/status response missing a 'statuses' array: {data!r}")
    for entry in statuses:
        if isinstance(entry, dict) and entry.get("context") == CONTEXT:
            return entry.get("state"), entry.get("description")
    return None, None


def decide(state: str | None) -> tuple[int, str]:
    """(exit_code, message). The ONLY state that yields 0 is the literal string 'success' —
    anything else, including None (never posted) or an unrecognized value, fails closed."""
    if state is None:
        return (
            1,
            f"PENDING — no {CONTEXT} verdict has been posted yet on this commit. This is NOT a "
            "defect: the gate session has not run scripts/harness_fable_gate.py yet. After it "
            "posts a verdict, re-trigger THIS run: `gh run rerun <this run id>`. Do NOT use "
            "`gh workflow run --ref` — a workflow_dispatch run lands its check-run in a different "
            "check suite and never enters the PR's rollup at all, so the PR stays BLOCKED "
            "(measured on #4543). Full procedure: "
            "docs/runbooks/merge-queue-discipline.md section 6quinquies.",
        )
    if state == "success":
        return 0, f"{CONTEXT} verdict = success"
    return 1, f"{CONTEXT} verdict = {state!r} — this PR does not pass the gate"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--event-name", required=True, choices=["pull_request", "merge_group", "workflow_dispatch"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-head-sha", default=None)
    parser.add_argument("--merge-group-head-ref", default=None)
    parser.add_argument("--dispatch-sha", default=None)
    parser.add_argument("--gh-bin", default="gh")
    args = parser.parse_args(argv)

    sha, reason = resolve_real_head_sha(
        event_name=args.event_name,
        repo=args.repo,
        pr_head_sha=args.pr_head_sha,
        merge_group_head_ref=args.merge_group_head_ref,
        dispatch_sha=args.dispatch_sha,
        gh_bin=args.gh_bin,
    )
    if sha is None:
        print(f"::error::harness_gate_read: could not resolve the real PR head sha — {reason}", file=sys.stderr)
        return 1
    print(f"harness_gate_read: real head sha = {sha} ({reason})")

    try:
        state, description = read_fable_gate_state(sha=sha, repo=args.repo, gh_bin=args.gh_bin)
    except GhCallError as exc:
        print(f"::error::harness_gate_read: CANNOT-VERIFY (read itself failed, not the same as 'no verdict') — {exc}", file=sys.stderr)
        return 1

    if description:
        print(f"harness_gate_read: posted description = {description!r}")

    code, message = decide(state)
    if code == 0:
        print(f"::notice::harness_gate_read: {message}")
    else:
        print(f"::error::harness_gate_read: {message}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
