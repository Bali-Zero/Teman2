from __future__ import annotations

from backend.services.research_os.action_intent_adapter import adapt_ops_intent_to_action_intent
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.tests.services.research_os.conftest import make_ops_intent_row


def test_action_item_ref_pins_the_real_sibling_action_item(ops_intent_row):
    item_result = adapt_ops_intent_to_action_item(ops_intent_row)
    intent_result = adapt_ops_intent_to_action_intent(ops_intent_row)

    assert intent_result.accepted
    intent = intent_result.canonical
    item = item_result.canonical
    assert intent.action_item_ref.action_item_id == item.action_item_id
    assert intent.action_item_ref.object_hash == item.object_hash


def test_expires_after_seconds_is_derived_from_real_legacy_timestamps():
    row = make_ops_intent_row(
        created_at="2026-08-20T10:00:00+00:00", expires_at="2026-08-20T11:30:00+00:00"
    )
    result = adapt_ops_intent_to_action_intent(row)

    assert result.accepted
    assert result.canonical.authority_required.expires_after_seconds == 5400


def test_idempotency_key_and_action_type_map_directly(ops_intent_row):
    result = adapt_ops_intent_to_action_intent(ops_intent_row)

    assert result.canonical.idempotency_key == ops_intent_row["idempotency_key"]
    assert result.canonical.action_type == ops_intent_row["intent_kind"]
    assert result.canonical.authority_required.role == ops_intent_row["effective_role"]


def test_rejects_when_sibling_action_item_is_rejected():
    row = make_ops_intent_row(
        created_at="2026-08-20T12:00:00+00:00", expires_at="2026-08-20T10:00:00+00:00"
    )
    result = adapt_ops_intent_to_action_intent(row)

    assert not result.accepted
    assert result.canonical is None


def test_unbacked_refs_disclosed_in_warnings(ops_intent_row):
    result = adapt_ops_intent_to_action_intent(ops_intent_row)

    assert any("requested_action_spec_ref" in w and "SYNTHESIZED_UNBACKED" in w for w in result.loss_report.warnings)
    assert any("action_item_ref IS genuinely backed" in w for w in result.loss_report.warnings)


def test_same_row_adapted_twice_is_idempotent(ops_intent_row):
    first = adapt_ops_intent_to_action_intent(ops_intent_row)
    second = adapt_ops_intent_to_action_intent(ops_intent_row)

    assert first.canonical.action_intent_id == second.canonical.action_intent_id
    assert first.canonical.object_hash == second.canonical.object_hash
