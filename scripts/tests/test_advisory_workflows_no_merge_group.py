"""Deadlock tripwire for the merge-queue-slim cure (perf(ci), 2026-08-27).

WHY THIS EXISTS: Zero's 2026-08-27 queue-unblock — the merge queue waits only
on the required-status-check contexts (11, per infra/required.d/contexts.json)
but every workflow, required or not, used to trigger on `merge_group` too, so
each queue entry spawned ~50 runs and the 11 that actually gate the merge
starved behind the ~40 that don't. The cure: advisory workflows (every
workflow that does NOT back one of the 11 required contexts) stop triggering
on `merge_group` — they keep running on `pull_request`/`push`/etc, so PR-time
coverage is unchanged, only the merge-queue run is dropped.

THE DEADLOCK THIS GUARDS AGAINST (superscar #2, "esiste != armato" in reverse):
if a workflow that DOES back one of the 11 required contexts ever loses its
`merge_group` trigger — by this cure over-reaching, or a later edit repeating
the mistake — that context can never be satisfied by a merge-queue run. GitHub
shows it "Expected — waiting for status to be reported" forever and every
queue entry times out at 90 minutes. This is silent at review time (the PR
that removed the trigger still merges fine on `pull_request`) and only bites
the next PR that tries to go through the queue — the classic superscar #2
shape of a green PR hiding a queue-wide outage.

This module re-derives "which workflow backs which required context" from
scripts/ci/required_context_map.py (the same resolver
check_required_workflow_conformance.py and snapshot_required_contexts.py
share) rather than hardcoding file names, so it can never drift from the
resolver's own logic — and re-parses each workflow's real `on:` block with
PyYAML rather than grepping, for the same reason
check_required_workflow_conformance.py does (a textual match on the string
"merge_group" hits conditionals and comments, not just the trigger key — see
that module's own `load_on_block`).

Run:  python3 -m pytest scripts/tests/test_advisory_workflows_no_merge_group.py -q
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTEXTS_PATH = REPO_ROOT / "infra" / "required.d" / "contexts.json"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def _load_module(name: str, rel_path: str):
    module_path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


required_context_map = _load_module("required_context_map", "scripts/ci/required_context_map.py")
conformance = _load_module(
    "check_required_workflow_conformance", "scripts/ci/check_required_workflow_conformance.py"
)


def _required_workflow_files() -> set[str]:
    """The set of workflow_file entries declared by infra/required.d/contexts.json
    — the live snapshot, not a hardcoded list, so this test tracks whichever
    11 (or N) contexts are actually required today without needing an edit
    when that count legitimately changes (it already has, twice, in one day:
    27 -> 9 -> 11)."""
    data = json.loads(CONTEXTS_PATH.read_text(encoding="utf-8"))
    files = {c["workflow_file"] for c in data["contexts"] if c.get("workflow_file")}
    assert files, "infra/required.d/contexts.json declares zero workflow-backed contexts — CANNOT VERIFY"
    return files


def test_every_required_contexts_workflow_file_exists():
    """Sanity precondition for the real test below — a typo'd workflow_file
    would make the merge_group check vacuously pass by never running it."""
    for rel in _required_workflow_files():
        assert (REPO_ROOT / rel).exists(), f"declared workflow_file does not exist: {rel}"


def test_every_required_context_workflow_still_triggers_on_merge_group():
    """THE deadlock tripwire. For every workflow file that backs at least one
    of the currently-required contexts, its `on:` block must still carry a
    `merge_group:` trigger — dropping it there stalls the queue, not just this
    repo's advisory coverage."""
    violations: list[str] = []
    for rel in sorted(_required_workflow_files()):
        on_block = conformance.load_on_block(REPO_ROOT / rel)
        assert on_block is not None, f"{rel}: could not be parsed"
        for v in conformance.check_merge_group_trigger(on_block):
            violations.append(f"{rel}: {v}")
    assert not violations, "required-context workflow(s) missing merge_group:\n" + "\n".join(violations)


def test_resolver_agrees_context_to_file_mapping_is_unambiguous():
    """Belt-and-suspenders on top of check_required_workflow_conformance.py's
    own file-exists check: every required context name must resolve to
    EXACTLY one (workflow, job) pair via required_context_map.py — an
    ambiguous or unresolvable name means the snapshot and the live workflows
    have drifted, which this cure must never mask."""
    data = json.loads(CONTEXTS_PATH.read_text(encoding="utf-8"))
    index = required_context_map.build_context_index(WORKFLOWS_DIR)
    unresolved = []
    for entry in data["contexts"]:
        if not entry.get("workflow_file"):
            continue  # allowlisted (not workflow-produced) — conformance.py's own remit
        name = entry["name"]
        matches = index.get(name, [])
        if len(matches) != 1:
            unresolved.append(f"{name!r} -> {matches}")
    assert not unresolved, "required context name(s) do not resolve to exactly one job:\n" + "\n".join(
        unresolved
    )
