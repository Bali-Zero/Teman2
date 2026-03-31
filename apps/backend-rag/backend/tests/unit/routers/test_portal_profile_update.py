"""Tests for portal profile update."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.portal.portal_service import PortalService


@pytest.mark.asyncio
async def test_update_profile_updates_allowed_fields():
    """update_profile updates only whitelisted fields."""
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None
    mock_conn.fetchrow.return_value = {
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

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={
            "phone": "+6281234567890",
            "whatsapp": "+6281234567890",
            "address": "Jl Raya Seminyak 123",
        },
    )

    assert result is not None
    mock_conn.execute.assert_called_once()
    call_sql = mock_conn.execute.call_args[0][0]
    assert "phone" in call_sql
    assert "whatsapp" in call_sql
    assert "address" in call_sql


@pytest.mark.asyncio
async def test_update_profile_rejects_sensitive_fields():
    """update_profile ignores non-whitelisted fields like name, passport."""
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None
    mock_conn.fetchrow.return_value = {
        "id": 1,
        "full_name": "John",
        "email": "john@test.com",
        "phone": "+62999",
        "whatsapp": None,
        "address": None,
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

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "passport_number": "STOLEN", "phone": "+62999"},
    )

    assert result is not None
    call_sql = mock_conn.execute.call_args[0][0]
    assert "full_name" not in call_sql
    assert "passport_number" not in call_sql
    assert "phone" in call_sql


@pytest.mark.asyncio
async def test_update_profile_empty_fields_noop():
    """update_profile with no valid fields returns profile without updating."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 1,
        "full_name": "John",
        "email": "john@test.com",
        "phone": None,
        "whatsapp": None,
        "address": None,
        "nationality": "US",
        "passport_number": None,
        "passport_expiry": None,
        "date_of_birth": None,
        "gender": None,
        "member_since": "2025-01-01",
        "assigned_to_email": None,
        "assigned_to_name": None,
        "assigned_to_avatar": None,
    }

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "nationality": "RU"},
    )

    assert result is not None
    mock_conn.execute.assert_not_called()
