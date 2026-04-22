"""Tests for Brevo stats client — subscriber + campaign metrics."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from backend.services.measurer.brevo_stats_client import (
    BrevoStatsClient,
    BrevoError,
)


@pytest.mark.asyncio
async def test_fetch_list_totals_aggregates_subscribers():
    client = BrevoStatsClient(api_key="xkeysib-abc")
    response = {
        "lists": [
            {"id": 1, "name": "newsletter", "totalSubscribers": 512, "totalBlacklisted": 3},
            {"id": 2, "name": "clients", "totalSubscribers": 420, "totalBlacklisted": 1},
        ]
    }
    with patch.object(client, "_get", AsyncMock(return_value=response)):
        result = await client.fetch_list_totals()
    assert result["total_subscribers"] == 932
    assert result["list_count"] == 2


@pytest.mark.asyncio
async def test_fetch_campaign_aggregates_returns_open_rate():
    client = BrevoStatsClient(api_key="xkeysib-abc")
    response = {
        "campaigns": [
            {
                "id": 10,
                "subject": "Test",
                "statistics": {
                    "globalStats": {
                        "sent": 1000,
                        "uniqueViews": 350,
                        "uniqueClicks": 45,
                    }
                },
            }
        ]
    }
    with patch.object(client, "_get", AsyncMock(return_value=response)):
        result = await client.fetch_campaign_aggregates(limit=30)
    assert result["campaigns_analyzed"] == 1
    assert result["avg_open_rate"] == pytest.approx(0.35)
    assert result["avg_click_rate"] == pytest.approx(0.045)


@pytest.mark.asyncio
async def test_raises_on_auth_failure():
    client = BrevoStatsClient(api_key="xkeysib-bad")
    with patch.object(client, "_get", AsyncMock(side_effect=BrevoError("401 unauthorized"))):
        with pytest.raises(BrevoError):
            await client.fetch_list_totals()
