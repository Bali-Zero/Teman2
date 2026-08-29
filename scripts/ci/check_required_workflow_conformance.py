#!/usr/bin/env python3
"""check_required_workflow_conformance.py — continuous (per-PR, not weekly)
guard that every required-status-check context's DEFINING workflow is safe
to be required at all.

WHY THIS EXISTS (Merge-OS v2 Wave 0, spec §4 Wave 0 "continuous conformance
check": research/operations/2026-08-10-merge-os-v2-submission-system.md,
Qwen F9). The specific trap this closes (Codex F12, independently confirmed
by a second cross-family seat against this exact repo, spec §6.2): a
required status check is satisfied only by a run of the workflow that
REPORTS that context. If that workflow's `on:` block carries a top-level
`paths:` filter, a PR outside those paths never starts a run at all — there
is no skipped/neutral status to satisfy the check, so GitHub shows the
context "Expected — waiting for status to be reported" FOREVER, and the PR
is hard-blocked with nothing red to fix. `docs-sync.yml` and
`migration-lint.yml` shipped exactly this defect (cured in this same PR);
this guard exists so the NEXT workflow that becomes required doesn't ship it
again, checked on every PR rather than caught after the fact.

WHAT IT CHECKS, against infra/required.d/contexts.json (the advisory
snapshot from scripts/ci/snapshot_required_contexts.py):

  For every context whose `workflow_file` is set (i.e. it IS produced by a
  workflow in this repo, as opposed to an external check like a required
  Copilot review):
    1. that workflow file exists on disk;
    2. its `on:` block includes a `merge_group:` trigger — a required
       context with no `merge_group` trigger cannot be satisfied by a
       merge-queue run at all, which either stalls the queue (nothing to
       report) or silently excludes the check from queue enforcement,
       neither of which is a state a required check should be in;
    3. its `on:` block includes a `pull_request:` trigger at all — a
       required context that only fires on `merge_group` reports "Expected
       — waiting for status" on every ordinary PR view forever (same W69
       shape as rule 4, opposite trigger). Added 2026-08-29 (L06-PR1
       trigger-symmetry): the live tree had nothing to catch this at the
       time — all 8 required-context-producing workflows already declare
       both triggers — but nothing PREVENTED a future one from declaring
       merge_group-only, and rule 4 alone is silent about that shape (an
       absent `pull_request` block is not a `paths:` filter);
    4. its `on.pull_request` sub-block carries NO top-level `paths:` or
       `paths-ignore:` key — the exact Codex F12 trap. `paths-ignore` was
       closed 2026-08-29 alongside rule 3; the earlier check matched only
       the literal token `paths`, so the same "innocent PR never starts a
       run" defect sailed straight through under the sibling key. The
       BRANCH axis is deliberately not judged here — see its own DECLARED
       SCOPE LIMIT below;
    5. if its `on.pull_request` sub-block declares a `types:` list, that
       list includes both `opened` AND `synchronize` — added 2026-08-29.
       Without `synchronize`, a push to an already-open PR never starts a
       new run on the new head, so this required context can be satisfied
       on an earlier head SHA and then simply absent on the SHA that
       actually merges; without `opened`, a PR that is opened and never
       pushed to again never triggers this workflow at all. A bare
       `pull_request:` (no `types:` key present at all) declares GitHub's
       default type set and is unaffected by this rule — deliberately NOT
       requiring `reopened` too: this repo has been bitten by over-match
       nine times (superscar #3), and every live `types:` declaration
       already lists all three, so requiring only the two keys that are
       load-bearing for the trap this rule exists to catch is the
       narrower, safer rule.

  For every context whose `workflow_file` is null (declared not
  workflow-produced — the allowlist path), the registered
  `allowlist_reason` must be a non-empty, non-placeholder string. An empty
  or missing reason fails: "not workflow-produced" is an assertion about the
  context, not a default for anything the resolver could not figure out
  (mirrors superscar #3's rule for exemptions generally — an exemption is a
  guard running in reverse, and wants its own justification, not a free
  pass). `scripts/ci/snapshot_required_contexts.py` writes a deliberately
  generic placeholder reason for anything it could not resolve — the point
  of requiring a "real" reason is that placeholder text must be replaced by
  a human/session who checked, not silently accepted.

DECLARED SCOPE LIMIT (residual risk, not hidden — same style as
scripts/lint_workflow_timeout_floor.py's own declared limit): rule 4 checks
`on.pull_request.{paths,paths-ignore}` ONLY, never `on.push.paths`. A `push:`-triggered run targets `main` directly,
after the PR already merged — it never gates whether a PR's required
context resolves, so a filter there is a different, legitimate cost
optimization (skip re-running on an irrelevant push to main), not the Codex
F12 trap. RE-MEASURED 2026-08-29 (the 2026-08-11 authoring count of "12"
below was never reproducible at that commit either and is corrected, not
merely updated — it overstated the live surface by 6x): 2 of the 8
required-context-producing workflows (`guard-conformance.yml`,
`organ-conformance.yml`) carry a `push.paths` filter; neither of those two
also carries `on.pull_request.paths`, so neither would false-positive under
this scope limit even before this correction. `merge_group:` itself does
not support a `paths:` sub-key in GitHub Actions at all, so there is
nothing to check there.

DECLARED SCOPE LIMIT — the BRANCH axis is not judged, deliberately, and
this is the more instructive of the limits. A `branches:` /
`branches-ignore:` filter under `on.pull_request` CAN break a required
context exactly the way `paths:` does: `branches: [develop]` never starts a
run for a PR to `main`, so the context hangs "Expected — waiting" forever.
A first cut of rule 4 therefore flagged both keys by PRESENCE, and a second
cross-family refuter round (2026-08-29) proved that an over-match —
`branches: [main]` fires on EVERY PR to the protected branch and is
perfectly innocent, `branches-ignore: [gh-pages]` likewise, yet both were
reported identically to the genuinely-broken `branches: [develop]`
(measured: all four shapes returned exactly one violation). Shipping it
would have been superscar #3's TENTH instance in this repo, inside the very
guard whose rule 5 cites the previous nine. The rule was WITHDRAWN rather
than patched twice in one PR (Rule 8: a correction that is itself wrong
means the surface is under-specified — write the spec, do not stack a third
fix).

The spec, recorded so the follow-up does not re-derive it: the verdict must
be DIRECTIONAL against the protected branch, which
`infra/required.d/contexts.json` already carries as its top-level `branch`
field ("main" today). `branches:` is guilty only when NO pattern in the list
can match the protected branch; `branches-ignore:` only when SOME pattern
CAN. That needs GitHub's branch-pattern glob semantics (`releases/**`, `!`
negation, `*` not crossing `/`) implemented and tested in their own right —
a real sub-problem with its own trap surface, not a key-presence check.
Until it lands, `branches: [develop]` on a required workflow is a live,
KNOWN, undetected defect class: declared here, not missed.

A third, pre-existing declared scope limit (load_on_block's own contract
— see its docstring below): `on: [pull_request, merge_group]` (list form)
and `on: pull_request` (bare scalar form) are both legal GitHub Actions
syntax, but `load_on_block` only recognizes a MAPPING `on:` block — either
form collapses to `{}`, which every rule above then reads as "no triggers
declared at all", over-reporting a workflow that actually declares BOTH
triggers correctly as failing rules 2 and 3. Not a silent miss (the failure
direction is loud, not blind) and not live today — none of the 8
required-context-producing workflows uses either form (verified 2026-08-29)
— but a false positive waiting for the first workflow author who writes
`on:` as a list or a bare scalar.

SCAR NOTE (L06-PR1, 2026-08-29 — measured this turn, do NOT "fix" this back
toward symmetric path filters on both triggers). A broader ask ("assert
identical path semantics on pull_request and merge_group") is
UNIMPLEMENTABLE by construction: `merge_group` does not accept `paths:` at
all, and this repo's own actionlint (a required context) refuses a workflow
that tries —

    "paths" filter is not available for merge_group event.
    it is only for push, pull_request, pull_request_target events [events]

— reproduced live against actionlint 1.7.12 at authoring time. Any workflow
built to satisfy that literal wording would itself fail a required check.
Rules 2-5 above are the achievable invariant that serves the actual danger
(trap #9/Codex F12's head-green/queue-red split), not a weakened version of
the broader ask.

Usage:
    python3 scripts/ci/check_required_workflow_conformance.py
        [--contexts infra/required.d/contexts.json] [--repo-root .]

Exit codes: 0 conformant · 1 one or more violations · 2 cannot verify
(contexts.json missing/unparseable, or has zero contexts — an empty sweep
is not a pass, W84 "esiste ≠ armato").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONTEXTS = REPO_ROOT / "infra" / "required.d" / "contexts.json"

_PLACEHOLDER_MARKERS = ("UNRESOLVED", "TODO", "FIXME", "")


def load_contexts(path: Path) -> dict[str, Any] | None:
    """Returns None on any failure to parse — never a partial/empty dict
    that a caller could mistake for 'zero contexts, all clean' (W84)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("contexts"), list):
        return None
    return data


def load_on_block(workflow_path: Path) -> dict[str, Any] | None:
    """The workflow's `on:` block, or None if the file is missing/unparseable.
    PyYAML parses a bare `on:` key as the boolean `True` (YAML 1.1 boolean
    literal) — `doc.get(True) or doc.get("on")` covers both spellings, the
    same pattern already used by scripts/verify_main_watch_schedule_scope.py."""
    try:
        doc = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(doc, dict):
        return None
    on_block = doc.get(True)
    if on_block is None:
        on_block = doc.get("on")
    return on_block if isinstance(on_block, dict) else {}


# ------------------------------------------------------------------ checks
# Every check_* function returns a list of violation strings (empty = pass).
# AST-censused by infra/guard-conformance/registry.json (ast-def-prefix
# "check_") — the guilt+innocence discipline this repo requires of every
# textual guard applies to the guard that watches OTHER guards' triggers too.


def check_merge_group_trigger(on_block: dict[str, Any]) -> list[str]:
    if "merge_group" not in on_block:
        return [
            "missing `merge_group:` trigger — this context cannot be satisfied "
            "by a merge-queue run"
        ]
    return []


def check_pull_request_trigger_present(on_block: dict[str, Any]) -> list[str]:
    """Added 2026-08-29 (L06-PR1). `"pull_request" not in on_block` means
    the key is ABSENT entirely — distinct from `on_block["pull_request"]
    is None`, which is the ordinary bare `pull_request:` (declared, no
    filters). `on_block["pull_request"]` may ALSO be a dict that narrows
    via `types:` (3 of the 8 required-context-producing workflows do, all
    with `[opened, synchronize, reopened]`) — either shape means the
    trigger is genuinely present and must keep passing this check;
    check_pull_request_types_include_opened_and_synchronize is the separate
    rule that judges what's INSIDE a `types:` list, not whether the
    `pull_request:` key exists at all."""
    if "pull_request" not in on_block:
        return [
            "missing `pull_request:` trigger — a merge-queue run can satisfy "
            "this context while a direct PR view of it stays 'Expected — "
            "waiting for status' forever (W69, opposite trigger of rule 4)"
        ]
    return []


def check_no_pull_request_trigger_filters(on_block: dict[str, Any]) -> list[str]:
    """Renamed 2026-08-29 (was check_no_pull_request_paths_filter) — it
    judges a KEY SET now, not the single literal token `paths`, and the old
    name would go stale the moment that set grows again (the branch axis is
    the declared, still-unbuilt candidate)."""
    pr_block = on_block.get("pull_request")
    if not isinstance(pr_block, dict):
        return []
    violations: list[str] = []
    for key in ("paths", "paths-ignore"):
        if key in pr_block:
            violations.append(
                f"top-level `{key}:` filter under `on.pull_request` — an innocent PR "
                "outside that filter never starts a run, so this required context "
                "hangs 'Expected — waiting' forever (Codex F12)"
            )
    return violations


def check_pull_request_types_include_opened_and_synchronize(
    on_block: dict[str, Any],
) -> list[str]:
    """Added 2026-08-29. A `types:` list that narrows the default set is
    only a defect if it drops `opened` or `synchronize` — those two are the
    pair a required workflow depends on to ever run at all (`opened`) and
    to run again on the SHA that actually merges (`synchronize`).
    Deliberately does NOT require `reopened` too: every live `types:`
    declaration in this repo already lists all three, so requiring only
    the two that are load-bearing for the trap this rule exists to catch
    is the narrower, safer rule (superscar #3: nine prior over-matches in
    this repo). A `types:` key present but not a list, or absent entirely
    (bare `pull_request:`), is out of scope for this rule — the former is
    a different malformed-workflow failure actionlint already catches, the
    latter means "GitHub's default types", both fine and must keep
    passing."""
    pr_block = on_block.get("pull_request")
    if not isinstance(pr_block, dict):
        return []
    types = pr_block.get("types")
    if not isinstance(types, list):
        return []
    missing = [t for t in ("opened", "synchronize") if t not in types]
    if missing:
        return [
            f"`on.pull_request.types` narrows to {types!r} without "
            f"{' and '.join(missing)} — a push to an open PR whose types list "
            "omits `synchronize` never starts a new run on the new head, and "
            "one that omits `opened` never triggers on a PR that is opened "
            "and never pushed to again"
        ]
    return []


def check_context_workflow_file_exists(entry: dict[str, Any], repo_root: Path) -> list[str]:
    """Assumes the caller only invokes this for entries that declare a
    workflow_file at all (evaluate() below branches allowlisted entries to
    check_allowlist_entry_has_reason instead) — a falsy workflow_file here
    is treated as absent, not specially reported, since that shape belongs
    to the allowlist check, not this one."""
    workflow_file = entry.get("workflow_file")
    if not workflow_file:
        return []
    if not (repo_root / workflow_file).exists():
        return [f"declared workflow_file `{workflow_file}` does not exist on disk"]
    return []


def check_allowlist_entry_has_reason(entry: dict[str, Any]) -> list[str]:
    reason = entry.get("allowlist_reason")
    if not isinstance(reason, str) or reason.strip() in _PLACEHOLDER_MARKERS:
        return [
            f"context `{entry.get('name')}` is allowlisted as not workflow-produced "
            f"(workflow_file: null) but carries no real `allowlist_reason` — "
            f"'not workflow-produced' is an assertion, not a default; write down why"
        ]
    return []


# ------------------------------------------------------------------ driver


def evaluate(contexts_path: Path, repo_root: Path) -> tuple[list[str], int]:
    """Returns (violations, contexts_checked). violations is empty on a
    clean run; contexts_checked == 0 is itself a violation-adjacent state
    the caller must treat as CANNOT-VERIFY, not as a pass."""
    data = load_contexts(contexts_path)
    if data is None:
        return ([f"BLIND: {contexts_path} is missing or not valid JSON"], 0)

    contexts = data["contexts"]
    if not contexts:
        return ([f"BLIND: {contexts_path} declares zero contexts"], 0)

    violations: list[str] = []
    on_block_cache: dict[str, dict[str, Any] | None] = {}

    for entry in contexts:
        name = entry.get("name", "<unnamed>")
        workflow_file = entry.get("workflow_file")

        if not workflow_file:
            violations.extend(check_allowlist_entry_has_reason(entry))
            continue

        file_violations = check_context_workflow_file_exists(entry, repo_root)
        if file_violations:
            violations.extend(f"[{name}] {v}" for v in file_violations)
            continue

        if workflow_file not in on_block_cache:
            on_block_cache[workflow_file] = load_on_block(repo_root / workflow_file)
        on_block = on_block_cache[workflow_file]
        if on_block is None:
            violations.append(f"[{name}] workflow {workflow_file} could not be parsed")
            continue

        rule_violations = (
            check_merge_group_trigger(on_block)
            + check_pull_request_trigger_present(on_block)
            + check_no_pull_request_trigger_filters(on_block)
            + check_pull_request_types_include_opened_and_synchronize(on_block)
        )
        for v in rule_violations:
            violations.append(f"[{name}] {workflow_file}: {v}")

    return (violations, len(contexts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contexts", default=str(DEFAULT_CONTEXTS))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    contexts_path = Path(args.contexts)
    repo_root = Path(args.repo_root)

    violations, checked = evaluate(contexts_path, repo_root)

    if checked == 0:
        print(f"required-workflow-conformance: CANNOT VERIFY — {violations[0] if violations else 'no contexts'}")
        return 2

    print(f"required-workflow-conformance: {checked} required context(s) checked, {len(violations)} violation(s)")
    for v in violations:
        print(f"  ✗ {v}")
    if not violations:
        print(
            "  ✓ every required context's defining workflow has merge_group + pull_request "
            "(no top-level paths:/paths-ignore:, and types: includes "
            "opened+synchronize when narrowed)"
        )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
