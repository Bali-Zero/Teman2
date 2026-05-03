"""Tests for MeasurerOrchestrator — fan out + record + graceful partial."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.measurer.base import (
    METRIC_IMPRESSIONS,
    METRIC_REACH,
    MetricDatum,
    MetricSampler,
    SamplerResult,
)
from backend.services.measurer.orchestrator import MeasurerOrchestrator
from backend.services.war_room.models import (
    MetricSource,
    Platform,
    WarRoomPost,
)


def _post(platform: Platform = Platform.INSTAGRAM) -> WarRoomPost:
    return WarRoomPost(
        id=uuid4(),
        draft_id=uuid4(),
        platform=platform,
        post_external_id="ext",
        tone_register=None,
        published_at=datetime.now(timezone.utc),
    )


class _StaticSampler(MetricSampler):
    def __init__(
        self,
        name: str,
        platforms: tuple[Platform, ...],
        source: MetricSource,
        result: SamplerResult,
    ) -> None:
        self.name = name
        self.platforms = platforms
        self.source = source
        self._result = result

    async def sample(self, post: WarRoomPost) -> SamplerResult:
        self._result.post_id = post.id
        return self._result


def _datum(name: str, value: float) -> MetricDatum:
    return MetricDatum(
        metric_name=name,
        value=value,
        source=MetricSource.META_GRAPH,
    )


# ── Init ──────────────────────────────────────────────────────


def test_requires_non_empty_sampler_list():
    with pytest.raises(ValueError):
        MeasurerOrchestrator(samplers=[])


# ── Fan out ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_measure_fans_out_to_matching_samplers():
    ig_sampler = _StaticSampler(
        name="meta_graph",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="meta_graph",
            post_id=uuid4(),
            ok=True,
            data=[
                _datum(METRIC_REACH, 1000),
                _datum(METRIC_IMPRESSIONS, 1500),
            ],
        ),
    )
    x_sampler = _StaticSampler(
        name="x_scraper",
        platforms=(Platform.X,),
        source=MetricSource.PLAYWRIGHT_SCRAPE,
        result=SamplerResult(
            sampler_name="x_scraper",
            post_id=uuid4(),
            ok=True,
            data=[_datum(METRIC_REACH, 55)],
        ),
    )
    repo = AsyncMock()
    repo.record_metric = AsyncMock()

    orch = MeasurerOrchestrator(samplers=[ig_sampler, x_sampler], repo=repo)
    post = _post(platform=Platform.INSTAGRAM)
    result = await orch.measure(post)

    assert result.recorded_datums == 2  # only IG sampler applied
    # 2 record_metric calls, all with META_GRAPH source
    calls = repo.record_metric.call_args_list
    assert len(calls) == 2
    for call in calls:
        assert call.args[3] == MetricSource.META_GRAPH


@pytest.mark.asyncio
async def test_measure_no_sampler_supports_platform():
    ig_sampler = _StaticSampler(
        name="meta_graph",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="meta_graph",
            post_id=uuid4(),
            ok=True,
        ),
    )
    orch = MeasurerOrchestrator(samplers=[ig_sampler])
    result = await orch.measure(_post(platform=Platform.X))
    assert result.recorded_datums == 0
    assert any("no sampler supports" in e for e in result.errors)


# ── Partial handling ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_measure_flags_partial_source_on_partial_result():
    sampler = _StaticSampler(
        name="meta_graph",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="meta_graph",
            post_id=uuid4(),
            ok=True,
            partial=True,
            data=[_datum(METRIC_REACH, 1000)],
        ),
    )
    repo = AsyncMock()
    repo.record_metric = AsyncMock()
    orch = MeasurerOrchestrator(samplers=[sampler], repo=repo)

    await orch.measure(_post())
    # even though sampler source is META_GRAPH, partial=True means we record
    # with source=PARTIAL so dashboards can detect the gap
    call = repo.record_metric.call_args
    assert call.args[3] == MetricSource.PARTIAL


# ── Errors ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_measure_collects_sampler_errors_but_continues():
    ok_sampler = _StaticSampler(
        name="ok",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="ok",
            post_id=uuid4(),
            ok=True,
            data=[_datum(METRIC_REACH, 500)],
        ),
    )
    bad_sampler = _StaticSampler(
        name="bad",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.PLAYWRIGHT_SCRAPE,
        result=SamplerResult(
            sampler_name="bad",
            post_id=uuid4(),
            ok=False,
            error="simulated",
        ),
    )
    repo = AsyncMock()
    repo.record_metric = AsyncMock()
    orch = MeasurerOrchestrator(
        samplers=[ok_sampler, bad_sampler], repo=repo,
    )

    result = await orch.measure(_post())
    assert result.recorded_datums == 1  # only ok sampler
    assert any("bad: simulated" in e for e in result.errors)
    assert result.any_partial is True


@pytest.mark.asyncio
async def test_measure_record_failure_does_not_abort():
    sampler = _StaticSampler(
        name="meta_graph",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="meta_graph",
            post_id=uuid4(),
            ok=True,
            data=[_datum(METRIC_REACH, 1), _datum(METRIC_IMPRESSIONS, 2)],
        ),
    )
    repo = AsyncMock()
    # first record raises, second succeeds
    call_count = {"n": 0}

    async def flaky_record(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("pg down")

    repo.record_metric = AsyncMock(side_effect=flaky_record)

    orch = MeasurerOrchestrator(samplers=[sampler], repo=repo)
    result = await orch.measure(_post())
    # 1 recorded (second call), 1 error captured
    assert result.recorded_datums == 1
    assert any("record reach" in e for e in result.errors)


@pytest.mark.asyncio
async def test_measure_without_repo_skips_recording():
    sampler = _StaticSampler(
        name="meta_graph",
        platforms=(Platform.INSTAGRAM,),
        source=MetricSource.META_GRAPH,
        result=SamplerResult(
            sampler_name="meta_graph",
            post_id=uuid4(),
            ok=True,
            data=[_datum(METRIC_REACH, 1)],
        ),
    )
    orch = MeasurerOrchestrator(samplers=[sampler], repo=None)
    result = await orch.measure(_post())
    assert result.recorded_datums == 1  # counted as attempted
