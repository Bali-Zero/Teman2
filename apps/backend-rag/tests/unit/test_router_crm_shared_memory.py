"""
Unit tests for CRM Shared Memory Router
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.crm_shared_memory import (
    get_client_full_context,
    get_team_overview,
    get_upcoming_renewals,
    search_shared_memory,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_request():
    """Mock FastAPI request object"""
    request = MagicMock()
    request.state = MagicMock()
    return request


# ============================================================================
# Tests for search_shared_memory
# ============================================================================


@pytest.mark.asyncio
async def test_search_shared_memory_renewal_query(mock_asyncpg_pool, mock_request):
    """Test search for renewal/expiry queries"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "client_name": "Test Client",
                "email": "test@example.com",
                "practice_type": "KITAS",
                "expiry_date": "2024-12-31",
                "days_until_expiry": 30,
            }
        ]
    )

    result = await search_shared_memory(
        q="clients with expiring KITAS", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "practices" in result
    assert "interpretation" in result
    assert len(result["practices"]) == 1
    assert (
        "expir" in result["interpretation"][0].lower()
        or "renewal" in result["interpretation"][0].lower()
    )


@pytest.mark.asyncio
async def test_search_shared_memory_client_query(mock_asyncpg_pool, mock_request):
    """Test search for client queries"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "full_name": "John Smith",
                "email": "john@example.com",
                "status": "active",
            }
        ]
    )

    result = await search_shared_memory(
        q="clients named John Smith", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "clients" in result
    assert isinstance(result["clients"], list)


@pytest.mark.asyncio
async def test_search_shared_memory_practice_query(mock_asyncpg_pool, mock_request):
    """Test search for practice queries"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "client_name": "Test Client",
                "practice_type": "PT PMA",
                "status": "in_progress",
            }
        ]
    )

    result = await search_shared_memory(
        q="PT PMA practices in progress", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "practices" in result
    assert isinstance(result["practices"], list)


@pytest.mark.asyncio
async def test_search_shared_memory_interaction_query(mock_asyncpg_pool, mock_request):
    """Test search for interaction queries"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "client_name": "Test Client",
                "interaction_type": "chat",
                "interaction_date": "2024-01-01",
            }
        ]
    )

    result = await search_shared_memory(
        q="recent interactions", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "interactions" in result
    assert isinstance(result["interactions"], list)


@pytest.mark.asyncio
async def test_search_shared_memory_urgent_query(mock_asyncpg_pool, mock_request):
    """Test search for urgent practices"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "client_name": "Test Client",
                "practice_type": "KITAS",
                "priority": "urgent",
            }
        ]
    )

    result = await search_shared_memory(
        q="urgent practices", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "practices" in result
    assert isinstance(result["practices"], list)


@pytest.mark.asyncio
async def test_search_shared_memory_empty_results(mock_asyncpg_pool, mock_request):
    """Test search with no results"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await search_shared_memory(
        q="nonexistent query", limit=20, request=mock_request, db_pool=pool
    )

    assert "query" in result
    assert "clients" in result
    assert "practices" in result
    assert "interactions" in result
    assert len(result["clients"]) == 0
    assert len(result["practices"]) == 0
    assert len(result["interactions"]) == 0


@pytest.mark.asyncio
async def test_search_shared_memory_database_error(mock_asyncpg_pool, mock_request):
    """Test search with database error"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    # Use a query that will trigger a SQL execution
    with pytest.raises(HTTPException) as exc_info:
        await search_shared_memory(
            q="urgent practices", limit=20, request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_search_shared_memory_client_with_practices(mock_asyncpg_pool, mock_request):
    """Test search for client with practices"""
    pool, conn = mock_asyncpg_pool

    # Mock fetch to return clients first, then practices
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "id": 1,
                    "full_name": "John Smith",
                    "email": "john@example.com",
                    "total_practices": 5,
                    "active_practices": 2,
                }
            ],  # clients
            [
                {
                    "id": 1,
                    "client_name": "John Smith",
                    "practice_type_name": "KITAS",
                    "status": "in_progress",
                }
            ],  # practices for clients
        ]
    )

    result = await search_shared_memory(
        q="John Smith", limit=20, request=mock_request, db_pool=pool
    )

    assert "clients" in result
    assert len(result["clients"]) > 0
    assert "practices" in result


@pytest.mark.asyncio
async def test_search_shared_memory_recent_interactions_with_30_days(
    mock_asyncpg_pool, mock_request
):
    """Test recent interactions with 30 days keyword"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[{"id": 1, "client_name": "Test", "interaction_date": "2024-01-01"}]
    )

    result = await search_shared_memory(
        q="recent interactions last 30 days", limit=20, request=mock_request, db_pool=pool
    )

    assert "interactions" in result


@pytest.mark.asyncio
async def test_search_shared_memory_recent_interactions_today(mock_asyncpg_pool, mock_request):
    """Test recent interactions with today keyword"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[{"id": 1, "client_name": "Test", "interaction_date": "2024-01-01"}]
    )

    result = await search_shared_memory(
        q="interactions today", limit=20, request=mock_request, db_pool=pool
    )

    assert "interactions" in result


@pytest.mark.asyncio
async def test_search_shared_memory_recent_interactions_week(mock_asyncpg_pool, mock_request):
    """Test recent interactions with week keyword"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[{"id": 1, "client_name": "Test", "interaction_date": "2024-01-01"}]
    )

    result = await search_shared_memory(
        q="interactions last week", limit=20, request=mock_request, db_pool=pool
    )

    assert "interactions" in result


# ============================================================================
# Tests for get_upcoming_renewals
# ============================================================================


@pytest.mark.asyncio
async def test_get_upcoming_renewals_success(mock_asyncpg_pool, mock_request):
    """Test successful retrieval of upcoming renewals"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {
                "client_name": "Test Client",
                "email": "test@example.com",
                "practice_type": "KITAS",
                "expiry_date": "2024-12-31",
                "days_until_expiry": 30,
            }
        ]
    )

    # Use __wrapped__ to bypass cache decorator
    result = await get_upcoming_renewals.__wrapped__(days=90, request=mock_request, db_pool=pool)

    assert "total_renewals" in result
    assert "days_ahead" in result
    assert "renewals" in result
    assert result["total_renewals"] == 1
    assert result["days_ahead"] == 90


@pytest.mark.asyncio
async def test_get_upcoming_renewals_empty(mock_asyncpg_pool, mock_request):
    """Test upcoming renewals with no results"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    # Use __wrapped__ to bypass cache decorator
    result = await get_upcoming_renewals.__wrapped__(days=30, request=mock_request, db_pool=pool)

    assert result["total_renewals"] == 0
    assert len(result["renewals"]) == 0


@pytest.mark.asyncio
async def test_get_upcoming_renewals_exception(mock_asyncpg_pool, mock_request):
    """Test upcoming renewals with database exception"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    # Use __wrapped__ to bypass cache decorator
    with pytest.raises(HTTPException) as exc_info:
        await get_upcoming_renewals.__wrapped__(days=90, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_client_full_context
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_full_context_success(mock_asyncpg_pool, mock_request):
    """Test successful retrieval of client full context"""
    pool, conn = mock_asyncpg_pool

    # Mock fetchrow for client
    conn.fetchrow = AsyncMock(
        return_value={
            "id": 1,
            "full_name": "Test Client",
            "email": "test@example.com",
            "first_contact_date": datetime.now(),
            "last_interaction_date": datetime.now(),
        }
    )

    # Mock fetch for practices, interactions, renewals
    conn.fetch = AsyncMock(
        side_effect=[
            [{"id": 1, "status": "in_progress", "practice_type_name": "KITAS"}],  # practices
            [
                {"id": 1, "interaction_date": datetime.now(), "action_items": ["Follow up"]}
            ],  # interactions
            [{"id": 1, "practice_type_name": "KITAS", "days_until_expiry": 30}],  # renewals
        ]
    )

    result = await get_client_full_context(client_id=1, request=mock_request, db_pool=pool)

    assert "client" in result
    assert "practices" in result
    assert "interactions" in result
    assert "renewals" in result
    assert "action_items" in result
    assert "summary" in result
    assert result["practices"]["total"] == 1
    assert result["practices"]["active"] == 1


@pytest.mark.asyncio
async def test_get_client_full_context_not_found(mock_asyncpg_pool, mock_request):
    """Test client full context with non-existent client"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_client_full_context(client_id=999, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_client_full_context_exception(mock_asyncpg_pool, mock_request):
    """Test client full context with database exception"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_full_context(client_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_team_overview
# ============================================================================


@pytest.mark.asyncio
async def test_get_team_overview_success(mock_asyncpg_pool, mock_request):
    """Test successful retrieval of team overview"""
    pool, conn = mock_asyncpg_pool

    # Mock fetchrow for counts
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"count": 50},  # total_active_clients
            {"count": 10},  # renewals_next_30_days
            {"count": 25},  # interactions_last_7_days
        ]
    )

    # Mock fetch for lists
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {"status": "in_progress", "count": 20},
                {"status": "completed", "count": 30},
            ],  # practices_by_status
            [{"assigned_to": "team1@example.com", "count": 15}],  # active_practices_by_team_member
            [{"code": "KITAS", "name": "KITAS", "count": 10}],  # active_practices_by_type
        ]
    )

    # Use __wrapped__ to bypass cache decorator
    result = await get_team_overview.__wrapped__(request=mock_request, db_pool=pool)

    assert "total_active_clients" in result
    assert "practices_by_status" in result
    assert "active_practices_by_team_member" in result
    assert "renewals_next_30_days" in result
    assert "interactions_last_7_days" in result
    assert "active_practices_by_type" in result
    assert result["total_active_clients"] == 50
    assert result["renewals_next_30_days"] == 10


@pytest.mark.asyncio
async def test_get_team_overview_exception(mock_asyncpg_pool, mock_request):
    """Test team overview with database exception"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    # Use __wrapped__ to bypass cache decorator
    with pytest.raises(HTTPException) as exc_info:
        await get_team_overview.__wrapped__(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Additional Tests for coverage
# ============================================================================


@pytest.mark.asyncio
async def test_search_shared_memory_practice_type_search(mock_asyncpg_pool, mock_request):
    """Test practice type specific search"""
    pool, conn = mock_asyncpg_pool

    # Setup conn fetch to return appropriate data
    # Order: 1) client search, 2) _get_practice_codes(), 3) practice type search
    conn.fetch = AsyncMock(
        side_effect=[
            [],  # clients query (no clients found for "KITAS")
            [{"code": "KITAS"}, {"code": "PT_PMA"}, {"code": "KITAP"}],  # _get_practice_codes()
            [
                {
                    "id": 1,
                    "practice_type_name": "KITAS",
                    "client_name": "Test Client",
                    "status": "in_progress",
                }
            ],  # practice type search
        ]
    )

    # Search for specific practice type
    result = await search_shared_memory(
        q="KITAS practices", limit=20, request=mock_request, db_pool=pool
    )

    assert "practices" in result
    assert len(result["practices"]) == 1
    assert "interpretation" in result


@pytest.mark.asyncio
async def test_search_shared_memory_practice_type_active_filter(mock_asyncpg_pool, mock_request):
    """Test practice type search with 'active' keyword"""
    pool, conn = mock_asyncpg_pool

    # Order: 1) client search, 2) _get_practice_codes(), 3) practice type search
    conn.fetch = AsyncMock(
        side_effect=[
            [],  # clients query
            [{"code": "KITAS"}, {"code": "PT_PMA"}, {"code": "KITAP"}],  # _get_practice_codes()
            [
                {"id": 1, "practice_type_name": "PT PMA", "status": "in_progress"}
            ],  # practice type search
        ]
    )

    result = await search_shared_memory(
        q="active PT_PMA practices", limit=20, request=mock_request, db_pool=pool
    )

    assert "practices" in result
    assert len(result["practices"]) == 1


@pytest.mark.asyncio
async def test_search_shared_memory_practice_type_completed_filter(mock_asyncpg_pool, mock_request):
    """Test practice type search with 'completed' keyword"""
    pool, conn = mock_asyncpg_pool

    # Order: 1) client search, 2) _get_practice_codes(), 3) practice type search
    conn.fetch = AsyncMock(
        side_effect=[
            [],  # clients query
            [{"code": "KITAS"}, {"code": "PT_PMA"}, {"code": "KITAP"}],  # _get_practice_codes()
            [
                {"id": 1, "practice_type_name": "KITAS", "status": "completed"}
            ],  # practice type search
        ]
    )

    result = await search_shared_memory(
        q="completed KITAS", limit=20, request=mock_request, db_pool=pool
    )

    assert "practices" in result
    assert len(result["practices"]) == 1


@pytest.mark.asyncio
async def test_get_client_full_context_without_action_items(mock_asyncpg_pool, mock_request):
    """Test client full context when interactions have no action_items"""
    pool, conn = mock_asyncpg_pool

    # Mock fetchrow for client
    conn.fetchrow = AsyncMock(
        return_value={
            "id": 1,
            "full_name": "Test Client",
            "email": "test@example.com",
            "first_contact_date": datetime.now(),
            "last_interaction_date": datetime.now(),
        }
    )

    # Mock fetch - interactions without action_items
    conn.fetch = AsyncMock(
        side_effect=[
            [{"id": 1, "status": "in_progress", "practice_type_name": "KITAS"}],  # practices
            [
                {"id": 1, "interaction_date": datetime.now()},  # interaction without action_items
                {
                    "id": 2,
                    "interaction_date": datetime.now(),
                    "action_items": None,
                },  # interaction with None action_items
            ],  # interactions
            [],  # renewals
        ]
    )

    result = await get_client_full_context(client_id=1, request=mock_request, db_pool=pool)

    assert "client" in result
    assert "action_items" in result
    # When no interactions have action_items, list should be empty
    assert result["action_items"] == []
