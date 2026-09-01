"""Tests for scripts/ci/check_required_workflow_conformance.py.

Guilt+innocence per cicatrix-superscar.md #3 ("nessuna guardia mergiata
senza un test di innocenza E di colpevolezza") for every `check_*` function
the module exports, PLUS a guilt+innocence pair on the real repo tree —
this is the guard's own guilt proof cited in the Merge-OS v2 Wave 0 PR body
(research/operations/2026-08-10-merge-os-v2-submission-system.md §4 Wave 0):
docs-sync.yml / migration-lint.yml FAILED this guard before their cure in
this same PR, and PASS it after.

EXTENDED 2026-08-29 (L06-PR1 trigger-symmetry, this repo's own re-derivation
of the same trap): rules 3 (pull_request trigger present at all) and 4's
`paths-ignore` half were added here rather than in a new, parallel script —
the module's own docstring already documented this exact invariant (rule 2
merge_group + rule 4-then-3 pull_request/paths) against this exact
`infra/required.d/contexts.json` input; a second script asserting the same
thing against the same file would be superscar #-family hypertrophy, not a
new antidote. See that module's SCAR NOTE for why the broader "identical
path filters on both triggers" ask is unimplementable (actionlint rejects
`paths:` under `merge_group`).

EXTENDED AGAIN 2026-08-29 (same day, second cross-family refuter round on
this exact guard): two blind non-Anthropic refuters independently found the
first cut of the trigger-symmetry rules still under-matched. Added here:
rule 4's `paths-ignore` half (the first cut matched only the literal token
`paths`) and a new rule 5 (`types:` narrowing that drops `opened` or `synchronize`
off a required workflow's `on.pull_request`). The same round also found and
removed the `ALLOWLIST` escape-hatch dict this file used to test: it was
empty, unreachable, and — per its own comment — silenced BOTH rule 2 and
rule 3/4/5 violations for any context sharing its `workflow_file`, wider
than its stated justification and dead code the moment it shipped.

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


# ------------------------------------------------------- check_pull_request_trigger_present


def test_guilt_missing_pull_request_trigger_flagged():
    # merge_group-only: a queue entry could satisfy this context while a
    # direct PR view of it hangs "Expected -- waiting" forever (W69).
    on_block = {"merge_group": None, "push": {"branches": ["main"]}}
    violations = mod.check_pull_request_trigger_present(on_block)
    assert violations
    assert "pull_request" in violations[0]


def test_innocence_bare_pull_request_passes():
    # {"pull_request": None} is the ordinary `pull_request:` bare-key shape
    # every real required workflow uses -- key PRESENT, value null. Must
    # NOT be confused with the key being absent entirely (the guilt case
    # above).
    on_block = {"pull_request": None, "merge_group": None}
    assert mod.check_pull_request_trigger_present(on_block) == []


def test_innocence_pull_request_with_types_passes():
    on_block = {"pull_request": {"types": ["opened", "synchronize", "reopened"]}, "merge_group": None}
    assert mod.check_pull_request_trigger_present(on_block) == []


# --------------------------------------------------------- check_no_pull_request_trigger_filters


def test_guilt_toplevel_pr_paths_filter_flagged():
    # The exact shape docs-sync.yml/migration-lint.yml shipped before this PR.
    on_block = {"pull_request": {"paths": ["scripts/docs_sync.py"]}, "merge_group": None}
    violations = mod.check_no_pull_request_trigger_filters(on_block)
    assert violations
    assert "paths" in violations[0]


def test_guilt_toplevel_pr_paths_ignore_filter_flagged():
    # Added 2026-08-29 (L06-PR1): the earlier check only matched the literal
    # token `paths`, so `paths-ignore` sailed through the exact same trap.
    on_block = {"pull_request": {"paths-ignore": ["docs/**"]}, "merge_group": None}
    violations = mod.check_no_pull_request_trigger_filters(on_block)
    assert violations
    assert "paths-ignore" in violations[0]






def test_guilt_both_paths_and_paths_ignore_flagged_once_each():
    on_block = {
        "pull_request": {"paths": ["a/**"], "paths-ignore": ["b/**"]},
        "merge_group": None,
    }
    violations = mod.check_no_pull_request_trigger_filters(on_block)
    assert len(violations) == 2
    joined = " ".join(violations)
    assert "paths-ignore" in joined and "`paths:`" in joined


def test_innocence_pull_request_branches_filter_is_out_of_scope():
    """DECLARED SCOPE LIMIT, deliberate (see the checker's docstring): a
    `branches:`/`branches-ignore:` filter under `on.pull_request` is NOT
    judged here. A first cut of this rule did flag them by key-presence and
    a second refuter round proved that an over-match: `branches: [main]`
    fires on every PR to the protected branch and is perfectly innocent,
    yet was flagged identically to the genuinely-broken `branches:
    [develop]`. Deciding it needs the DIRECTIONAL test against the
    protected branch this fixture pins as still-unbuilt."""
    innocent = {"pull_request": {"branches": ["main"]}, "merge_group": None}
    guilty_shape = {"pull_request": {"branches": ["develop"]}, "merge_group": None}
    assert mod.check_no_pull_request_trigger_filters(innocent) == []
    # and the genuinely-broken shape is ALSO unjudged today — that is the
    # declared gap, recorded so a future session sees it is known, not missed.
    assert mod.check_no_pull_request_trigger_filters(guilty_shape) == []


def test_innocence_pull_request_without_paths_passes():
    on_block = {"pull_request": None, "merge_group": None}
    assert mod.check_no_pull_request_trigger_filters(on_block) == []


def test_innocence_push_paths_filter_is_out_of_scope():
    # Declared scope limit (docstring): on.push.paths is a different,
    # legitimate optimization, never the Codex F12 trap. RE-MEASURED
    # 2026-08-29: 2 of 8 real required-context workflows in this repo
    # carry exactly this shape (guard-conformance.yml, organ-
    # conformance.yml) -- the 2026-08-11 authoring docstring's "12" was
    # never reproducible and is corrected in the module docstring too.
    on_block = {
        "pull_request": {},
        "merge_group": None,
        "push": {"branches": ["main"], "paths": ["scripts/**"]},
    }
    assert mod.check_no_pull_request_trigger_filters(on_block) == []


# ------------------------------ check_pull_request_types_include_opened_and_synchronize


def test_guilt_types_missing_synchronize_flagged():
    on_block = {"pull_request": {"types": ["opened"]}, "merge_group": None}
    violations = mod.check_pull_request_types_include_opened_and_synchronize(on_block)
    assert violations
    assert "synchronize" in violations[0]


def test_guilt_types_missing_opened_flagged():
    on_block = {"pull_request": {"types": ["synchronize"]}, "merge_group": None}
    violations = mod.check_pull_request_types_include_opened_and_synchronize(on_block)
    assert violations
    assert "opened" in violations[0]


def test_guilt_types_missing_both_flagged():
    on_block = {"pull_request": {"types": ["labeled"]}, "merge_group": None}
    violations = mod.check_pull_request_types_include_opened_and_synchronize(on_block)
    assert violations
    assert "opened" in violations[0] and "synchronize" in violations[0]


def test_innocence_types_with_opened_and_synchronize_passes():
    on_block = {"pull_request": {"types": ["opened", "synchronize"]}, "merge_group": None}
    assert mod.check_pull_request_types_include_opened_and_synchronize(on_block) == []


def test_innocence_types_with_all_three_passes():
    # Every live `types:` declaration in this repo uses exactly this shape
    # (tests.yml, security.yml, harness-floor.yml, verified 2026-08-29) --
    # deliberately NOT requiring `reopened` (superscar #3: over-match).
    on_block = {
        "pull_request": {"types": ["opened", "synchronize", "reopened"]},
        "merge_group": None,
    }
    assert mod.check_pull_request_types_include_opened_and_synchronize(on_block) == []


def test_innocence_bare_pull_request_no_types_key_passes():
    on_block = {"pull_request": None, "merge_group": None}
    assert mod.check_pull_request_types_include_opened_and_synchronize(on_block) == []


def test_innocence_pull_request_dict_without_types_key_passes():
    on_block = {"pull_request": {}, "merge_group": None}
    assert mod.check_pull_request_types_include_opened_and_synchronize(on_block) == []


def test_innocence_malformed_types_not_a_list_out_of_scope():
    # types: present but not a list is a different, actionlint-shaped
    # malformed-workflow failure -- out of scope for this rule by design.
    on_block = {"pull_request": {"types": "opened"}, "merge_group": None}
    assert mod.check_pull_request_types_include_opened_and_synchronize(on_block) == []


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


def test_guilt_evaluate_flags_merge_group_only_workflow(tmp_path):
    """A required workflow that declares merge_group but never pull_request
    at all -- rule 3, added 2026-08-29. Not the docs-sync historical shape
    (which had pull_request+paths, no merge_group); this is the mirror
    trigger missing entirely."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "queue-only.yml").write_text(
        "on:\n  merge_group:\n  push:\n    branches: [main]\njobs:\n"
        "  check:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "queue-only-check", "workflow_file": ".github/workflows/queue-only.yml"}],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert len(violations) == 1
    assert "pull_request" in violations[0]


def test_guilt_evaluate_flags_paths_ignore_end_to_end(tmp_path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "half-cured.yml").write_text(
        "on:\n  pull_request:\n    paths-ignore:\n      - docs/**\n  merge_group:\n"
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "half-cured-check", "workflow_file": ".github/workflows/half-cured.yml"}],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert len(violations) == 1
    assert "paths-ignore" in violations[0]




def test_guilt_evaluate_flags_types_missing_synchronize_end_to_end(tmp_path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "opened-only.yml").write_text(
        "on:\n  pull_request:\n    types: [opened]\n  merge_group:\n"
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "opened-only-check", "workflow_file": ".github/workflows/opened-only.yml"}],
    )
    violations, checked = mod.evaluate(contexts_path, tmp_path)
    assert checked == 1
    assert len(violations) == 1
    assert "synchronize" in violations[0]


def test_innocence_non_required_sibling_workflow_never_flagged(tmp_path):
    """Anti-over-match (superscar #3): a workflow file that exists on disk
    with a real Codex-F12-shaped defect (paths filter, no merge_group) but
    is NOT named by any contexts.json entry must never surface a violation
    -- evaluate() only walks the declared required set, it never scans the
    workflows directory. Proves the real 43-workflow class (path-filtered,
    non-required, correct by design) can never be swept in by accident."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "required.yml").write_text(
        "on:\n  pull_request:\n  merge_group:\njobs:\n  check:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    (wf_dir / "advisory-only.yml").write_text(
        "on:\n  pull_request:\n    paths:\n      - apps/mouth/**\n"
        "jobs:\n  lint:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    contexts_path = _write_contexts(
        tmp_path,
        [{"name": "required-check", "workflow_file": ".github/workflows/required.yml"}],
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


# --------------------------------------------------------------------- module docstring


def test_module_docstring_records_the_actionlint_refusal_fact():
    """Anti-regression (W102 shape): the module's own docstring must keep
    the verbatim actionlint refusal message and an explicit "do not fix
    this back" instruction, so a future session does not re-derive and
    re-attempt the unimplementable "identical paths on both triggers"
    version of this guard."""
    doc = mod.__doc__ or ""
    assert '"paths" filter is not available for merge_group event' in doc
    assert "do NOT" in doc and "fix" in doc


def test_module_has_no_allowlist_escape_hatch():
    """Anti-regression for the second refuter round (2026-08-29): the
    ALLOWLIST dict this module used to carry was empty, pinned empty, and
    keyed on bare workflow_file -- one entry silenced EVERY rule for EVERY
    context sharing that file, wider than its own stated "rule 3/4 escape
    hatch" justification (it also swallowed rule 2's merge_group check).
    Dead code the moment it shipped; removed rather than fixed. Does NOT
    assert anything about check_allowlist_entry_has_reason, which is a
    different, pre-existing mechanism (governs contexts whose
    workflow_file is null) and stays untouched."""
    assert not hasattr(mod, "ALLOWLIST")
