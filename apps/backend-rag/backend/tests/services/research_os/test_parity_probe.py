"""The parity probe reports divergence; it never asserts equality across
every field (most are intentionally approximated/synthesized, see each
adapter's loss report). These tests prove both halves: a correctly-adapted
object probes clean, and an artificially corrupted one is CAUGHT rather
than silently passed.
"""

from __future__ import annotations

from backend.services.research_os.action_intent_adapter import adapt_ops_intent_to_action_intent
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.operational_receipt_adapter import (
    adapt_ops_receipt_to_operational_receipt,
)
from backend.services.research_os.parity import (
    probe_action_intent_parity,
    probe_action_item_parity,
    probe_operational_receipt_parity,
)


def test_action_item_probe_is_clean_on_a_correct_adaptation(ops_intent_row):
    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    report = probe_action_item_parity(ops_intent_row, item)

    assert report.clean
    assert report.fields_checked > 0


def test_action_item_probe_catches_a_corrupted_due_at(ops_intent_row):
    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    corrupted_sla = item.sla.model_copy(update={"due_at": item.sla.opened_at.replace(year=item.sla.opened_at.year + 5)})
    corrupted_item = item.model_copy(update={"sla": corrupted_sla})

    report = probe_action_item_parity(ops_intent_row, corrupted_item)

    assert not report.clean
    assert any(d.field == "sla.due_at" for d in report.divergences)


def test_action_intent_probe_is_clean_on_a_correct_adaptation(ops_intent_row):
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    report = probe_action_intent_parity(ops_intent_row, intent)

    assert report.clean


def test_action_intent_probe_catches_a_corrupted_idempotency_key(ops_intent_row):
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    corrupted = intent.model_copy(update={"idempotency_key": "not-the-real-key"})

    report = probe_action_intent_parity(ops_intent_row, corrupted)

    assert not report.clean
    assert any(d.field == "idempotency_key" for d in report.divergences)


def test_operational_receipt_probe_is_clean_on_a_correct_adaptation(ops_receipt_row, ops_intent_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    report = probe_operational_receipt_parity(ops_receipt_row, receipt)

    assert report.clean


def test_operational_receipt_probe_catches_a_corrupted_outcome_code(ops_receipt_row, ops_intent_row):
    receipt = adapt_ops_receipt_to_operational_receipt(ops_receipt_row, ops_intent_row).canonical
    corrupted = receipt.model_copy(update={"outcome_code": "wrong.code"})

    report = probe_operational_receipt_parity(ops_receipt_row, corrupted)

    assert not report.clean
    assert any(d.field == "outcome_code" for d in report.divergences)
