"""Tests for backend/scripts/experience_to_skill_aggregator.py.

The job scans successful trajectories in the Experience Library and
proposes (never creates) a skill when a cluster of ≥N similar episodes
from the same cell lands within a rolling window.

Cluster key (deliberately conservative): (cell, sorted_tags_tuple). We only
aggregate trajectories that already agree on tags — no NLP matching.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.scripts.experience_to_skill_aggregator import (
    cluster_trajectories,
    propose_skills_from_clusters,
    main,
)


def _traj(
    cell: str = "curator",
    outcome: str = "success",
    tags: list[str] | None = None,
    trajectory_id: str = "t1",
    procedure: str = "published asset cleanly",
    days_ago: int = 0,
) -> dict:
    vf = (
        datetime.now(timezone.utc).date() - timedelta(days=days_ago)
    ).isoformat()
    return {
        "id": trajectory_id,
        "cell_origin": cell,
        "type": "trajectory",
        "outcome": outcome,
        "procedure": procedure,
        "tags": json.dumps(tags or []),
        "valid_from": vf,
        "valid_to": None,
        "confidence": 0.7,
    }


# ─── cluster_trajectories ─────────────────────────────────────────


def test_cluster_by_cell_and_tags():
    trajs = [
        _traj(cell="curator", tags=["ig", "carousel"], trajectory_id=f"t{i}")
        for i in range(12)
    ] + [
        _traj(cell="curator", tags=["wa"], trajectory_id=f"w{i}")
        for i in range(3)
    ] + [
        _traj(cell="other", tags=["ig", "carousel"], trajectory_id=f"o{i}")
        for i in range(5)
    ]
    clusters = cluster_trajectories(trajs)
    assert ("curator", ("carousel", "ig")) in clusters
    assert len(clusters[("curator", ("carousel", "ig"))]) == 12
    assert ("curator", ("wa",)) in clusters
    assert ("other", ("carousel", "ig")) in clusters


def test_cluster_skips_untagged_trajectories():
    """Trajectories with no tags can't be clustered safely — skip them."""
    trajs = [_traj(tags=[], trajectory_id=f"n{i}") for i in range(20)]
    clusters = cluster_trajectories(trajs)
    assert clusters == {}


def test_cluster_only_success_outcome():
    """Failure / partial trajectories must not contribute to skill proposals."""
    trajs = [
        _traj(tags=["ig"], outcome="success", trajectory_id="ok"),
        _traj(tags=["ig"], outcome="failure", trajectory_id="ko"),
        _traj(tags=["ig"], outcome="partial", trajectory_id="part"),
    ]
    clusters = cluster_trajectories(trajs)
    key = ("curator", ("ig",))
    assert key in clusters
    assert len(clusters[key]) == 1
    assert clusters[key][0]["id"] == "ok"


def test_cluster_window_excludes_old_trajectories():
    """Trajectories older than window_days must not appear in clusters."""
    trajs = [
        _traj(tags=["ig"], trajectory_id=f"t{i}", days_ago=i)
        for i in range(15)
    ]
    clusters = cluster_trajectories(trajs, window_days=7)
    key = ("curator", ("ig",))
    assert key in clusters
    # days_ago 0..6 inclusive = 7 entries
    assert len(clusters[key]) == 7


# ─── propose_skills_from_clusters ─────────────────────────────────


def test_proposal_emitted_when_threshold_met():
    trajs = [
        _traj(tags=["ig"], trajectory_id=f"t{i}",
              procedure=f"published ig asset iteration {i}")
        for i in range(10)
    ]
    clusters = cluster_trajectories(trajs)
    proposals = propose_skills_from_clusters(clusters, min_cluster_size=10)
    assert len(proposals) == 1
    p = proposals[0]
    assert p["cell"] == "curator"
    assert p["tags"] == ["ig"]
    assert p["n_trajectories"] == 10
    assert "skill_id" in p
    assert p["skill_id"].startswith("curator:")
    assert "procedure" in p
    # Proposed skill must carry a non-empty aggregate procedure + example ids.
    assert p["procedure"]
    assert len(p["example_trajectory_ids"]) <= 5
    assert set(p["example_trajectory_ids"]).issubset({f"t{i}" for i in range(10)})


def test_proposal_not_emitted_below_threshold():
    trajs = [
        _traj(tags=["ig"], trajectory_id=f"t{i}")
        for i in range(5)
    ]
    clusters = cluster_trajectories(trajs)
    proposals = propose_skills_from_clusters(clusters, min_cluster_size=10)
    assert proposals == []


def test_proposal_default_confidence_lower_than_curated_seed():
    """Aggregated proposals are auto-generated: confidence must stay below
    the hand-picked seed default (0.6)."""
    trajs = [_traj(tags=["ig"], trajectory_id=f"t{i}") for i in range(10)]
    clusters = cluster_trajectories(trajs)
    proposals = propose_skills_from_clusters(clusters, min_cluster_size=10)
    assert proposals[0]["confidence"] <= 0.5


# ─── main() smoke ─────────────────────────────────────────────────


def test_main_writes_proposals_jsonl_when_cluster_meets_threshold(tmp_path):
    from cell_core.genome import Genome

    db = tmp_path / "trajectories.db"
    g = Genome(db_path=str(db))
    for i in range(10):
        g.record_trajectory(
            cell="curator",
            trajectory_id=f"t{i}",
            outcome="success",
            procedure=f"published ig asset iteration {i}",
            tags=["ig"],
        )

    out = tmp_path / "skill_creation_proposals.jsonl"
    rc = main([
        "--db-path", str(db),
        "--out", str(out),
        "--min-cluster-size", "10",
        "--window-days", "7",
    ])
    assert rc == 0
    assert out.exists()
    lines = [line for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    proposal = json.loads(lines[0])
    assert proposal["cell"] == "curator"
    assert proposal["n_trajectories"] == 10


def test_main_no_proposals_writes_empty_file(tmp_path):
    from cell_core.genome import Genome

    db = tmp_path / "empty.db"
    g = Genome(db_path=str(db))
    # One-off trajectory: below threshold.
    g.record_trajectory(
        cell="c", trajectory_id="solo", outcome="success",
        procedure="x", tags=["ig"],
    )
    out = tmp_path / "proposals.jsonl"
    rc = main([
        "--db-path", str(db), "--out", str(out),
        "--min-cluster-size", "10", "--window-days", "7",
    ])
    assert rc == 0
    if out.exists():
        assert out.read_text().strip() == ""
