"""Tests for PortalProfileService — auto-creates team_members records for clients."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn


@pytest.mark.asyncio
async def test_ensure_portal_profile_creates_record(mock_pool):
    """When client has email, should insert team_members record."""
    pool, conn = mock_pool
    conn.fetchval.return_value = "generated-uuid-123"

    from backend.services.portal.portal_profile_service import PortalProfileService

    service = PortalProfileService(pool)
    result = await service.ensure_portal_profile(
        client_id=42,
        email="test@example.com",
        full_name="Test User",
    )

    assert result == "generated-uuid-123"
    conn.fetchval.assert_called_once()
    sql_call = conn.fetchval.call_args[0][0]
    assert "INSERT INTO team_members" in sql_call
    assert "full_name" in sql_call
    assert "ON CONFLICT" in sql_call


@pytest.mark.asyncio
async def test_ensure_portal_profile_skips_without_email(mock_pool):
    """When client has no email, should return None and not insert."""
    pool, conn = mock_pool

    from backend.services.portal.portal_profile_service import PortalProfileService

    service = PortalProfileService(pool)
    result = await service.ensure_portal_profile(
        client_id=42,
        email=None,
        full_name="Test User",
    )

    assert result is None
    conn.fetchval.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_portal_profile_skips_empty_email(mock_pool):
    """When client has empty string email, should return None."""
    pool, conn = mock_pool

    from backend.services.portal.portal_profile_service import PortalProfileService

    service = PortalProfileService(pool)
    result = await service.ensure_portal_profile(
        client_id=42,
        email="  ",
        full_name="Test User",
    )

    assert result is None
    conn.fetchval.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_portal_profile_handles_db_error(mock_pool):
    """DB errors should be caught and logged, not raised."""
    pool, conn = mock_pool
    conn.fetchval.side_effect = Exception("connection lost")

    from backend.services.portal.portal_profile_service import PortalProfileService

    service = PortalProfileService(pool)
    result = await service.ensure_portal_profile(
        client_id=42,
        email="test@example.com",
        full_name="Test User",
    )

    assert result is None
