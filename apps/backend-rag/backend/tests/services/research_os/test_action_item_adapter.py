from __future__ import annotations

from research_os.enums import QueueState

from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.loss_report import (
    LegacyFieldFate,
    LossReportIncompleteError,
    assert_every_legacy_field_accounted_for,
)
from backend.tests.services.research_os.conftest import make_ops_intent_row


def test_adapts_a_succeeded_row_into_a_valid_action_item(ops_intent_row):
    result = adapt_ops_intent_to_action_item(ops_intent_row)

    assert result.accepted
    item = result.canonical
    assert item is not None
    assert item.queue_state == QueueState.CLOSED
    assert item.close_reason == "completed"
    assert item.revision == 1
    assert item.supersedes_action_item_ref is None
    assert item.current_intent_ref is None


def test_every_legacy_field_is_accounted_for_never_silently_dropped(ops_intent_row):
    result = adapt_ops_intent_to_action_item(ops_intent_row)

    # Re-run the same check the adapter runs internally, independently from
    # the test suite -- the exit criterion is a PARITY test, not a trust of
    # the adapter's own bookkeeping.
    assert_every_legacy_field_accounted_for(dict(ops_intent_row), result.loss_report)
    fates = result.loss_report.fates()
    assert set(fates) == set(ops_intent_row)
    assert all(isinstance(f, LegacyFieldFate) for f in fates.values())


def test_priority_loss_is_disclosed_not_silent(ops_intent_row):
    result = adapt_ops_intent_to_action_item(ops_intent_row)

    assert any("priority" in w for w in result.loss_report.warnings)
    assert any("decision_packet_ref" in w and "SYNTHESIZED_UNBACKED" in w for w in result.loss_report.warnings)


def test_unbacked_refs_are_machine_checkable_not_only_prose(ops_intent_row):
    """Per an adversarial review (Kimi K3): a loss report is documentation a
    consumer could skip. The same fact must also be branch-able in code,
    via the object's own `extensions` -- this is that check.
    """

    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    marker = item.extensions["com.balizero.research-os-adapters"]
    assert marker.extension_version == "1.0.0"
    assert set(marker.payload["unbacked_refs"]) == {"decision_packet_ref", "requested_action_spec_ref"}


def test_status_value_set_map_covers_every_legacy_status():
    for status in [
        "queued",
        "claimed",
        "running",
        "succeeded",
        "failed",
        "cancelled_revoked",
        "outcome_unknown",
    ]:
        row = make_ops_intent_row(status=status)
        result = adapt_ops_intent_to_action_item(row)
        assert result.accepted, f"status={status} should be adaptable"


def test_unrecognized_status_is_rejected_with_full_field_ledger():
    row = make_ops_intent_row(status="not_a_real_status")
    result = adapt_ops_intent_to_action_item(row)

    assert not result.accepted
    assert result.canonical is None
    assert set(result.loss_report.fates()) == set(row)
    assert all(f == LegacyFieldFate.REJECTED for f in result.loss_report.fates().values())


def test_clock_skew_row_is_rejected_not_silently_coerced():
    row = make_ops_intent_row(
        created_at="2026-08-20T12:00:00+00:00", expires_at="2026-08-20T10:00:00+00:00"
    )
    result = adapt_ops_intent_to_action_item(row)

    assert not result.accepted
    assert result.canonical is None


def test_incomplete_loss_report_is_caught_by_the_guard(ops_intent_row):
    result = adapt_ops_intent_to_action_item(ops_intent_row)
    truncated_fields = result.loss_report.fields[:-1]
    from dataclasses import replace

    truncated_report = replace(result.loss_report, fields=truncated_fields)

    try:
        assert_every_legacy_field_accounted_for(dict(ops_intent_row), truncated_report)
        raised = False
    except LossReportIncompleteError:
        raised = True
    assert raised, "dropping one field's report entry must be caught, not silently pass"
