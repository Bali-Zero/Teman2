from __future__ import annotations

from dataclasses import replace

from backend.services.research_os.loss_report import (
    LegacyFieldFate,
    LossReportIncompleteError,
    assert_every_legacy_field_accounted_for,
)
from backend.services.research_os.operational_receipt_adapter import (
    adapt_ops_receipt_to_operational_receipt,
)
from backend.tests.services.research_os.conftest import make_ops_receipt_row


def test_every_row_is_rejected_pending_the_s9_c0_freeze_change_ruling(
    ops_intent_row, ops_receipt_row
):
    """This adapter is intentionally non-functional as of 2026-08-24: see its
    module docstring and the PENDING-ARMS ledger row for why -- a
    synthesized execution_attempt_ref would make every receipt this source
    could produce permanently unclosable (operational_receipt.py's own
    close_execution_attempt gate), and no other v1 receipt_type is
    expressible from ops_receipts.
    """

    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)

    assert not result.accepted
    assert result.canonical is None
    assert all(f == LegacyFieldFate.REJECTED for f in result.loss_report.fates().values())
    assert set(result.loss_report.fates()) == set(ops_receipt_row)


def test_rejection_reason_names_the_architectural_blocker(ops_intent_row, ops_receipt_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)
    reason = result.loss_report.fields[0].reason
    assert "execution_attempt_ref" in reason
    assert "S9-C0" in reason


def test_mismatched_intent_id_pairing_is_rejected_for_its_own_reason(ops_intent_row):
    mismatched_receipt = make_ops_receipt_row(intent_id="0198f3a1-0000-7000-8000-000000000999")
    result = adapt_ops_receipt_to_operational_receipt(mismatched_receipt, ops_intent_row)

    assert not result.accepted
    reason = result.loss_report.fields[0].reason
    assert "mismatched pairing" in reason
    assert "S9-C0" not in reason  # rejected for pairing, before the architectural check is reached


def test_parent_rejection_is_propagated_for_its_own_reason(ops_intent_row, ops_receipt_row):
    bad_intent = {**ops_intent_row, "status": "not_a_real_status"}
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, bad_intent)

    assert not result.accepted
    reason = result.loss_report.fields[0].reason
    assert "action_item adaptation" in reason


def test_non_terminal_status_is_rejected_for_its_own_reason(ops_intent_row):
    non_terminal_receipt = make_ops_receipt_row(status="claimed")
    result = adapt_ops_receipt_to_operational_receipt(non_terminal_receipt, ops_intent_row)

    assert not result.accepted
    reason = result.loss_report.fields[0].reason
    assert "non-terminal status" in reason


def test_clock_skew_is_rejected_for_its_own_reason(ops_intent_row, ops_receipt_row):
    skewed_intent = {**ops_intent_row, "completed_at": "2026-08-20T23:00:00+00:00"}
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, skewed_intent)

    assert not result.accepted
    reason = result.loss_report.fields[0].reason
    assert "clock skew" in reason


def test_every_terminal_status_still_hits_the_architectural_block(ops_intent_row):
    for status in ["succeeded", "failed", "cancelled_revoked", "outcome_unknown"]:
        receipt_row = make_ops_receipt_row(status=status)
        result = adapt_ops_receipt_to_operational_receipt(receipt_row, ops_intent_row)
        assert not result.accepted
        assert "S9-C0" in result.loss_report.fields[0].reason, f"status={status}"


def test_incomplete_loss_report_is_caught_by_the_guard(ops_intent_row, ops_receipt_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)
    truncated_fields = result.loss_report.fields[:-1]
    truncated_report = replace(result.loss_report, fields=truncated_fields)

    try:
        assert_every_legacy_field_accounted_for(dict(ops_receipt_row), truncated_report)
        raised = False
    except LossReportIncompleteError:
        raised = True
    assert raised, "dropping one field's report entry must be caught, not silently pass"
