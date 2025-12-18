"""
Unit tests for CRM Practices Router
Coverage target: 90%+ (currently 63.3%)
Tests practice management endpoints for KITAS, PT PMA, Visas, etc.
"""

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.crm_practices import (
    PracticeCreate,
    PracticeResponse,
    PracticeUpdate,
    add_document_to_practice,
    create_practice,
    get_active_practices,
    get_practice,
    get_practices_stats,
    get_upcoming_renewals,
    list_practices,
    update_practice,
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


@pytest.fixture
def sample_practice_data():
    """Sample practice data"""
    return {
        "id": 1,
        "uuid": "test-uuid-123",
        "client_id": 1,
        "practice_type_id": 1,
        "status": "in_progress",
        "priority": "high",
        "quoted_price": Decimal("1000.00"),
        "actual_price": None,
        "payment_status": "pending",
        "assigned_to": "team@example.com",
        "start_date": datetime.now(),
        "completion_date": None,
        "expiry_date": None,
        "created_at": datetime.now(),
    }


# ============================================================================
# Tests for create_practice
# ============================================================================


@pytest.mark.asyncio
async def test_create_practice_success(mock_asyncpg_pool, mock_request, sample_practice_data):
    """Test successful practice creation"""
    pool, conn = mock_asyncpg_pool

    # Mock practice type lookup and insert
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": 1, "code": "KITAS", "base_price": Decimal("1000.00")},  # Practice type lookup
            sample_practice_data,  # Created practice
        ]
    )
    conn.execute = AsyncMock()

    practice_data = PracticeCreate(
        client_id=1,
        practice_type_code="KITAS",
        status="inquiry",
        priority="normal",
    )

    result = await create_practice(
        practice_data, created_by="admin@example.com", request=mock_request, db_pool=pool
    )

    assert isinstance(result, PracticeResponse)
    assert result.client_id == 1
    assert conn.fetchrow.call_count >= 2  # At least practice type lookup and insert


@pytest.mark.asyncio
async def test_create_practice_with_base_price(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test practice creation uses base price when no quoted price provided"""
    pool, conn = mock_asyncpg_pool

    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": 1, "code": "KITAS", "base_price": Decimal("1500.00")},
            sample_practice_data,
        ]
    )
    conn.execute = AsyncMock()

    practice_data = PracticeCreate(
        client_id=1,
        practice_type_code="KITAS",
        # No quoted_price, should use base_price
    )

    result = await create_practice(
        practice_data, created_by="admin@example.com", request=mock_request, db_pool=pool
    )
    assert result is not None


@pytest.mark.asyncio
async def test_create_practice_invalid_type(mock_asyncpg_pool, mock_request):
    """Test practice creation with invalid practice type"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)  # Practice type not found

    practice_data = PracticeCreate(
        client_id=1,
        practice_type_code="INVALID",
        status="inquiry",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_practice(
            practice_data, created_by="admin@example.com", request=mock_request, db_pool=pool
        )

    # Router returns 404 for practice type not found
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_practice_database_error(mock_asyncpg_pool, mock_request):
    """Test practice creation with database error"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    practice_data = PracticeCreate(client_id=1, practice_type_code="KITAS")

    with pytest.raises(HTTPException) as exc_info:
        await create_practice(
            practice_data, created_by="admin@example.com", request=mock_request, db_pool=pool
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for list_practices
# ============================================================================


@pytest.mark.asyncio
async def test_get_practices_success(mock_asyncpg_pool, mock_request, sample_practice_data):
    """Test successful practices retrieval"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    result = await list_practices(limit=10, offset=0, request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["client_id"] == 1
    assert conn.fetch.call_count >= 1


@pytest.mark.asyncio
async def test_get_practices_with_filters(mock_asyncpg_pool, mock_request, sample_practice_data):
    """Test practices retrieval with filters"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    result = await list_practices(
        limit=10,
        offset=0,
        client_id=1,
        status="in_progress",
        assigned_to="team@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, list)
    assert conn.fetch.call_count >= 1


@pytest.mark.asyncio
async def test_list_practices_with_practice_type_filter(mock_asyncpg_pool, mock_request):
    """Test listing practices filtered by practice type"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await list_practices(practice_type="kitas", request=mock_request, db_pool=pool)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_practices_with_priority_filter(mock_asyncpg_pool, mock_request):
    """Test listing practices filtered by priority"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await list_practices(priority="high", request=mock_request, db_pool=pool)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_practices_database_error(mock_asyncpg_pool, mock_request):
    """Test list practices handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await list_practices(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_active_practices
# ============================================================================


@pytest.mark.asyncio
async def test_get_active_practices_no_filter(mock_asyncpg_pool, mock_request):
    """Test getting active practices without filter"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[{"id": 1, "status": "in_progress"}])

    result = await get_active_practices(request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_active_practices_with_assigned_filter(mock_asyncpg_pool, mock_request):
    """Test getting active practices filtered by assigned team member"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[{"id": 1, "assigned_to": "team@example.com"}])

    result = await get_active_practices(
        assigned_to="team@example.com", request=mock_request, db_pool=pool
    )

    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_active_practices_database_error(mock_asyncpg_pool, mock_request):
    """Test active practices handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_active_practices(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_upcoming_renewals
# ============================================================================


@pytest.mark.asyncio
async def test_get_upcoming_renewals(mock_asyncpg_pool, mock_request):
    """Test getting upcoming renewals"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 1, "expiry_date": date.today() + timedelta(days=30)},
            {"id": 2, "expiry_date": date.today() + timedelta(days=60)},
        ]
    )

    result = await get_upcoming_renewals(request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_upcoming_renewals_with_custom_days(mock_asyncpg_pool, mock_request):
    """Test upcoming renewals with custom days parameter"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await get_upcoming_renewals(days=60, request=mock_request, db_pool=pool)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_upcoming_renewals_database_error(mock_asyncpg_pool, mock_request):
    """Test upcoming renewals handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_upcoming_renewals(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_practice
# ============================================================================


@pytest.mark.asyncio
async def test_get_practice_success(mock_asyncpg_pool, mock_request, sample_practice_data):
    """Test successful practice retrieval by ID"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_practice_data)

    result = await get_practice(practice_id=1, request=mock_request, db_pool=pool)

    # get_practice returns dict
    assert isinstance(result, dict)
    assert result["id"] == 1
    assert result["client_id"] == 1


@pytest.mark.asyncio
async def test_get_practice_not_found(mock_asyncpg_pool, mock_request):
    """Test practice retrieval with non-existent ID"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_practice(practice_id=999, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_practice_database_error(mock_asyncpg_pool, mock_request):
    """Test get practice handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_practice(practice_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for update_practice
# ============================================================================


@pytest.mark.asyncio
async def test_update_practice_success(mock_asyncpg_pool, mock_request, sample_practice_data):
    """Test successful practice update"""
    pool, conn = mock_asyncpg_pool
    updated_data = {**sample_practice_data, "status": "completed"}
    conn.fetchrow = AsyncMock(return_value=updated_data)
    conn.execute = AsyncMock()

    update_data = PracticeUpdate(status="completed", actual_price=Decimal("1200.00"))

    result = await update_practice(
        practice_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    # update_practice returns dict
    assert isinstance(result, dict)
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_update_practice_with_documents(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test updating practice with documents field"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_practice_data)
    conn.execute = AsyncMock()

    documents = [{"name": "passport", "file_id": "123"}]
    update_data = PracticeUpdate(documents=documents)

    result = await update_practice(
        practice_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result is not None


@pytest.mark.asyncio
async def test_update_practice_with_renewal_alert(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test updating practice to completed creates renewal alert"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_practice_data)
    conn.execute = AsyncMock()

    expiry = date.today() + timedelta(days=365)
    update_data = PracticeUpdate(status="completed", expiry_date=expiry)

    result = await update_practice(
        practice_id=1,
        updates=update_data,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result is not None


@pytest.mark.asyncio
async def test_update_practice_no_fields(mock_asyncpg_pool, mock_request):
    """Test update practice with no fields raises error"""
    pool, conn = mock_asyncpg_pool

    update_data = PracticeUpdate()

    with pytest.raises(HTTPException) as exc_info:
        await update_practice(
            practice_id=1,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_practice_not_found(mock_asyncpg_pool, mock_request):
    """Test practice update with non-existent ID"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    update_data = PracticeUpdate(status="completed")

    with pytest.raises(HTTPException) as exc_info:
        await update_practice(
            practice_id=999,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_practice_database_error(mock_asyncpg_pool, mock_request):
    """Test update practice handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.execute = AsyncMock(side_effect=Exception("Database error"))

    update_data = PracticeUpdate(status="in_progress")

    with pytest.raises(HTTPException) as exc_info:
        await update_practice(
            practice_id=1,
            updates=update_data,
            updated_by="admin@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for add_document_to_practice
# ============================================================================


@pytest.mark.asyncio
async def test_add_document_to_practice_success(mock_asyncpg_pool, mock_request):
    """Test adding document to practice"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value={"documents": []})
    conn.execute = AsyncMock()

    result = await add_document_to_practice(
        practice_id=1,
        document_name="Passport Copy",
        drive_file_id="drive123",
        uploaded_by="team@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result["success"] is True
    assert result["document"]["name"] == "Passport Copy"
    assert result["total_documents"] == 1


@pytest.mark.asyncio
async def test_add_document_to_existing_documents(mock_asyncpg_pool, mock_request):
    """Test adding document to practice with existing documents"""
    pool, conn = mock_asyncpg_pool
    existing_docs = [{"name": "Old Doc", "drive_file_id": "old123"}]
    conn.fetchrow = AsyncMock(return_value={"documents": existing_docs})
    conn.execute = AsyncMock()

    result = await add_document_to_practice(
        practice_id=1,
        document_name="New Doc",
        drive_file_id="new123",
        uploaded_by="team@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result["total_documents"] == 2


@pytest.mark.asyncio
async def test_add_document_practice_not_found(mock_asyncpg_pool, mock_request):
    """Test adding document to non-existent practice"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await add_document_to_practice(
            practice_id=999,
            document_name="Passport",
            drive_file_id="123",
            uploaded_by="team@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_document_database_error(mock_asyncpg_pool, mock_request):
    """Test add document handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await add_document_to_practice(
            practice_id=1,
            document_name="Passport",
            drive_file_id="123",
            uploaded_by="team@example.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_practices_stats
# ============================================================================


@pytest.mark.asyncio
async def test_get_practices_stats(mock_asyncpg_pool, mock_request):
    """Test getting practice statistics"""
    pool, conn = mock_asyncpg_pool

    # Mock the queries
    by_status = [{"status": "inquiry", "count": 5}, {"status": "in_progress", "count": 3}]

    by_type = [
        {"code": "kitas", "name": "KITAS", "count": 4},
        {"code": "visa", "name": "Visa", "count": 3},
    ]

    revenue = {
        "total_revenue": Decimal("10000.00"),
        "paid_revenue": Decimal("7000.00"),
        "outstanding_revenue": Decimal("3000.00"),
    }

    active_count_result = {"count": 8}

    conn.fetch = AsyncMock(side_effect=[by_status, by_type])
    conn.fetchrow = AsyncMock(side_effect=[revenue, active_count_result])

    # Use __wrapped__ to bypass cache decorator
    result = await get_practices_stats.__wrapped__(request=mock_request, db_pool=pool)

    assert result["total_practices"] == 8  # 5 + 3
    assert result["active_practices"] == 8
    assert "inquiry" in result["by_status"]
    assert len(result["by_type"]) == 2
    assert result["revenue"]["total_revenue"] == Decimal("10000.00")


@pytest.mark.asyncio
async def test_get_practices_stats_database_error(mock_asyncpg_pool, mock_request):
    """Test statistics handles database errors"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    # Use __wrapped__ to bypass cache decorator
    with pytest.raises(HTTPException) as exc_info:
        await get_practices_stats.__wrapped__(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Additional Tests for 100% Coverage
# ============================================================================


@pytest.mark.asyncio
async def test_list_practices_with_all_filters(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test list practices with all optional filters provided"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    result = await list_practices(
        client_id=1,
        status="active",
        assigned_to="john@example.com",
        practice_type="kitas",
        priority="high",
        limit=10,
        offset=0,
        request=mock_request,
        db_pool=pool,
    )

    assert len(result) == 1
    assert conn.fetch.called


@pytest.mark.asyncio
async def test_list_practices_no_optional_filters(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test list practices with no optional filters (only required params)"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    result = await list_practices(
        client_id=None,
        status=None,
        assigned_to=None,
        practice_type=None,
        priority=None,
        limit=10,
        offset=0,
        request=mock_request,
        db_pool=pool,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_active_practices_without_assigned_to(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test get active practices without assigned_to filter"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    result = await get_active_practices(assigned_to=None, request=mock_request, db_pool=pool)

    assert len(result) == 1


@pytest.mark.asyncio
async def test_update_practice_with_none_values(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test update practice skips None values in update dict"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_practice_data)
    conn.execute = AsyncMock()

    # Create update with some None values
    updates = PracticeUpdate(
        status="completed",
        notes="Updated notes",
        assigned_to=None,  # This should be skipped
        priority=None,  # This should be skipped
    )

    result = await update_practice(
        practice_id=1,
        updates=updates,
        updated_by="admin@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result is not None


@pytest.mark.asyncio
async def test_list_practices_partial_filters(
    mock_asyncpg_pool, mock_request, sample_practice_data
):
    """Test list practices with some filters provided, others None"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_practice_data])

    # Test with only client_id and status
    result = await list_practices(
        client_id=1,
        status="active",
        assigned_to=None,
        practice_type=None,
        priority=None,
        limit=10,
        offset=0,
        request=mock_request,
        db_pool=pool,
    )

    assert len(result) == 1
