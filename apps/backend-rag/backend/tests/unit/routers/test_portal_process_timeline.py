"""Tests for portal process timeline endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers.portal_process_timeline import _build_timeline


@pytest.mark.asyncio
async def test_timeline_returns_steps_for_valid_practice() -> None:
    """Timeline endpoint returns ordered steps for a practice belonging to the client."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 10,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        "assigned_to": "asya@balizero.com",
    }

    mock_conn.fetch.return_value = [
        {
            "old_status": None,
            "new_status": "inquiry",
            "changed_at": "2026-01-15T10:00:00+00:00",
            "changed_by": "system",
        },
        {
            "old_status": "inquiry",
            "new_status": "quotation_sent",
            "changed_at": "2026-01-15T14:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "quotation_sent",
            "new_status": "payment_pending",
            "changed_at": "2026-01-16T09:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "payment_pending",
            "new_status": "in_progress",
            "changed_at": "2026-01-17T11:00:00+00:00",
            "changed_by": "system",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=10, client_id=1)

    assert result is not None
    assert result["practice_id"] == 10
    assert result["practice_name"] == "KITAS B211A"
    assert result["current_status"] == "in_progress"
    assert len(result["steps"]) == 4
    assert result["steps"][0]["status"] == "inquiry"
    assert result["steps"][0]["completed"] is True
    assert result["steps"][-1]["status"] == "in_progress"
    assert result["steps"][-1]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_returns_none_for_wrong_client() -> None:
    """Timeline endpoint returns None if practice does not belong to the client."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=999, client_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_timeline_fallback_when_no_status_log() -> None:
    """Timeline returns single step when practice_status_log table doesn't exist."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 5,
        "client_id": 1,
        "status": "waiting_documents",
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "damar@balizero.com",
    }

    # Simulate table not existing
    mock_conn.fetch.side_effect = Exception("relation practice_status_log does not exist")

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=5, client_id=1)

    assert result is not None
    assert result["practice_name"] == "PT PMA Setup"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["status"] == "waiting_documents"
    assert result["steps"][0]["is_current"] is True
