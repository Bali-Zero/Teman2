"""
Unit tests for backend/services/crm/client_core.py
Covers: ClientValidator, PracticeValidator, InteractionValidator, sanitize_input,
        validate_uuid, normalize_phone_e164, extract_entities_from_text,
        CRMAuditor, EnhancedCRMService, get_enhanced_crm_service
"""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.exceptions import DatabaseError, ResourceNotFoundError, ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — mock DB pool
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_pool():
    """Standard asyncpg pool mock."""
    pool = MagicMock()
    conn = AsyncMock()

    class _AsyncCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AsyncCtx())
    return pool, conn


# Patch heavy CRM imports at module level before importing client_core
@pytest.fixture(autouse=True)
def _patch_crm_deps():
    """Patch cache_query dependencies so we don't need a real DB."""
    with (
        patch("backend.services.crm.client_core.crm_cache") as mock_crm_cache,
        patch("backend.services.crm.client_core.query_cache") as mock_query_cache,
        patch("backend.services.crm.client_core.CRMQueryOptimizer") as mock_optimizer_cls,
        patch("backend.services.crm.client_core.invalidate_client_cache") as mock_invalidate,
        patch("backend.services.crm.client_core.health_check_crm_tables") as mock_health,
    ):
        mock_crm_cache.get = AsyncMock(return_value=None)
        mock_crm_cache.set = AsyncMock()
        mock_crm_cache.clear = AsyncMock()

        mock_query_cache.set_practice_types = AsyncMock()

        optimizer = AsyncMock()
        optimizer.search_clients_optimized = AsyncMock(return_value=([], 0))
        optimizer.batch_insert_clients = AsyncMock(return_value=[1, 2])
        optimizer.get_clients_with_practices = AsyncMock(return_value=[])
        optimizer.get_practice_statistics = AsyncMock(return_value={})
        optimizer.get_overdue_practices = AsyncMock(return_value=[])
        mock_optimizer_cls.return_value = optimizer

        mock_health.return_value = {"status": "ok"}

        yield {
            "crm_cache": mock_crm_cache,
            "query_cache": mock_query_cache,
            "optimizer": optimizer,
            "invalidate": mock_invalidate,
            "health": mock_health,
        }


# Import after patching setup is in place (imports happen at test collection time,
# so we use a direct import here — the autouse fixture ensures env vars are set
# by the conftest before this module is collected)
from backend.services.crm.client_core import (
    AuditAction,
    ClientValidator,
    CRMAuditor,
    EnhancedCRMService,
    InteractionValidator,
    PracticeValidator,
    extract_entities_from_text,
    get_enhanced_crm_service,
    normalize_phone_e164,
    sanitize_input,
    validate_uuid,
)


# ─────────────────────────────────────────────────────────────────────────────
# sanitize_input
# ─────────────────────────────────────────────────────────────────────────────

def test_sanitize_input_none():
    assert sanitize_input(None) is None


def test_sanitize_input_empty_string():
    assert sanitize_input("") is None


def test_sanitize_input_strips_whitespace():
    assert sanitize_input("  hello  ") == "hello"


def test_sanitize_input_truncates_to_max_length():
    result = sanitize_input("a" * 300, max_length=10)
    assert len(result) == 10


def test_sanitize_input_removes_control_characters():
    result = sanitize_input("hello\x00world")
    assert "\x00" not in result
    assert "hello" in result


# ─────────────────────────────────────────────────────────────────────────────
# validate_uuid
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_uuid_valid():
    assert validate_uuid("550e8400-e29b-41d4-a716-446655440000") is True


def test_validate_uuid_invalid():
    assert validate_uuid("not-a-uuid") is False


def test_validate_uuid_uppercase_works():
    assert validate_uuid("550E8400-E29B-41D4-A716-446655440000") is True


# ─────────────────────────────────────────────────────────────────────────────
# normalize_phone_e164
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_phone_none():
    assert normalize_phone_e164("") is None


def test_normalize_phone_indonesian_zero_prefix():
    result = normalize_phone_e164("081234567890")
    assert result == "+6281234567890"


def test_normalize_phone_indonesian_8_prefix():
    result = normalize_phone_e164("81234567890")
    assert result == "+6281234567890"


def test_normalize_phone_already_e164():
    result = normalize_phone_e164("+6281234567890")
    assert result == "+6281234567890"


def test_normalize_phone_too_short():
    result = normalize_phone_e164("123")
    assert result is None


def test_normalize_phone_strips_non_digits():
    result = normalize_phone_e164("+62 812-3456-7890")
    assert result == "+6281234567890"


# ─────────────────────────────────────────────────────────────────────────────
# extract_entities_from_text
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_entities_emails():
    text = "Contact me at user@example.com or admin@test.org"
    result = extract_entities_from_text(text)
    assert "user@example.com" in result["emails"]
    assert "admin@test.org" in result["emails"]


def test_extract_entities_phones():
    text = "Call me at +628123456789 or 0812-3456-789"
    result = extract_entities_from_text(text)
    assert len(result["phones"]) >= 1


def test_extract_entities_passports():
    text = "My passport is A1234567 and C9876543"
    result = extract_entities_from_text(text)
    assert len(result["passports"]) >= 1


def test_extract_entities_empty():
    result = extract_entities_from_text("")
    assert result["emails"] == []
    assert result["phones"] == []
    assert result["passports"] == []


# ─────────────────────────────────────────────────────────────────────────────
# ClientValidator
# ─────────────────────────────────────────────────────────────────────────────

def test_client_validator_valid():
    v = ClientValidator(full_name="John Doe", email="john@example.com")
    assert v.full_name == "John Doe"
    assert v.email == "john@example.com"


def test_client_validator_name_stripped():
    v = ClientValidator(full_name="  Jane  ")
    assert v.full_name == "Jane"


def test_client_validator_name_too_short():
    with pytest.raises(Exception):
        ClientValidator(full_name="X")


def test_client_validator_phone_cleaned():
    v = ClientValidator(full_name="Test User", phone="+62 812-3456-789")
    assert v.phone is not None
    assert " " not in v.phone


def test_client_validator_phone_too_short():
    with pytest.raises(Exception):
        ClientValidator(full_name="Test User", phone="123")


def test_client_validator_passport_uppercased():
    v = ClientValidator(full_name="Test User", passport_number="a1234567")
    assert v.passport_number == "A1234567"


def test_client_validator_passport_invalid():
    with pytest.raises(Exception):
        ClientValidator(full_name="Test User", passport_number="invalid!!!")


def test_client_validator_defaults():
    v = ClientValidator(full_name="Test User")
    assert v.status == "active"
    assert v.client_type == "individual"
    assert v.tags == []


# ─────────────────────────────────────────────────────────────────────────────
# PracticeValidator
# ─────────────────────────────────────────────────────────────────────────────

def test_practice_validator_valid():
    v = PracticeValidator(client_id=1, practice_type_id=2)
    assert v.status == "inquiry"
    assert v.priority == "normal"


def test_practice_validator_invalid_status():
    with pytest.raises(Exception):
        PracticeValidator(client_id=1, practice_type_id=2, status="invalid_status")


def test_practice_validator_invalid_priority():
    with pytest.raises(Exception):
        PracticeValidator(client_id=1, practice_type_id=2, priority="super_urgent")


def test_practice_validator_valid_status_options():
    for status in ["inquiry", "waiting_documents", "sending_invoice", "on_process", "completed"]:
        v = PracticeValidator(client_id=1, practice_type_id=2, status=status)
        assert v.status == status


def test_practice_validator_valid_priority_options():
    for priority in ["low", "normal", "high", "urgent"]:
        v = PracticeValidator(client_id=1, practice_type_id=2, priority=priority)
        assert v.priority == priority


def test_practice_validator_negative_client_id():
    with pytest.raises(Exception):
        PracticeValidator(client_id=-1, practice_type_id=2)


# ─────────────────────────────────────────────────────────────────────────────
# InteractionValidator
# ─────────────────────────────────────────────────────────────────────────────

def test_interaction_validator_valid():
    v = InteractionValidator(interaction_type="chat")
    assert v.interaction_type == "chat"


def test_interaction_validator_invalid_type():
    with pytest.raises(Exception):
        InteractionValidator(interaction_type="fax")


def test_interaction_validator_valid_sentiment():
    v = InteractionValidator(interaction_type="email", sentiment="positive")
    assert v.sentiment == "positive"


def test_interaction_validator_invalid_sentiment():
    with pytest.raises(Exception):
        InteractionValidator(interaction_type="email", sentiment="happy")


def test_interaction_validator_none_sentiment():
    v = InteractionValidator(interaction_type="note", sentiment=None)
    assert v.sentiment is None


# ─────────────────────────────────────────────────────────────────────────────
# CRMAuditor
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def auditor(mock_pool):
    pool, conn = mock_pool
    return CRMAuditor(pool), conn


@pytest.mark.asyncio
async def test_auditor_log_adds_to_buffer(auditor):
    audit, conn = auditor
    await audit.log(
        action=AuditAction.CLIENT_CREATED,
        entity_type="client",
        entity_id=1,
        user_id="user1",
        new_values={"name": "Test"},
    )
    assert len(audit._buffer) == 1


@pytest.mark.asyncio
async def test_auditor_log_flushes_when_buffer_full(auditor, mock_pool):
    pool, conn = mock_pool
    audit = CRMAuditor(pool, buffer_size=2)
    conn.execute = AsyncMock()

    await audit.log(
        action=AuditAction.CLIENT_CREATED,
        entity_type="client",
        entity_id=1,
        user_id="user1",
    )
    await audit.log(
        action=AuditAction.CLIENT_UPDATED,
        entity_type="client",
        entity_id=1,
        user_id="user1",
    )
    # Buffer should be flushed
    assert len(audit._buffer) == 0


@pytest.mark.asyncio
async def test_auditor_log_client_created(auditor):
    audit, conn = auditor
    await audit.log_client_created(1, "user1", {"name": "Test"})
    assert len(audit._buffer) == 1
    assert audit._buffer[0]["action"] == AuditAction.CLIENT_CREATED.value


@pytest.mark.asyncio
async def test_auditor_log_client_updated(auditor):
    audit, conn = auditor
    await audit.log_client_updated(1, "user1", {"name": "Old"}, {"name": "New"})
    assert len(audit._buffer) == 1
    assert audit._buffer[0]["action"] == AuditAction.CLIENT_UPDATED.value


@pytest.mark.asyncio
async def test_auditor_log_practice_status_change(auditor):
    audit, conn = auditor
    await audit.log_practice_status_change(1, "user1", "inquiry", "on_process")
    assert len(audit._buffer) == 1
    assert audit._buffer[0]["action"] == AuditAction.PRACTICE_STATUS_CHANGED.value


@pytest.mark.asyncio
async def test_auditor_log_assignment_change(auditor):
    audit, conn = auditor
    await audit.log_assignment_change("client", 1, "user1", "old_user", "new_user")
    assert len(audit._buffer) == 1
    assert audit._buffer[0]["action"] == AuditAction.ASSIGNMENT_CHANGED.value


def test_auditor_calculate_changes(auditor):
    audit, _ = auditor
    old = {"name": "Old", "email": "old@test.com", "status": "active"}
    new = {"name": "New", "email": "old@test.com", "status": "inactive"}
    changes = audit._calculate_changes(old, new)
    assert "name" in changes
    assert changes["name"]["old"] == "Old"
    assert changes["name"]["new"] == "New"
    assert "email" not in changes  # unchanged


def test_auditor_sanitize_values_redacts_sensitive(auditor):
    audit, _ = auditor
    values = {"name": "Test", "password": "secret123", "api_key": "abc", "phone": "123"}
    sanitized = audit._sanitize_values(values)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["name"] == "Test"
    assert sanitized["phone"] == "123"


def test_auditor_sanitize_values_none():
    pool = MagicMock()
    audit = CRMAuditor(pool)
    assert audit._sanitize_values(None) is None


@pytest.mark.asyncio
async def test_auditor_log_system_user_when_no_user_id(auditor):
    audit, conn = auditor
    await audit.log(
        action=AuditAction.DATA_EXPORTED,
        entity_type="client",
        entity_id=1,
        user_id=None,
    )
    assert audit._buffer[0]["user_id"] == "system"


@pytest.mark.asyncio
async def test_auditor_log_with_metadata(auditor):
    audit, conn = auditor
    await audit.log(
        action=AuditAction.CLIENT_CREATED,
        entity_type="client",
        entity_id=1,
        user_id="user1",
        metadata={"ip_address": "127.0.0.1", "user_agent": "test-browser"},
    )
    assert audit._buffer[0]["ip_address"] == "127.0.0.1"
    assert audit._buffer[0]["user_agent"] == "test-browser"


@pytest.mark.asyncio
async def test_auditor_get_audit_trail(auditor, mock_pool):
    pool, conn = mock_pool
    audit = CRMAuditor(pool)
    conn.fetchval = AsyncMock(return_value=5)
    conn.fetch = AsyncMock(return_value=[])

    records, total = await audit.get_audit_trail(entity_type="client", entity_id=1)
    assert total == 5
    assert records == []


@pytest.mark.asyncio
async def test_auditor_get_audit_trail_with_filters(auditor, mock_pool):
    pool, conn = mock_pool
    audit = CRMAuditor(pool)
    conn.fetchval = AsyncMock(return_value=3)
    conn.fetch = AsyncMock(return_value=[])

    records, total = await audit.get_audit_trail(
        entity_type="client",
        user_id="user1",
        action=AuditAction.CLIENT_CREATED,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
    )
    assert total == 3


@pytest.mark.asyncio
async def test_auditor_close_flushes_buffer(auditor, mock_pool):
    pool, conn = mock_pool
    audit = CRMAuditor(pool)
    conn.execute = AsyncMock()
    await audit.log(
        action=AuditAction.CLIENT_CREATED,
        entity_type="client",
        entity_id=1,
        user_id="user1",
    )
    assert len(audit._buffer) == 1
    await audit.close()
    assert len(audit._buffer) == 0


def test_auditor_stop_periodic_flush_noop_when_no_task(auditor):
    audit, _ = auditor
    audit._flush_task = None
    audit.stop_periodic_flush()  # Should not raise


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — initialize
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def crm_service(mock_pool):
    pool, conn = mock_pool
    return EnhancedCRMService(pool), conn


@pytest.mark.asyncio
async def test_crm_service_initialize(crm_service, mock_pool):
    service, conn = crm_service
    pool, conn = mock_pool
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await service.initialize()
    assert service._initialized is True


@pytest.mark.asyncio
async def test_crm_service_initialize_idempotent(crm_service, mock_pool):
    service, conn = crm_service
    pool, conn = mock_pool
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await service.initialize()
    await service.initialize()  # Second call is noop
    assert service._initialized is True


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — create_client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_client_success(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=None)  # No duplicate
    conn.fetchrow = AsyncMock(return_value={
        "id": 1,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "whatsapp": None,
        "nationality": None,
        "passport_number": None,
        "status": "active",
        "client_type": "individual",
        "assigned_to": None,
        "custom_fields": {},
    })

    with patch.object(service.auditor, "log_client_created", new_callable=AsyncMock):
        result = await service.create_client({"full_name": "John Doe", "email": "john@example.com"})

    assert result["id"] == 1
    assert result["full_name"] == "John Doe"


@pytest.mark.asyncio
async def test_create_client_duplicate_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=42)  # Duplicate found

    with pytest.raises(ValidationError):
        await service.create_client({
            "full_name": "John Doe",
            "email": "john@example.com",
        })


@pytest.mark.asyncio
async def test_create_client_db_error_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(side_effect=Exception("db error"))

    with pytest.raises(DatabaseError):
        await service.create_client({"full_name": "John Doe"})


@pytest.mark.asyncio
async def test_create_client_invalid_input_raises(crm_service):
    service, _ = crm_service
    with pytest.raises(Exception):
        await service.create_client({"full_name": "X"})  # Name too short


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — update_client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_client_success(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    old_row = {
        "id": 1,
        "full_name": "Old Name",
        "email": "old@example.com",
        "phone": None,
        "whatsapp": None,
        "status": "active",
        "client_type": "individual",
        "assigned_to": None,
        "nationality": None,
        "passport_number": None,
        "custom_fields": {},
        "tags": [],
        "notes": None,
        "deleted_at": None,
    }
    new_row = {**old_row, "full_name": "New Name"}
    conn.fetchrow = AsyncMock(side_effect=[old_row, new_row])

    with patch.object(service.auditor, "log_client_updated", new_callable=AsyncMock):
        result = await service.update_client(1, {"full_name": "New Name"})

    assert result["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_client_not_found_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundError):
        await service.update_client(999, {"full_name": "New"})


@pytest.mark.asyncio
async def test_update_client_disallowed_column_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    old_row = {
        "id": 1,
        "full_name": "Test",
        "email": None,
        "phone": None,
        "whatsapp": None,
        "status": "active",
        "client_type": "individual",
        "assigned_to": None,
        "nationality": None,
        "passport_number": None,
        "custom_fields": {},
        "tags": [],
        "notes": None,
        "deleted_at": None,
    }
    conn.fetchrow = AsyncMock(return_value=old_row)

    with pytest.raises((ValidationError, DatabaseError)):
        await service.update_client(1, {"malicious_column": "injection"})


@pytest.mark.asyncio
async def test_update_client_no_changes_returns_old(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    old_row = {
        "id": 1,
        "full_name": "Same Name",
        "email": None,
        "phone": None,
        "whatsapp": None,
        "status": "active",
        "client_type": "individual",
        "assigned_to": None,
        "nationality": None,
        "passport_number": None,
        "custom_fields": {},
        "tags": [],
        "notes": None,
        "deleted_at": None,
    }
    conn.fetchrow = AsyncMock(return_value=old_row)

    result = await service.update_client(1, {"full_name": "Same Name"})
    # Returns old data (no actual update)
    assert result["full_name"] == "Same Name"


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — get_client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_client_cache_hit(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["crm_cache"].get = AsyncMock(return_value={"id": 1, "full_name": "Cached"})

    result = await service.get_client(1)
    assert result["id"] == 1
    assert result["full_name"] == "Cached"


@pytest.mark.asyncio
async def test_get_client_cache_miss_db_hit(crm_service, mock_pool, _patch_crm_deps):
    service, _ = crm_service
    pool, conn = mock_pool
    _patch_crm_deps["crm_cache"].get = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "From DB"})

    result = await service.get_client(1)
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_get_client_not_found_returns_none(crm_service, mock_pool, _patch_crm_deps):
    service, _ = crm_service
    pool, conn = mock_pool
    _patch_crm_deps["crm_cache"].get = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)

    result = await service.get_client(999)
    assert result is None


@pytest.mark.asyncio
async def test_get_client_with_practices(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["crm_cache"].get = AsyncMock(return_value=None)
    _patch_crm_deps["optimizer"].get_clients_with_practices = AsyncMock(
        return_value=[{"id": 1, "practices": []}],
    )

    result = await service.get_client(1, include_practices=True)
    assert result["id"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — create_practice
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_practice_success(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value={
        "id": 10,
        "client_id": 1,
        "practice_type_id": 2,
        "status": "inquiry",
        "priority": "normal",
    })

    with patch.object(service.auditor, "log", new_callable=AsyncMock):
        result = await service.create_practice({"client_id": 1, "practice_type_id": 2})

    assert result["id"] == 10


@pytest.mark.asyncio
async def test_create_practice_invalid_data_raises(crm_service):
    service, _ = crm_service
    with pytest.raises(Exception):
        await service.create_practice({"client_id": -1, "practice_type_id": 2})


@pytest.mark.asyncio
async def test_create_practice_db_error_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("db error"))

    with pytest.raises(DatabaseError):
        await service.create_practice({"client_id": 1, "practice_type_id": 2})


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — update_practice_status
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_practice_status_success(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    old = {"status": "inquiry", "client_id": 1}
    updated = {
        "id": 10, "status": "on_process", "client_id": 1,
        "assigned_to": None, "actual_price": None,
    }
    conn.fetchrow = AsyncMock(side_effect=[old, updated])

    with patch.object(service.auditor, "log_practice_status_change", new_callable=AsyncMock):
        result = await service.update_practice_status(10, "on_process", user_id="user1")

    assert result["status"] == "on_process"


@pytest.mark.asyncio
async def test_update_practice_status_not_found_raises(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundError):
        await service.update_practice_status(999, "completed")


@pytest.mark.asyncio
async def test_update_practice_status_completed_triggers_hr_bonus(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    old = {"status": "on_process", "client_id": 1}
    updated = {"id": 10, "status": "completed", "client_id": 1, "assigned_to": "agent@balizero.com"}
    conn.fetchrow = AsyncMock(side_effect=[old, updated])

    with patch.object(service.auditor, "log_practice_status_change", new_callable=AsyncMock):
        with patch.object(service, "_create_hr_bonus_entry", new_callable=AsyncMock) as mock_bonus:
            await service.update_practice_status(10, "completed")

    mock_bonus.assert_called_once_with(10, updated)


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — batch_create_clients
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_create_clients_success(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["optimizer"].batch_insert_clients = AsyncMock(return_value=[1, 2, 3])

    ids = await service.batch_create_clients([
        {"full_name": "Client One"},
        {"full_name": "Client Two"},
        {"full_name": "Client Three"},
    ])
    assert ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_batch_create_clients_invalid_raises(crm_service):
    service, _ = crm_service
    with pytest.raises(DatabaseError):
        await service.batch_create_clients([{"full_name": "X"}])  # Name too short


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — search_clients
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_clients(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["optimizer"].search_clients_optimized = AsyncMock(
        return_value=([{"id": 1, "full_name": "John"}], 1),
    )

    results, total = await service.search_clients("john")
    assert total == 1
    assert results[0]["full_name"] == "John"


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — _find_duplicate_client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_duplicate_by_email(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=42)

    result = await service._find_duplicate_client({"email": "dup@example.com"})
    assert result == 42


@pytest.mark.asyncio
async def test_find_duplicate_by_phone(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    # No email in data → only phone fetchval is called, returns 99
    conn.fetchval = AsyncMock(return_value=99)

    result = await service._find_duplicate_client({
        "email": None,
        "phone": "081234567890",
    })
    assert result == 99


@pytest.mark.asyncio
async def test_find_duplicate_no_match(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=None)

    result = await service._find_duplicate_client({"email": "new@example.com"})
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService — utility methods
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_statistics(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["optimizer"].get_practice_statistics = AsyncMock(return_value={"total": 5})

    result = await service.get_statistics()
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_get_overdue_practices(crm_service, _patch_crm_deps):
    service, _ = crm_service
    _patch_crm_deps["optimizer"].get_overdue_practices = AsyncMock(return_value=[{"id": 1}])

    result = await service.get_overdue_practices(days=7)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_health_check(crm_service, _patch_crm_deps, mock_pool):
    service, _ = crm_service
    pool, _ = mock_pool
    _patch_crm_deps["health"].return_value = {"status": "ok"}

    result = await service.health_check()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_close(crm_service):
    service, _ = crm_service
    with patch.object(service.auditor, "close", new_callable=AsyncMock) as mock_close:
        await service.close()
    mock_close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _create_hr_bonus_entry
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hr_bonus_skips_no_assigned_to(crm_service):
    service, _ = crm_service
    # Should complete without error (early return)
    await service._create_hr_bonus_entry(1, {"assigned_to": None})


@pytest.mark.asyncio
async def test_hr_bonus_skips_when_table_not_exists(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(return_value=False)  # table doesn't exist

    await service._create_hr_bonus_entry(1, {"assigned_to": "agent@balizero.com"})
    # Should return early, no exception


@pytest.mark.asyncio
async def test_hr_bonus_failure_does_not_propagate(crm_service, mock_pool):
    service, _ = crm_service
    pool, conn = mock_pool
    conn.fetchval = AsyncMock(side_effect=Exception("unexpected db error"))

    # Should log warning but not raise
    await service._create_hr_bonus_entry(1, {"assigned_to": "agent@balizero.com"})


# ─────────────────────────────────────────────────────────────────────────────
# get_enhanced_crm_service singleton
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_crm_singleton():
    import backend.services.crm.client_core as mod
    mod._enhanced_crm_service = None
    yield
    mod._enhanced_crm_service = None


@pytest.mark.asyncio
async def test_get_enhanced_crm_service_creates_once(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    s1 = await get_enhanced_crm_service(pool)
    s2 = await get_enhanced_crm_service(pool)
    assert s1 is s2
