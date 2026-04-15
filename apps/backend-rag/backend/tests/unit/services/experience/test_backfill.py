"""Unit tests for backend.scripts.backfill_lam_to_experience.

Tests the pure-Python logic (outcome normalisation, trajectory construction,
dedup keys) without a live Qdrant. The Qdrant scroll is exercised via a
fake client in backfill_all().
"""
from __future__ import annotations

import pytest

from backend.scripts.backfill_lam_to_experience import (
    AMBIGUOUS_OUTCOMES,
    backfill_all,
    build_trajectory_record,
    normalize_outcome,
    trajectory_id_for_episode,
)
from backend.services.experience.service import ExperienceService


# ─── normalize_outcome — conservative mapping ─────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("success", "success"),
        ("SUCCESS", "success"),
        ("ok", "success"),
        ("succeeded", "success"),
        ("failure", "failure"),
        ("failed", "failure"),
        ("error", "failure"),
        ("partial", "partial"),
        ("partially_successful", "partial"),
    ],
)
def test_normalize_outcome_explicit_positive(raw: str, expected: str) -> None:
    assert normalize_outcome(raw) == expected


@pytest.mark.parametrize("raw", ["", "unknown", None, "?", "completed", "done", "maybe"])
def test_normalize_outcome_ambiguous_returns_none(raw) -> None:
    """Conservative rule: ambiguous or missing outcome → skip (returns None)."""
    assert normalize_outcome(raw) is None


def test_ambiguous_outcomes_documented() -> None:
    """The AMBIGUOUS_OUTCOMES set is the explicit allowlist of what we skip."""
    assert "completed" in AMBIGUOUS_OUTCOMES
    assert "done" in AMBIGUOUS_OUTCOMES


# ─── trajectory_id_for_episode — stable dedup key ────────────────────


def test_trajectory_id_is_prefixed():
    tid = trajectory_id_for_episode("abc-123")
    assert tid.startswith("lam:")
    assert "abc-123" in tid


def test_trajectory_id_stable():
    """Same episode_id always produces same trajectory_id (dedup correctness)."""
    assert trajectory_id_for_episode("x") == trajectory_id_for_episode("x")


# ─── build_trajectory_record — field wiring ──────────────────────────


def test_build_record_from_valid_episode():
    episode = {
        "id": "ep_1",
        "content": "Resolved visa query with KBLI 70209.",
        "agent": "lam_main",
        "tags": ["visa", "kbli"],
        "outcome": "success",
        "timestamp": "2026-04-01T10:00:00Z",
        "metadata": {"tokens": 2100, "duration_ms": 9000},
    }
    rec = build_trajectory_record(episode)
    assert rec is not None
    assert rec.trajectory_id == "lam:ep_1"
    assert rec.cell == "lam_main"
    assert rec.outcome == "success"
    assert rec.tokens == 2100
    assert rec.duration_ms == 9000
    assert "visa" in rec.tags


def test_build_record_skips_ambiguous_outcome():
    episode = {
        "id": "ep_2", "content": "x", "agent": "lam",
        "outcome": "completed",  # ambiguous
    }
    assert build_trajectory_record(episode) is None


def test_build_record_skips_empty_content():
    episode = {
        "id": "ep_3", "content": "", "agent": "lam", "outcome": "success",
    }
    assert build_trajectory_record(episode) is None


def test_build_record_handles_missing_metadata():
    episode = {
        "id": "ep_4", "content": "body", "agent": "lam", "outcome": "success",
    }
    rec = build_trajectory_record(episode)
    assert rec is not None
    assert rec.tokens is None
    assert rec.duration_ms is None
    assert rec.tags == []


def test_build_record_agent_fallback_when_missing():
    """Episodes without 'agent' default to 'lam_legacy' cell, never crash."""
    episode = {"id": "ep_5", "content": "x", "outcome": "success"}
    rec = build_trajectory_record(episode)
    assert rec is not None
    assert rec.cell == "lam_legacy"


# ─── backfill_all — orchestration with fake scroll source ────────────


class _FakeQdrantSource:
    """Minimal stand-in for a scroll iterator over LAM episodes."""

    def __init__(self, episodes: list[dict]) -> None:
        self._episodes = episodes

    def iter_episodes(self):
        yield from self._episodes


def test_backfill_records_only_explicit_outcomes(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "b.db"))
    source = _FakeQdrantSource([
        {"id": "a", "content": "good run", "agent": "lam", "outcome": "success"},
        {"id": "b", "content": "crashed", "agent": "lam", "outcome": "failed"},
        {"id": "c", "content": "done", "agent": "lam", "outcome": "completed"},  # skip
        {"id": "d", "content": "", "agent": "lam", "outcome": "success"},  # skip empty
        {"id": "e", "content": "try again", "agent": "lam", "outcome": "partial"},
    ])
    report = backfill_all(source, svc, dry_run=False)

    assert report["total_seen"] == 5
    assert report["recorded"] == 3
    assert report["skipped_ambiguous"] == 1
    assert report["skipped_empty"] == 1
    stats = svc.stats()
    assert stats["total"] == 3
    assert stats["by_outcome"]["success"] == 1
    assert stats["by_outcome"]["failure"] == 1
    assert stats["by_outcome"]["partial"] == 1


def test_backfill_is_idempotent(tmp_path):
    """Running twice on the same source does not duplicate rows."""
    svc = ExperienceService(db_path=str(tmp_path / "b.db"))
    source = _FakeQdrantSource([
        {"id": "a", "content": "x", "agent": "lam", "outcome": "success"},
        {"id": "b", "content": "y", "agent": "lam", "outcome": "failed"},
    ])
    backfill_all(source, svc, dry_run=False)
    backfill_all(source, svc, dry_run=False)
    stats = svc.stats()
    assert stats["total"] == 2


def test_backfill_dry_run_does_not_write(tmp_path):
    svc = ExperienceService(db_path=str(tmp_path / "b.db"))
    source = _FakeQdrantSource([
        {"id": "a", "content": "x", "agent": "lam", "outcome": "success"},
    ])
    report = backfill_all(source, svc, dry_run=True)
    assert report["recorded"] == 0
    assert report["would_record"] == 1
    assert svc.stats()["total"] == 0
