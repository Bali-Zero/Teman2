"""Pure aggregation tests for the Visa Oracle SHADOW evidence gate."""

from __future__ import annotations

import uuid
from datetime import timedelta

from backend.services.visa_engine.models import RulePack
from backend.services.visa_engine.shadow_evidence import (
    REQUIRED_INTERVIEW_CATEGORIES,
    evaluate_shadow_evidence,
)
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader


def _green_fixture() -> tuple[list[dict[str, object]], RulePack, uuid.UUID]:
    pack = RulePack.model_validate(gold_loader.load_rule_pack_raw())
    db_pack_id = uuid.uuid5(pack.payload.rule_pack_id, "database-row")
    product_template = pack.payload.products[0]
    products = tuple(
        product_template.model_copy(
            update={
                "product_version_id": uuid.uuid5(pack.payload.rule_pack_id, f"product-{index}"),
                "product_code": f"X{index:02d}",
            }
        )
        for index in range(30)
    )
    pack = pack.model_copy(
        update={"payload": pack.payload.model_copy(update={"products": products})}
    )
    source_id = str(pack.payload.source_records[0].source_record_id)
    categories = sorted(REQUIRED_INTERVIEW_CATEGORIES)
    rows: list[dict[str, object]] = []
    for index in range(1_000):
        evaluated_at = gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=index % 7, seconds=index)
        rows.append(
            {
                "request_fingerprint": index.to_bytes(32, "big"),
                "request_category": categories[index % len(categories)],
                "candidate_summary": [
                    {
                        "product_version_id": str(products[index % 30].product_version_id),
                        "product_code": str(products[index % 30].product_code),
                    }
                ],
                "grounding_summary": [
                    {
                        "claim_kind": "VERDICT",
                        "claim_code": "SUPPORTED_CANDIDATES",
                        "source_record_ids": [source_id],
                    }
                ],
                "citations": [{"source_record_id": source_id}],
                "verdict": "SUPPORTED_CANDIDATES",
                "rule_pack_id": db_pack_id,
                "ruleset_activation_id": uuid.uuid5(pack.payload.rule_pack_id, "shadow-activation"),
                "rule_pack_sha256": bytes.fromhex(pack.payload_sha256),
                "effective_at": evaluated_at,
                "observed_at": evaluated_at,
                "evaluated_at": evaluated_at,
            }
        )
    return rows, pack, db_pack_id


def test_green_shadow_projection_still_cannot_arm_enforce() -> None:
    rows, pack, db_pack_id = _green_fixture()
    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-a"]["green"] is True
    assert gates["G-c"]["green"] is True
    assert gates["G-b"]["status"] == "UNMEASURED"
    assert gates["G-d"]["status"] == "UNMEASURED"
    assert report["enforce_ready"] is False
    assert report["gate_status"] == "RED"


def test_duplicate_request_and_ungrounded_verdict_fail_closed() -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[-1]["request_fingerprint"] = rows[0]["request_fingerprint"]
    rows[-1]["candidate_summary"] = [
        {
            "product_version_id": str(uuid.uuid4()),
            "product_code": "X29",
        }
    ]
    rows[-1]["ruleset_activation_id"] = None
    rows[-1]["rule_pack_sha256"] = None
    rows[0]["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "SUPPORTED_CANDIDATES",
            "source_record_ids": [],
        }
    ]
    rows[0]["citations"] = []

    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-a"]["green"] is False
    assert gates["G-a"]["distinct_requests"] == 999
    assert gates["G-a"]["invalid_candidate_bindings"] == 1
    assert gates["G-c"]["green"] is False
    assert gates["G-c"]["decisions_without_citations"] == 1
    assert gates["G-c"]["missing_ruleset_activations"] == 1
    assert gates["G-c"]["missing_rule_pack_digests"] == 1
    assert gates["G-c"]["ungrounded_claims"] == 1


def test_citationless_needs_input_abstention_passes_grounding() -> None:
    rows, pack, db_pack_id = _green_fixture()
    rows[0]["verdict"] = "NEEDS_INPUT"
    rows[0]["candidate_summary"] = []
    rows[0]["grounding_summary"] = [
        {
            "claim_kind": "VERDICT",
            "claim_code": "NEEDS_INPUT",
            "source_record_ids": [],
        }
    ]
    rows[0]["citations"] = []

    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=gold_loader.GOLD_EFFECTIVE_AT,
        window_end=gold_loader.GOLD_EFFECTIVE_AT + timedelta(days=8),
    )

    gates = report["gates"]
    assert gates["G-c"]["green"] is True
    assert gates["G-c"]["decisions_without_citations"] == 0
    assert gates["G-c"]["ungrounded_claims"] == 0


def test_window_shorter_than_seven_full_days_fails_volume() -> None:
    rows, pack, db_pack_id = _green_fixture()
    start = gold_loader.GOLD_EFFECTIVE_AT
    report = evaluate_shadow_evidence(
        rows,
        {db_pack_id: pack.payload},
        window_start=start,
        window_end=start + timedelta(days=6, hours=23),
    )

    gate_a = report["gates"]["G-a"]
    assert gate_a["longest_consecutive_utc_day_streak"] == 7
    assert gate_a["window_duration_hours"] == 167
    assert gate_a["green"] is False


def test_empty_window_is_red_not_vacuously_green() -> None:
    start = gold_loader.GOLD_EFFECTIVE_AT
    report = evaluate_shadow_evidence(
        [],
        {},
        window_start=start,
        window_end=start + timedelta(days=8),
    )

    assert report["gates"]["G-a"]["green"] is False
    assert report["gates"]["G-c"]["green"] is False
    assert report["enforce_ready"] is False
