"""Tests for scripts/ci/lint_unreachable_workflow_conditions.py.

Guilt+innocence per cicatrix-superscar.md #3 ("nessuna guardia mergiata
senza un test di innocenza E di colpevolezza") plus a LIMIT class (rule 2 of
the guard's own module docstring: an expression outside the decidable shape
must be visibly UNDECIDED, never silently folded into a clean report) and a
SCAR-PIN against the real `.github/workflows/security.yml` this guard was
built to cure (commit 4e2d8367e / #4218 orphaned its alarm; this same PR
cures it — see security.yml's own comment above the Telegram-alert step).

Run:  python3 -m pytest scripts/tests/test_unreachable_workflow_conditions.py -q
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "lint_unreachable_workflow_conditions.py"
_MODULE_NAME = "lint_unreachable_workflow_conditions"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
# Registered in sys.modules BEFORE exec_module: the target module combines
# `@dataclass(frozen=True)` with `from __future__ import annotations`, and
# dataclass field-type resolution looks up `sys.modules[cls.__module__]` —
# skipping this registration crashes with `AttributeError: 'NoneType' object
# has no attribute '__dict__'` at import time (verified live, 2026-08-20;
# neither sibling loader in this dir needed it because neither target module
# combines those two features).
sys.modules[_MODULE_NAME] = mod
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write_workflow(repo: Path, name: str, content: str) -> Path:
    wf_dir = repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    path = wf_dir / name
    path.write_text(content, encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    return tmp_path


def _run_cli(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--repo-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ============================================================= GUILT cases


def test_guilt_a_exact_security_yml_shape_is_flagged():
    """The exact bug: push:[develop] narrows the branch filter, but the
    if: still names 'refs/heads/main' — a standing contradiction."""
    on_block = {"push": {"branches": ["develop"]}}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "failure() && github.event_name == 'push' && github.ref == 'refs/heads/main'",
        trigger_paths,
    )
    assert satisfiable is False, reason


def test_guilt_b_no_push_trigger_at_all_is_flagged():
    """A workflow with no push: trigger at all, but an if: that requires
    event_name=='push', can never fire."""
    on_block = {"pull_request": {}, "schedule": [{"cron": "0 0 * * *"}]}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "github.event_name == 'push'",
        trigger_paths,
    )
    assert satisfiable is False, reason


def test_guilt_c_mirror_direction_push_main_if_ref_develop_is_flagged():
    """The mirror of (a): push:[main] but the if: names 'refs/heads/develop'.
    A guard that only catches one direction is half a guard."""
    on_block = {"push": {"branches": ["main"]}}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "failure() && github.event_name == 'push' && github.ref == 'refs/heads/develop'",
        trigger_paths,
    )
    assert satisfiable is False, reason


# ========================================================= INNOCENCE cases


def test_innocence_d_cured_security_yml_condition_under_real_on_block():
    """The CURED condition, evaluated against security.yml's real `on:`
    block (push:[develop], pull_request, merge_group, schedule x2,
    workflow_dispatch) — satisfiable via the `schedule` disjunct."""
    on_block = {
        "push": {"branches": ["develop"]},
        "pull_request": {"types": ["opened", "synchronize", "reopened"]},
        "merge_group": None,
        "schedule": [{"cron": "17 19 * * *"}, {"cron": "0 0 * * 0"}],
        "workflow_dispatch": None,
    }
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "failure() && (github.event_name == 'schedule' || "
        "(github.event_name == 'push' && github.ref == 'refs/heads/develop'))",
        trigger_paths,
    )
    assert satisfiable is True, reason


def test_innocence_e_unfiltered_push_is_never_flagged():
    on_block = {"push": None}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "github.event_name == 'push' && github.ref == 'refs/heads/anything-at-all'",
        trigger_paths,
    )
    assert satisfiable is True, reason


def test_innocence_f_steps_and_needs_only_condition_not_even_undecided(tmp_path):
    """An if: that never names github.event_name/github.ref is entirely
    out of this guard's domain — not a finding, not even 'not analyzed'."""
    if_text = "needs.changes.result == 'success' && steps.check.outputs.ok == 'true'"
    assert mod.mentions_relevant_fields(if_text) is False

    workflow = """\
name: fake
on:
  push:
    branches: [develop]
jobs:
  build:
    runs-on: ubuntu-latest
    needs: []
    steps:
      - name: conditional step
        if: needs.changes.result == 'success' && steps.check.outputs.ok == 'true'
        run: echo hi
"""
    path = _write_workflow(tmp_path, "fake.yml", workflow)
    result = mod.analyze_workflow(path, tmp_path)
    assert result.parse_error is None
    assert result.in_scope_count == 0
    assert result.findings == []
    assert result.undecided == []


def test_innocence_g_merge_group_workflow_naming_ref_is_not_flagged():
    """Bias-to-silence per rule 4: merge_group's real ref is the queue's own
    ref, never a static branch — but this module treats it as UNKNOWN
    (satisfiable), never asserts unreachable."""
    on_block = {"merge_group": None}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "github.event_name == 'merge_group' && github.ref == 'refs/heads/main'",
        trigger_paths,
    )
    assert satisfiable is True, reason


# ================================================================ LIMIT case


def test_limit_h_unsupported_shape_is_not_analyzed_and_does_not_exit_nonzero(tmp_path):
    """An if: outside the decidable shape (here: a function call WITH
    arguments, `contains(...)`) must land in the 'not analyzed' bucket and
    must NOT, on its own, make the CLI exit non-zero."""
    workflow = """\
name: fake-limit
on:
  push:
    branches: [develop]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: weird step
        if: contains(github.ref, 'release-')
        run: echo hi
"""
    _write_workflow(tmp_path, "fake-limit.yml", workflow)
    _git_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    proc = _run_cli(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NOT ANALYZED" in proc.stdout
    assert "contains" in proc.stdout


def test_limit_h_unit_level_undecided_reason():
    on_block = {"push": {"branches": ["develop"]}}
    trigger_paths = mod.extract_trigger_paths(on_block)
    satisfiable, reason, ast = mod.analyze_condition(
        "contains(github.ref, 'release-')",
        trigger_paths,
    )
    assert satisfiable is None
    assert reason  # a non-empty explanation, not a silent None


# ============================================================== SCAR-PIN


def test_scar_pin_real_security_yml_reports_zero_findings():
    """Part A actually cured it: the guard, run against the REAL
    security.yml in this branch, must report zero findings for it."""
    path = REPO_ROOT / ".github" / "workflows" / "security.yml"
    assert path.exists(), "security.yml must exist in this worktree"
    result = mod.analyze_workflow(path, REPO_ROOT)
    assert result.parse_error is None
    assert result.findings == [], [
        (f.condition.file, f.condition.scope, f.condition.text) for f in result.findings
    ]
    # And the guard actually looked at the alert condition (not a false
    # "clean" from mentions_relevant_fields skipping it entirely).
    assert result.in_scope_count >= 1


_CURED_IF = (
    "failure() && (github.event_name == 'schedule' || "
    "(github.event_name == 'push' && github.ref == 'refs/heads/develop'))"
)
_PRECURE_IF = "failure() && github.event_name == 'push' && github.ref == 'refs/heads/main'"


def test_scar_pin_precure_text_of_the_real_step_is_flagged(tmp_path):
    """Reconstruct the PRE-cure text of the real step in a tmp copy (never
    reverting the tracked file) and confirm the guard would have caught it."""
    real_text = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    assert _CURED_IF in real_text, "the cured if: text moved — update _CURED_IF to match"
    precure_text = real_text.replace(_CURED_IF, _PRECURE_IF)
    assert precure_text != real_text

    path = _write_workflow(tmp_path, "security.yml", precure_text)
    result = mod.analyze_workflow(path, tmp_path)
    assert result.parse_error is None
    assert len(result.findings) == 1, result.findings
    assert "Telegram alert" in result.findings[0].condition.scope
