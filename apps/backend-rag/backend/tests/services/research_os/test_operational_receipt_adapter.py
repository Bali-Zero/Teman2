from __future__ import annotations

from research_os.enums import ExecutionTerminalOutcome

from backend.services.research_os.loss_report import assert_every_legacy_field_accounted_for
from backend.services.research_os.operational_receipt_adapter import (
    adapt_ops_receipt_to_operational_receipt,
)
from backend.tests.services.research_os.conftest import make_ops_intent_row, make_ops_receipt_row


def test_adapts_a_succeeded_receipt(ops_receipt_row, ops_intent_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)

    assert result.accepted
    receipt = result.canonical
    assert receipt.receipt_type == "execution.result"
    assert receipt.terminal_outcome == ExecutionTerminalOutcome.SUCCEEDED
    assert receipt.subject_refs[0].object_id == ops_intent_row["intent_id"]
    assert_every_legacy_field_accounted_for(dict(ops_receipt_row), result.loss_report)


def test_terminal_outcome_map_covers_every_terminal_status():
    for status, expected in [
        ("succeeded", ExecutionTerminalOutcome.SUCCEEDED),
        ("failed", ExecutionTerminalOutcome.FAILED),
        ("cancelled_revoked", ExecutionTerminalOutcome.CANCELLED),
        ("outcome_unknown", ExecutionTerminalOutcome.UNKNOWN),
    ]:
        intent_row = make_ops_intent_row(status=status)
        receipt_row = make_ops_receipt_row(status=status)
        result = adapt_ops_receipt_to_operational_receipt(receipt_row, intent_row)
        assert result.accepted, f"status={status} should be adaptable"
        assert result.canonical.terminal_outcome == expected


def test_non_terminal_status_is_rejected():
    intent_row = make_ops_intent_row(status="running")
    receipt_row = make_ops_receipt_row(status="running")
    result = adapt_ops_receipt_to_operational_receipt(receipt_row, intent_row)

    assert not result.accepted
    assert result.canonical is None


def test_mismatched_parent_row_is_rejected(ops_receipt_row):
    wrong_parent = make_ops_intent_row(intent_id="not-the-parent")
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, wrong_parent)

    assert not result.accepted


def test_execution_attempt_ref_disclosed_as_unbacked(ops_receipt_row, ops_intent_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)

    assert any("execution_attempt_ref" in w and "SYNTHESIZED_UNBACKED" in w for w in result.loss_report.warnings)


def test_idempotency_key_falls_back_to_receipt_id_when_no_completed_at(ops_receipt_row):
    intent_row = make_ops_intent_row(completed_at=None)
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, intent_row)

    assert result.accepted
    assert result.canonical.idempotency_key == ops_receipt_row["receipt_id"]
    assert result.canonical.observed_at == result.canonical.recorded_at
