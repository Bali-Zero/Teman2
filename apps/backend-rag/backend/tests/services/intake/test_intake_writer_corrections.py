"""Fast tests for Intake's field-level learning evidence."""

from __future__ import annotations

from typing import Any

from backend.services.intake import writer


def _plan(
    *,
    original_fields: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    original_client_id: int | None = 10,
    client_id: int | None = 10,
) -> writer.CommitPlan:
    return writer.CommitPlan(
        proposal_id=1,
        queue_id=2,
        client_id=client_id,
        practice_id=None,
        decision="AUTO_ATTACH",
        doc_type="passport",
        committed_by="reviewer@example.test",
        idempotency_key="ik:test",
        payload={},
        source="whatsapp",
        blob_hash="a" * 64,
        pipeline_version="test-v1",
        original_fields=original_fields,
        human_field_overrides=overrides or {},
        original_client_id=original_client_id,
        entity_confidence=0.82,
        extraction_model="qwen3.5:9b",
        validation_passed=True,
    )


def test_feedback_distinguishes_approved_corrected_and_untouched_null() -> None:
    plan = _plan(
        original_fields={
            "name": {"value": " Alice ", "confidence": 0.91, "source_page": 1},
            "passport_no": {
                "value": "OLD123",
                "confidence": 0.74,
                "source_page": 1,
            },
            "expiry": {"value": None, "confidence": 0.0, "source_page": None},
        },
        overrides={"passport_no": "NEW123"},
    )

    rows = writer._correction_evidence_rows(plan, advance_to="routed")
    by_field = {row["field_name"]: row for row in rows}

    assert set(by_field) == {"name", "passport_no"}
    assert by_field["name"]["outcome"] == "approved"
    assert by_field["name"]["human_value"] == "Alice"
    assert by_field["passport_no"]["outcome"] == "corrected"
    assert by_field["passport_no"]["ai_value"] == "OLD123"
    assert by_field["passport_no"]["human_value"] == "NEW123"
    assert by_field["passport_no"]["ai_confidence"] == 0.74


def test_feedback_records_entity_override() -> None:
    plan = _plan(
        original_fields={},
        original_client_id=10,
        client_id=99,
    )

    rows = writer._correction_evidence_rows(plan, advance_to="routed")

    assert rows == [
        {
            "field_name": "__entity__",
            "ai_value": "10",
            "human_value": "99",
            "ai_confidence": 0.82,
            "outcome": "corrected",
            "model_id": "entity-resolution",
            "stage": "route",
            "rule_passed": None,
        }
    ]


def test_auto_attach_is_labelled_separately_from_human_approval() -> None:
    plan = _plan(
        original_fields={
            "passport_no": {
                "value": "AA123456",
                "confidence": 0.95,
                "source_page": 1,
            }
        }
    )

    rows = writer._correction_evidence_rows(plan, advance_to="auto_routed")

    assert len(rows) == 1
    assert rows[0]["outcome"] == "auto_committed"
    assert rows[0]["field_name"] == "passport_no"


def test_fieldless_commit_still_contributes_document_denominator() -> None:
    plan = _plan(original_fields={})

    rows = writer._correction_evidence_rows(plan, advance_to="routed")

    assert rows[0]["field_name"] == "__document__"
    assert rows[0]["outcome"] == "approved"
