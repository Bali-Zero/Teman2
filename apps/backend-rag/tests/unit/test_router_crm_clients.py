"""
Unit tests for CRM Clients Router
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.crm_clients import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    create_client,
    delete_client,
    get_client,
    get_client_by_email,
    get_client_summary,
    get_clients_stats,
    list_clients,
    update_client,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool"""
    from unittest.mock import AsyncMock

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


@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL connection (legacy)"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def mock_settings():
    """Mock settings"""
    mock = MagicMock()
    mock.database_url = "postgresql://test:test@localhost/test"
    return mock


@pytest.fixture
def sample_client_data():
    """Sample client data"""
    return {
        "id": 1,
        "uuid": "test-uuid-123",
        "full_name": "Test Client",
        "email": "test@example.com",
        "phone": "+1234567890",
        "whatsapp": "+1234567890",
        "nationality": "Italian",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "team@example.com",
        "first_contact_date": datetime.now(),
        "last_interaction_date": None,
        "tags": ["vip"],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


# ============================================================================
# Tests for create_client
# ============================================================================


@pytest.mark.asyncio
async def test_create_client_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful client creation"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    conn.execute = AsyncMock()

    client_data = ClientCreate(
        full_name="Test Client",
        email="test@example.com",
        phone="+1234567890",
        tags=["vip"],
    )

    result = await create_client(
        client_data, created_by="admin@example.com", request=mock_request, db_pool=pool
    )

    assert isinstance(result, ClientResponse)
    assert result.full_name == "Test Client"
    assert result.email == "test@example.com"


@pytest.mark.asyncio
async def test_create_client_database_error(mock_asyncpg_pool, mock_request):
    """Test client creation with database error"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    client_data = ClientCreate(full_name="Test Client")

    with pytest.raises(HTTPException) as exc_info:
        await create_client(
            client_data, created_by="admin@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 500


# NOTE: test_create_client_no_database_url removed - now uses dependency injection


# ============================================================================
# Tests for get_clients
# ============================================================================


@pytest.mark.asyncio
async def test_get_clients_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful clients retrieval"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_client_data])

    result = await list_clients(limit=10, offset=0, request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].full_name == "Test Client"


@pytest.mark.asyncio
async def test_get_clients_with_filters(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test clients retrieval with filters"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_client_data])

    result = await list_clients(
        limit=10,
        offset=0,
        status="active",
        assigned_to="team@example.com",
        search="Test",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_clients_empty(mock_asyncpg_pool, mock_request):
    """Test clients retrieval with no results"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await list_clients(request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# Tests for get_client
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful client retrieval by ID"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)

    result = await get_client(client_id=1, request=mock_request, db_pool=pool)

    assert isinstance(result, ClientResponse)
    assert result.id == 1
    assert result.full_name == "Test Client"


@pytest.mark.asyncio
async def test_get_client_not_found(mock_asyncpg_pool, mock_request):
    """Test client retrieval with non-existent ID"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_client(client_id=999, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 404


# ============================================================================
# Tests for update_client
# ============================================================================


@pytest.mark.asyncio
async def test_update_client_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful client update"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    updated_data = {**sample_client_data, "status": "active"}
    conn.fetchrow = AsyncMock(return_value=updated_data)
    conn.execute = AsyncMock()

    update_data = ClientUpdate(status="active", notes="Updated notes")

    result = await update_client(
        client_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, ClientResponse)
    assert result.status == "active"


@pytest.mark.asyncio
async def test_update_client_not_found(mock_asyncpg_pool, mock_request):
    """Test client update with non-existent ID"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    update_data = ClientUpdate(status="inactive")

    with pytest.raises(HTTPException) as exc_info:
        await update_client(
            client_id=999,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_client_partial(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test partial client update"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    conn.execute = AsyncMock()

    update_data = ClientUpdate(email="newemail@example.com")

    result = await update_client(
        client_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, ClientResponse)


# ============================================================================
# Additional tests for IntegrityError and exception handlers
# ============================================================================


@pytest.mark.asyncio
async def test_create_client_integrity_error(mock_asyncpg_pool, mock_request):
    """Test client creation with IntegrityError (duplicate email)"""
    from unittest.mock import AsyncMock

    import asyncpg

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=asyncpg.UniqueViolationError("Duplicate email"))

    client_data = ClientCreate(full_name="Test Client", email="duplicate@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await create_client(
            client_data, created_by="admin@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_clients_exception(mock_asyncpg_pool, mock_request):
    """Test list_clients with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database connection lost"))

    with pytest.raises(HTTPException) as exc_info:
        await list_clients(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_client_exception(mock_asyncpg_pool, mock_request):
    """Test get_client with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client(client_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_client_by_email
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_by_email_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful client retrieval by email"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)

    result = await get_client_by_email(email="test@example.com", request=mock_request, db_pool=pool)

    assert isinstance(result, ClientResponse)
    assert result.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_client_by_email_not_found(mock_asyncpg_pool, mock_request):
    """Test client retrieval by email with non-existent email"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_client_by_email(
            email="nonexistent@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_client_by_email_exception(mock_asyncpg_pool, mock_request):
    """Test get_client_by_email with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_by_email(email="test@example.com", request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for update_client error cases
# ============================================================================


@pytest.mark.asyncio
async def test_update_client_invalid_field(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test update_client with valid field (full_name IS in allowed fields now)"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    conn.execute = AsyncMock()

    # full_name IS in allowed fields in the new implementation
    update_data = ClientUpdate(full_name="Updated Name")

    result = await update_client(
        client_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    # Should succeed since full_name is valid
    assert isinstance(result, ClientResponse)


@pytest.mark.asyncio
async def test_update_client_no_fields(mock_asyncpg_pool, mock_request):
    """Test update_client with no fields to update"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock()

    # Create empty update (all None values)
    update_data = ClientUpdate()

    with pytest.raises(HTTPException) as exc_info:
        await update_client(
            client_id=1,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 400
    assert "No fields to update" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_client_json_fields(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test update_client with JSON fields (tags, custom_fields)"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    conn.execute = AsyncMock()

    # Update tags and custom_fields
    update_data = ClientUpdate(tags=["vip", "urgent"], custom_fields={"priority": "high"})

    result = await update_client(
        client_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, ClientResponse)
    conn.fetchrow.assert_called()


@pytest.mark.asyncio
async def test_update_client_exception(mock_asyncpg_pool, mock_request):
    """Test update_client with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    update_data = ClientUpdate(status="active")

    with pytest.raises(HTTPException) as exc_info:
        await update_client(
            client_id=1,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for delete_client
# ============================================================================


@pytest.mark.asyncio
async def test_delete_client_success(mock_asyncpg_pool, mock_request):
    """Test successful client deletion (soft delete)"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.execute = AsyncMock()

    result = await delete_client(
        client_id=1, deleted_by="admin@example.com", request=mock_request, db_pool=pool
    )

    assert result["success"] is True
    assert "inactive" in result["message"]


@pytest.mark.asyncio
async def test_delete_client_not_found(mock_asyncpg_pool, mock_request):
    """Test delete_client with non-existent ID"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await delete_client(
            client_id=999, deleted_by="admin@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_client_exception(mock_asyncpg_pool, mock_request):
    """Test delete_client with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await delete_client(
            client_id=1, deleted_by="admin@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_client_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_summary_success(mock_asyncpg_pool, mock_request, sample_client_data):
    """Test successful client summary retrieval"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    # Mock fetchrow for client data
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    # Mock fetch for practices, interactions, renewals
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "id": 1,
                    "status": "in_progress",
                    "practice_type_name": "Visa",
                    "category": "immigration",
                }
            ],  # practices
            [{"id": 1, "type": "email", "interaction_date": datetime.now()}],  # interactions
            [{"id": 1, "status": "pending", "alert_date": datetime.now()}],  # renewals
        ]
    )

    result = await get_client_summary(client_id=1, request=mock_request, db_pool=pool)

    assert "client" in result
    assert "practices" in result
    assert "interactions" in result
    assert "renewals" in result
    assert result["practices"]["total"] == 1
    assert result["practices"]["active"] == 1


@pytest.mark.asyncio
async def test_get_client_summary_not_found(mock_asyncpg_pool, mock_request):
    """Test get_client_summary with non-existent client"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_client_summary(client_id=999, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_client_summary_exception(mock_asyncpg_pool, mock_request):
    """Test get_client_summary with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_summary(client_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_clients_stats
# ============================================================================


@pytest.mark.asyncio
async def test_get_clients_stats_success(mock_asyncpg_pool, mock_request):
    """Test successful clients stats retrieval"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool

    # Mock fetch for by_status and by_team_member
    conn.fetch = AsyncMock(
        side_effect=[
            [{"status": "active", "count": 10}, {"status": "inactive", "count": 5}],  # by_status
            [
                {"assigned_to": "team1@example.com", "count": 8},
                {"assigned_to": "team2@example.com", "count": 7},
            ],  # by_team_member
        ]
    )
    # Mock fetchrow for new_last_30_days
    conn.fetchrow = AsyncMock(return_value={"count": 3})

    # Patch the cache to skip caching during tests
    with patch("app.routers.crm_clients.cached", lambda **kwargs: lambda f: f):
        # Import fresh to apply the patch (or call the underlying function directly)
        result = await get_clients_stats.__wrapped__(request=mock_request, db_pool=pool)

    assert "total" in result
    assert "by_status" in result
    assert "by_team_member" in result
    assert "new_last_30_days" in result
    assert result["total"] == 15  # 10 + 5
    assert result["by_status"]["active"] == 10
    assert result["new_last_30_days"] == 3


@pytest.mark.asyncio
async def test_get_clients_stats_exception(mock_asyncpg_pool, mock_request):
    """Test get_clients_stats with database exception"""
    from unittest.mock import AsyncMock

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        # Call the underlying function directly to bypass cache decorator
        await get_clients_stats.__wrapped__(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500
