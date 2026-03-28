"""
Unit tests for auto_practice_creator job.

Tests:
- Practice type lookup
- Duplicate detection
- Practice creation logic
- Full job execution
- Error handling
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jobs.auto_practice_creator import (
    RENEWAL_TRIGGER_DAYS,
    check_existing_renewal_practice,
    create_renewal_practice,
    get_practice_type_id,
    run_auto_practice_creator,
)


@pytest.mark.asyncio
async def test_get_practice_type_id_found():
    """Test get_practice_type_id returns ID when found"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"id": 42}

    result = await get_practice_type_id(mock_pool, "kitas_work")

    assert result == 42
    mock_conn.fetchrow.assert_awaited_once_with(
        "SELECT id FROM practice_types WHERE code = $1 AND active = true", "KITAS_RENEWAL"
    )


@pytest.mark.asyncio
async def test_get_practice_type_id_not_found():
    """Test get_practice_type_id returns None when not found"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = None

    result = await get_practice_type_id(mock_pool, "unknown_visa")

    assert result is None


@pytest.mark.asyncio
async def test_get_practice_type_id_mapping():
    """Test visa type to practice type mapping"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"id": 123}

    # Test all mappings
    mappings = {
        "kitas_work": "KITAS_RENEWAL",
        "kitas_spouse": "KITAS_SPOUSE_RENEWAL",
        "kitap": "KITAP_RENEWAL",
        "tourist_visa": "TOURIST_VISA_EXTENSION",
        "business_visa": "BUSINESS_VISA_RENEWAL",
        "social_visa": "SOCIAL_VISA_EXTENSION",
        "other": "VISA_RENEWAL_GENERAL",
        "unknown": "VISA_RENEWAL_GENERAL",  # fallback
    }

    for visa_type, expected_code in mappings.items():
        mock_conn.fetchrow.reset_mock()
        await get_practice_type_id(mock_pool, visa_type)
        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.await_args[0]
        assert call_args[1] == expected_code


@pytest.mark.asyncio
async def test_check_existing_renewal_practice_exists():
    """Test check_existing_renewal_practice returns True when practice exists"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"count": 1}

    result = await check_existing_renewal_practice(mock_pool, client_id=123, visa_record_id=456)

    assert result is True
    mock_conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_existing_renewal_practice_not_exists():
    """Test check_existing_renewal_practice returns False when no practice"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"count": 0}

    result = await check_existing_renewal_practice(mock_pool, client_id=123, visa_record_id=456)

    assert result is False


@pytest.mark.asyncio
async def test_create_renewal_practice_success():
    """Test create_renewal_practice creates practice and timeline event"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )

    # Mock practice created
    mock_conn.fetchrow.return_value = {"id": 999, "uuid": "test-uuid-123"}

    with patch("backend.jobs.auto_practice_creator.get_practice_type_id", return_value=42):
        result = await create_renewal_practice(
            db_pool=mock_pool,
            client_id=123,
            client_name="John Doe",
            visa_record_id=456,
            visa_type="kitas_work",
            visa_number="C123456",
            expiry_date=datetime.now(tz=timezone.utc).date() + timedelta(days=60),
            assigned_to="agent@example.com",
        )

    assert result == 999
    assert mock_conn.execute.await_count == 1  # timeline event created


@pytest.mark.asyncio
async def test_create_renewal_practice_no_practice_type():
    """Test create_renewal_practice returns None when practice type not found"""
    mock_pool = AsyncMock()

    with patch("backend.jobs.auto_practice_creator.get_practice_type_id", return_value=None):
        result = await create_renewal_practice(
            db_pool=mock_pool,
            client_id=123,
            client_name="John Doe",
            visa_record_id=456,
            visa_type="unknown",
            visa_number="X999",
            expiry_date=datetime.now(tz=timezone.utc).date() + timedelta(days=60),
            assigned_to=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_create_renewal_practice_priority_high():
    """Test create_renewal_practice sets high priority when <30 days"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"id": 999, "uuid": "test-uuid"}

    with patch("backend.jobs.auto_practice_creator.get_practice_type_id", return_value=42):
        await create_renewal_practice(
            db_pool=mock_pool,
            client_id=123,
            client_name="John Doe",
            visa_record_id=456,
            visa_type="kitas_work",
            visa_number="C123456",
            expiry_date=datetime.now(tz=timezone.utc).date() + timedelta(days=20),  # <30 days
            assigned_to=None,
        )

    # Check priority was set to 'high'
    call_args = mock_conn.fetchrow.await_args[0]
    assert call_args[4] == "high"  # priority argument


@pytest.mark.asyncio
async def test_create_renewal_practice_priority_normal():
    """Test create_renewal_practice sets normal priority when >=30 days"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetchrow.return_value = {"id": 999, "uuid": "test-uuid"}

    with patch("backend.jobs.auto_practice_creator.get_practice_type_id", return_value=42):
        await create_renewal_practice(
            db_pool=mock_pool,
            client_id=123,
            client_name="John Doe",
            visa_record_id=456,
            visa_type="kitas_work",
            visa_number="C123456",
            expiry_date=datetime.now(tz=timezone.utc).date() + timedelta(days=60),  # >=30 days
            assigned_to=None,
        )

    # Check priority was set to 'normal'
    call_args = mock_conn.fetchrow.await_args[0]
    assert call_args[4] == "normal"  # priority argument


@pytest.mark.asyncio
async def test_run_auto_practice_creator_no_visas():
    """Test run_auto_practice_creator with no expiring visas"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )
    mock_conn.fetch.return_value = []  # No visas expiring

    stats = await run_auto_practice_creator(mock_pool)

    assert stats["visas_checked"] == 0
    assert stats["practices_created"] == 0
    assert stats["practices_skipped"] == 0
    assert stats["errors"] == 0


@pytest.mark.asyncio
async def test_run_auto_practice_creator_creates_practices():
    """Test run_auto_practice_creator creates practices for expiring visas"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )

    target_date = datetime.now(tz=timezone.utc).date() + timedelta(days=RENEWAL_TRIGGER_DAYS)

    # Mock visas expiring in 60 days
    mock_conn.fetch.return_value = [
        {
            "visa_record_id": 1,
            "client_id": 101,
            "visa_type": "kitas_work",
            "visa_number": "C123456",
            "expiry_date": target_date,
            "status": "active",
            "client_name": "John Doe",
            "client_email": "john@example.com",
            "assigned_to": "agent@example.com",
            "client_status": "active",
        },
        {
            "visa_record_id": 2,
            "client_id": 102,
            "visa_type": "kitas_spouse",
            "visa_number": "C789012",
            "expiry_date": target_date,
            "status": "expiring_soon",
            "client_name": "Jane Smith",
            "client_email": "jane@example.com",
            "assigned_to": None,
            "client_status": "active",
        },
    ]

    with (
        patch(
            "backend.jobs.auto_practice_creator.check_existing_renewal_practice", return_value=False
        ),
        patch(
            "backend.jobs.auto_practice_creator.create_renewal_practice",
            side_effect=[999, 1000],  # Practice IDs
        ),
    ):
        stats = await run_auto_practice_creator(mock_pool)

    assert stats["visas_checked"] == 2
    assert stats["practices_created"] == 2
    assert stats["practices_skipped"] == 0
    assert stats["errors"] == 0


@pytest.mark.asyncio
async def test_run_auto_practice_creator_skips_existing():
    """Test run_auto_practice_creator skips visas with existing practices"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )

    target_date = datetime.now(tz=timezone.utc).date() + timedelta(days=RENEWAL_TRIGGER_DAYS)

    mock_conn.fetch.return_value = [
        {
            "visa_record_id": 1,
            "client_id": 101,
            "visa_type": "kitas_work",
            "visa_number": "C123456",
            "expiry_date": target_date,
            "status": "active",
            "client_name": "John Doe",
            "client_email": "john@example.com",
            "assigned_to": "agent@example.com",
            "client_status": "active",
        }
    ]

    # Mock existing practice found
    with (
        patch(
            "backend.jobs.auto_practice_creator.check_existing_renewal_practice", return_value=True
        ),
        patch("backend.jobs.auto_practice_creator.create_renewal_practice") as mock_create,
    ):
        stats = await run_auto_practice_creator(mock_pool)

    assert stats["visas_checked"] == 1
    assert stats["practices_created"] == 0
    assert stats["practices_skipped"] == 1
    assert stats["errors"] == 0
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_run_auto_practice_creator_handles_errors():
    """Test run_auto_practice_creator handles creation errors gracefully"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock())
    )

    target_date = datetime.now(tz=timezone.utc).date() + timedelta(days=RENEWAL_TRIGGER_DAYS)

    mock_conn.fetch.return_value = [
        {
            "visa_record_id": 1,
            "client_id": 101,
            "visa_type": "kitas_work",
            "visa_number": "C123456",
            "expiry_date": target_date,
            "status": "active",
            "client_name": "John Doe",
            "client_email": "john@example.com",
            "assigned_to": "agent@example.com",
            "client_status": "active",
        }
    ]

    with (
        patch(
            "backend.jobs.auto_practice_creator.check_existing_renewal_practice", return_value=False
        ),
        patch(
            "backend.jobs.auto_practice_creator.create_renewal_practice",
            return_value=None,  # Creation failed
        ),
    ):
        stats = await run_auto_practice_creator(mock_pool)

    assert stats["visas_checked"] == 1
    assert stats["practices_created"] == 0
    assert stats["practices_skipped"] == 0
    assert stats["errors"] == 1
