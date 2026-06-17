"""Tests for the Skill Coach proposal-evaluation CLI."""

from __future__ import annotations

import json

from cell_core.genome import Genome

from backend.scripts.skill_coach_evaluate_proposals import main


def test_cli_writes_redacted_evidence_cards(tmp_path):
    db_path = tmp_path / "experience.db"
    proposals_path = tmp_path / "proposals.jsonl"
    out_path = tmp_path / "evidence.jsonl"

    genome = Genome(db_path=str(db_path))
    for i in range(3):
        genome.record_trajectory(
            cell="rag",
            trajectory_id=f"t{i}",
            outcome="success",
            procedure=f"customer raw content {i}",
            tags=["retrieval"],
        )

    proposals_path.write_text(
        json.dumps(
            {
                "cell": "rag",
                "skill_id": "rag:agg_retrieval",
                "tags": ["retrieval"],
                "procedure": "Use retrieval pattern.",
                "precondition": "rag retrieval run",
                "success_criterion": "success repeats",
                "confidence": 0.45,
                "example_trajectory_ids": ["t0", "t1", "t2"],
            }
        )
        + "\n"
    )

    rc = main(
        [
            "--db-path",
            str(db_path),
            "--proposals",
            str(proposals_path),
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    payload = out_path.read_text()
    assert "shadow_eligible" in payload
    assert "customer raw content" not in payload
