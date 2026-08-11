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
    3. its `on.pull_request` sub-block carries NO top-level `paths:` key —
       the exact Codex F12 trap.

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
scripts/lint_workflow_timeout_floor.py's own declared limit): rule 3 checks
`on.pull_request.paths` ONLY, never `on.push.paths`. A `push:`-triggered run
targets `main` directly, after the PR already merged — it never gates
whether a PR's required context resolves, so a `paths:` filter there is a
different, legitimate cost optimization (skip re-running on an irrelevant
push to main), not the Codex F12 trap. Checked empirically against this
repo's OWN required-context workflows at authoring time (2026-08-11): 12 of
them carry a `push.paths` filter and would ALL false-positive under a
scope that didn't draw this line — none of them carry a `pull_request.paths`
filter. `merge_group:` itself does not support a `paths:` sub-key in GitHub
Actions at all, so there is nothing to check there.

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


def check_no_pull_request_paths_filter(on_block: dict[str, Any]) -> list[str]:
    pr_block = on_block.get("pull_request")
    if isinstance(pr_block, dict) and "paths" in pr_block:
        return [
            "top-level `paths:` filter under `on.pull_request` — an innocent PR "
            "outside those paths never starts a run, so this required context "
            "hangs 'Expected — waiting' forever (Codex F12)"
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

        for v in check_merge_group_trigger(on_block):
            violations.append(f"[{name}] {workflow_file}: {v}")
        for v in check_no_pull_request_paths_filter(on_block):
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
        print("  ✓ every required context's defining workflow has merge_group + no top-level pull_request paths:")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
