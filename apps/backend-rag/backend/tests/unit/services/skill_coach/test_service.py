"""Unit tests for the Skill Coach dry-run evaluator."""

from __future__ import annotations

import json
import logging

from backend.services.skill_coach.models import SkillCoachEvidence
from backend.services.skill_coach.service import SkillCoachService, _fully_redacted_card


def _proposal(**overrides):
    base = {
        "cell": "rag",
        "skill_id": "rag:agg_retrieval",
        "tags": ["retrieval", "rerank"],
        "procedure": "Use the validated retrieval rerank sequence.",
        "precondition": "Cell 'rag' running with tags ['retrieval', 'rerank'].",
        "success_criterion": "Outcome reaches success repeatedly.",
        "confidence": 0.9,
        "example_trajectory_ids": ["t1", "t2", "t3"],
    }
    base.update(overrides)
    return base


def _trajectory(
    trajectory_id: str,
    outcome: str = "success",
    tags: list[str] | str | None = None,
    procedure: str = "raw trajectory body must not leak",
):
    return {
        "id": trajectory_id,
        "cell_origin": "rag",
        "outcome": outcome,
        "tags": tags if tags is not None else ["retrieval", "rerank"],
        "procedure": procedure,
    }


def test_shadow_eligible_when_three_successes_support_the_proposal(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(),
        [
            _trajectory("t1"),
            _trajectory("t2"),
            _trajectory("t3"),
        ],
    )

    assert card.status == "shadow_eligible"
    assert card.support_count == 3
    assert card.hurt_count == 0
    assert card.false_apply_count == 0
    assert card.confidence == 0.5


def test_failure_history_rejects_the_proposal(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(),
        [
            _trajectory("t1"),
            _trajectory("t2"),
            _trajectory("bad", outcome="failure"),
        ],
    )

    assert card.status == "rejected"
    assert card.support_count == 2
    assert card.hurt_count == 1
    assert card.false_apply_count == 1


def test_partial_history_counts_hurt_without_false_apply(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(),
        [
            _trajectory("t1"),
            _trajectory("partial", outcome="partial"),
        ],
    )

    assert card.status == "rejected"
    assert card.hurt_count == 1
    assert card.false_apply_count == 0


def test_low_support_stays_proposed(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(),
        [
            _trajectory("t1"),
            _trajectory("t2"),
        ],
    )

    assert card.status == "proposed"
    assert card.support_count == 2


def test_redaction_rejects_clear_customer_data_without_echoing_the_value(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(procedure="Email the customer at customer@example.test."),
        [
            _trajectory("t1"),
            _trajectory("t2"),
            _trajectory("t3"),
        ],
    )

    payload = card.model_dump_json()
    assert card.status == "rejected"
    assert card.redaction_status == "failed"
    assert "email" in card.redaction_findings
    assert "customer@example.test" not in payload


def test_redaction_scans_every_output_field_before_serialization(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(
            cell="rag customer@example.test",
            skill_id="rag:+62-812-3456-7890",
            tags=["retrieval", "NPWP 09.254.294.3-407.000"],
            procedure="Use retrieval pattern.",
            precondition="clean",
            success_criterion="clean",
        ),
        [],
    )

    payload = card.model_dump_json()
    assert card.status == "rejected"
    assert card.redaction_status == "failed"
    assert "customer@example.test" not in payload
    assert "+62-812-3456-7890" not in payload
    assert "09.254.294.3-407.000" not in payload


def test_fully_redacted_card_zeroes_correlation_counters():
    card = SkillCoachEvidence(
        proposal_id="p",
        skill_id="s",
        cell="rag",
        tags=["retrieval"],
        scope="Project",
        status="shadow_eligible",
        source_trajectory_ids=["t1"],
        preconditions="pre",
        procedure="body",
        success_criteria="done",
        confidence=0.5,
        redaction_status="passed",
        redaction_findings=[],
        support_count=9,
        hurt_count=2,
        false_apply_count=1,
        neutral_count=4,
        history_sample_size=15,
        decision_reason="eligible",
        created_at="2026-06-16T00:00:00+00:00",
    )

    redacted = _fully_redacted_card(
        card=card,
        findings=["email"],
        reason="rejected: serialized evidence card contains customer-data markers",
    )

    assert redacted.support_count == 0
    assert redacted.hurt_count == 0
    assert redacted.false_apply_count == 0
    assert redacted.neutral_count == 0
    assert redacted.history_sample_size == 0


def test_evidence_card_does_not_include_raw_trajectory_payload(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))

    card = service.evaluate_proposal(
        _proposal(),
        [
            _trajectory("t1", procedure="CLIENT RAW SECRET 123"),
            _trajectory("t2", procedure="CLIENT RAW SECRET 456"),
            _trajectory("t3", procedure="CLIENT RAW SECRET 789"),
        ],
    )

    payload = card.model_dump_json()
    assert "CLIENT RAW SECRET" not in payload
    assert card.source_trajectory_ids == ["t1", "t2", "t3"]


def test_source_trajectory_ids_must_match_history_and_are_capped(tmp_path):
    service = SkillCoachService(evidence_path=str(tmp_path / "evidence.jsonl"))
    trajectories = [_trajectory(f"t{i}") for i in range(25)]

    card = service.evaluate_proposal(
        _proposal(
            example_trajectory_ids=["t0", "missing", "customer@example.test", *[f"t{i}" for i in range(1, 25)]]
        ),
        trajectories,
    )

    assert "missing" not in card.source_trajectory_ids
    assert "customer@example.test" not in card.source_trajectory_ids
    assert len(card.source_trajectory_ids) == 20


def test_write_and_read_creation_proposals_filters_status(tmp_path):
    evidence_path = tmp_path / "evidence.jsonl"
    service = SkillCoachService(evidence_path=str(evidence_path))
    cards = [
        service.evaluate_proposal(_proposal(skill_id="a"), [_trajectory("a1")]),
        service.evaluate_proposal(
            _proposal(skill_id="b"),
            [_trajectory("b1"), _trajectory("b2"), _trajectory("b3")],
        ),
    ]

    service.write_evidence(cards)

    shadow = service.creation_proposals(status="shadow_eligible")
    assert len(shadow) == 1
    assert shadow[0]["skill_id"] == "b"
    assert json.loads(evidence_path.read_text().splitlines()[0])["skill_id"] == "a"


def test_creation_proposals_skips_unsafe_manual_jsonl_rows(tmp_path):
    evidence_path = tmp_path / "evidence.jsonl"
    service = SkillCoachService(evidence_path=str(evidence_path))
    safe_card = service.evaluate_proposal(
        _proposal(),
        [_trajectory("t1"), _trajectory("t2"), _trajectory("t3")],
    )
    evidence_path.write_text(
        json.dumps(safe_card.model_dump(mode="json"))
        + "\n"
        + json.dumps(
            {
                **safe_card.model_dump(mode="json"),
                "skill_id": "unsafe-customer@example.test",
            }
        )
        + "\n"
    )

    rows = service.creation_proposals()

    assert len(rows) == 1
    assert rows[0]["skill_id"] == "rag:agg_retrieval"


def test_malformed_jsonl_warning_never_logs_raw_line(tmp_path, caplog):
    evidence_path = tmp_path / "evidence.jsonl"
    evidence_path.write_text('{"skill_id": "customer@example.test"\n')
    service = SkillCoachService(evidence_path=str(evidence_path))

    with caplog.at_level(logging.WARNING):
        assert service.creation_proposals() == []

    assert "customer@example.test" not in caplog.text
