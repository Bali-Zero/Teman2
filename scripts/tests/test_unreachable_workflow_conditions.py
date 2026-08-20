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
import re
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


# --- The alarm must NAME the ref it fired on, never assert one -----------------
#
# Second half of the same defect, and the half a satisfiability checker cannot
# see: widening the condition to `schedule || push-on-develop` made the step
# REACHABLE, but its title and body still read "... on main", so on a develop
# push the alarm would have reported the wrong branch and sent whoever read it
# at 07:30 to look at a branch that was fine (W114/W106 — a message that
# inventories mutable state will lie). The condition and the message were
# written the same day from the same belief; these assertions stop them from
# being able to disagree again.

_ALARM_NAME_MARKER = "Telegram alert — production image failed to BUILD"
_ALARM_BODY_MARKER = "image failed to BUILD"
_BRANCH_LITERAL_RE = re.compile(r"\b(main|develop|master)\b")


def _alarm_human_text(workflow_text: str) -> list[str]:
    """The alarm's HUMAN-FACING strings: its `name:` line and the body line the
    owner actually reads. Deliberately NOT the `if:` — that one has to name
    branches, it is the condition. Fails loud rather than returning an empty
    list, so a renamed step can never read as 'no branch literals found'."""
    lines = [
        line
        for line in workflow_text.splitlines()
        if (_ALARM_NAME_MARKER in line and line.lstrip().startswith("- name:"))
        or (_ALARM_BODY_MARKER in line and "<b>" in line)
    ]
    assert len(lines) == 2, (
        "expected exactly the alarm's name line and its body line; got "
        f"{len(lines)}: {lines!r} — the step was renamed or its body reworded, "
        "so this scar-pin is no longer looking at the alarm it was written for"
    )
    return lines


def test_scar_pin_alarm_names_the_ref_instead_of_hardcoding_a_branch():
    """INNOCENCE: today's alarm carries no branch literal in the text a human
    reads, and does interpolate the real ref."""
    text = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    human = _alarm_human_text(text)
    for line in human:
        assert not _BRANCH_LITERAL_RE.search(line), (
            f"the alarm asserts a branch instead of naming one: {line.strip()!r} — "
            "it can fire on a develop push AND on the scheduled run, so a "
            "hardcoded branch name is wrong on at least one of them"
        )
    assert any("${REF}" in line for line in human), (
        "the alarm body must interpolate the ref it fired on"
    )
    assert "REF: ${{ github.ref_name }}" in text, (
        "REF must come from github.ref_name in the step's env: block"
    )


def test_guilt_rehardcoding_the_branch_in_the_alarm_is_caught():
    """GUILT: the next person who writes 'on main' back into the alarm gets a
    red, not a lying alert. Mutates a copy in memory — the tracked file is
    never touched."""
    text = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    regressed = text.replace("failed to BUILD on ${REF}", "failed to BUILD on main")
    assert regressed != text, "the body line moved — update this mutation to match"
    human = _alarm_human_text(regressed)
    assert any(_BRANCH_LITERAL_RE.search(line) for line in human), (
        "the regression must be visible in the alarm's human-facing text"
    )


# ================================================== cross-family refuter (Kimi K3) fixes
#
# Four false-accusation paths a cross-family refuter found in this guard
# itself, reproduced independently before being fixed (a refuter can
# hallucinate too — cicatrix-superscar #6). Each test below asserts the
# FALSE ACCUSATION does not happen: the guard is about to become a required
# check, so wrongly reporting a reachable if: as unreachable hard-blocks an
# innocent PR — the severe class this whole file exists to prevent.


def test_guilt_case_insensitive_event_name_and_ref_are_not_flagged(tmp_path):
    """GitHub's `==`/`!=` operators ignore case for the whole compared
    string (docs.github.com/en/actions/reference/workflows-and-actions/
    expressions: "GitHub ignores case when comparing strings", verified
    2026-08-20) — 'Push' == the real 'push' event, and 'REFS/HEADS/MAIN' ==
    the real 'refs/heads/main'. Pre-fix this input was flagged with 2
    findings and exit 1 while both conditions are true on a real run."""
    workflow = """\
on:
  push:
    branches: [main]
jobs:
  a:
    runs-on: ubuntu-latest
    if: github.event_name == 'Push'
    steps:
      - run: echo hi
        if: github.ref == 'REFS/HEADS/MAIN'
"""
    _write_workflow(tmp_path, "fake-case.yml", workflow)
    _git_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    proc = _run_cli(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "UNREACHABLE" not in proc.stdout, proc.stdout
    assert "0 finding(s)" in proc.stdout, proc.stdout


def test_guilt_github_glob_plus_metachar_is_not_flagged(tmp_path):
    """GitHub's filter-pattern glob defines `+` as "one or more of the
    preceding character" — `branches: ['ma+n']` matches a real push to
    branch 'maaan'. `fnmatch` treats `+` as an ordinary literal character
    (verified: `fnmatch.fnmatch('maaan', 'ma+n')` is False) — pre-fix this
    mismatch made the guard treat 'maaan' as never matching the `on:`
    filter and flag the if: as unreachable, when GitHub would actually run
    it."""
    workflow = """\
on:
  push:
    branches: ['ma+n']
jobs:
  a:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/maaan'
    steps:
      - run: echo hi
"""
    _write_workflow(tmp_path, "fake-glob.yml", workflow)
    _git_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    proc = _run_cli(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "UNREACHABLE" not in proc.stdout, proc.stdout


def test_guilt_backslash_metachar_is_not_flagged():
    """Same class as the `+` case, for GitHub's other glob-only
    metacharacter (`\\`, escape-the-next-character) — unit-level via
    `extract_trigger_paths`, confirming the push trigger's ref is left
    unconstrained (never mismodeled as a literal-backslash fnmatch)."""
    on_block = {"push": {"branches": [r"release\*"]}}
    trigger_paths = mod.extract_trigger_paths(on_block)
    assert len(trigger_paths) == 1
    assert trigger_paths[0].ref_matcher is mod._any_ref, (
        "a branches: pattern containing '\\\\' must fall back to an "
        "unconstrained ref, never be matched via fnmatch"
    )


def test_guilt_job_if_after_steps_does_not_swap_line_numbers(tmp_path):
    """A job-level `if:` written textually AFTER `steps:` (legal YAML — key
    order inside a mapping is free) used to get the STEP's line number, and
    the step's `if:` got the JOB's — a required check that sends the
    reviewer to the wrong `if:` while its own docstring promised it never
    could. Distinct if:-texts here so the assertion cannot pass by
    coincidence (an ambiguous same-text case is covered separately)."""
    workflow = """\
on:
  push:
    branches: [develop]
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
        if: github.event_name == 'push' && github.ref == 'refs/heads/STEPBRANCH'
    if: github.event_name == 'push' && github.ref == 'refs/heads/JOBBRANCH'
"""
    path = _write_workflow(tmp_path, "fake-lineno.yml", workflow)
    result = mod.analyze_workflow(path, tmp_path)
    assert result.parse_error is None
    assert len(result.findings) == 2, result.findings

    by_scope = {f.condition.scope: f.condition for f in result.findings}
    job_cond = by_scope["job:a"]
    step_cond = next(c for scope, c in by_scope.items() if scope != "job:a")

    assert "JOBBRANCH" in job_cond.text
    assert "STEPBRANCH" in step_cond.text
    # Line 10 is the job-level if:, line 9 is the step's — verified against
    # the raw text above (1-indexed, counting from `on:`).
    assert job_cond.line == 10, (job_cond.line, workflow.splitlines())
    assert step_cond.line == 9, (step_cond.line, workflow.splitlines())


def test_guilt_ambiguous_duplicate_if_text_gets_no_line_never_a_wrong_one(tmp_path):
    """When job-if and step-if carry the IDENTICAL text (so which raw line
    belongs to which cannot be recovered from text alone), the guard must
    leave BOTH without a line number rather than guess — the contract is
    'never a wrong line, only an absent one'."""
    workflow = """\
on:
  push:
    branches: [develop]
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
"""
    path = _write_workflow(tmp_path, "fake-ambiguous.yml", workflow)
    result = mod.analyze_workflow(path, tmp_path)
    assert result.parse_error is None
    assert len(result.findings) == 2, result.findings
    assert all(f.condition.line is None for f in result.findings), [
        (f.condition.scope, f.condition.line) for f in result.findings
    ]


def test_guilt_assumed_satisfiable_ref_is_not_folded_into_clean_report(tmp_path):
    """A `schedule`-only if: naming a specific `ref` is 'satisfiable' only
    because this guard cannot disprove an unconstrained/unknown ref
    (declared limit #2) — that verdict must land in its own
    'SATISFIABLE ONLY UNDER AN ASSUMED/UNKNOWN REF' bucket, never silently
    under the green 'every in-scope if: is satisfiable' line, and must
    never be a finding (exit 0)."""
    workflow = """\
on:
  schedule:
    - cron: "0 0 * * *"
jobs:
  a:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    steps:
      - run: echo hi
"""
    path = _write_workflow(tmp_path, "fake-assumed.yml", workflow)
    result = mod.analyze_workflow(path, tmp_path)
    assert result.parse_error is None
    assert result.findings == []
    assert len(result.assumed_satisfiable) == 1, result.assumed_satisfiable

    _git_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    proc = _run_cli(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SATISFIABLE ONLY UNDER AN ASSUMED/UNKNOWN REF" in proc.stdout, proc.stdout
    assert "every in-scope if: is satisfiable" not in proc.stdout, proc.stdout


def test_innocence_mixed_definite_and_assumed_witness_stays_in_clean_report(tmp_path):
    """A condition satisfiable via BOTH a real (push-branch) trigger path
    AND an unconstrained (schedule) one must NOT land in the
    assumed-satisfiable bucket — it is genuinely, definitely satisfiable
    already, without needing to assume anything."""
    on_block = {
        "push": {"branches": ["main"]},
        "schedule": [{"cron": "0 0 * * *"}],
    }
    trigger_paths = mod.extract_trigger_paths(on_block)
    _, _, ast = mod.analyze_condition(
        "github.event_name == 'schedule' || "
        "(github.event_name == 'push' && github.ref == 'refs/heads/main')",
        trigger_paths,
    )
    assert ast is not None
    assert any(mod._evaluate_certain(ast, tp) for tp in trigger_paths), (
        "a real push-branch witness must be provable without assuming an unknown ref"
    )
