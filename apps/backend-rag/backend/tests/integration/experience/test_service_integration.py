"""Integration tests for ExperienceService against a real SQLite Genome.

These exercise:
- Persistence across service instances (WAL durability)
- Coexistence with Genome skills in the shared store
- Concurrent record from multiple threads (write_lock correctness)
- get_by_id lookup used by the router layer
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from backend.services.experience.models import (
    TrajectoryQuery,
    TrajectoryRecord,
)
from backend.services.experience.service import ExperienceService


# ─── Persistence ──────────────────────────────────────────────────────


def test_trajectory_persists_across_service_instances(tmp_path):
    db = str(tmp_path / "shared.db")
    svc_a = ExperienceService(db_path=db)
    svc_a.record(TrajectoryRecord(
        trajectory_id="durable", cell="c1", outcome="success",
        procedure="must survive reopen",
    ))

    svc_b = ExperienceService(db_path=db)
    results = svc_b.query(TrajectoryQuery(query="survive"))
    assert len(results) == 1
    assert results[0].trajectory_id == "durable"


def test_trajectory_coexists_with_skill_entries(tmp_path):
    """Writing trajectories must not corrupt skill/pattern entries in the same DB."""
    db = str(tmp_path / "shared.db")
    svc = ExperienceService(db_path=db)

    # Use the underlying Genome directly to plant a skill.
    svc._genome.record_skill(
        cell="c1", skill_id="s1",
        procedure="classic consolidated technique",
        confidence=0.9,
    )
    svc.record(TrajectoryRecord(
        trajectory_id="t1", cell="c1", outcome="success",
        procedure="one-off episode",
    ))

    # Skill search still works and does not see the trajectory
    hits = svc._genome.search("consolidated")
    assert len(hits) == 1
    assert hits[0]["type"] == "skill"

    # Trajectory search does not see the skill
    trajs = svc.query(TrajectoryQuery(query="episode"))
    assert len(trajs) == 1
    assert trajs[0].trajectory_id == "t1"


# ─── Concurrency ──────────────────────────────────────────────────────


def test_concurrent_record_preserves_all_writes(tmp_path):
    """20 threads × 5 trajectories = 100 distinct rows, zero loss."""
    db = str(tmp_path / "concurrent.db")
    svc = ExperienceService(db_path=db)
    errors: list[Exception] = []

    def writer(tid: int) -> None:
        try:
            for i in range(5):
                svc.record(TrajectoryRecord(
                    trajectory_id=f"t_{tid}_{i}",
                    cell=f"cell_{tid % 3}",
                    outcome="success" if i % 2 == 0 else "partial",
                    procedure=f"thread {tid} step {i}",
                ))
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(writer, tid) for tid in range(20)]
        for f in as_completed(futures):
            f.result()

    assert errors == [], f"concurrent errors: {errors}"
    stats = svc.stats()
    assert stats["total"] == 100


# ─── Router hook: get_by_id ───────────────────────────────────────────


def test_get_by_id_returns_trajectory(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "db.sqlite"))
    svc.record(TrajectoryRecord(
        trajectory_id="abc", cell="c", outcome="success",
        procedure="lookup me by id", tokens=500,
    ))
    found = svc.get_by_id("abc")
    assert found is not None
    assert found.trajectory_id == "abc"
    assert found.tokens == 500


def test_get_by_id_returns_none_when_missing(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "db.sqlite"))
    assert svc.get_by_id("nope") is None


def test_get_by_id_ignores_non_trajectory_entries(tmp_path):
    """A skill row with the same id must not be returned as a trajectory."""
    svc = ExperienceService(db_path=str(tmp_path / "db.sqlite"))
    svc._genome.record_skill(cell="c", skill_id="shared_id", procedure="skill body")
    assert svc.get_by_id("shared_id") is None


# ─── Stats edge cases ────────────────────────────────────────────────


def test_stats_zero_when_empty(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "empty.db"))
    stats = svc.stats()
    assert stats["total"] == 0
    assert stats["by_outcome"] == {"success": 0, "failure": 0, "partial": 0}


def test_stats_scoped_by_cell(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "multi.db"))
    svc.record(TrajectoryRecord(
        trajectory_id="a1", cell="cell_a", outcome="success", procedure="p",
    ))
    svc.record(TrajectoryRecord(
        trajectory_id="b1", cell="cell_b", outcome="failure", procedure="p",
    ))
    assert svc.stats(cell="cell_a")["total"] == 1
    assert svc.stats(cell="cell_b")["total"] == 1
    assert svc.stats()["total"] == 2
