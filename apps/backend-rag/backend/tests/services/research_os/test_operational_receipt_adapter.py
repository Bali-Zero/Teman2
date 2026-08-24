from __future__ import annotations

from research_os.enums import ExecutionTerminalOutcome

from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.loss_report import (
    LegacyFieldFate,
    LossReportIncompleteError,
    assert_every_legacy_field_accounted_for,
)
from backend.services.research_os.operational_receipt_adapter import (
    adapt_ops_receipt_to_operational_receipt,
)
from backend.tests.services.research_os.conftest import make_ops_receipt_row


def test_adapts_a_matching_pair_into_a_valid_operational_receipt(ops_intent_row, ops_receipt_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)

    assert result.accepted
    receipt = result.canonical
    assert receipt is not None
    assert receipt.receipt_type == "execution.result"
    assert receipt.terminal_outcome == ExecutionTerminalOutcome.SUCCEEDED
    assert receipt.outcome_code == "effect_acknowledged"


def test_every_legacy_field_is_accounted_for_never_silently_dropped(
    ops_intent_row, ops_receipt_row
):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)

    assert_every_legacy_field_accounted_for(dict(ops_receipt_row), result.loss_report)
    fates = result.loss_report.fates()
    assert set(fates) == set(ops_receipt_row)
    assert all(isinstance(f, LegacyFieldFate) for f in fates.values())


def test_mismatched_intent_id_pairing_is_rejected(ops_intent_row):
    mismatched_receipt = make_ops_receipt_row(intent_id="0198f3a1-0000-7000-8000-000000000999")
    result = adapt_ops_receipt_to_operational_receipt(mismatched_receipt, ops_intent_row)

    assert not result.accepted
    assert result.canonical is None
    assert all(f == LegacyFieldFate.REJECTED for f in result.loss_report.fates().values())


def test_subject_refs_pins_the_real_sibling_action_item(ops_intent_row, ops_receipt_row):
    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    assert item is not None and receipt is not None

    assert len(receipt.subject_refs) == 1
    ref = receipt.subject_refs[0]
    assert ref.object_kind == "action_item"
    assert ref.object_id == str(item.action_item_id)
    assert ref.object_hash == item.object_hash


def test_classification_matches_sibling_action_item(ops_intent_row, ops_receipt_row):
    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    assert item is not None and receipt is not None

    assert receipt.classification.risk_class == item.risk_class
    assert receipt.classification.sensitivity == item.sensitivity


def test_unbacked_refs_are_machine_checkable_not_only_prose(ops_intent_row, ops_receipt_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    marker = receipt.extensions["com.balizero.research-os-adapters"]
    assert marker.extension_version == "1.1.0"
    assert set(marker.payload["unbacked_refs"]) == {"execution_attempt_ref"}


def test_pending_ruling_is_machine_checkable_not_only_prose(ops_intent_row, ops_receipt_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    marker = receipt.extensions["com.balizero.research-os-adapters"]
    assert set(marker.payload["pending_ruling"]) == {
        "execution_attempt_ref",
        "idempotency_key",
        "classification.risk_class",
        "classification.sensitivity",
    }


def test_extensions_is_always_explicitly_set_never_omitted(ops_intent_row, ops_receipt_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    assert "extensions" in receipt.model_fields_set


def test_non_terminal_status_is_rejected(ops_intent_row):
    non_terminal_receipt = make_ops_receipt_row(status="claimed")
    result = adapt_ops_receipt_to_operational_receipt(non_terminal_receipt, ops_intent_row)

    assert not result.accepted
    assert result.canonical is None


def test_outcome_code_falls_back_when_receipt_json_unparseable(ops_intent_row):
    malformed_receipt = make_ops_receipt_row(receipt_json="not valid json{{{")
    result = adapt_ops_receipt_to_operational_receipt(malformed_receipt, ops_intent_row)

    assert result.accepted
    assert result.canonical.outcome_code == "unbacked-outcome-succeeded"


def test_outcome_code_falls_back_when_code_key_absent(ops_intent_row):
    no_code_receipt = make_ops_receipt_row(receipt_json='{"other_field": "value"}')
    result = adapt_ops_receipt_to_operational_receipt(no_code_receipt, ops_intent_row)

    assert result.accepted
    assert result.canonical.outcome_code == "unbacked-outcome-succeeded"


def test_supersedes_ref_is_always_none_and_family_id_disclosed(ops_intent_row, ops_receipt_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    assert receipt.supersedes_operational_receipt_ref is None
    assert receipt.operational_receipt_family_id.startswith("bali-zero-magazine.ops-receipt.")


def test_status_value_set_map_covers_every_terminal_status(ops_intent_row):
    for status in ["succeeded", "failed", "cancelled_revoked", "outcome_unknown"]:
        receipt_row = make_ops_receipt_row(status=status)
        result = adapt_ops_receipt_to_operational_receipt(receipt_row, ops_intent_row)
        assert result.accepted, f"status={status} should be adaptable"


def test_incomplete_loss_report_is_caught_by_the_guard(ops_intent_row, ops_receipt_row):
    result = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row)
    truncated_fields = result.loss_report.fields[:-1]
    from dataclasses import replace

    truncated_report = replace(result.loss_report, fields=truncated_fields)

    try:
        assert_every_legacy_field_accounted_for(dict(ops_receipt_row), truncated_report)
        raised = False
    except LossReportIncompleteError:
        raised = True
    assert raised, "dropping one field's report entry must be caught, not silently pass"
