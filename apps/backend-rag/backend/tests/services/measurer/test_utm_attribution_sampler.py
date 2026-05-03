"""Tests for UTMAttributionSampler — lead_lookup_fn injection + persist."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.measurer.base import METRIC_LEADS_ATTRIBUTED
from backend.services.measurer.utm_attribution_sampler import (
    AttributedLead,
    UTMAttributionSampler,
)
from backend.services.war_room.models import (
    ConversionStage,
    MetricSource,
    Platform,
    WarRoomPost,
)


def _post(platform: Platform = Platform.INSTAGRAM) -> WarRoomPost:
    return WarRoomPost(
        id=uuid4(),
        draft_id=uuid4(),
        platform=platform,
        post_external_id="ig-1",
        tone_register=None,
        published_at=datetime.now(timezone.utc),
    )


def _lead(
    *,
    stage: ConversionStage = ConversionStage.LEAD,
    revenue: Decimal | None = None,
) -> AttributedLead:
    return AttributedLead(
        contact_id=uuid4(),
        utm_campaign="warroom_permenkumham",
        utm_medium="ig",
        utm_source="warroom",
        attributed_at=datetime.now(timezone.utc),
        conversion_stage=stage,
        revenue_idr=revenue,
    )


@pytest.mark.asyncio
async def test_sample_zero_leads_returns_zero_metric():
    repo = AsyncMock()
    repo.attribute_lead = AsyncMock()

    async def lookup(post, since_at):
        return []

    sampler = UTMAttributionSampler(repo=repo, lead_lookup_fn=lookup)
    result = await sampler.sample(_post())
    assert result.ok is True
    assert len(result.data) == 1
    datum = result.data[0]
    assert datum.metric_name == METRIC_LEADS_ATTRIBUTED
    assert datum.value == 0.0
    assert datum.source == MetricSource.UTM_CRM
    repo.attribute_lead.assert_not_called()


@pytest.mark.asyncio
async def test_sample_persists_each_lead():
    repo = AsyncMock()
    repo.attribute_lead = AsyncMock()

    async def lookup(post, since_at):
        return [
            _lead(stage=ConversionStage.LEAD),
            _lead(stage=ConversionStage.CLIENT, revenue=Decimal("20000000")),
        ]

    sampler = UTMAttributionSampler(repo=repo, lead_lookup_fn=lookup)
    result = await sampler.sample(_post())
    assert result.ok is True
    assert result.data[0].value == 2.0
    assert repo.attribute_lead.await_count == 2


@pytest.mark.asyncio
async def test_sample_partial_on_persist_failure():
    repo = AsyncMock()

    # First call fails, second call succeeds
    async def flaky_attribute(*args, **kwargs):
        if repo.attribute_lead.await_count == 1:
            raise RuntimeError("db down")

    repo.attribute_lead = AsyncMock(side_effect=flaky_attribute)

    async def lookup(post, since_at):
        return [_lead(), _lead()]

    sampler = UTMAttributionSampler(repo=repo, lead_lookup_fn=lookup)
    result = await sampler.sample(_post())
    assert result.ok is True
    assert result.partial is True
    assert result.data[0].value == 2.0
    assert result.data[0].meta["persist_errors"] == 1


@pytest.mark.asyncio
async def test_sample_handles_lookup_exception():
    repo = AsyncMock()

    async def lookup(post, since_at):
        raise RuntimeError("crm pool exhausted")

    sampler = UTMAttributionSampler(repo=repo, lead_lookup_fn=lookup)
    result = await sampler.sample(_post())
    assert result.ok is False
    assert "RuntimeError" in (result.error or "")


@pytest.mark.asyncio
async def test_sample_skips_persist_when_disabled():
    repo = AsyncMock()
    repo.attribute_lead = AsyncMock()

    async def lookup(post, since_at):
        return [_lead(), _lead(), _lead()]

    sampler = UTMAttributionSampler(
        repo=repo, lead_lookup_fn=lookup, persist_leads=False,
    )
    result = await sampler.sample(_post())
    assert result.ok is True
    assert result.data[0].value == 3.0
    repo.attribute_lead.assert_not_called()


def test_sampler_supports_all_platforms():
    async def lookup(post, since_at):
        return []

    sampler = UTMAttributionSampler(repo=AsyncMock(), lead_lookup_fn=lookup)
    for p in (
        Platform.INSTAGRAM, Platform.X, Platform.LINKEDIN,
        Platform.BLOG, Platform.NEWSLETTER,
    ):
        assert sampler.supports(p) is True
