"""PR3a (2026-09-18) — tests for lint_workflow_script.py.

Verifies the linter correctly:
- Flags an agent( call with no literal model: (RULE 1)
- Flags an agent( call whose label: contains "gate" (RULE 2)
- Flags a phase("Run") while/for loop with no numeric cap or *Cap-style constant (RULE 3)
- Stays quiet on a fixture that satisfies all three rules (innocence)
- Stays quiet on the two documented exemptions (provenance-wrapper indirection,
  bounded for-of/for-in) — regression guard for the false positives found 2026-09-18
  against kbli-batch-a-lot.js and second-army.js
- Is green against the LIVE infra/workflows/*.js tree (this repo's own convention,
  see test_lint_asyncpg_except_completeness.py's test_main_exit_0_on_clean)
- Refuses to report clean on a blind (zero-file) sweep, and does not over-match that
  guard onto an explicit non-.js argv or a single clean in-scope file
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_workflow_script.py"
REPO_ROOT = SCRIPT_PATH.parents[1]
FIXTURES_DIR = (
    Path(__file__).resolve().parent
    / "fixtures" / "lint_workflow_script" / "repo" / "infra" / "workflows"
)


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("lint_workflow_script_mod", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


def test_no_model_is_violation(lint):
    violations = lint.find_violations(FIXTURES_DIR / "no_model.js")
    assert len(violations) == 1
    assert "model:" in violations[0][1]


def test_gate_label_is_violation(lint):
    violations = lint.find_violations(FIXTURES_DIR / "gate_label.js")
    assert len(violations) == 1
    assert "gate" in violations[0][1]


def test_uncapped_loop_is_violation(lint):
    violations = lint.find_violations(FIXTURES_DIR / "uncapped_loop.js")
    assert len(violations) == 1
    assert "cap" in violations[0][1]


def test_clean_fixture_is_clean(lint):
    assert lint.find_violations(FIXTURES_DIR / "clean.js") == []


def test_exemptions_fixture_is_clean(lint):
    """Regression guard for both false positives found against the live repo
    (2026-09-18): a provenance-wrapper indirection and a bounded for-of loop."""
    assert lint.find_violations(FIXTURES_DIR / "exemptions.js") == []


def test_main_exit_0_on_clean(capsys):
    """Run on the live codebase's infra/workflows/*.js — must be green."""
    mod = _load_lint_module()
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0, f"linter should be green on the live repo; output:\n{captured.out}"
    assert "no violations" in captured.out


# --------------------------------------------------------------------------
# BLIND-SCAN GUARD (cicatrix #2/#4 — "0 files traversed != clean").
# --------------------------------------------------------------------------


def test_guilt_blind_sweep_refuses_to_report_clean(lint, monkeypatch, capsys):
    monkeypatch.setattr(
        lint, "DEFAULT_GLOB_DIR", "scripts/tests/fixtures/__no_such_dir_for_blind_scan__"
    )
    rc = lint.main([])
    captured = capsys.readouterr()
    assert rc == 2, "a blind sweep must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert "no violations" not in captured.out


def test_innocence_explicit_non_js_file_is_still_green(lint, tmp_path, capsys):
    """A pre-commit passing only a non-.js file is legitimate — the guard must not bite."""
    not_js = tmp_path / "notes.md"
    not_js.write_text("nothing to see here\n", encoding="utf-8")
    rc = lint.main([str(not_js)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no violations" in captured.out
    assert "BLIND SCAN" not in captured.err


def test_innocence_one_clean_in_scope_file_is_enough(lint, capsys):
    """The guard fires at EXACTLY zero — a single swept file must satisfy it."""
    rc = lint.main([str(FIXTURES_DIR / "clean.js")])
    captured = capsys.readouterr()
    assert rc == 0
    assert "BLIND SCAN" not in captured.err


# --------------------------------------------------------------------------
# DEFECT 1 (PR3a', 2026-09-18) — relative_to(repo_root) must not traceback on an
# out-of-root explicit target (gate reproduction: a /tmp copy of a live .js file).
# --------------------------------------------------------------------------


def test_guilt_out_of_root_violation_prints_absolute_path_no_traceback(lint, tmp_path, capsys):
    guilty = tmp_path / "guilty.js"
    guilty.write_text(
        (FIXTURES_DIR / "no_model.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    rc = lint.main([str(guilty)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "model:" in captured.out
    assert str(guilty) in captured.out
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_innocence_in_root_violation_still_prints_relative_path(lint, capsys):
    rc = lint.main([str(FIXTURES_DIR / "no_model.js")])
    captured = capsys.readouterr()
    assert rc == 1
    assert str(REPO_ROOT) not in captured.out
