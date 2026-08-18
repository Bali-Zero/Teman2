"""Fixture-driven tests for QW-6a's HRR reason audit tooling.

Zero network/prod access: every test loads the local JSON fixture
(``fixtures/hrr_reason_audit_sample.json``) via ``load_fixture`` and drives
the pure computation functions only. ``fetch_decisions_pg`` (the live-ledger
path, QW-6b) is never invoked here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hrr_reason_audit import (
    DecisionRow,
    build_report,
    compute_conclusive_rate,
    compute_malformed_review_reason_claims,
    compute_reason_counts,
    compute_sequence_activation_split,
    filter_rows,
    load_fixture,
    main as hrr_main,
    row_from_mapping,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hrr_reason_audit_sample.json"
SCOPE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hrr_reason_audit_scope_sample.json"


@pytest.fixture()
def rows() -> list[DecisionRow]:
    return load_fixture(FIXTURE_PATH)


@pytest.fixture()
def scope_rows() -> list[DecisionRow]:
    return load_fixture(SCOPE_FIXTURE_PATH)


def test_load_fixture_row_count(rows: list[DecisionRow]) -> None:
    assert len(rows) == 8


def test_reason_counts_split_by_traffic_source_post_seq7(rows: list[DecisionRow]) -> None:
    report = compute_reason_counts(rows, min_sequence=7)

    assert report["real"]["SPONSOR_WITNESS_MISSING"] == {
        "reason_count": 2,
        "decisions_with_this_reason": 2,
    }
    assert report["real"]["AMBIGUOUS_PURPOSE"] == {
        "reason_count": 1,
        "decisions_with_this_reason": 1,
    }
    assert report["synthetic_driver"]["PROBE_TOKEN_UNRESOLVED"] == {
        "reason_count": 1,
        "decisions_with_this_reason": 1,
    }
    # The pre-seq-7 legacy row must NEVER surface here (min_sequence gate).
    assert "PRE_SEQ7_LEGACY_REASON" not in json.dumps(report)
    # No legacy_unknown bucket should appear once the seq-7 gate excludes it.
    assert "legacy_unknown" not in report


def test_reason_counts_never_pool_synthetic_into_real(rows: list[DecisionRow]) -> None:
    """Contamination guard: a synthetic_driver reason code must never land
    under the 'real' bucket, and vice versa — this is QW-6a's mandatory
    split, not a nice-to-have."""

    report = compute_reason_counts(rows, min_sequence=7)
    assert "PROBE_TOKEN_UNRESOLVED" not in report.get("real", {})
    assert "SPONSOR_WITNESS_MISSING" not in report.get("synthetic_driver", {})


def test_conclusive_rate_split_post_seq7(rows: list[DecisionRow]) -> None:
    report = compute_conclusive_rate(rows, min_sequence=7)

    real = report["real"]
    assert real["total"] == 5
    assert real["inconclusive"] == 3  # 2x HRR + 1x NEEDS_INPUT
    assert real["conclusive"] == 2  # SUPPORTED_CANDIDATES + NO_SUPPORTED_PATH
    assert real["conclusive_rate_pct"] == 40.0
    assert real["by_verdict"] == {
        "HUMAN_REVIEW_REQUIRED": 2,
        "SUPPORTED_CANDIDATES": 1,
        "NEEDS_INPUT": 1,
        "NO_SUPPORTED_PATH": 1,
    }

    synth = report["synthetic_driver"]
    assert synth["total"] == 1
    assert synth["conclusive"] == 0
    assert synth["conclusive_rate_pct"] == 0.0

    # Pre-seq-7 legacy row (rule_pack_sequence=6) must be excluded entirely.
    assert "legacy_unknown" not in report


def test_conclusive_rate_gate_pre_seq7_reproduces_zero_percent(rows: list[DecisionRow]) -> None:
    """Sanity-anchor to the plan's stated baseline: with the gate lowered to
    include the pre-seq-7 legacy row (min_sequence=6), that row's own bucket
    reads 0% conclusive — same shape as the documented "6,610/6,610 HRR,
    0% conclusive" pre-seq-7 contamination baseline."""

    report = compute_conclusive_rate(rows, min_sequence=6)
    legacy = report["legacy_unknown"]
    assert legacy["total"] == 1
    assert legacy["conclusive_rate_pct"] == 0.0
    assert legacy["by_verdict"] == {"HUMAN_REVIEW_REQUIRED": 1}


def test_sequence_activation_split_has_no_min_sequence_gate(rows: list[DecisionRow]) -> None:
    """(d) is the optional un-gated breakdown — it must show every sequence,
    including the pre-seq-7 legacy row and the NULL-sequence
    TEMPORARILY_UNAVAILABLE row, so an auditor can see exactly where the
    conclusive rate flips."""

    report = compute_sequence_activation_split(rows)

    assert report["7"]["act-7-a"]["real"] == {
        "HUMAN_REVIEW_REQUIRED": 2,
        "SUPPORTED_CANDIDATES": 1,
        "NEEDS_INPUT": 1,
    }
    assert report["7"]["act-7-a"]["synthetic_driver"] == {"HUMAN_REVIEW_REQUIRED": 1}
    assert report["6"]["act-6-legacy"]["legacy_unknown"] == {"HUMAN_REVIEW_REQUIRED": 1}
    assert report["8"]["act-8-a"]["real"] == {"NO_SUPPORTED_PATH": 1}
    assert report["unknown"]["unknown"]["real"] == {"TEMPORARILY_UNAVAILABLE": 1}


def test_build_report_is_json_serializable(rows: list[DecisionRow]) -> None:
    report = build_report(rows, min_sequence=7)
    # Round-trips clean — this is exactly what --out writes for QW-6b.
    json.dumps(report)
    assert report["total_rows_fetched"] == 8
    assert report["total_rows_in_scope"] == 8  # all 8 fixture rows are PRODUCTION/SHADOW
    assert report["min_sequence"] == 7


def test_row_from_mapping_tolerates_json_string_grounding_summary() -> None:
    raw = {
        "decision_id": "x",
        "verdict": "HUMAN_REVIEW_REQUIRED",
        "traffic_source": "real",
        "rule_pack_sequence": 7,
        "ruleset_activation_id": "a",
        "grounding_summary": json.dumps(
            [{"claim_kind": "REVIEW_REASON", "claim_code": "FOO", "source_record_ids": []}]
        ),
    }
    row = row_from_mapping(raw)
    assert row.review_reason_codes == ["FOO"]


def test_row_from_mapping_rejects_unknown_verdict() -> None:
    with pytest.raises(ValueError):
        row_from_mapping(
            {
                "decision_id": "x",
                "verdict": "TOTALLY_MADE_UP",
                "traffic_source": None,
                "rule_pack_sequence": None,
                "ruleset_activation_id": None,
                "grounding_summary": [],
            }
        )


def test_row_from_mapping_malformed_grounding_summary_is_empty_not_a_crash() -> None:
    row = row_from_mapping(
        {
            "decision_id": "x",
            "verdict": "HUMAN_REVIEW_REQUIRED",
            "traffic_source": "real",
            "rule_pack_sequence": 7,
            "ruleset_activation_id": None,
            "grounding_summary": "{not valid json",
        }
    )
    assert row.review_reason_codes == []


def test_filter_rows_defaults_to_production_shadow_only(scope_rows: list[DecisionRow]) -> None:
    """kimi adversarial review F1/F2/F8 (2026-08-16): TEST-environment and
    ENFORCE-mode rows must never silently pollute the default PRODUCTION/
    SHADOW audit scope."""

    scoped = filter_rows(scope_rows)
    scoped_ids = {row.decision_id for row in scoped}

    assert scoped_ids == {
        "00000000-0000-0000-0000-0000000000a1",
        "00000000-0000-0000-0000-0000000000a4",
    }


def test_filter_rows_all_sentinel_disables_scope(scope_rows: list[DecisionRow]) -> None:
    assert len(filter_rows(scope_rows, environment="ALL", engine_mode="ALL")) == len(scope_rows)


def test_filter_rows_can_target_a_different_environment(scope_rows: list[DecisionRow]) -> None:
    scoped = filter_rows(scope_rows, environment="TEST")
    assert {row.decision_id for row in scoped} == {"00000000-0000-0000-0000-0000000000a2"}


def test_build_report_defaults_exclude_test_and_enforce_rows(
    scope_rows: list[DecisionRow],
) -> None:
    """build_report scopes BEFORE computing anything else — a TEST row's
    reason code must never reach reason_counts, and an ENFORCE row's verdict
    must never reach conclusive_rate, under the default call."""

    report = build_report(scope_rows, min_sequence=7)

    assert report["environment_filter"] == "PRODUCTION"
    assert report["engine_mode_filter"] == "SHADOW"
    assert report["total_rows_fetched"] == 4
    assert report["total_rows_in_scope"] == 2

    assert "SHOULD_NOT_APPEAR_IN_PRODUCTION_AUDIT" not in json.dumps(report)

    real = report["conclusive_rate"]["real"]
    assert real["total"] == 2  # a1 (HRR) + a4 (SUPPORTED_CANDIDATES) only
    assert real["conclusive_rate_pct"] == 50.0

    split = report["sequence_activation_split"]["7"]["act-7-prod"]["real"]
    assert split == {"HUMAN_REVIEW_REQUIRED": 1, "SUPPORTED_CANDIDATES": 1}


def test_malformed_review_reason_claims_are_counted_not_dropped(
    scope_rows: list[DecisionRow],
) -> None:
    """kimi adversarial review F9 (2026-08-16): a REVIEW_REASON claim with a
    NULL claim_code must surface as dirty data, not vanish silently."""

    scoped = filter_rows(scope_rows)
    malformed = compute_malformed_review_reason_claims(scoped, min_sequence=7)
    assert malformed == {"real": 1}

    # And the well-formed sibling claim on the same row is still counted.
    reasons = compute_reason_counts(scoped, min_sequence=7)
    assert reasons["real"]["VALID_REASON_X"] == {
        "reason_count": 1,
        "decisions_with_this_reason": 1,
    }


def test_row_from_mapping_uses_engine_decision_id_not_surrogate_pk() -> None:
    """kimi adversarial review F5 (2026-08-16): fetch_decisions_pg selects
    ``d.decision_id`` (the engine's domain UUID), never the surrogate
    ``d.id`` PK — this test pins the DecisionRow field/fixture contract so a
    future regression back to ``d.id`` cannot land unnoticed. The live SQL
    column name itself is exercised only by QW-6b (no DSN here)."""

    row = row_from_mapping(
        {
            "decision_id": "engine-domain-uuid",
            "verdict": "NEEDS_INPUT",
            "traffic_source": "real",
            "rule_pack_sequence": 7,
            "ruleset_activation_id": None,
            "grounding_summary": [],
            "environment": "PRODUCTION",
            "engine_mode": "SHADOW",
        }
    )
    assert row.decision_id == "engine-domain-uuid"


def test_unknown_traffic_source_value_buckets_as_legacy_unknown() -> None:
    """A value outside migration 256's CHECK enum (should be impossible at
    the DB layer, but defense-in-depth) must never masquerade as a known
    bucket — it fails closed into legacy_unknown, same as NULL."""

    row = row_from_mapping(
        {
            "decision_id": "x",
            "verdict": "SUPPORTED_CANDIDATES",
            "traffic_source": "not_a_real_enum_value",
            "rule_pack_sequence": 7,
            "ruleset_activation_id": None,
            "grounding_summary": [],
        }
    )
    assert row.traffic_bucket == "legacy_unknown"


def test_cli_fixture_mode_works_even_if_dsn_env_var_is_exported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """kimi adversarial review F3 (2026-08-16): before this fix, an operator
    with VISA_DECISIONS_RO_DSN exported (exactly QW-6b's own environment)
    could not run ``--fixture`` for a dry run — argparse's env-var default
    made ``--fixture`` + the ambient env var look like ``--fixture --dsn``
    together and hard-error. This must now succeed."""

    monkeypatch.setenv("VISA_DECISIONS_RO_DSN", "postgresql://irrelevant/should-not-be-used")
    rc = hrr_main(["--fixture", str(FIXTURE_PATH)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_rows_fetched"] == 8
