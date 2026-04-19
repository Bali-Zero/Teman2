"""Tests for CostAdvisor — weekly analysis of llm_cost_events → recommendations."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.observability.cost_advisor import (
    CostAdvisor,
    CostRecommendation,
    EndpointCostSummary,
)


def _make_pool_with_rows(rows):
    """Build a fake asyncpg-like pool whose `acquire()` yields a conn
    that returns `rows` from `fetch()` and nothing from `fetchval()`.
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


# ---------------------------------------------------------------------------
# analyze_last_window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_last_window_aggregates_by_endpoint_and_model():
    pool, conn = _make_pool_with_rows([
        {
            "endpoint": "article_composer",
            "model": "deepseek-chat",
            "provider": "deepseek",
            "call_count": 10,
            "total_cost_usd": Decimal("0.50"),
            "avg_cost_per_call_usd": Decimal("0.05"),
            "p50_latency_ms": 400,
            "p95_latency_ms": 800,
            "success_rate": 0.95,
        },
    ])

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    summaries = await advisor.analyze_last_window(days=7)

    assert len(summaries) == 1
    s = summaries[0]
    assert isinstance(s, EndpointCostSummary)
    assert s.endpoint == "article_composer"
    assert s.model == "deepseek-chat"
    assert s.provider == "deepseek"
    assert s.call_count == 10
    assert s.total_cost_usd == Decimal("0.50")
    assert s.success_rate == 0.95
    conn.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_last_window_returns_empty_list_when_no_data():
    pool, _ = _make_pool_with_rows([])
    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    summaries = await advisor.analyze_last_window(days=7)
    assert summaries == []


# ---------------------------------------------------------------------------
# detect_spikes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_spikes_flags_endpoints_over_3x_baseline():
    pool, conn = _make_pool_with_rows([])
    # Baseline avg $0.10/week; last week $0.40 → 4× → spike
    conn.fetchval = AsyncMock(return_value=Decimal("0.10"))

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    summaries = [
        EndpointCostSummary(
            endpoint="spiky",
            model="m",
            provider="p",
            call_count=1,
            total_cost_usd=Decimal("0.40"),
            avg_cost_per_call_usd=Decimal("0.40"),
            p50_latency_ms=1,
            p95_latency_ms=1,
            success_rate=1.0,
        ),
    ]
    spikes = await advisor.detect_spikes(summaries, baseline_days=28)
    assert spikes == {"spiky"}


@pytest.mark.asyncio
async def test_detect_spikes_returns_empty_when_baseline_zero():
    pool, conn = _make_pool_with_rows([])
    conn.fetchval = AsyncMock(return_value=Decimal("0"))

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    summaries = [
        EndpointCostSummary(
            endpoint="new_ep",
            model="m",
            provider="p",
            call_count=1,
            total_cost_usd=Decimal("5.00"),
            avg_cost_per_call_usd=Decimal("5.00"),
            p50_latency_ms=1,
            p95_latency_ms=1,
            success_rate=1.0,
        ),
    ]
    spikes = await advisor.detect_spikes(summaries, baseline_days=28)
    assert spikes == set()


@pytest.mark.asyncio
async def test_detect_spikes_does_not_flag_within_multiplier():
    pool, conn = _make_pool_with_rows([])
    # Baseline $1.00/week; last week $2.00 → 2× → NOT a spike (< 3×)
    conn.fetchval = AsyncMock(return_value=Decimal("1.00"))

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    summaries = [
        EndpointCostSummary(
            endpoint="growing_normally",
            model="m",
            provider="p",
            call_count=1,
            total_cost_usd=Decimal("2.00"),
            avg_cost_per_call_usd=Decimal("2.00"),
            p50_latency_ms=1,
            p95_latency_ms=1,
            success_rate=1.0,
        ),
    ]
    spikes = await advisor.detect_spikes(summaries, baseline_days=28)
    assert spikes == set()


# ---------------------------------------------------------------------------
# propose_substitutions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_substitutions_returns_parsed_recommendations():
    pool, _ = _make_pool_with_rows([])

    mock_oauth = MagicMock()
    mock_oauth.complete = AsyncMock(return_value=json.dumps([
        {
            "endpoint": "hot",
            "current_model": "claude-sonnet-4-6",
            "proposed_model": "deepseek-chat",
            "estimated_monthly_saving_usd": "100.0",
            "quality_tradeoff": "Lower writing quality",
            "confidence": "medium",
        },
    ]))

    advisor = CostAdvisor(pg_pool=pool, oauth_client=mock_oauth)
    advisor.analyze_last_window = AsyncMock(return_value=[
        EndpointCostSummary(
            endpoint="hot",
            model="claude-sonnet-4-6",
            provider="claude_oauth",
            call_count=100,
            total_cost_usd=Decimal("50"),
            avg_cost_per_call_usd=Decimal("0.50"),
            p50_latency_ms=500,
            p95_latency_ms=1000,
            success_rate=0.98,
        ),
    ])
    advisor.detect_spikes = AsyncMock(return_value=set())

    recs = await advisor.propose_substitutions(top_n=5)

    assert len(recs) == 1
    r = recs[0]
    assert r.endpoint == "hot"
    assert r.proposed_model == "deepseek-chat"
    assert r.estimated_monthly_saving_usd == Decimal("100.0")
    assert r.confidence == "medium"
    assert r.spike_flag is False


@pytest.mark.asyncio
async def test_propose_substitutions_retries_once_on_malformed_json():
    pool, _ = _make_pool_with_rows([])

    mock_oauth = MagicMock()
    mock_oauth.complete = AsyncMock(side_effect=[
        "not json {",  # first call malformed
        json.dumps([]),  # second call valid (empty array)
    ])

    advisor = CostAdvisor(pg_pool=pool, oauth_client=mock_oauth)
    advisor.analyze_last_window = AsyncMock(return_value=[
        EndpointCostSummary(
            endpoint="x", model="m", provider="p",
            call_count=1, total_cost_usd=Decimal("1"),
            avg_cost_per_call_usd=Decimal("1"),
            p50_latency_ms=1, p95_latency_ms=1, success_rate=1.0,
        ),
    ])
    advisor.detect_spikes = AsyncMock(return_value=set())

    recs = await advisor.propose_substitutions(top_n=5)
    assert recs == []
    assert mock_oauth.complete.await_count == 2


@pytest.mark.asyncio
async def test_propose_substitutions_pins_confidence_high_on_spike():
    pool, _ = _make_pool_with_rows([])

    mock_oauth = MagicMock()
    mock_oauth.complete = AsyncMock(return_value=json.dumps([
        {
            "endpoint": "spiky_ep",
            "current_model": "x",
            "proposed_model": "y",
            "estimated_monthly_saving_usd": "10.0",
            "quality_tradeoff": "ok",
            "confidence": "low",  # will be overridden to 'high' because it's a spike
        },
    ]))

    advisor = CostAdvisor(pg_pool=pool, oauth_client=mock_oauth)
    advisor.analyze_last_window = AsyncMock(return_value=[
        EndpointCostSummary(
            endpoint="spiky_ep", model="x", provider="p",
            call_count=1, total_cost_usd=Decimal("30"),
            avg_cost_per_call_usd=Decimal("30"),
            p50_latency_ms=1, p95_latency_ms=1, success_rate=1.0,
        ),
    ])
    advisor.detect_spikes = AsyncMock(return_value={"spiky_ep"})

    recs = await advisor.propose_substitutions(top_n=5)
    assert len(recs) == 1
    assert recs[0].spike_flag is True
    assert recs[0].confidence == "high"


@pytest.mark.asyncio
async def test_propose_substitutions_empty_when_no_summaries():
    pool, _ = _make_pool_with_rows([])
    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    advisor.analyze_last_window = AsyncMock(return_value=[])
    advisor.detect_spikes = AsyncMock(return_value=set())

    recs = await advisor.propose_substitutions(top_n=5)
    assert recs == []


# ---------------------------------------------------------------------------
# persist_recommendations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_recommendations_inserts_and_counts():
    pool, conn = _make_pool_with_rows([])
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    rec = CostRecommendation(
        endpoint="x",
        current_model="a",
        proposed_model="b",
        estimated_monthly_saving_usd=Decimal("5"),
        quality_tradeoff="ok",
        confidence="medium",
        spike_flag=False,
    )
    inserted = await advisor.persist_recommendations([rec])

    assert inserted == 1
    call_sql = conn.execute.await_args.args[0]
    assert "llm_cost_recommendations" in call_sql
    assert "NOT EXISTS" in call_sql


@pytest.mark.asyncio
async def test_persist_recommendations_dedup_when_duplicate():
    pool, conn = _make_pool_with_rows([])
    conn.execute = AsyncMock(return_value="INSERT 0 0")  # zero rows inserted

    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    rec = CostRecommendation(
        endpoint="x",
        current_model="a",
        proposed_model="b",
        estimated_monthly_saving_usd=Decimal("5"),
        quality_tradeoff="ok",
        confidence="medium",
        spike_flag=False,
    )
    inserted = await advisor.persist_recommendations([rec])
    assert inserted == 0


@pytest.mark.asyncio
async def test_persist_recommendations_empty_list_noop():
    pool, _ = _make_pool_with_rows([])
    advisor = CostAdvisor(pg_pool=pool, oauth_client=MagicMock())
    inserted = await advisor.persist_recommendations([])
    assert inserted == 0
