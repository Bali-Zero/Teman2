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
- Recognises a regex literal as a regex literal (PR3e item 1, 2026-09-18) instead of
  misreading it as a string/comment opener, and refuses (exit 2) rather than report
  CLEAN if neutralization ever leaves the paren/brace balance non-zero
- Reports a QUOTED `"model"` key as unpinned BY DESIGN (PR3e item 2, 2026-09-18) — a
  documented fail-safe false accusation, not a missed real one
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


def test_documented_bypass_fixture_is_lexically_invisible(lint):
    """CONDITION 3 (PR3a', dw-gate-6, 2026-09-18): the wrapper exemption is bypassable —
    callSeat(prompt, {no model}) stays green here BY DESIGN, because the static lint
    cannot read opts.model through the callSeat indirection either way (legitimate or
    not). This is the hole named in the RULE 1 docstring, not a silent gap: the
    compensating control is infra/workflows/run-second-army.mjs:121's assertModelPinned,
    a RUNTIME guard this static lint does not (and structurally cannot) replace."""
    assert lint.find_violations(FIXTURES_DIR / "documented_bypass.js") == []


def test_single_argument_agent_object_literal_is_checked(lint):
    """OBSERVATION 4 (PR3a', 2026-09-18): agent({...}) with ONE argument must be scanned
    like any other call's last argument — only the guilty (no model:) function fires."""
    violations = lint.find_violations(FIXTURES_DIR / "single_arg_object_literal.js")
    assert len(violations) == 1
    assert "model:" in violations[0][1]


def test_cap_name_only_in_comment_is_violation(lint):
    """DEFECT :253 (PR3d, 2026-09-18): a cap name mentioned only in a comment must not
    silence RULE 3 — the loop below it is genuinely uncapped."""
    violations = lint.find_violations(FIXTURES_DIR / "cap_name_only_in_comment.js")
    assert len(violations) == 1
    assert "cap" in violations[0][1]


def test_cap_name_in_code_stays_clean(lint):
    """Twin of the guilt fixture above: a REAL maxRounds constant must still satisfy
    RULE 3 once the search moves to the neutralized span."""
    assert lint.find_violations(FIXTURES_DIR / "cap_name_in_code.js") == []


def test_loop_before_first_phase_is_violation(lint):
    """DEFECT :245 (PR3d, 2026-09-18): a loop above the file's first phase( call must
    still be scanned — only the pre-phase, genuinely-uncapped loop fires. Wording per
    item 3 (PR3e, 2026-09-18, gate-10 obs 7): this file DOES have a phase( call later
    on, just not before this loop — that must read "before first phase(", not the
    "no phase(" wording reserved for a file with no phase( call anywhere (see
    test_no_phase_uncapped_loop_is_violation)."""
    violations = lint.find_violations(FIXTURES_DIR / "loop_before_first_phase.js")
    assert len(violations) == 1
    assert "before first phase(" in violations[0][1]


def test_no_phase_uncapped_loop_is_violation(lint):
    """DEFECT :245 (PR3d, 2026-09-18): a file with NO phase( call at all must still be
    scanned — an empty phase_calls list must not mean an empty spans list."""
    violations = lint.find_violations(FIXTURES_DIR / "no_phase_uncapped_loop.js")
    assert len(violations) == 1
    assert "no phase(" in violations[0][1]


def test_no_phase_capped_loop_stays_clean(lint):
    """Twin of the fixture above: the new implicit leading span must not over-fire on
    a phase(-less file whose loop genuinely IS capped."""
    assert lint.find_violations(FIXTURES_DIR / "no_phase_capped_loop.js") == []


def test_nested_model_key_is_violation(lint):
    """DEFECT :229 (PR3d, 2026-09-18): a `model:` key nested inside
    schema.properties.model must not satisfy RULE 1 — only a genuine top-level
    `model:` on the options object literal counts."""
    violations = lint.find_violations(FIXTURES_DIR / "nested_model_key.js")
    assert len(violations) == 1
    assert "model:" in violations[0][1]


def test_nested_schema_with_top_level_model_stays_clean(lint):
    """Twin of the fixture above: the SAME nested schema.properties.model shape is
    still clean once a real top-level model: is also present."""
    assert lint.find_violations(FIXTURES_DIR / "nested_schema_with_top_level_model.js") == []


def test_parenthesized_object_literal_is_checked(lint):
    """DEFECT :184 (PR3d, 2026-09-18): a parenthesized object literal
    (`agent(p, ({ label: "x" }))`) used to be skipped as unreadable indirection --
    it must be read exactly like the unwrapped form."""
    violations = lint.find_violations(FIXTURES_DIR / "parenthesized_object_literal.js")
    assert len(violations) == 1
    assert "model:" in violations[0][1]


def test_parenthesized_object_literal_with_model_stays_clean(lint):
    """Twin of the fixture above: the same wrapping-paren shape stays clean once a
    real top-level model: is present."""
    assert (
        lint.find_violations(FIXTURES_DIR / "parenthesized_object_literal_with_model.js")
        == []
    )


def test_for_await_loop_is_recognised(lint):
    """OBSERVATION 5 (PR3a', 2026-09-18): `for await (` must be recognised as a loop.
    The declared for-await...of stays exempt (bounded, same as plain for...of); the
    for-await onto a pre-declared variable has no declaration keyword, so it is NOT
    exempt and needs a cap like any other for(...) — only that one fires."""
    violations = lint.find_violations(FIXTURES_DIR / "for_await_loop.js")
    assert len(violations) == 1
    assert "for(" in violations[0][1]
    assert "cap" in violations[0][1]


# --------------------------------------------------------------------------
# ITEM 1 (PR3e, 2026-09-18, gate-10 obs 1, HIGH) -- regex literals must not blind the
# tokenizer to the rest of the file/line.
# --------------------------------------------------------------------------


def test_guilt_regex_with_quote_no_longer_blinds_the_scan(lint):
    """b01: pre-fix, a regex containing a quote (`.replace(/'/g, "")`) was read as a
    string opener and blanked the REST OF THE FILE -- both violations below must now
    be visible."""
    violations = lint.find_violations(FIXTURES_DIR / "regex_quote_b01.js")
    assert len(violations) == 2
    messages = [msg for _, msg in violations]
    assert any("model:" in m for m in messages)
    assert any("cap" in m for m in messages)


def test_guilt_regex_with_double_slash_no_longer_blinds_the_line(lint):
    """b02: pre-fix, a regex containing `//` (`/https:\\/\\//`) was read as a line
    comment and blanked the rest of the LINE -- the unpinned agent( call sharing that
    line must still be reported."""
    violations = lint.find_violations(FIXTURES_DIR / "regex_double_slash_b02.js")
    assert len(violations) == 1
    assert "model:" in violations[0][1]


def test_innocence_division_chain_is_not_misread_as_regex(lint):
    """A chain of divisions (`a / b / c`) must stay clean -- neither `/` follows an
    opener character, so neither opens a phantom regex literal."""
    assert lint.find_violations(FIXTURES_DIR / "division_not_regex.js") == []


def test_innocence_live_repo_regex_literals_still_clean_and_balanced(lint):
    """The six live infra/workflows/*.js files carry 11 real regex literals today
    (kbli-batch-a-lot.js: 2, modus-bench.js: 1, saetta.js: 8 -- verified 2026-09-19 by
    direct execution; the module docstring's own worked example, `/https:\\/\\//`, is
    the same escaped-slash shape as saetta.js's `/\\/$/`). This is a regression guard:
    find_violations must not raise _UnbalancedAfterNeutralization on any of them."""
    for name in (
        "kbli-batch-a-lot.js",
        "kbli-pilot-a1.js",
        "modus-bench.js",
        "saetta.js",
        "second-army.js",
        "verify-template.js",
    ):
        path = REPO_ROOT / "infra" / "workflows" / name
        assert lint.find_violations(path) == [], f"{name} must stay clean under the new tokenizer"


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


def test_guilt_explicit_nonexistent_target_is_a_blind_scan(lint, tmp_path, capsys):
    """OBSERVATION 6 (PR3a', 2026-09-18): a nonexistent explicit path must refuse, not
    silently report '0 file(s) scanned, no violations, exit 0'."""
    ghost = tmp_path / "does_not_exist.js"
    rc = lint.main([str(ghost)])
    captured = capsys.readouterr()
    assert rc == 2, "a nonexistent explicit target must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert str(ghost) in captured.err
    assert "no violations" not in captured.out


# --------------------------------------------------------------------------
# SAFETY NET (item 1, PR3e, 2026-09-18, gate-10 obs 1) -- a non-zero paren/brace
# balance after neutralization must refuse the file, not guess.
# --------------------------------------------------------------------------


def test_guilt_unbalanced_after_neutralization_raises_from_find_violations(lint):
    with pytest.raises(lint._UnbalancedAfterNeutralization):
        lint.find_violations(FIXTURES_DIR / "regex_false_open_desyncs_balance.js")


def test_guilt_unbalanced_after_neutralization_main_exits_2(lint, capsys):
    rc = lint.main([str(FIXTURES_DIR / "regex_false_open_desyncs_balance.js")])
    captured = capsys.readouterr()
    assert rc == 2, "an unbalanced neutralization must not exit 0 or 1 -- it proves nothing"
    assert "regex_false_open_desyncs_balance.js" in captured.err
    assert "no violations" not in captured.out


def test_guilt_quoted_model_key_is_reported_unpinned_by_design(lint):
    """DOCUMENTED LIMIT (item 2, PR3e, 2026-09-18, gate-10 obs 2): _neutralize_js blanks
    a quoted string's own delimiting quotes along with its contents, so a QUOTED
    `"model"` key is lexically invisible to _entry_key_is_model by the time RULE 1
    inspects the object -- this is a fail-safe FALSE ACCUSATION, not a missed real one,
    and is asserted here rather than only documented so the behaviour cannot drift
    silently. See the module docstring's "Known accusing-side limits" and
    _entry_key_is_model's own docstring."""
    violations = lint.find_violations(FIXTURES_DIR / "quoted_model_key.js")
    assert len(violations) == 1
    line_no, msg = violations[0]
    assert line_no == 10
    assert "no literal `model:`" in msg


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
