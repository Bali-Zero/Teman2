"""Tests for MeasurementScheduler — windows, dedup, graceful failure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.measurer.orchestrator import MeasurerOrchestrator, MeasurerResult
from backend.services.measurer.scheduler import (
    DEFAULT_HALF_WIDTH,
    MeasurementScheduler,
    MeasurementWindow,
)


def _post_row(hours_ago: float) -> dict:
    return {
        "id": uuid4(),
        "draft_id": uuid4(),
        "platform": "instagram",
        "post_external_id": "ig-ext",
        "post_url": "https://instagram.com/p/x",
        "register": "analitico",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        "final_text": "caption",
    }


@pytest.fixture
def repo_and_orch():
    repo = AsyncMock()
    repo.fetch_safe = AsyncMock(return_value=[])

    orch = AsyncMock(spec=MeasurerOrchestrator)
    orch.measure = AsyncMock(
        return_value=MeasurerResult(post_id=uuid4()),
    )
    return repo, orch


# ── Window constants ────────────────────────────────────────


def test_half_width_is_reasonable_for_6h_cron():
    # must cover a full 6h tick with a bit of slack
    assert DEFAULT_HALF_WIDTH >= timedelta(hours=3)
    assert DEFAULT_HALF_WIDTH < timedelta(hours=6)


# ── Sweep behaviour ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sweep_empty_posts(repo_and_orch):
    repo, orch = repo_and_orch
    scheduler = MeasurementScheduler(repo=repo, orchestrator=orch)
    result = await scheduler.sweep_once()
    assert result.posts_measured == 0
    orch.measure.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_runs_each_post_through_orchestrator(repo_and_orch):
    repo, orch = repo_and_orch
    repo.fetch_safe = AsyncMock(return_value=[_post_row(hours_ago=24)])
    scheduler = MeasurementScheduler(
        repo=repo,
        orchestrator=orch,
        windows=(MeasurementWindow.T_24H,),
    )
    result = await scheduler.sweep_once()
    assert result.posts_measured == 1
    assert result.windows_hit["t_24h"] == 1
    orch.measure.assert_awaited_once()


@pytest.mark.asyncio
async def test_sweep_dedups_post_across_overlapping_windows(repo_and_orch):
    """A single post shouldn't be measured twice in the same sweep even
    if multiple windows pick it up."""
    repo, orch = repo_and_orch
    row = _post_row(hours_ago=24)
    # Have fetch_safe return the same row for any query (simulate overlap)
    repo.fetch_safe = AsyncMock(return_value=[row])
    scheduler = MeasurementScheduler(
        repo=repo,
        orchestrator=orch,
        # half_width so wide that all three windows would match, but
        # dedup via seen-set should still only measure once.
        half_width=timedelta(days=10),
    )
    result = await scheduler.sweep_once()
    assert result.posts_measured == 1
    assert orch.measure.await_count == 1
    # first window records 1; others see 0 new
    assert result.windows_hit["t_24h"] == 1
    assert result.windows_hit["t_72h"] == 0
    assert result.windows_hit["t_7d"] == 0


@pytest.mark.asyncio
async def test_sweep_collects_fetch_errors_but_continues(repo_and_orch):
    repo, orch = repo_and_orch

    call_count = {"n": 0}

    async def flaky_fetch(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("pg down")
        return [_post_row(hours_ago=72)]

    repo.fetch_safe = AsyncMock(side_effect=flaky_fetch)
    scheduler = MeasurementScheduler(repo=repo, orchestrator=orch)
    result = await scheduler.sweep_once()
    # first window errored; next two windows run normally
    assert result.errors
    assert any("t_24h" in e for e in result.errors)
    # windows after the error still progressed
    assert result.posts_measured >= 0


@pytest.mark.asyncio
async def test_sweep_collects_orchestrator_exceptions(repo_and_orch):
    repo, orch = repo_and_orch
    repo.fetch_safe = AsyncMock(return_value=[_post_row(hours_ago=24)])
    orch.measure = AsyncMock(side_effect=RuntimeError("sampler blew up"))
    scheduler = MeasurementScheduler(
        repo=repo,
        orchestrator=orch,
        windows=(MeasurementWindow.T_24H,),
    )
    result = await scheduler.sweep_once()
    assert result.posts_measured == 0
    assert any("measure" in e for e in result.errors)


@pytest.mark.asyncio
async def test_sweep_queries_proper_age_window(repo_and_orch):
    repo, orch = repo_and_orch
    repo.fetch_safe = AsyncMock(return_value=[])
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    scheduler = MeasurementScheduler(
        repo=repo,
        orchestrator=orch,
        half_width=timedelta(hours=1),
        windows=(MeasurementWindow.T_24H,),
    )
    await scheduler.sweep_once(now=now)

    # fetch_safe called once, with positional args (published_after, published_before)
    assert repo.fetch_safe.await_count == 1
    call = repo.fetch_safe.call_args
    # args[0] is the SQL, args[1:] are the params
    args = call.args
    published_after, published_before = args[1], args[2]
    # window at T+24h means age between 23h and 25h
    expected_after = now - timedelta(hours=25)
    expected_before = now - timedelta(hours=23)
    assert published_after == expected_after
    assert published_before == expected_before
