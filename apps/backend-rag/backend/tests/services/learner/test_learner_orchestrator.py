"""Tests for LearnerOrchestrator — sweep + classify + record."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.learner.genome_adapter import (
    GenomeAdapter,
    ScarEntry,
    SkillEntry,
)
from backend.services.learner.learner_orchestrator import (
    LearnerOrchestrator,
)
from backend.services.learner.score_calculator import ScoreCalculator
from backend.services.measurer.base import (
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LEADS_ATTRIBUTED,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
)
from backend.services.war_room.models import (
    DraftStatus,
    RejectionReason,
    WarRoomDraft,
)

# ── Fakes ─────────────────────────────────────────────────────


@dataclass
class _FakeGenomeAdapter(GenomeAdapter):
    skills: list[SkillEntry] = field(default_factory=list)
    scars: list[ScarEntry] = field(default_factory=list)

    def __init__(self) -> None:
        self.genome = object()  # pretend present
        self.cell = "war_room"
        self.skills = []
        self.scars = []

    @property
    def available(self) -> bool:
        return True

    async def record_skill(self, entry: SkillEntry) -> str:
        self.skills.append(entry)
        return "inserted"

    async def record_scar(self, entry: ScarEntry) -> str:
        self.scars.append(entry)
        return "inserted"


def _post_row(
    *,
    hours_ago: float = 80.0,
    platform: str = "instagram",
    register: str | None = "analitico",
) -> dict:
    return {
        "id": uuid4(),
        "draft_id": uuid4(),
        "platform": platform,
        "post_external_id": "ig-" + str(uuid4())[:6],
        "post_url": "https://x/y",
        "register": register,
        "published_at": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        "final_text": "caption",
    }


def _draft(
    *,
    status: DraftStatus = DraftStatus.APPROVED,
    rejection_reason: str | None = None,
) -> WarRoomDraft:
    now = datetime.now(timezone.utc)
    return WarRoomDraft(
        id=uuid4(),
        topic="t",
        status=status,
        rejection_reason=rejection_reason,
        created_at=now,
        updated_at=now,
    )


def _metrics_high() -> dict[str, float]:
    """Values that should push composite above p70.

    Breakdown with norm_reach=1.0:
      0.35*1.0 + 0.25*0.35 + 0.25*1.0 + 0.15*0.25
      = 0.35 + 0.0875 + 0.25 + 0.0375 = 0.725 > 0.70
    """
    return {
        METRIC_REACH: 10000,
        METRIC_IMPRESSIONS: 10000,
        METRIC_LIKES: 2500,
        METRIC_COMMENTS: 500,
        METRIC_SHARES: 500,
        METRIC_SAVES: 2500,
        METRIC_LEADS_ATTRIBUTED: 20,
    }


def _metrics_low() -> dict[str, float]:
    """Values that should push composite below p20."""
    return {
        METRIC_REACH: 10,
        METRIC_IMPRESSIONS: 10000,
        METRIC_LIKES: 1,
        METRIC_COMMENTS: 0,
        METRIC_SHARES: 0,
        METRIC_SAVES: 0,
        METRIC_LEADS_ATTRIBUTED: 0,
    }


def _metrics_partial() -> dict[str, float]:
    """Missing reach → incomplete."""
    return {
        METRIC_IMPRESSIONS: 10000,
        METRIC_LIKES: 100,
        METRIC_COMMENTS: 5,
        METRIC_SHARES: 5,
        METRIC_SAVES: 50,
        METRIC_LEADS_ATTRIBUTED: 3,
    }


@pytest.fixture
def repo_genome():
    repo = AsyncMock()
    repo.fetch_safe = AsyncMock(return_value=[])
    repo.get_draft = AsyncMock(return_value=_draft(status=DraftStatus.APPROVED))
    genome = _FakeGenomeAdapter()
    return repo, genome


def _make_orchestrator(repo, genome) -> LearnerOrchestrator:
    return LearnerOrchestrator(
        repo=repo,
        genome=genome,
        calculator=ScoreCalculator(),
        skill_threshold=0.7,
        scar_threshold=0.2,
    )


async def _stub_metric_fetch(
    repo,
    *,
    posts: list[dict],
    metrics_for_post: dict[Any, dict[str, float]],
    reach_history_by_platform: dict[str, list[float]] | None = None,
) -> None:
    """Wire repo.fetch_safe to return the right rows depending on the SQL."""
    reach_history_by_platform = reach_history_by_platform or {}

    async def side_effect(query: str, *args):
        q = query.strip()
        if "FROM war_room_posts" in q and "WHERE published_at" in q:
            return posts
        if "FROM war_room_metrics m" in q and "JOIN war_room_posts p" in q:
            platform = args[0]
            return [{"value": v} for v in reach_history_by_platform.get(platform, [])]
        if "FROM war_room_metrics" in q and "WHERE post_id" in q:
            post_id = args[0]
            metrics = metrics_for_post.get(post_id, {})
            return [
                {
                    "metric_name": k,
                    "value": v,
                    "source": "meta_graph",
                    "collected_at": datetime.now(timezone.utc),
                }
                for k, v in metrics.items()
            ]
        return []

    repo.fetch_safe = AsyncMock(side_effect=side_effect)


# ── Sweep behaviour ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sweep_empty_posts(repo_genome):
    repo, genome = repo_genome
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert result.posts_considered == 0
    assert result.skills_recorded == 0
    assert result.scars_recorded == 0


@pytest.mark.asyncio
async def test_sweep_high_score_records_skill(repo_genome):
    repo, genome = repo_genome
    row = _post_row()
    await _stub_metric_fetch(
        repo,
        posts=[row],
        metrics_for_post={row["id"]: _metrics_high()},
        reach_history_by_platform={
            "instagram": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
        },
    )
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert result.skills_recorded == 1
    assert result.scars_recorded == 0
    assert len(genome.skills) == 1
    sk = genome.skills[0]
    assert sk.skill_id.startswith("war_room:analitico:instagram:")
    assert sk.domain == "war_room"


@pytest.mark.asyncio
async def test_sweep_low_score_records_scar(repo_genome):
    repo, genome = repo_genome
    row = _post_row()
    await _stub_metric_fetch(
        repo,
        posts=[row],
        metrics_for_post={row["id"]: _metrics_low()},
        reach_history_by_platform={
            "instagram": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
        },
    )
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert result.scars_recorded == 1
    assert result.skills_recorded == 0
    assert len(genome.scars) == 1
    assert genome.scars[0].scar_id.startswith("war_room_scar:low_score:instagram:")


@pytest.mark.asyncio
async def test_sweep_incomplete_counted_not_recorded(repo_genome):
    repo, genome = repo_genome
    row = _post_row()
    await _stub_metric_fetch(
        repo,
        posts=[row],
        metrics_for_post={row["id"]: _metrics_partial()},
    )
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert result.incomplete == 1
    assert result.skills_recorded == 0
    assert result.scars_recorded == 0


# ── Zero-rejected short-circuit ────────────────────────────────


@pytest.mark.asyncio
async def test_rejected_by_zero_always_records_scar(repo_genome):
    repo, genome = repo_genome
    row = _post_row()
    repo.get_draft = AsyncMock(return_value=_draft(
        status=DraftStatus.REJECTED,
        rejection_reason=RejectionReason.TONE.value,
    ))
    await _stub_metric_fetch(
        repo,
        posts=[row],
        metrics_for_post={row["id"]: _metrics_high()},  # even with great metrics
        reach_history_by_platform={
            "instagram": [100, 500, 1000, 1500, 2000, 2500],
        },
    )
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert result.scars_recorded == 1
    scar = genome.scars[0]
    assert "tone" in scar.precondition
    assert scar.scar_id.startswith("war_room_scar:zero_rejected:tone:")


@pytest.mark.asyncio
async def test_sla_expired_does_not_trigger_zero_scar(repo_genome):
    """Drafts expired via SLA are different from Zero's active rejection."""
    repo, genome = repo_genome
    row = _post_row()
    repo.get_draft = AsyncMock(return_value=_draft(
        status=DraftStatus.REJECTED,
        rejection_reason=RejectionReason.SLA_EXPIRED.value,
    ))
    await _stub_metric_fetch(
        repo,
        posts=[row],
        metrics_for_post={row["id"]: _metrics_high()},
        reach_history_by_platform={
            "instagram": [100, 500, 1000, 1500, 2000, 2500],
        },
    )
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    # high metrics → skill recorded; no zero-rejection scar
    assert result.skills_recorded == 1
    assert result.scars_recorded == 0


# ── Graceful failures ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_posts_failure_surfaces_error_no_crash(repo_genome):
    repo, genome = repo_genome
    repo.fetch_safe = AsyncMock(side_effect=RuntimeError("pg down"))
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert any("eligible_posts" in e for e in result.errors)
    assert result.skills_recorded == 0
    assert result.scars_recorded == 0


@pytest.mark.asyncio
async def test_reach_history_failure_does_not_abort_post_processing(repo_genome):
    repo, genome = repo_genome
    row = _post_row()

    async def side_effect(query, *args):
        q = query.strip()
        if "FROM war_room_posts" in q and "WHERE published_at" in q:
            return [row]
        if "JOIN war_room_posts" in q:
            raise RuntimeError("reach history down")
        if "FROM war_room_metrics" in q and "WHERE post_id" in q:
            return [
                {
                    "metric_name": k,
                    "value": v,
                    "source": "meta_graph",
                    "collected_at": datetime.now(timezone.utc),
                }
                for k, v in _metrics_high().items()
            ]
        return []

    repo.fetch_safe = AsyncMock(side_effect=side_effect)
    orch = _make_orchestrator(repo, genome)
    result = await orch.sweep_once()
    assert any("reach_history" in e for e in result.errors)
    # processing continued — skill recorded with missing reach history,
    # which normalises to 0.5 (median fallback), so result depends on metrics
    assert result.posts_considered == 1
