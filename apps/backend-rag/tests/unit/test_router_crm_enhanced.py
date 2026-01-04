"""
Unit tests for CRM Enhanced Router
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

from app.routers.crm_enhanced import (
    ClientProfileUpdate,
    DocumentCreate,
    DocumentUpdate,
    FamilyMemberCreate,
    FamilyMemberUpdate,
    archive_document,
    create_document,
    create_family_member,
    delete_family_member,
    get_all_expiry_alerts,
    get_client_documents,
    get_client_profile,
    get_document_categories,
    get_expiry_alerts_summary,
    get_family_members,
    update_client_profile,
    update_document,
    update_family_member,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def sample_client_data():
    """Sample client data"""
    return {
        "id": 1,
        "uuid": "test-uuid-123",
        "full_name": "Test Client",
        "email": "test@example.com",
        "phone": "+1234567890",
        "nationality": "Italian",
        "passport_expiry": "2025-12-31",
        "date_of_birth": "1990-01-01",
        "avatar_url": "https://example.com/avatar.jpg",
        "google_drive_folder_id": "folder123",
        "company_name": "Test Company",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "team@example.com",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_family_member_data():
    """Sample family member data"""
    return {
        "id": 1,
        "full_name": "Jane Doe",
        "relationship": "spouse",
        "date_of_birth": "1992-05-15",
        "nationality": "Italian",
        "passport_expiry": "2025-06-30",
        "visa_expiry": "2024-12-31",
        "email": "jane@example.com",
        "phone": "+1234567891",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_document_data():
    """Sample document data"""
    return {
        "id": 1,
        "document_type": "Passport",
        "document_category": "immigration",
        "file_name": "passport.pdf",
        "file_id": "file123",
        "expiry_date": "2025-12-31",
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


# ============================================================================
# Tests for get_client_profile
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_profile_success(mock_db_pool, sample_client_data):
    """Test successful retrieval of client profile"""
    pool, conn = mock_db_pool

    # Mock client fetch
    conn.fetchrow = AsyncMock(return_value=sample_client_data)
    # Mock family members fetch
    conn.fetch = AsyncMock(return_value=[])
    # Mock documents fetch
    conn.fetch = AsyncMock(return_value=[])
    # Mock expiry_alerts fetch
    conn.fetch = AsyncMock(return_value=[])
    # Mock practices fetch
    conn.fetch = AsyncMock(return_value=[])

    # Setup fetch to return different results on consecutive calls
    async def mock_fetch(query, *args):
        if "client_family_members" in query:
            return []
        elif "documents d" in query:
            return []
        elif "client_expiry_alerts_view" in query:
            return []
        elif "practices p" in query:
            return []
        return []

    conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await get_client_profile(1, pool)

    assert "client" in result
    assert result["client"]["id"] == 1
    assert "family_members" in result
    assert "documents" in result
    assert "expiry_alerts" in result
    assert "practices" in result
    assert "stats" in result
    assert result["stats"]["family_count"] == 0
    assert result["stats"]["documents_count"] == 0
    assert result["stats"]["practices_count"] == 0


@pytest.mark.asyncio
async def test_get_client_profile_not_found(mock_db_pool):
    """Test client profile not found"""
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_client_profile(999, pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_client_profile_with_family_members(
    mock_db_pool, sample_client_data, sample_family_member_data
):
    """Test client profile with family members"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=sample_client_data)

    call_count = 0

    async def mock_fetch(query, *args):
        nonlocal call_count
        call_count += 1
        if "client_family_members" in query:
            return [sample_family_member_data]
        elif "documents d" in query:
            return []
        elif "client_expiry_alerts_view" in query:
            return []
        elif "practices p" in query:
            return []
        return []

    conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await get_client_profile(1, pool)

    assert result["stats"]["family_count"] == 1
    assert len(result["family_members"]) == 1
    assert result["family_members"][0]["full_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_get_client_profile_with_documents(
    mock_db_pool, sample_client_data, sample_document_data
):
    """Test client profile with documents"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=sample_client_data)

    # Setup fetch to return different results on consecutive calls
    fetch_results = [
        [],  # family_members
        [sample_document_data],  # documents
        [],  # expiry_alerts
        [],  # practices
    ]
    fetch_call_count = 0

    async def mock_fetch(query, *args):
        nonlocal fetch_call_count
        result = fetch_results[fetch_call_count % len(fetch_results)]
        fetch_call_count += 1
        return result

    conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await get_client_profile(1, pool)

    assert result["stats"]["documents_count"] == 1
    assert len(result["documents"]) == 1
    assert result["documents"][0]["document_type"] == "Passport"


@pytest.mark.asyncio
async def test_get_client_profile_with_expiry_alerts(mock_db_pool, sample_client_data):
    """Test client profile with expiry alerts"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=sample_client_data)

    alert_data = {
        "entity_type": "document",
        "entity_id": 1,
        "entity_name": "Passport",
        "document_type": "Passport",
        "expiry_date": "2024-12-31",
        "days_until_expiry": 30,
        "alert_color": "red",
    }

    # Setup fetch to return different results on consecutive calls
    fetch_results = [
        [],  # family_members
        [],  # documents
        [alert_data],  # expiry_alerts
        [],  # practices
    ]
    fetch_call_count = 0

    async def mock_fetch(query, *args):
        nonlocal fetch_call_count
        result = fetch_results[fetch_call_count % len(fetch_results)]
        fetch_call_count += 1
        return result

    conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await get_client_profile(1, pool)

    assert result["stats"]["red_alerts"] == 1
    assert len(result["expiry_alerts"]) == 1
    assert result["expiry_alerts"][0]["alert_color"] == "red"


# ============================================================================
# Tests for update_client_profile
# ============================================================================


@pytest.mark.asyncio
async def test_update_client_profile_success(mock_db_pool):
    """Test successful client profile update"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    data = ClientProfileUpdate(
        avatar_url="https://example.com/new-avatar.jpg",
        google_drive_folder_id="new_folder123",
    )

    result = await update_client_profile(1, data, pool)

    assert result["success"] is True
    assert conn.execute.called


@pytest.mark.asyncio
async def test_update_client_profile_all_fields(mock_db_pool):
    """Test client profile update with all fields"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    data = ClientProfileUpdate(
        avatar_url="https://example.com/avatar.jpg",
        google_drive_folder_id="folder123",
        date_of_birth="1990-01-01",
        passport_expiry="2025-12-31",
        company_name="New Company",
    )

    result = await update_client_profile(1, data, pool)

    assert result["success"] is True
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_client_profile_no_fields(mock_db_pool):
    """Test client profile update with no fields"""
    pool, conn = mock_db_pool

    data = ClientProfileUpdate()

    with pytest.raises(HTTPException) as exc_info:
        await update_client_profile(1, data, pool)

    assert exc_info.value.status_code == 400
    assert "No fields to update" in exc_info.value.detail


# ============================================================================
# Tests for get_family_members
# ============================================================================


@pytest.mark.asyncio
async def test_get_family_members_success(mock_db_pool, sample_family_member_data):
    """Test successful retrieval of family members"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[sample_family_member_data])

    result = await get_family_members(1, pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["full_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_get_family_members_empty(mock_db_pool):
    """Test retrieval of family members when empty"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_family_members(1, pool)

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_family_members_ordered(mock_db_pool):
    """Test family members are returned correctly (ordering is done by SQL)"""
    pool, conn = mock_db_pool

    # SQL does the ordering, we just return the data as SQL would
    members = [
        {"id": 2, "full_name": "Spouse", "relationship": "spouse"},
        {"id": 1, "full_name": "Child", "relationship": "child"},
        {"id": 3, "full_name": "Other", "relationship": "other"},
    ]

    conn.fetch = AsyncMock(return_value=members)

    result = await get_family_members(1, pool)

    assert len(result) == 3
    assert all(m["relationship"] in ["spouse", "child", "other"] for m in result)


# ============================================================================
# Tests for create_family_member
# ============================================================================


@pytest.mark.asyncio
async def test_create_family_member_success(mock_db_pool):
    """Test successful family member creation"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.fetchval = AsyncMock(return_value=123)

    data = FamilyMemberCreate(
        full_name="Jane Doe",
        relationship="spouse",
        date_of_birth="1992-05-15",
        nationality="Italian",
        email="jane@example.com",
    )

    result = await create_family_member(1, data, pool)

    assert result["success"] is True
    assert result["id"] == 123
    conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_create_family_member_client_not_found(mock_db_pool):
    """Test family member creation when client not found"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=None)

    data = FamilyMemberCreate(full_name="Jane Doe", relationship="spouse")

    with pytest.raises(HTTPException) as exc_info:
        await create_family_member(999, data, pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_family_member_all_fields(mock_db_pool):
    """Test family member creation with all fields"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.fetchval = AsyncMock(return_value=456)

    data = FamilyMemberCreate(
        full_name="John Doe",
        relationship="child",
        date_of_birth="2010-01-01",
        nationality="Italian",
        passport_number="AB123456",
        passport_expiry="2030-12-31",
        current_visa_type="KITAS",
        visa_expiry="2025-12-31",
        email="john@example.com",
        phone="+1234567890",
        notes="Test notes",
    )

    result = await create_family_member(1, data, pool)

    assert result["success"] is True
    assert result["id"] == 456


# ============================================================================
# Tests for update_family_member
# ============================================================================


@pytest.mark.asyncio
async def test_update_family_member_success(mock_db_pool):
    """Test successful family member update"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    data = FamilyMemberUpdate(full_name="Jane Updated", email="newemail@example.com")

    result = await update_family_member(1, 123, data, pool)

    assert result["success"] is True
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_family_member_no_fields(mock_db_pool):
    """Test family member update with no fields"""
    pool, conn = mock_db_pool

    data = FamilyMemberUpdate()

    with pytest.raises(HTTPException) as exc_info:
        await update_family_member(1, 123, data, pool)

    assert exc_info.value.status_code == 400
    assert "No fields to update" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_family_member_not_found(mock_db_pool):
    """Test family member update when not found"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 0")

    data = FamilyMemberUpdate(full_name="Jane Updated")

    with pytest.raises(HTTPException) as exc_info:
        await update_family_member(1, 999, data, pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


# ============================================================================
# Tests for delete_family_member
# ============================================================================


@pytest.mark.asyncio
async def test_delete_family_member_success(mock_db_pool):
    """Test successful family member deletion"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="DELETE 1")

    result = await delete_family_member(1, 123, pool)

    assert result["success"] is True
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_delete_family_member_not_found(mock_db_pool):
    """Test family member deletion when not found"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="DELETE 0")

    with pytest.raises(HTTPException) as exc_info:
        await delete_family_member(1, 999, pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


# ============================================================================
# Tests for get_client_documents
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_documents_success(mock_db_pool, sample_document_data):
    """Test successful retrieval of client documents"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[sample_document_data])

    result = await get_client_documents(1, pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["document_type"] == "Passport"


@pytest.mark.asyncio
async def test_get_client_documents_with_category(mock_db_pool, sample_document_data):
    """Test client documents filtered by category"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[sample_document_data])

    result = await get_client_documents(1, category="immigration", pool=pool)

    assert len(result) == 1
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_client_documents_include_archived(mock_db_pool, sample_document_data):
    """Test client documents including archived"""
    pool, conn = mock_db_pool

    archived_doc = {**sample_document_data, "is_archived": True}
    conn.fetch = AsyncMock(return_value=[sample_document_data, archived_doc])

    result = await get_client_documents(1, include_archived=True, pool=pool)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_client_documents_empty(mock_db_pool):
    """Test retrieval of client documents when empty"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_client_documents(1, pool=pool)

    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# Tests for create_document
# ============================================================================


@pytest.mark.asyncio
async def test_create_document_success(mock_db_pool):
    """Test successful document creation"""
    pool, conn = mock_db_pool

    conn.fetchval = AsyncMock(return_value=789)

    data = DocumentCreate(
        document_type="Passport",
        document_category="immigration",
        file_name="passport.pdf",
        file_id="file123",
        expiry_date="2025-12-31",
    )

    result = await create_document(1, data, pool)

    assert result["success"] is True
    assert result["id"] == 789
    conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_create_document_all_fields(mock_db_pool):
    """Test document creation with all fields"""
    pool, conn = mock_db_pool

    conn.fetchval = AsyncMock(return_value=999)

    data = DocumentCreate(
        document_type="KITAS",
        document_category="immigration",
        file_name="kitas.pdf",
        file_id="file456",
        file_url="https://example.com/file.pdf",
        google_drive_file_url="https://drive.google.com/file",
        expiry_date="2025-12-31",
        notes="Important document",
        family_member_id=1,
        practice_id=2,
    )

    result = await create_document(1, data, pool)

    assert result["success"] is True
    assert result["id"] == 999


# ============================================================================
# Tests for update_document
# ============================================================================


@pytest.mark.asyncio
async def test_update_document_success(mock_db_pool):
    """Test successful document update"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    data = DocumentUpdate(document_type="Updated Passport", status="verified")

    result = await update_document(1, 123, data, pool)

    assert result["success"] is True
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_document_no_fields(mock_db_pool):
    """Test document update with no fields"""
    pool, conn = mock_db_pool

    data = DocumentUpdate()

    with pytest.raises(HTTPException) as exc_info:
        await update_document(1, 123, data, pool)

    assert exc_info.value.status_code == 400
    assert "No fields to update" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_document_not_found(mock_db_pool):
    """Test document update when not found"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 0")

    data = DocumentUpdate(document_type="Updated")

    with pytest.raises(HTTPException) as exc_info:
        await update_document(1, 999, data, pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_update_document_archive(mock_db_pool):
    """Test document update with is_archived field"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    data = DocumentUpdate(is_archived=True)

    result = await update_document(1, 123, data, pool)

    assert result["success"] is True


# ============================================================================
# Tests for archive_document
# ============================================================================


@pytest.mark.asyncio
async def test_archive_document_success(mock_db_pool):
    """Test successful document archiving"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await archive_document(1, 123, permanent=False, pool=pool)

    assert result["success"] is True
    assert result["action"] == "archived"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_archive_document_permanent_delete(mock_db_pool):
    """Test permanent document deletion"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="DELETE 1")

    result = await archive_document(1, 123, permanent=True, pool=pool)

    assert result["success"] is True
    assert result["action"] == "deleted"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_archive_document_not_found(mock_db_pool):
    """Test document archiving when not found"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 0")

    with pytest.raises(HTTPException) as exc_info:
        await archive_document(1, 999, permanent=False, pool=pool)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_archive_document_permanent_delete_not_found(mock_db_pool):
    """Test permanent deletion when document not found"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="DELETE 0")

    with pytest.raises(HTTPException) as exc_info:
        await archive_document(1, 999, permanent=True, pool=pool)

    assert exc_info.value.status_code == 404


# ============================================================================
# Tests for get_document_categories
# ============================================================================


@pytest.mark.asyncio
async def test_get_document_categories_success(mock_db_pool):
    """Test successful retrieval of document categories"""
    pool, conn = mock_db_pool

    categories = [
        {
            "code": "immigration",
            "name": "Immigration",
            "category_group": "legal",
            "has_expiry": True,
        },
        {"code": "tax", "name": "Tax", "category_group": "legal", "has_expiry": False},
    ]

    conn.fetch = AsyncMock(return_value=categories)

    result = await get_document_categories(pool)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["code"] == "immigration"


@pytest.mark.asyncio
async def test_get_document_categories_empty(mock_db_pool):
    """Test retrieval of document categories when empty"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_document_categories(pool)

    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# Tests for get_all_expiry_alerts
# ============================================================================


@pytest.mark.asyncio
async def test_get_all_expiry_alerts_success(mock_db_pool):
    """Test successful retrieval of expiry alerts"""
    pool, conn = mock_db_pool

    alerts = [
        {
            "entity_type": "document",
            "entity_id": 1,
            "entity_name": "Passport",
            "client_id": 1,
            "client_name": "Test Client",
            "document_type": "Passport",
            "expiry_date": "2024-12-31",
            "days_until_expiry": 30,
            "alert_color": "red",
            "assigned_to": "team@example.com",
        }
    ]

    conn.fetch = AsyncMock(return_value=alerts)

    result = await get_all_expiry_alerts(pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["alert_color"] == "red"


@pytest.mark.asyncio
async def test_get_all_expiry_alerts_with_color_filter(mock_db_pool):
    """Test expiry alerts filtered by color"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_all_expiry_alerts(alert_color="red", pool=pool)

    assert isinstance(result, list)
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_expiry_alerts_with_assigned_to_filter(mock_db_pool):
    """Test expiry alerts filtered by assigned_to"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_all_expiry_alerts(assigned_to="team@example.com", pool=pool)

    assert isinstance(result, list)
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_expiry_alerts_with_limit(mock_db_pool):
    """Test expiry alerts with limit"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_all_expiry_alerts(limit=50, pool=pool)

    assert isinstance(result, list)
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_expiry_alerts_with_all_filters(mock_db_pool):
    """Test expiry alerts with all filters"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_all_expiry_alerts(
        alert_color="yellow", assigned_to="team@example.com", limit=25, pool=pool
    )

    assert isinstance(result, list)


# ============================================================================
# Tests for get_expiry_alerts_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_expiry_alerts_summary_success(mock_db_pool):
    """Test successful retrieval of expiry alerts summary"""
    pool, conn = mock_db_pool

    summary = {"expired": 5, "red": 10, "yellow": 15, "green": 20}
    urgent = [
        {
            "client_name": "Client 1",
            "entity_name": "Passport",
            "document_type": "Passport",
            "expiry_date": "2024-12-31",
            "days_until_expiry": 10,
            "alert_color": "red",
        }
    ]

    conn.fetchrow = AsyncMock(return_value=summary)
    conn.fetch = AsyncMock(return_value=urgent)

    result = await get_expiry_alerts_summary(pool)

    assert "counts" in result
    assert "urgent_alerts" in result
    assert result["counts"]["expired"] == 5
    assert result["counts"]["red"] == 10
    assert len(result["urgent_alerts"]) == 1


@pytest.mark.asyncio
async def test_get_expiry_alerts_summary_empty(mock_db_pool):
    """Test expiry alerts summary when empty"""
    pool, conn = mock_db_pool

    summary = {"expired": 0, "red": 0, "yellow": 0, "green": 0}
    conn.fetchrow = AsyncMock(return_value=summary)
    conn.fetch = AsyncMock(return_value=[])

    result = await get_expiry_alerts_summary(pool)

    assert result["counts"]["expired"] == 0
    assert len(result["urgent_alerts"]) == 0
