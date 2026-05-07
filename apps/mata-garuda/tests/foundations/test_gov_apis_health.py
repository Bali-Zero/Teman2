import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch
from mata_garuda.foundations.gov_apis_health import (
    PortalHealth,
    HealthReport,
    probe_portal,
    probe_inventory,
    load_inventory,
)


def test_load_inventory_returns_seed_entries():
    inventory = load_inventory()
    assert len(inventory) >= 14
    assert any(p["id"] == "djp" for p in inventory)
    assert any(p["id"] == "bps" for p in inventory)
    assert any(p["id"] == "jdihn" for p in inventory)


@pytest.mark.asyncio
async def test_probe_portal_marks_operational_on_200():
    with patch("mata_garuda.foundations.gov_apis_health.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.status_code = 200
        mock_cls.return_value.__aenter__.return_value = mock_client

        result = await probe_portal({"id": "djp", "url": "https://pajak.go.id"})

    assert isinstance(result, PortalHealth)
    assert result.id == "djp"
    assert result.status == "operational"
    assert result.http_code == 200


@pytest.mark.asyncio
async def test_probe_portal_marks_dns_failure_on_connect_error():
    with patch("mata_garuda.foundations.gov_apis_health.httpx.AsyncClient") as mock_cls:
        from httpx import ConnectError

        mock_client = AsyncMock()
        mock_client.get.side_effect = ConnectError("DNS resolution failed")
        mock_cls.return_value.__aenter__.return_value = mock_client

        result = await probe_portal({"id": "dead-portal", "url": "https://dead.go.id"})

    assert result.status == "dns_failure"


@pytest.mark.asyncio
async def test_probe_inventory_aggregates_results():
    fake_inventory = [
        {"id": "djp", "url": "https://pajak.go.id"},
        {"id": "bps", "url": "https://bps.go.id"},
    ]
    with patch("mata_garuda.foundations.gov_apis_health.probe_portal") as mock_probe:
        mock_probe.side_effect = [
            PortalHealth(id="djp", url="https://pajak.go.id", status="operational", http_code=200),
            PortalHealth(id="bps", url="https://bps.go.id", status="cf_challenge", http_code=403),
        ]
        report = await probe_inventory(fake_inventory)

    assert isinstance(report, HealthReport)
    assert report.total == 2
    assert report.operational == 1
    assert len(report.results) == 2
