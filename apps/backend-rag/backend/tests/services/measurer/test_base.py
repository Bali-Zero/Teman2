"""Tests for Measurer base classes + canonical metric names."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.services.measurer.base import (
    ALL_METRIC_NAMES,
    METRIC_CLICKS,
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LEADS_ATTRIBUTED,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
    METRIC_VIDEO_VIEWS,
    MetricDatum,
    MetricSampler,
    SamplerResult,
)
from backend.services.war_room.models import MetricSource, Platform


def test_all_canonical_metric_names_present():
    assert ALL_METRIC_NAMES == {
        METRIC_REACH,
        METRIC_IMPRESSIONS,
        METRIC_SAVES,
        METRIC_SHARES,
        METRIC_LIKES,
        METRIC_COMMENTS,
        METRIC_CLICKS,
        METRIC_LEADS_ATTRIBUTED,
        METRIC_VIDEO_VIEWS,
    }


def test_metric_datum_default_timestamp_is_utc():
    d = MetricDatum(
        metric_name=METRIC_REACH,
        value=123,
        source=MetricSource.META_GRAPH,
    )
    assert d.collected_at.tzinfo is not None


def test_metric_datum_accepts_meta():
    d = MetricDatum(
        metric_name=METRIC_SAVES,
        value=5,
        source=MetricSource.META_GRAPH,
        meta={"raw": "from api"},
    )
    assert d.meta == {"raw": "from api"}


def test_sampler_result_dataclass():
    r = SamplerResult(
        sampler_name="meta_graph",
        post_id=uuid4(),
        ok=True,
    )
    assert r.data == []
    assert r.partial is False


def test_metric_sampler_is_abstract():
    with pytest.raises(TypeError):
        MetricSampler()  # type: ignore[abstract]


def test_metric_sampler_supports_check():
    class _X(MetricSampler):
        name = "x"
        platforms = (Platform.X,)
        source = MetricSource.PLAYWRIGHT_SCRAPE

        async def sample(self, post):  # pragma: no cover
            return SamplerResult(sampler_name=self.name, post_id=post.id, ok=True)

    s = _X()
    assert s.supports(Platform.X) is True
    assert s.supports(Platform.INSTAGRAM) is False
