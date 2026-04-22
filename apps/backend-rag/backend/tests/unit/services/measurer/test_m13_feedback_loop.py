"""Tests for M13FeedbackLoop — collect, delta, retrain trigger."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from backend.services.measurer.m13_feedback_loop import (
    M13FeedbackLoop,
    M13CollectionHorizon,
)


class _FakeAcq:
    def __init__(self, conn):
        self._c = conn

    async def __aenter__(self):
        return self._c

    async def __aexit__(self, *a):
        return None


class _FakePool:
    def __init__(self, conn):
        self._c = conn

    def acquire(self):
        return _FakeAcq(self._c)


@pytest.mark.asyncio
async def test_collect_persists_one_row_per_metric():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = _FakePool(conn)
    loop = M13FeedbackLoop(db_pool=pool)
    post_id = uuid4()
    await loop.collect_post_metrics(
        post_id=post_id,
        horizon=M13CollectionHorizon.T_24H,
        metrics={"likes": 120, "saves": 34, "reach": 1500},
        source="ig_graph",
    )
    # 3 metrics → 3 inserts
    assert conn.execute.await_count == 3
    # Check SQL mentions post_metrics_history
    sql = conn.execute.await_args_list[0].args[0]
    assert "INSERT INTO post_metrics_history" in sql


@pytest.mark.asyncio
async def test_compute_delta_vs_baseline_returns_pct():
    conn = AsyncMock()
    # Recent avg engagement, then baseline avg engagement
    conn.fetchval = AsyncMock(side_effect=[0.054, 0.040])
    pool = _FakePool(conn)
    loop = M13FeedbackLoop(db_pool=pool)
    delta = await loop.compute_delta_vs_baseline(channel="instagram", pillar="audience")
    assert delta == pytest.approx(0.35, rel=0.01)  # (0.054 - 0.040)/0.040


def test_smoothing_caps_weight_change():
    loop = M13FeedbackLoop(db_pool=None)
    new_w = loop._smooth_weight(old=0.5, desired=1.0, cap=0.2)
    assert new_w == pytest.approx(0.6, rel=0.01)  # 0.5 + (1.0 - 0.5) * 0.2


def test_should_trigger_retrain_on_positive_breach():
    loop = M13FeedbackLoop(db_pool=None)
    assert loop.should_trigger_retrain(delta=0.12) is True  # >10%
    assert loop.should_trigger_retrain(delta=-0.15) is True  # <-10%
    assert loop.should_trigger_retrain(delta=0.05) is False


def test_threshold_breach_pillar_drop():
    loop = M13FeedbackLoop(db_pool=None)
    assert loop.is_pillar_threshold_breach(delta=-0.25) is True  # <-20%
    assert loop.is_pillar_threshold_breach(delta=-0.10) is False
    assert loop.is_pillar_threshold_breach(delta=0.30) is False  # positive not a breach
