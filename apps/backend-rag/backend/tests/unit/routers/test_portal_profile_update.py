"""Tests for portal profile update."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal.portal_service import PortalService

_PROFILE_ROW = {
    "id": 1,
    "full_name": "John",
    "email": "john@test.com",
    "phone": "+6281234567890",
    "whatsapp": "+6281234567890",
    "address": "Jl Raya Seminyak 123",
    "nationality": "US",
    "passport_number": "AB123",
    "passport_expiry": None,
    "date_of_birth": None,
    "gender": "M",
    "member_since": "2025-01-01",
    "assigned_to_email": None,
    "assigned_to_name": None,
    "assigned_to_avatar": None,
}


def _make_service(fetchrow_return: dict | None = None) -> tuple["PortalService", AsyncMock]:
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None
    mock_conn.fetchrow.return_value = fetchrow_return or _PROFILE_ROW

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    return PortalService(mock_pool), mock_conn


@pytest.mark.asyncio
async def test_update_profile_updates_allowed_fields():
    """update_profile runs UPDATE + notification_alerts INSERT + portal_messages INSERT."""
    service, mock_conn = _make_service()

    result = await service.update_profile(
        client_id=1,
        fields={
            "phone": "+6281234567890",
            "whatsapp": "+6281234567890",
            "address": "Jl Raya Seminyak 123",
        },
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is not None

    # Three execute calls: UPDATE, notification_alerts, portal_messages
    assert mock_conn.execute.call_count == 3

    update_sql = mock_conn.execute.call_args_list[0][0][0]
    assert "phone" in update_sql
    assert "whatsapp" in update_sql
    assert "address" in update_sql

    alert_sql = mock_conn.execute.call_args_list[1][0][0]
    assert "notification_alerts" in alert_sql
    assert "portal_profile_update" in alert_sql

    msg_sql = mock_conn.execute.call_args_list[2][0][0]
    assert "portal_messages" in msg_sql
    assert "client_to_team" in msg_sql


@pytest.mark.asyncio
async def test_update_profile_rejects_sensitive_fields():
    """update_profile ignores non-whitelisted fields; only allowed field triggers side effects."""
    service, mock_conn = _make_service(
        fetchrow_return={**_PROFILE_ROW, "phone": "+62999", "whatsapp": None, "address": None},
    )

    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "passport_number": "STOLEN", "phone": "+62999"},
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is not None

    # Still 3 calls: UPDATE (phone only), notification_alerts, portal_messages
    assert mock_conn.execute.call_count == 3

    update_sql = mock_conn.execute.call_args_list[0][0][0]
    assert "full_name" not in update_sql
    assert "passport_number" not in update_sql
    assert "phone" in update_sql


@pytest.mark.asyncio
async def test_update_profile_empty_fields_noop():
    """update_profile with no valid fields does NOT call execute at all."""
    service, mock_conn = _make_service()

    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "nationality": "RU"},
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is not None
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_notification_failure_does_not_raise():
    """If notification_alerts INSERT fails, update_profile still returns profile (graceful degradation)."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = _PROFILE_ROW

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # notification_alerts INSERT
            raise Exception("DB constraint error")
        return None

    mock_conn.execute.side_effect = execute_side_effect

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"phone": "+62888"},
        current_user={"client_id": 1, "email": "c1@example.com"},
    )

    assert result is not None  # Profile returned despite notification failure
