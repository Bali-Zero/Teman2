"""Tests for scripts/ci/check_required_workflow_conformance.py.

Guilt+innocence per cicatrix-superscar.md #3 ("nessuna guardia mergiata
senza un test di innocenza E di colpevolezza") for every `check_*` function
the module exports, PLUS a guilt+innocence pair on the real repo tree —
this is the guard's own guilt proof cited in the Merge-OS v2 Wave 0 PR body
(research/operations/2026-08-10-merge-os-v2-submission-system.md §4 Wave 0):
docs-sync.yml / migration-lint.yml FAILED this guard before their cure in
this same PR, and PASS it after.

Run:  python3 -m pytest scripts/tests/test_check_required_workflow_conformance.py -q
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "check_required_workflow_conformance.py"
_spec = importlib.util.spec_from_file_location("check_required_workflow_conformance", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


# --------------------------------------------------------------- check_merge_group_trigger


def test_guilt_missing_merge_group_flagged():
    on_block = {"pull_request": {}, "push": {"branches": ["main"]}}
    violations = mod.check_merge_group_trigger(on_block)
    assert violations
    assert "merge_group" in violations[0]


def test_innocence_merge_group_present_passes():
    on_block = {"pull_request": {}, "merge_group": None}
    assert mod.check_merge_group_trigger(on_block) == []


# --------------------------------------------------------- check_no_pull_request_paths_filter


def test_guilt_toplevel_pr_paths_filter_flagged():
    # The exact shape docs-sync.yml/migration-lint.yml shipped before this PR.
    on_block = {"pull_request": {"paths": ["scripts/docs_sync.py"]}, "merge_group": None}
    violations = mod.check_no_pull_request_paths_filter(on_block)
    assert violations
    assert "paths" in violations[0]


def test_innocence_pull_request_without_paths_passes():
    on_block = {"pull_request": None, "merge_group": None}
    assert mod.check_no_pull_request_paths_filter(on_block) == []


def test_innocence_push_paths_filter_is_out_of_scope():
    # Declared scope limit (docstring): on.push.paths is a different,
    # legitimate optimization, never the Codex F12 trap. 12 real required
    # workflows in this repo carry exactly this shape.
    on_block = {
        "pull_request": {},
        "merge_group": None,
        "push": {"branches": ["main"], "paths": ["scripts/**"]},
    }
    assert mod.check_no_pull_request_paths_filter(on_block) == []


# ----------------------------------------------------- check_context_workflow_file_exists


def test_guilt_missing_workflow_file_flagged(tmp_path):
    entry = {"workflow_file": ".github/workflows/does-not-exist.yml"}
    violations = mod.check_context_workflow_file_exists(entry, tmp_path)
    assert violations
    assert "does not exist" in violations[0]


def test_innocence_real_workflow_file_passes():
    entry = {"workflow_file": ".github/workflows/root-guard.yml"}
    assert mod.check_context_workflow_file_exists(entry, REPO_ROOT) == []


# -------------------------------------------------------- check_allowlist_entry_has_reason


def test_guilt_empty_allowlist_reason_flagged():
    entry = {"name": "Some External Check", "workflow_file": None, "allowlist_reason": ""}
    violations = mod.check_allowlist_entry_has_reason(entry)
    assert violations
    assert "Some External Check" in violations[0]


def test_guilt_missing_allowlist_reason_flagged():
    entry = {"name": "Some External Check", "workflow_file": None}
    assert mod.check_allowlist_entry_has_reason(entry)


def test_innocence_real_allowlist_reason_passes():
    entry = {
        "name": "Vercel",
        "workflow_file": None,
        "allowlist_reason": "External Vercel deployment check, not produced by any "
        "workflow file in this repo — verified 2026-08-11.",
    }
    assert mod.check_allowlist_entry_has_reason(entry) == []


# --------------------------------------------------------------------------- evaluate()


def _write_contexts(tmp_path: Path, contexts: list[dict]) -> Path:
    path = tmp_path / "contexts.json"
    path.write_text(json.dumps({"contexts": contexts}), encoding="utf-8")
    return path


def test_guilt_evaluate_flags_the_pre_cure_docs_sync_shape(tmp_path):
    """Reconstructs the EXACT on: shape docs-sync.yml carried before this PR
    (top-level pull_request.paths, no merge_group) and proves evaluate()
    catches it — the guard's own guilt proof against a real historical
    defect, not just a synthetic fixture."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "docs-sync.yml").write_text(
        "on:\n"
        "  pull_request:\n"
        "    paths:\n"
        "      - scripts/docs_sync.py\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  check-docs-sync:\n"
        "    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "check-docs-sync", "workflow_file": ".github/workflows/docs-sync.yml"}],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert len(violations) == 2  # missing merge_group AND top-level paths
    joined = " ".join(violations)
    assert "merge_group" in joined
    assert "paths" in joined


def test_innocence_evaluate_passes_the_cured_shape(tmp_path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "docs-sync.yml").write_text(
        "on:\n"
        "  pull_request:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  merge_group:\n"
        "jobs:\n"
        "  check-docs-sync:\n"
        "    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "check-docs-sync", "workflow_file": ".github/workflows/docs-sync.yml"}],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert violations == []


def test_innocence_allowlisted_context_with_reason_passes(tmp_path):
    contexts_path = _write_contexts(
        tmp_path,
        [
            {
                "name": "Vercel",
                "workflow_file": None,
                "allowlist_reason": "External check, verified 2026-08-11.",
            }
        ],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert violations == []


def test_guilt_blind_on_missing_contexts_file(tmp_path):
    violations, checked = mod.evaluate(tmp_path / "does-not-exist.json", tmp_path)
    assert checked == 0
    assert violations and "BLIND" in violations[0]


def test_guilt_blind_on_zero_contexts(tmp_path):
    contexts_path = _write_contexts(tmp_path, [])
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 0
    assert violations and "BLIND" in violations[0]


# ------------------------------------------------------------- live repo tree (guilt proof)


def test_the_real_repo_tree_is_conformant_today():
    """The actual proof this PR ships: run the guard against the REAL
    infra/required.d/contexts.json + the REAL .github/workflows/ tree. Fails
    if a future required context regresses into the Codex F12 trap without
    anyone noticing (this test is what makes the guard armed, not just
    present — W81 "esiste != armato")."""
    violations, checked = mod.evaluate(mod.DEFAULT_CONTEXTS, REPO_ROOT)
    assert checked > 0, "contexts.json must declare at least one required context"
    assert violations == [], f"live repo tree has conformance violations: {violations}"


def test_main_cli_exits_zero_on_the_real_repo_tree(capsys):
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0, captured.out
