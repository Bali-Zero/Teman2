"""Pure unit tests for `naga_backfill`: argument refusals, manifest determinism, report shape.

No PostgreSQL here -- every test either drives `main()`'s argument-parsing path (which never
opens a connection before a refusal) or calls the pure hashing/rendering functions directly.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from backend.services.research_os import naga_backfill as nb

MODULE_PATH = Path(nb.__file__)

SENTINEL_CLAIM_TEXT = "SENTINEL-legacy-claim-text-must-never-reach-the-report"


# --------------------------------------------------------------------------------------------
# Argument-shape refusals -- all exit 2, all before any connection could be opened.
# --------------------------------------------------------------------------------------------


def test_unknown_cohort_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", "seed_public_regulatory", "--dry-run"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "seed_public_regulatory" in err
    assert "legacy_naga_claims" in err


def test_totally_unknown_cohort_name_is_also_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", "not-a-real-cohort"])
    assert excinfo.value.code == 2
    assert "not-a-real-cohort" in capsys.readouterr().err


def test_apply_without_manifest_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", nb.PRODUCTION_COHORT, "--apply"])
    assert excinfo.value.code == 2
    assert "--manifest" in capsys.readouterr().err


def test_apply_with_malformed_manifest_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", nb.PRODUCTION_COHORT, "--apply", "--manifest", "not-hex"])
    assert excinfo.value.code == 2
    assert "--manifest" in capsys.readouterr().err


def test_both_modes_at_once_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(
            [
                "--cohort",
                nb.PRODUCTION_COHORT,
                "--dry-run",
                "--apply",
                "--manifest",
                "0" * 64,
            ]
        )
    assert excinfo.value.code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_missing_cohort_flag_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--dry-run"])
    assert excinfo.value.code == 2


def test_missing_dsn_env_var_names_the_variable_not_a_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_name = "NAGA_BACKFILL_DSN_TEST_UNSET_MARKER"
    assert env_name not in os.environ
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", nb.PRODUCTION_COHORT, "--dry-run", "--dsn-env", env_name])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert env_name in err


def test_missing_dsn_env_var_refusal_never_leaks_a_set_sibling_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Even when SOME env var carries a secret-shaped value, the refusal for a DIFFERENT,
    unset name never echoes any value at all -- only the missing name."""

    monkeypatch.setenv("NAGA_BACKFILL_DSN_TEST_SECRET_SIBLING", "postgresql://user:hunter2@host/db")
    env_name = "NAGA_BACKFILL_DSN_TEST_STILL_UNSET"
    with pytest.raises(SystemExit) as excinfo:
        nb.main(["--cohort", nb.PRODUCTION_COHORT, "--dry-run", "--dsn-env", env_name])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "hunter2" not in err
    assert env_name in err


# --------------------------------------------------------------------------------------------
# Manifest determinism -- pure functions, no I/O.
# --------------------------------------------------------------------------------------------


def test_source_snapshot_hash_is_deterministic_for_identical_rows() -> None:
    """Two INDEPENDENTLY built row sets carrying the same values -- different objects, and the
    columns inserted in a different order -- must hash the same, or the canonicalisation is not
    doing its job. Hashing one object twice would only prove the function is not random."""

    rows: list[dict[str, Any]] = [
        {"id": "a", "claim_text": "hello", "confidence": 0.5},
        {"id": "b", "claim_text": "world", "confidence": 0.9},
    ]
    same_rows_other_key_order: list[dict[str, Any]] = [
        {"confidence": 0.5, "id": "a", "claim_text": "hello"},
        {"claim_text": "world", "confidence": 0.9, "id": "b"},
    ]
    assert nb.compute_source_snapshot_hash(rows) == nb.compute_source_snapshot_hash(
        same_rows_other_key_order
    )


def test_source_snapshot_hash_changes_when_one_field_changes() -> None:
    base = [{"id": "a", "claim_text": "hello", "confidence": 0.5}]
    mutated = [{"id": "a", "claim_text": "hello!", "confidence": 0.5}]
    assert nb.compute_source_snapshot_hash(base) != nb.compute_source_snapshot_hash(mutated)


def test_source_snapshot_hash_is_a_valid_sha256_hex_digest() -> None:
    digest = nb.compute_source_snapshot_hash([{"id": "a", "claim_text": "x"}])
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_manifest_hash_is_deterministic_for_identical_input() -> None:
    decisions = [("a", "excluded", "statement_not_from_source"), ("b", "admitted", "fam-1")]
    _, hash1 = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions
    )
    _, hash2 = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions
    )
    assert hash1 == hash2
    assert re.fullmatch(r"[0-9a-f]{64}", hash1)


def test_manifest_hash_changes_when_a_decision_changes() -> None:
    decisions_a = [("a", "excluded", "statement_not_from_source")]
    decisions_b = [("a", "excluded", "content_hash_is_url")]
    _, hash_a = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions_a
    )
    _, hash_b = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions_b
    )
    assert hash_a != hash_b


def test_manifest_hash_is_independent_of_decision_input_order() -> None:
    decisions_forward = [("a", "excluded", "r1"), ("b", "admitted", "fam-1")]
    decisions_backward = [("b", "admitted", "fam-1"), ("a", "excluded", "r1")]
    _, hash_forward = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions_forward
    )
    _, hash_backward = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash="0" * 64, decisions=decisions_backward
    )
    assert hash_forward == hash_backward


def test_manifest_hash_changes_when_cohort_changes() -> None:
    decisions = [("a", "excluded", "statement_not_from_source")]
    _, hash_a = nb.compute_manifest(
        cohort="legacy_naga_claims", source_snapshot_hash="0" * 64, decisions=decisions
    )
    _, hash_b = nb.compute_manifest(
        cohort="some_other_cohort", source_snapshot_hash="0" * 64, decisions=decisions
    )
    assert hash_a != hash_b


# --------------------------------------------------------------------------------------------
# Report never carries legacy text -- counts and hashes only.
# --------------------------------------------------------------------------------------------


def _fake_dry_run_report() -> nb.DryRunReport:
    return nb.DryRunReport(
        mode="dry-run",
        cohort=nb.PRODUCTION_COHORT,
        manifest_hash="a" * 64,
        source_snapshot_hash="b" * 64,
        legacy_rows_read=1,
        admitted=0,
        excluded=1,
        excluded_by_reason={"statement_not_from_source": 1},
        kind_counts=nb._zero_kind_counts(),
    )


def test_rendered_text_report_never_contains_legacy_claim_text() -> None:
    rows = [{"id": "a", "claim_text": SENTINEL_CLAIM_TEXT}]
    decisions = [("a", "excluded", "statement_not_from_source")]
    snapshot_hash = nb.compute_source_snapshot_hash(rows)
    _, manifest_hash = nb.compute_manifest(
        cohort=nb.PRODUCTION_COHORT, source_snapshot_hash=snapshot_hash, decisions=decisions
    )
    report = nb.DryRunReport(
        mode="dry-run",
        cohort=nb.PRODUCTION_COHORT,
        manifest_hash=manifest_hash,
        source_snapshot_hash=snapshot_hash,
        legacy_rows_read=1,
        admitted=0,
        excluded=1,
        excluded_by_reason={"statement_not_from_source": 1},
        kind_counts=nb._zero_kind_counts(),
    )
    text = nb.render_report(report, as_json=False)
    assert SENTINEL_CLAIM_TEXT not in text
    # The manifest hash IS expected in the report -- it is the run's identity and what `--apply`
    # is bound to. Asserting its PRESENCE is the real contract; the previous
    # `assert manifest_hash not in text or True` was `X or True`, true for every input.
    assert manifest_hash in text
    assert SENTINEL_CLAIM_TEXT not in json.dumps(report.as_dict())


def test_rendered_json_report_never_contains_legacy_claim_text() -> None:
    report = _fake_dry_run_report()
    text = nb.render_report(report, as_json=True)
    assert SENTINEL_CLAIM_TEXT not in text
    parsed = json.loads(text)
    assert parsed["mode"] == "dry-run"
    assert "claim_text" not in text


def test_apply_report_written_entries_carry_only_id_and_hash() -> None:
    report = nb.ApplyReport(
        mode="apply",
        cohort=nb.PRODUCTION_COHORT,
        manifest_hash="a" * 64,
        source_snapshot_hash="b" * 64,
        legacy_rows_read=1,
        admitted=1,
        excluded=0,
        excluded_by_reason={},
        kind_counts=nb._zero_kind_counts(),
        written=(("claim-1", "c" * 64),),
    )
    data = report.as_dict()
    assert data["written"] == [{"object_id": "claim-1", "object_hash": "c" * 64}]
    assert SENTINEL_CLAIM_TEXT not in nb.render_report(report, as_json=False)
    assert SENTINEL_CLAIM_TEXT not in nb.render_report(report, as_json=True)


# --------------------------------------------------------------------------------------------
# Hard fence: this module issues no write statement of its own, and never touches naga_claims
# except with a SELECT (naga_persistence.py's own test uses the identical AST technique).
# --------------------------------------------------------------------------------------------

_WRITE_STATEMENT_RE = re.compile(
    r"\b(INSERT INTO|UPDATE|DELETE FROM|TRUNCATE|COPY)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE
)
_CONN_METHODS = {"execute", "fetch", "fetchval", "fetchrow"}


def _sql_string_literals() -> list[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    literals: list[str] = []
    for node in ast.walk(tree):
        call = node.value if isinstance(node, ast.Await) else node
        if not isinstance(call, ast.Call):
            continue
        if not (isinstance(call.func, ast.Attribute) and call.func.attr in _CONN_METHODS):
            continue
        if not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            literals.append(first.value)
    return literals


def test_module_issues_at_least_one_real_sql_statement() -> None:
    assert _sql_string_literals(), "expected real SQL literals passed to conn.execute/fetch*"


def test_module_issues_no_direct_write_statements() -> None:
    matches: list[tuple[str, str]] = []
    for sql in _sql_string_literals():
        matches.extend(_WRITE_STATEMENT_RE.findall(sql))
    assert matches == [], (
        f"naga_backfill.py must route every write through naga_persistence, found: {matches}"
    )


def test_module_never_writes_naga_claims_only_selects_it() -> None:
    saw_naga_claims = False
    for sql in _sql_string_literals():
        if "naga_claims" in sql:
            saw_naga_claims = True
            assert re.search(r"\bSELECT\b", sql, re.IGNORECASE) is not None
            assert _WRITE_STATEMENT_RE.search(sql) is None
    assert saw_naga_claims, "expected at least one SELECT referencing naga_claims"


def test_module_source_never_hashes_in_sql() -> None:
    for sql in _sql_string_literals():
        assert re.search(r"sha256\s*\(", sql, re.IGNORECASE) is None
