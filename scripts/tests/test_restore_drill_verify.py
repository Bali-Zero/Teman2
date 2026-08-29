"""restore_drill_verify.py must catch the degenerate shape and must never
accuse a healthy restore.

TRAUMA this replaces: the drill's OLD success condition was a bare table
census (`TABLES -ge 50`) — a restore that produces 60 EMPTY tables passed it.
The workflow's own comment records why that mattered: on 2026-06-06 a
`PGPASSWORD` env-prefix landed on the wrong side of a pipe, psql got no
password, the restore silently produced 0 tables, and the drill reported
success. This corpus proves the replacement (a) genuinely fails on a
degenerate restore, naming every broken relation individually rather than an
aggregate "FAILED", and (b) never conflates "could not measure" with
"measured zero" (cicatrix-scars.md W106b / superscar #9) — the class of bug
this whole module exists to close off.

Guilt fixture: scripts/tests/fixtures/restore_drill/degenerate.json — four
relations, each broken for a DIFFERENT reason (schema drift, below-floor row
count, relational violations, missing relation), and one left clean, so a
test against this file can assert the exact named-failing set rather than a
blanket "everything is red" (a test that would pass even if the evaluator
only ever emitted a single generic failure).
Innocence fixture: scripts/tests/fixtures/restore_drill/healthy.json — all
five relations PASS.

Run:  python3 scripts/tests/test_restore_drill_verify.py
      pytest scripts/tests/test_restore_drill_verify.py -q
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_CI_DIR = Path(__file__).resolve().parents[1] / "ci"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "restore_drill"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "restore_drill_verify", _CI_DIR / "restore_drill_verify.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec: `Invariant` is a frozen dataclass
    # under `from __future__ import annotations`, and dataclasses resolves
    # its string annotations via `sys.modules[cls.__module__]` -- a module
    # loaded via spec_from_file_location that is never added to sys.modules
    # crashes there with `AttributeError: 'NoneType' object has no attribute
    # '__dict__'` (measured, not assumed: this exact failure on the first
    # run of this file, before this line existed).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rdv = _load_module()


def _load_fixture(name: str) -> dict[str, Any]:
    with open(_FIXTURES / name) as f:
        return json.load(f)


def _healthy_relations() -> list[dict[str, Any]]:
    return copy.deepcopy(_load_fixture("healthy.json")["relations"])


# ---------------------------------------------------------------------------
# Innocence: the healthy fixture.
# ---------------------------------------------------------------------------


def test_healthy_fixture_is_five_explicit_passes():
    result = rdv.evaluate(_load_fixture("healthy.json")["relations"])
    assert result["aggregate"] == "PASS"
    assert len(result["invariants"]) == 5, "must always emit exactly 5 verdicts, one per declared invariant"
    for verdict in result["invariants"]:
        assert verdict["status"] == "PASS", verdict
        assert verdict["reasons"] == [], verdict


def test_healthy_fixture_cli_exits_zero():
    fx_path = str(_FIXTURES / "healthy.json")
    rc = rdv.main(["--fixture", fx_path])
    assert rc == 0


def test_healthy_fixture_covers_the_legitimately_zero_row_case():
    """events_outbox is pruned daily (migration 144) -- 0 rows is a healthy
    state, not a degenerate one. Pinned so nobody "fixes" the fixture into a
    non-zero count and silently deletes the one case that proves min_rows is
    NOT applied blindly to every relation."""
    healthy = _load_fixture("healthy.json")
    outbox = next(r for r in healthy["relations"] if r["relation"] == "events_outbox")
    assert outbox["row_count"] == 0
    result = rdv.evaluate(healthy["relations"])
    verdict = next(v for v in result["invariants"] if v["relation"] == "events_outbox")
    assert verdict["status"] == "PASS", verdict


# ---------------------------------------------------------------------------
# Guilt: the degenerate fixture. Mixed on purpose -- 4 broken, 1 clean.
# ---------------------------------------------------------------------------


def test_degenerate_fixture_names_every_failed_invariant_not_an_aggregate_only_failure():
    result = rdv.evaluate(_load_fixture("degenerate.json")["relations"])
    assert result["aggregate"] != "PASS"

    by_relation = {v["relation"]: v for v in result["invariants"]}
    assert len(by_relation) == 5

    expected_broken = {"conversations", "clients", "visa_decisions", "events_outbox"}
    broken = {rel for rel, v in by_relation.items() if v["status"] != "PASS"}
    assert broken == expected_broken, f"expected exactly {expected_broken} broken, got {broken}"

    # The one relation the fixture leaves clean really is reported clean --
    # a test that only checked the broken set could pass even if the
    # evaluator marked EVERYTHING broken (which "names every failed
    # invariant, not an aggregate failure" explicitly rules out).
    assert by_relation["visa_decision_retention_policies"]["status"] == "PASS"
    assert by_relation["visa_decision_retention_policies"]["reasons"] == []

    # Each broken relation names its OWN, distinct cause -- not a shared
    # generic string that would pass even if every check collapsed to one
    # "something is wrong" message.
    assert any("missing required column" in r for r in by_relation["conversations"]["reasons"])
    assert any("below floor" in r for r in by_relation["clients"]["reasons"])
    assert any("verdict_unknown" in r for r in by_relation["visa_decisions"]["reasons"])
    assert any("citations_not_array" in r for r in by_relation["visa_decisions"]["reasons"])
    assert any("relation missing" in r for r in by_relation["events_outbox"]["reasons"])


def test_degenerate_fixture_cli_exits_nonzero(capsys):
    fx_path = str(_FIXTURES / "degenerate.json")
    rc = rdv.main(["--fixture", fx_path, "--json"])
    assert rc != 0
    out = json.loads(capsys.readouterr().out)
    assert out["aggregate"] != "PASS"
    broken = {v["relation"] for v in out["invariants"] if v["status"] != "PASS"}
    assert broken == {"conversations", "clients", "visa_decisions", "events_outbox"}


def test_degenerate_fixture_prose_output_names_relations_not_just_aggregate(capsys):
    fx_path = str(_FIXTURES / "degenerate.json")
    rdv.main(["--fixture", fx_path])
    out = capsys.readouterr().out
    for relation in ("conversations", "clients", "visa_decisions", "events_outbox"):
        assert relation in out, f"prose output silently dropped {relation}"


# ---------------------------------------------------------------------------
# "Cannot measure" must never be silently reported as "measured zero"
# (cicatrix-scars.md W106b / superscar #9). Each of these is exercised
# directly against `evaluate()`, not via a fixture FILE, because each one
# is a class of MEASUREMENT failure rather than a schema/data fact — the
# two fixture files above are reserved for the plan's own file list.
# ---------------------------------------------------------------------------


def test_a_relation_absent_from_the_measurement_list_is_cannot_verify_not_a_pass():
    """A future bug that silently drops one relation from the measurement
    set must never read as that relation passing."""
    relations = _healthy_relations()
    relations = [r for r in relations if r["relation"] != "events_outbox"]
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "events_outbox")
    assert verdict["status"] == "CANNOT-VERIFY"
    assert "no measurement recorded" in verdict["reasons"][0]
    assert result["aggregate"] == "CANNOT-VERIFY"


def test_a_query_error_is_cannot_verify_not_a_pass():
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "visa_decisions":
            r.clear()
            r.update({"relation": "visa_decisions", "error": "connection to server was lost"})
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "visa_decisions")
    assert verdict["status"] == "CANNOT-VERIFY"
    assert "connection to server was lost" in verdict["reasons"][0]


def test_a_declared_check_missing_from_violations_is_cannot_verify_not_zero():
    """The whole point of this test: `violations` reporting NOTHING for a
    check must never be read the same as `violations` reporting 0 for it."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            del r["violations"]["client_type_unknown"]
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "CANNOT-VERIFY"
    assert any("client_type_unknown" in r and "could not be measured" in r for r in verdict["reasons"])


def test_a_relation_reported_existing_with_zero_columns_is_cannot_verify():
    """A relation cannot exist in Postgres with zero columns (a PRIMARY KEY
    alone guarantees at least one) -- this is the measurement lying about
    its own input, not a fact about the schema."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["columns"] = []
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "CANNOT-VERIFY"
    assert "zero columns" in verdict["reasons"][0]


def test_a_boolean_violation_count_is_cannot_verify_not_a_silent_fail():
    """Guilt: `isinstance(True, int)` is True in Python, and `True < 0` is
    False for both True and False -- a fixture typo like
    `"client_type_unknown": true` (JSON `true` decodes to a Python bool)
    would otherwise sail past the malformed-value guard entirely and land
    in the `count != 0` branch as a genuine-looking FAIL
    ("client_type_unknown: True row(s) violate"), never the
    CANNOT-VERIFY-with-a-clear-reason the guard exists to give. Not
    reachable via --dsn (Postgres count(*) is always a bigint), but
    reachable by an ordinary fixture-authoring mistake -- exactly the input
    class the guard's own comment claims to catch."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["violations"]["client_type_unknown"] = True
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "CANNOT-VERIFY", verdict
    assert any("malformed value" in r and "True" in r for r in verdict["reasons"])


def test_ordinary_integer_violation_counts_still_evaluate_normally():
    """Innocence, paired with the guilt test above: the bool exclusion must
    not disturb ordinary int handling -- a real zero still PASSes and a
    real nonzero count still FAILs."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["violations"]["client_type_unknown"] = 0
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "PASS", verdict

    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["violations"]["client_type_unknown"] = 3
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "FAIL", verdict
    assert any("client_type_unknown: 3 row(s) violate" in r for r in verdict["reasons"])


def test_a_missing_column_and_the_checks_it_blocks_are_both_named_not_only_one():
    """A relation can carry BOTH a genuine FAIL-class finding (a missing
    column) and a CANNOT-VERIFY-class one (a check that could not run as a
    result) at once. Both must be visible -- an earlier draft of the
    evaluator discarded the FAIL-class reason whenever a CANNOT-VERIFY one
    also fired for the same relation."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "conversations":
            r["columns"] = [c for c in r["columns"] if c != "messages"]
            r.pop("violations", None)
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "conversations")
    assert verdict["status"] == "CANNOT-VERIFY"
    assert any("missing required column" in r and "messages" in r for r in verdict["reasons"])
    assert any("messages_not_json_array" in r for r in verdict["reasons"])


# ---------------------------------------------------------------------------
# Relational-check math, pinned directly (guilt + innocence on the same
# invariant, independent of any fixture file).
# ---------------------------------------------------------------------------


def test_visa_decisions_temporarily_unavailable_may_lack_a_rule_pack():
    """Mirrors migration 252's own CHECK: only a TEMPORARILY_UNAVAILABLE
    verdict may have a null rule_pack_id."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "visa_decisions":
            r["violations"]["temporarily_unavailable_missing_pack"] = 0
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "visa_decisions")
    assert verdict["status"] == "PASS"


def test_visa_decisions_non_unavailable_without_a_pack_is_flagged():
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "visa_decisions":
            r["violations"]["temporarily_unavailable_missing_pack"] = 1
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "visa_decisions")
    assert verdict["status"] == "FAIL"
    assert any("temporarily_unavailable_missing_pack" in reason for reason in verdict["reasons"])


def test_row_count_below_floor_fails_a_relation_that_has_one():
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["row_count"] = 0
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "FAIL"
    assert "below floor" in verdict["reasons"][0]


def test_row_count_exactly_at_the_floor_passes():
    """The floor is "below which zero is provably wrong" (module docstring)
    -- AT the floor is not below it. Pinned because the prior round measured
    this boundary as untested: changing the evaluator's `<` to `<=` left
    every existing test green, since no fixture set row_count == min_rows
    exactly. clients carries min_rows=1; row_count == 1 must PASS."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["row_count"] = 1
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "PASS", verdict


def test_zero_rows_does_not_fail_a_relation_with_no_floor():
    """visa_decisions/events_outbox/visa_decision_retention_policies carry
    min_rows=None -- zero rows must never fail them on row count alone."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] in ("visa_decisions", "visa_decision_retention_policies"):
            r["row_count"] = 0
    result = rdv.evaluate(relations)
    for relation in ("visa_decisions", "visa_decision_retention_policies"):
        verdict = next(v for v in result["invariants"] if v["relation"] == relation)
        assert verdict["status"] == "PASS", verdict


# ---------------------------------------------------------------------------
# FAIL vs CANNOT-VERIFY status, pinned directly. The module's own docstring
# states this discrimination as its core thesis: "A missing relation or a
# missing required column is a genuinely diagnosable finding -- scored
# FAIL, not CANNOT-VERIFY". Every existing CANNOT-VERIFY test above asserts
# `status == "CANNOT-VERIFY"` explicitly, but nothing asserted the FAIL side
# of the SAME discrimination with an equally explicit status check -- the
# only guilt coverage for the missing-relation branch (evaluate_one's
# `exists is not True` case) was a substring check on `reasons`
# ("relation missing" in ...), which a mutation from FAIL to CANNOT-VERIFY
# on that branch does not disturb (measured: 16/16 tests stayed green under
# that exact mutation before these two tests existed).
# ---------------------------------------------------------------------------


def test_relation_missing_from_restore_is_status_fail_not_cannot_verify():
    """A relation absent from the restore is a diagnosable defect (the
    restore is provably incomplete), not an untaken measurement -- must be
    FAIL, never CANNOT-VERIFY, even though both statuses would make
    `broken = {status != PASS}` assertions pass identically."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "events_outbox":
            r.clear()
            r.update({"relation": "events_outbox", "exists": False})
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "events_outbox")
    assert verdict["status"] == "FAIL", verdict
    assert "relation missing" in verdict["reasons"][0]


def test_missing_required_column_alone_is_status_fail_not_cannot_verify():
    """A required column dropped from the schema is likewise diagnosable
    (the app cannot work without it), not a measurement failure -- isolated
    here from any CANNOT-VERIFY trigger: the removed column (`updated_at`)
    is not referenced by any of clients' violation checks, so `violations`
    stays fully measured and row_count stays above its floor. (Contrast
    `test_a_missing_column_and_the_checks_it_blocks_are_both_named_not_only_one`
    above, which removes `messages` from conversations AND pops its
    `violations` dict -- there BOTH a FAIL-class and a CANNOT-VERIFY-class
    reason fire together, and CANNOT-VERIFY correctly wins per the
    evaluator's own precedence. This test isolates the FAIL-only case.)"""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["columns"] = [c for c in r["columns"] if c != "updated_at"]
    result = rdv.evaluate(relations)
    verdict = next(v for v in result["invariants"] if v["relation"] == "clients")
    assert verdict["status"] == "FAIL", verdict
    assert any("missing required column" in r and "updated_at" in r for r in verdict["reasons"])


# ---------------------------------------------------------------------------
# The exit-code mapping the PASS/FAIL/CANNOT-VERIFY status feeds
# (`_EXIT_FOR_AGGREGATE`) is itself a claim this module makes about a
# caller-visible contract (docstring "Exit codes" section) -- pinned per
# value, not just "zero vs nonzero", because the previous round measured
# that swapping the FAIL (1) and CANNOT-VERIFY (3) exit codes left every
# existing test green too (nothing asserted an exact nonzero value).
# ---------------------------------------------------------------------------


def test_exit_code_for_pass_aggregate_is_exactly_zero():
    rc = rdv.main(["--fixture", str(_FIXTURES / "healthy.json")])
    assert rc == 0


def test_exit_code_for_a_pure_fail_aggregate_is_exactly_one(tmp_path):
    """A fixture with exactly one genuine FAIL and no CANNOT-VERIFY anywhere
    -- confirms `aggregate == "FAIL"` maps to exit 1, distinct from
    CANNOT-VERIFY's exit 3."""
    relations = _healthy_relations()
    for r in relations:
        if r["relation"] == "clients":
            r["row_count"] = 0
    fx = tmp_path / "pure_fail.json"
    fx.write_text(json.dumps({"relations": relations}))
    rc = rdv.main(["--fixture", str(fx), "--json"])
    assert rc == 1


def test_exit_code_for_cannot_verify_aggregate_is_exactly_three(capsys):
    """degenerate.json's `conversations` relation carries both a FAIL-class
    reason (missing column) and a CANNOT-VERIFY-class one (the check that
    references that column cannot run) -- CANNOT-VERIFY wins per the
    evaluator's precedence, so this fixture's aggregate is CANNOT-VERIFY,
    not FAIL (verified directly here, not assumed)."""
    fx_path = str(_FIXTURES / "degenerate.json")
    rc = rdv.main(["--fixture", fx_path, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["aggregate"] == "CANNOT-VERIFY", out
    assert rc == 3


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


def test_mutually_exclusive_source_flags_are_enforced():
    try:
        rdv.main([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse to reject a call with neither --dsn nor --fixture")


if __name__ == "__main__":
    # Delegate to real pytest (not a hand-rolled loop) so fixture-dependent
    # tests (capsys) run correctly even outside a `pytest` invocation --
    # matching test_probe_merge_gate_integrity.py's own convention.
    raise SystemExit(pytest.main([__file__, "-v"]))
