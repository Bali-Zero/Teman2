"""Tests for PortalNotificationService — inserts portal_messages for clients."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_notify_document_uploaded(mock_pool):
    """Should insert a portal_messages record for document upload."""
    pool, conn = mock_pool
    conn.fetchval.return_value = 1

    from backend.services.portal.portal_notification_service import PortalNotificationService

    service = PortalNotificationService(pool)
    msg_id = await service.notify_document_uploaded(
        client_id=42,
        document_type="passport",
        sent_by="team@balizero.com",
    )

    assert msg_id == 1
    sql = conn.fetchval.call_args[0][0]
    assert "INSERT INTO portal_messages" in sql
    assert "team_to_client" in sql


@pytest.mark.asyncio
async def test_notify_practice_status_changed(mock_pool):
    """Should insert a portal_messages record for practice status change."""
    pool, conn = mock_pool
    conn.fetchval.return_value = 2

    from backend.services.portal.portal_notification_service import PortalNotificationService

    service = PortalNotificationService(pool)
    msg_id = await service.notify_practice_status_changed(
        client_id=42,
        practice_id=10,
        practice_type="KITAS Application",
        new_status="on_process",
        sent_by="team@balizero.com",
    )

    assert msg_id == 2


@pytest.mark.asyncio
async def test_notify_profile_updated(mock_pool):
    """Should insert a portal_messages record for profile update."""
    pool, conn = mock_pool
    conn.fetchval.return_value = 3

    from backend.services.portal.portal_notification_service import PortalNotificationService

    service = PortalNotificationService(pool)
    msg_id = await service.notify_profile_updated(
        client_id=42,
        updated_fields=["passport_number", "passport_expiry"],
        sent_by="team@balizero.com",
    )

    assert msg_id == 3
    sql = conn.fetchval.call_args[0][0]
    assert "portal_messages" in sql


@pytest.mark.asyncio
async def test_notify_profile_updated_skips_internal_fields(mock_pool):
    """Should return None if only internal fields were updated."""
    pool, conn = mock_pool

    from backend.services.portal.portal_notification_service import PortalNotificationService

    service = PortalNotificationService(pool)
    result = await service.notify_profile_updated(
        client_id=42,
        updated_fields=["assigned_to", "notes", "tags"],
        sent_by="team@balizero.com",
    )

    assert result is None
    conn.fetchval.assert_not_called()


@pytest.mark.asyncio
async def test_notify_handles_db_error(mock_pool):
    """DB errors should be caught and logged, return None."""
    pool, conn = mock_pool
    conn.fetchval.side_effect = Exception("db error")

    from backend.services.portal.portal_notification_service import PortalNotificationService

    service = PortalNotificationService(pool)
    result = await service.notify_document_uploaded(
        client_id=42, document_type="passport", sent_by="team@balizero.com",
    )

    assert result is None
