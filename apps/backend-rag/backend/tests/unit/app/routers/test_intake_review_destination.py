from backend.app.routers.intake_review import _apply_document_destination_override
from backend.services.intake.writer import CommitPlan, WriteOp


def _plan() -> CommitPlan:
    return CommitPlan(
        proposal_id=42,
        queue_id=7,
        client_id=21,
        practice_id=365,
        decision="AUTO_ATTACH",
        doc_type="passport",
        committed_by="adit@balizero.com",
        idempotency_key="ik:test",
        payload={
            "document_type": "passport",
            "document_category": "immigration",
            "file_id": "drive-file",
        },
        ops=[
            WriteOp(
                table="documents",
                verb="UPSERT",
                values={
                    "client_id": 21,
                    "document_type": "passport",
                    "document_category": "immigration",
                },
            ),
            WriteOp(
                table="practices.documents[]",
                verb="APPEND_JSON",
                values={
                    "practice_id": 365,
                    "name": "passport",
                    "status": "received",
                },
            ),
        ],
    )


def test_destination_override_updates_payload_and_write_ops() -> None:
    plan = _plan()

    _apply_document_destination_override(
        plan,
        document_category="pma",
        document_subtype="nib",
    )

    assert plan.doc_type == "nib"
    assert plan.payload["document_type"] == "nib"
    assert plan.payload["document_category"] == "pma"
    assert plan.ops[0].values["document_type"] == "nib"
    assert plan.ops[0].values["document_category"] == "pma"
    assert plan.ops[1].values["name"] == "nib"


def test_destination_override_ignores_empty_values() -> None:
    plan = _plan()

    _apply_document_destination_override(
        plan,
        document_category=" ",
        document_subtype=None,
    )

    assert plan.doc_type == "passport"
    assert plan.payload["document_type"] == "passport"
    assert plan.payload["document_category"] == "immigration"
    assert plan.ops[0].values["document_type"] == "passport"
    assert plan.ops[0].values["document_category"] == "immigration"
    assert plan.ops[1].values["name"] == "passport"
