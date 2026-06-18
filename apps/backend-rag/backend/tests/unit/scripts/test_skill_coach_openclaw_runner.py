"""Tests for the Skill Coach OpenClaw cycle runner."""

from __future__ import annotations

import json

from cell_core.genome import Genome


def test_runner_aggregates_and_evaluates_skill_coach_cycle(tmp_path):
    from backend.scripts.skill_coach_openclaw_runner import run_skill_coach_cycle

    db_path = tmp_path / "experience.db"
    proposals_path = tmp_path / "skill_creation_proposals.jsonl"
    evidence_path = tmp_path / "skill_coach_evidence.jsonl"

    genome = Genome(db_path=str(db_path))
    for i in range(3):
        genome.record_trajectory(
            cell="rag",
            trajectory_id=f"t{i}",
            outcome="success",
            procedure=f"retrieve clean context iteration {i}",
            tags=["retrieval"],
        )

    summary = run_skill_coach_cycle(
        db_path=str(db_path),
        proposals_path=str(proposals_path),
        evidence_path=str(evidence_path),
        min_cluster_size=3,
        window_days=7,
        min_support=3,
    )

    assert summary["status"] == "ok"
    assert summary["proposals_written"] == 1
    assert summary["evidence_written"] == 1
    assert summary["evidence_by_status"] == {"shadow_eligible": 1}
    assert proposals_path.exists()
    assert evidence_path.exists()

    evidence = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    assert evidence[0]["status"] == "shadow_eligible"
    assert evidence[0]["support_count"] == 3
    assert "retrieve clean context" in evidence[0]["procedure"]
    assert "customer raw content" not in evidence_path.read_text()


def test_runner_can_skip_aggregation_and_only_refresh_evidence(tmp_path):
    from backend.scripts.skill_coach_openclaw_runner import run_skill_coach_cycle

    db_path = tmp_path / "experience.db"
    proposals_path = tmp_path / "skill_creation_proposals.jsonl"
    evidence_path = tmp_path / "skill_coach_evidence.jsonl"

    genome = Genome(db_path=str(db_path))
    for i in range(2):
        genome.record_trajectory(
            cell="crm",
            trajectory_id=f"crm-{i}",
            outcome="success",
            procedure=f"normalise contact field iteration {i}",
            tags=["crm", "normalise"],
        )

    proposals_path.write_text(
        json.dumps(
            {
                "cell": "crm",
                "skill_id": "crm:agg_normalise",
                "tags": ["crm", "normalise"],
                "procedure": "Normalise contact fields before merge.",
                "precondition": "CRM intake has repeated contact-shape drift.",
                "success_criterion": "Contact merge completes without duplicated fields.",
                "confidence": 0.45,
                "example_trajectory_ids": ["crm-0", "crm-1"],
            }
        )
        + "\n"
    )

    summary = run_skill_coach_cycle(
        db_path=str(db_path),
        proposals_path=str(proposals_path),
        evidence_path=str(evidence_path),
        min_support=3,
        run_aggregator=False,
    )

    assert summary["status"] == "ok"
    assert summary["aggregator_ran"] is False
    assert summary["proposals_written"] == 1
    assert summary["evidence_written"] == 1
    assert summary["evidence_by_status"] == {"proposed": 1}


def test_cli_writes_single_json_summary(tmp_path, capsys):
    from backend.scripts.skill_coach_openclaw_runner import main

    db_path = tmp_path / "experience.db"
    proposals_path = tmp_path / "skill_creation_proposals.jsonl"
    evidence_path = tmp_path / "skill_coach_evidence.jsonl"
    proposals_path.write_text("")

    rc = main(
        [
            "--db-path",
            str(db_path),
            "--proposals",
            str(proposals_path),
            "--out",
            str(evidence_path),
            "--skip-aggregator",
        ]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert output["aggregator_ran"] is False
    assert output["proposals_written"] == 0
    assert output["evidence_written"] == 0
