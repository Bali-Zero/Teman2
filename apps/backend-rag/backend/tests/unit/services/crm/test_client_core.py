"""
Supplementary unit tests for backend/services/crm/client_core.py
Targets coverage gaps left by test_client_core_coverage.py:
- CRMAuditor.start_periodic_flush / stop_periodic_flush
- CRMAuditor.log error path
- CRMAuditor._flush_buffer error path
- EnhancedCRMService.initialize error path
- EnhancedCRMService.update_practice_status error path
- EnhancedCRMService._create_hr_bonus_entry detailed logic
- Validator edge cases (phone length boundary)
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.exceptions import DatabaseError, ResourceNotFoundError


# Patch heavy CRM imports before importing client_core
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
        mock_query_cache.set_practice_types = AsyncMock()

        optimizer = AsyncMock()
        optimizer.search_clients_optimized = AsyncMock(return_value=([], 0))
        optimizer.batch_insert_clients = AsyncMock(return_value=[1, 2])
        optimizer.get_clients_with_practices = AsyncMock(return_value=[])
        mock_optimizer_cls.return_value = optimizer

        yield {
            "crm_cache": mock_crm_cache,
            "query_cache": mock_query_cache,
            "optimizer": optimizer,
            "invalidate": mock_invalidate,
        }


from backend.services.crm.client_core import (
    AuditAction,
    ClientValidator,
    CRMAuditor,
    EnhancedCRMService,
    InteractionValidator,
    PracticeValidator,
    extract_entities_from_text,
    normalize_phone_e164,
    sanitize_input,
    validate_uuid,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    return pool, conn


# ═══════════════════════════════════════════════════════════════════════════════
# CRMAuditor — periodic flush
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditorPeriodicFlush:
    @pytest.mark.asyncio
    async def test_start_periodic_flush_creates_task(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool)

        # start_periodic_flush creates an asyncio.Task
        auditor.start_periodic_flush(interval_seconds=9999)
        assert auditor._flush_task is not None
        assert not auditor._flush_task.done()

        # Clean up
        auditor._flush_task.cancel()
        try:
            await auditor._flush_task
        except asyncio.CancelledError:
            pass

    def test_stop_periodic_flush_cancels(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool)

        mock_task = MagicMock()
        mock_task.done.return_value = False
        auditor._flush_task = mock_task

        auditor.stop_periodic_flush()
        mock_task.cancel.assert_called_once()

    def test_stop_periodic_flush_done_task(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool)

        mock_task = MagicMock()
        mock_task.done.return_value = True
        auditor._flush_task = mock_task

        auditor.stop_periodic_flush()
        mock_task.cancel.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# CRMAuditor — log error path
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditorLogErrors:
    @pytest.mark.asyncio
    async def test_log_exception_does_not_propagate(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool, buffer_size=100)

        # Force _flush_buffer to raise
        auditor._flush_buffer = AsyncMock(side_effect=Exception("DB down"))

        # Fill buffer to trigger flush
        for i in range(101):
            await auditor.log(
                action=AuditAction.CLIENT_CREATED,
                entity_type="client",
                entity_id=i,
                user_id="user",
            )

        # Should not raise - the exception is caught internally

    @pytest.mark.asyncio
    async def test_log_with_none_metadata(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool)

        await auditor.log(
            action=AuditAction.CLIENT_UPDATED,
            entity_type="client",
            entity_id=1,
            user_id="user",
            old_values={"name": "old"},
            new_values={"name": "new"},
            metadata=None,
        )
        assert len(auditor._buffer) == 1
        assert auditor._buffer[0]["ip_address"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# CRMAuditor — _flush_buffer error
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditorFlushBufferError:
    @pytest.mark.asyncio
    async def test_flush_buffer_db_error(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        auditor = CRMAuditor(pool)

        # Add entry
        auditor._buffer.append({
            "action": "client_created",
            "entity_type": "client",
            "entity_id": "1",
            "user_id": "user",
            "changes": None,
            "old_values": None,
            "new_values": None,
            "metadata": {},
            "ip_address": None,
            "user_agent": None,
        })

        conn.execute = AsyncMock(side_effect=Exception("DB error"))

        # Should not raise; error is logged
        await auditor._flush_buffer()


# ═══════════════════════════════════════════════════════════════════════════════
# EnhancedCRMService — initialize error
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnhancedCRMServiceInitError:
    @pytest.mark.asyncio
    async def test_initialize_db_error_raises(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.execute = AsyncMock(side_effect=Exception("DB connection failed"))

        svc = EnhancedCRMService(pool)

        with pytest.raises(Exception, match="DB connection failed"):
            await svc.initialize()

    @pytest.mark.asyncio
    async def test_search_clients_delegates(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        svc = EnhancedCRMService(pool)

        result = await svc.search_clients("test")
        assert result == ([], 0)


# ═══════════════════════════════════════════════════════════════════════════════
# EnhancedCRMService — update_practice_status error
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdatePracticeStatusError:
    @pytest.mark.asyncio
    async def test_update_practice_status_db_error(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        # First fetchrow returns old status
        conn.fetchrow = AsyncMock(side_effect=[
            {"status": "in_progress", "client_id": 1},
            Exception("DB error on update"),
        ])

        svc = EnhancedCRMService(pool)

        with pytest.raises(DatabaseError):
            await svc.update_practice_status(1, "completed")


# ═══════════════════════════════════════════════════════════════════════════════
# EnhancedCRMService — _create_hr_bonus_entry
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateHRBonusEntry:
    @pytest.mark.asyncio
    async def test_bonus_no_practice_type(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(side_effect=[True, None])  # table exists, no rate
        conn.fetchrow = AsyncMock(return_value=None)  # no practice_type

        svc = EnhancedCRMService(pool)
        # Should not raise
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )

    @pytest.mark.asyncio
    async def test_bonus_no_rate(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(return_value=True)  # table exists
        conn.fetchrow = AsyncMock(side_effect=[
            {"code": "KITAS"},  # practice_type found
            None,  # no rate found
        ])

        svc = EnhancedCRMService(pool)
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )

    @pytest.mark.asyncio
    async def test_bonus_no_employee(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(return_value=True)
        conn.fetchrow = AsyncMock(side_effect=[
            {"code": "KITAS"},  # practice_type
            {"id": 1, "amount_idr": 500000},  # rate
            None,  # no employee
        ])

        svc = EnhancedCRMService(pool)
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )

    @pytest.mark.asyncio
    async def test_bonus_duplicate(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(side_effect=[True, 42])  # table exists, existing bonus
        conn.fetchrow = AsyncMock(side_effect=[
            {"code": "KITAS"},  # practice_type
            {"id": 1, "amount_idr": 500000},  # rate
            {"id": 10},  # employee
        ])

        svc = EnhancedCRMService(pool)
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )

    @pytest.mark.asyncio
    async def test_bonus_success(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(side_effect=[True, None])  # table exists, no duplicate
        conn.fetchrow = AsyncMock(side_effect=[
            {"code": "KITAS"},  # practice_type
            {"id": 1, "amount_idr": 500000},  # rate
            {"id": 10},  # employee
        ])
        conn.execute = AsyncMock()

        svc = EnhancedCRMService(pool)
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bonus_table_not_exists(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(return_value=False)  # table not exists

        svc = EnhancedCRMService(pool)
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )

    @pytest.mark.asyncio
    async def test_bonus_exception_does_not_propagate(self, mock_pool: tuple) -> None:
        pool, conn = mock_pool
        conn.fetchval = AsyncMock(side_effect=Exception("unexpected"))

        svc = EnhancedCRMService(pool)
        # Should not raise
        await svc._create_hr_bonus_entry(
            1, {"assigned_to": "alice@balizero.com"},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Validator edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidatorEdgeCases:
    def test_phone_exactly_8_digits(self) -> None:
        v = ClientValidator(full_name="Test", phone="+12345678")
        assert v.phone == "+12345678"

    def test_phone_with_spaces(self) -> None:
        v = ClientValidator(full_name="Test", phone="+62 812 3456 789")
        assert v.phone is not None
        # Only digits and + should remain
        assert " " not in (v.phone or "")

    def test_name_multiple_spaces_collapsed(self) -> None:
        v = ClientValidator(full_name="John    Doe")
        assert v.full_name == "John Doe"

    def test_interaction_all_valid_types(self) -> None:
        for t in ("chat", "email", "whatsapp", "call", "meeting", "note"):
            v = InteractionValidator(interaction_type=t)
            assert v.interaction_type == t

    def test_practice_all_valid_statuses(self) -> None:
        for s in ("inquiry", "waiting_documents", "sending_invoice", "on_process", "completed"):
            v = PracticeValidator(client_id=1, practice_type_id=1, status=s)
            assert v.status == s


# ═══════════════════════════════════════════════════════════════════════════════
# AuditAction enum
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditAction:
    def test_values(self) -> None:
        assert AuditAction.CLIENT_CREATED.value == "client_created"
        assert AuditAction.PRACTICE_STATUS_CHANGED.value == "practice_status_changed"
        assert AuditAction.BULK_OPERATION.value == "bulk_operation"

    def test_all_members(self) -> None:
        # Ensure the enum has all expected members
        expected = {
            "CLIENT_CREATED", "CLIENT_UPDATED", "CLIENT_DELETED",
            "PRACTICE_CREATED", "PRACTICE_UPDATED", "PRACTICE_DELETED",
            "PRACTICE_STATUS_CHANGED",
            "INTERACTION_CREATED", "INTERACTION_UPDATED",
            "ASSIGNMENT_CHANGED", "DATA_EXPORTED", "BULK_OPERATION",
        }
        actual = {m.name for m in AuditAction}
        assert expected == actual


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_phone_e164 edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizePhoneEdge:
    def test_with_country_code_62(self) -> None:
        result = normalize_phone_e164("628123456789")
        assert result == "+628123456789"

    def test_with_dashes_and_spaces(self) -> None:
        result = normalize_phone_e164("+62-812-345-6789")
        assert result == "+628123456789"

    def test_empty_string(self) -> None:
        assert normalize_phone_e164("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# extract_entities edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractEntitiesEdge:
    def test_passport_uppercase_matching(self) -> None:
        result = extract_entities_from_text("My passport is A1234567")
        assert "A1234567" in result["passports"]

    def test_no_entities(self) -> None:
        result = extract_entities_from_text("No useful information here")
        assert result["emails"] == []
        assert result["phones"] == []
        assert result["passports"] == []
