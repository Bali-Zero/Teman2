"""
Unit tests for backend/app/routers/crm_clients.py
Covers: create_client, list_clients, get_client, get_client_by_email,
        update_client, delete_client, get_client_summary
Direct function calls with mocked dependencies (no TestClient).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_current_user():
    return {
        "id": "user-uuid-123",
        "email": "zero@balizero.com",
        "role": "admin",
        "full_name": "Test Admin",
    }


@pytest.fixture
def mock_team_user():
    return {
        "id": "user-uuid-456",
        "email": "team@balizero.com",
        "role": "team",
        "full_name": "Team Member",
    }


@pytest.fixture
def sample_client_row():
    """A sample DB row returned by fetchrow for a client."""
    return {
        "id": 1,
        "uuid": str(uuid.uuid4()),
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+621234567890",
        "whatsapp": "+621234567890",
        "company_name": None,
        "nationality": "Australian",
        "passport_number": "PA123456",
        "passport_expiry": datetime(2028, 1, 1).date(),
        "date_of_birth": datetime(1990, 5, 15).date(),
        "gender": "male",
        "birthplace": "Sydney",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "zero@balizero.com",
        "tax_consultant": None,
        "avatar_url": None,
        "address": "Bali, Indonesia",
        "notes": "Test client",
        "first_contact_date": datetime.now(tz=timezone.utc),
        "last_interaction_date": None,
        "last_sentiment": None,
        "last_interaction_summary": None,
        "tags": ["vip"],
        "lead_source": "website",
        "service_interest": ["visa"],
        "custom_fields": {},
        "tax_id": None,
        "npwp": None,
        "nib": None,
        "current_visa_type": None,
        "current_visa_sponsor": None,
        "created_at": datetime.now(tz=timezone.utc),
        "updated_at": datetime.now(tz=timezone.utc),
        "created_by": "zero@balizero.com",
    }


# ============================================================
# Pydantic model validation tests
# ============================================================


def test_client_create_valid():
    from backend.app.routers.crm_clients import ClientCreate

    c = ClientCreate(full_name="John Doe", email="john@example.com")
    assert c.full_name == "John Doe"
    assert c.status == "active"
    assert c.client_type == "individual"


def test_client_create_invalid_status():
    from backend.app.routers.crm_clients import ClientCreate

    with pytest.raises(ValueError, match="status must be one of"):
        ClientCreate(full_name="John", status="invalid_status")


def test_client_create_invalid_client_type():
    from backend.app.routers.crm_clients import ClientCreate

    with pytest.raises(ValueError, match="client_type must be one of"):
        ClientCreate(full_name="John", client_type="nonprofit")


def test_client_create_empty_name():
    from backend.app.routers.crm_clients import ClientCreate

    with pytest.raises(ValueError, match="full_name cannot be empty"):
        ClientCreate(full_name="")


def test_client_create_long_name():
    from backend.app.routers.crm_clients import ClientCreate

    with pytest.raises(ValueError, match="less than 200"):
        ClientCreate(full_name="A" * 201)


def test_client_create_empty_email_becomes_none():
    from backend.app.routers.crm_clients import ClientCreate

    c = ClientCreate(full_name="John Doe", email="")
    assert c.email is None


def test_client_create_empty_date_becomes_none():
    from backend.app.routers.crm_clients import ClientCreate

    c = ClientCreate(full_name="John Doe", passport_expiry="", date_of_birth="")
    assert c.passport_expiry is None
    assert c.date_of_birth is None


def test_client_create_minor_rejected():
    from backend.app.routers.crm_clients import ClientCreate

    with pytest.raises(ValueError, match="MINORE"):
        ClientCreate(full_name="Kid", date_of_birth="2020-01-01")


def test_client_update_valid():
    from backend.app.routers.crm_clients import ClientUpdate

    u = ClientUpdate(full_name="Jane Doe", status="prospect")
    assert u.full_name == "Jane Doe"
    assert u.status == "prospect"


def test_client_update_invalid_status():
    from backend.app.routers.crm_clients import ClientUpdate

    with pytest.raises(ValueError):
        ClientUpdate(status="unknown")


def test_client_update_normalize_gender():
    from backend.app.routers.crm_clients import ClientUpdate

    u = ClientUpdate(gender="M")
    assert u.gender == "male"
    u2 = ClientUpdate(gender="F")
    assert u2.gender == "female"


def test_client_update_tax_consultant_valid():
    from backend.app.routers.crm_clients import ClientUpdate

    u = ClientUpdate(tax_consultant="veronika.tax@balizero.com")
    assert u.tax_consultant == "veronika.tax@balizero.com"


def test_client_update_tax_consultant_invalid():
    from backend.app.routers.crm_clients import ClientUpdate

    with pytest.raises(ValueError, match="tax_consultant must be one of"):
        ClientUpdate(tax_consultant="random@email.com")


def test_client_update_tax_consultant_empty_string_becomes_none():
    from backend.app.routers.crm_clients import ClientUpdate

    u = ClientUpdate(tax_consultant="")
    assert u.tax_consultant is None


def test_client_update_full_name_empty_rejected():
    from backend.app.routers.crm_clients import ClientUpdate

    with pytest.raises(ValueError, match="full_name cannot be empty"):
        ClientUpdate(full_name="   ")


def test_client_update_minor_rejected():
    from backend.app.routers.crm_clients import ClientUpdate

    with pytest.raises(ValueError, match="MINORE"):
        ClientUpdate(date_of_birth="2020-06-01")


def test_client_response_uuid_conversion():
    from backend.app.routers.crm_clients import ClientResponse

    r = ClientResponse(
        id=1,
        uuid=uuid.uuid4(),
        full_name="Test",
        status="active",
        client_type="individual",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert isinstance(r.uuid, str)


def test_client_response_tags_none_becomes_list():
    from backend.app.routers.crm_clients import ClientResponse

    r = ClientResponse(
        id=1,
        uuid="abc",
        full_name="Test",
        status="active",
        client_type="individual",
        tags=None,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert r.tags == []


def test_client_response_date_conversion():
    from backend.app.routers.crm_clients import ClientResponse

    r = ClientResponse(
        id=1,
        uuid="abc",
        full_name="Test",
        status="active",
        client_type="individual",
        passport_expiry=datetime(2028, 1, 1).date(),
        date_of_birth=datetime(1990, 1, 1).date(),
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert r.passport_expiry == "2028-01-01"
    assert r.date_of_birth == "1990-01-01"


# ============================================================
# get_client — success + not found
# ============================================================


@pytest.mark.asyncio
async def test_get_client_success(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import get_client

    mock_db_pool._mock_conn.fetchrow.return_value = sample_client_row

    with patch(
        "backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()
    ):
        result = await get_client(
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result.id == 1
    assert result.full_name == "John Doe"


@pytest.mark.asyncio
async def test_get_client_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import get_client

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_client(
            client_id=999,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# get_client_by_email — success + not found
# ============================================================


@pytest.mark.asyncio
async def test_get_client_by_email_success(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import get_client_by_email

    mock_db_pool._mock_conn.fetchrow.return_value = sample_client_row

    with patch(
        "backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()
    ):
        result = await get_client_by_email(
            email="john@example.com",
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result.email == "john@example.com"


@pytest.mark.asyncio
async def test_get_client_by_email_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import get_client_by_email

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_client_by_email(
            email="notfound@example.com",
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# list_clients — success path
# ============================================================


@pytest.mark.asyncio
async def test_list_clients_success(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import list_clients

    mock_db_pool._mock_conn.fetch.return_value = [sample_client_row]

    with (
        patch("backend.app.routers.crm_clients.get_crm_user_filter", return_value=None),
        patch("backend.app.routers.crm_clients.is_crm_admin", return_value=True),
    ):
        result = await list_clients(
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert len(result) == 1
    assert result[0].full_name == "John Doe"


@pytest.mark.asyncio
async def test_list_clients_no_email(mock_db_pool):
    from backend.app.routers.crm_clients import list_clients

    with pytest.raises(HTTPException) as exc_info:
        await list_clients(
            db_pool=mock_db_pool,
            current_user={"email": ""},
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_list_clients_with_filters(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import list_clients

    mock_db_pool._mock_conn.fetch.return_value = [sample_client_row]

    with (
        patch("backend.app.routers.crm_clients.get_crm_user_filter", return_value=None),
        patch("backend.app.routers.crm_clients.is_crm_admin", return_value=True),
    ):
        result = await list_clients(
            status="active",
            search="John",
            nationality="Australian",
            assigned_to="zero@balizero.com",
            passport_expiring_days=365,
            limit=10,
            offset=0,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_clients_expired_passport_filter(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import list_clients

    mock_db_pool._mock_conn.fetch.return_value = [sample_client_row]

    with (
        patch("backend.app.routers.crm_clients.get_crm_user_filter", return_value=None),
        patch("backend.app.routers.crm_clients.is_crm_admin", return_value=True),
    ):
        result = await list_clients(
            passport_expiring_days=0,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_clients_rbac_team_user(mock_db_pool, mock_team_user, sample_client_row):
    from backend.app.routers.crm_clients import list_clients

    mock_db_pool._mock_conn.fetch.return_value = [sample_client_row]

    with (
        patch("backend.app.routers.crm_clients.get_crm_user_filter", return_value="team@balizero.com"),
        patch("backend.app.routers.crm_clients.is_crm_admin", return_value=False),
    ):
        result = await list_clients(
            db_pool=mock_db_pool,
            current_user=mock_team_user,
        )
    assert isinstance(result, list)


# ============================================================
# delete_client — success + not found
# ============================================================


@pytest.mark.asyncio
async def test_delete_client_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import delete_client

    mock_db_pool._mock_conn.fetchrow.return_value = {"id": 1}
    mock_db_pool._mock_conn.execute.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.audit_change", side_effect=lambda **kw: lambda f: f),
    ):
        result = await delete_client(
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_client_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import delete_client

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await delete_client(
            client_id=999,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# create_client — success path (mocked service)
# ============================================================


@pytest.mark.asyncio
async def test_create_client_success(mock_db_pool, mock_current_user, sample_client_row):
    from unittest.mock import MagicMock as MM

    from backend.app.routers.crm_clients import ClientCreate, create_client

    client_data = ClientCreate(
        full_name="Jane Doe",
        email="jane@example.com",
        status="active",
    )

    mock_service = MagicMock()
    mock_service.create_client = AsyncMock(return_value=sample_client_row)

    background_tasks = MM()

    with (
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.services.integrations.service_account_drive_service.ServiceAccountDriveService", side_effect=Exception("skip")),
    ):
        result = await create_client(
            client=client_data,
            background_tasks=background_tasks,
            current_user=mock_current_user,
            client_service=mock_service,
            db_pool=mock_db_pool,
        )
    assert result.id == 1


@pytest.mark.asyncio
async def test_create_client_no_email_in_user(mock_db_pool):
    from backend.app.routers.crm_clients import ClientCreate, create_client

    client_data = ClientCreate(full_name="Jane Doe")
    mock_service = MagicMock()
    background_tasks = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await create_client(
            client=client_data,
            background_tasks=background_tasks,
            current_user={"email": ""},
            client_service=mock_service,
            db_pool=mock_db_pool,
        )
    assert exc_info.value.status_code in (401, 500)


@pytest.mark.asyncio
async def test_create_client_with_company_and_nib(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import ClientCreate, create_client

    client_data = ClientCreate(
        full_name="Jane Corp",
        company_name="PT Test",
        status="active",
        client_type="company",
    )

    mock_service = MagicMock()
    mock_service.create_client = AsyncMock(return_value=sample_client_row)
    background_tasks = MagicMock()

    # Simulate no existing company found by NIB
    mock_db_pool._mock_conn.fetchval.return_value = None

    with (
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.services.integrations.service_account_drive_service.ServiceAccountDriveService", side_effect=Exception("skip")),
    ):
        result = await create_client(
            client=client_data,
            background_tasks=background_tasks,
            current_user=mock_current_user,
            client_service=mock_service,
            db_pool=mock_db_pool,
        )
    assert result.id == 1


# ============================================================
# update_client — success + not found + no fields
# ============================================================


@pytest.mark.asyncio
async def test_update_client_success(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import ClientUpdate, update_client

    updates = ClientUpdate(full_name="Updated Name")
    mock_db_pool._mock_conn.fetchrow.return_value = sample_client_row
    mock_db_pool._mock_conn.execute.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.services.portal.portal_notification_service.PortalNotificationService", side_effect=Exception("skip")),
    ):
        result = await update_client(
            updates=updates,
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result.id == 1


@pytest.mark.asyncio
async def test_update_client_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import ClientUpdate, update_client

    updates = ClientUpdate(notes="test")
    mock_db_pool._mock_conn.fetchrow.return_value = None
    mock_db_pool._mock_conn.execute.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_client(
            updates=updates,
            client_id=999,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_client_date_field_conversion(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import ClientUpdate, update_client

    updates = ClientUpdate(passport_expiry="2030-06-15", date_of_birth="1990-01-01")
    mock_db_pool._mock_conn.fetchrow.return_value = sample_client_row
    mock_db_pool._mock_conn.execute.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.services.portal.portal_notification_service.PortalNotificationService", side_effect=Exception("skip")),
    ):
        result = await update_client(
            updates=updates,
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result.id == 1


@pytest.mark.asyncio
async def test_update_client_nullable_field(mock_db_pool, mock_current_user, sample_client_row):
    from backend.app.routers.crm_clients import ClientUpdate, update_client

    updates = ClientUpdate(tax_consultant=None)
    mock_db_pool._mock_conn.fetchrow.return_value = sample_client_row
    mock_db_pool._mock_conn.execute.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients.invalidate_cache", new=AsyncMock()),
        patch("backend.services.portal.portal_notification_service.PortalNotificationService", side_effect=Exception("skip")),
    ):
        result = await update_client(
            updates=updates,
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result.id == 1


# ============================================================
# get_client_summary — success + not found
# ============================================================


@pytest.mark.asyncio
async def test_get_client_summary_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import get_client_summary

    client_row = {
        "id": 1,
        "uuid": str(uuid.uuid4()),
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "whatsapp": None,
        "nationality": "Australian",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "zero@balizero.com",
        "passport_number": "PA123",
        "passport_expiry": datetime(2028, 1, 1).date(),
        "tags": ["vip"],
        "created_at": datetime.now(tz=timezone.utc),
        "notes": None,
    }

    # fetchrow returns client row, then fetch returns practices, interactions, documents
    mock_db_pool._mock_conn.fetchrow.return_value = client_row
    mock_db_pool._mock_conn.fetch.return_value = []

    with patch(
        "backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()
    ):
        result = await get_client_summary(
            client_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result["client"]["id"] == 1


@pytest.mark.asyncio
async def test_get_client_summary_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients import get_client_summary

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with (
        patch("backend.app.routers.crm_clients.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_client_summary(
            client_id=999,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# get_client_service helper
# ============================================================


def test_get_client_service_returns_service():
    from backend.app.routers.crm_clients import get_client_service

    pool = MagicMock()
    svc = get_client_service(db_pool=pool)
    from backend.services.crm.client_service import ClientService
    assert isinstance(svc, ClientService)
