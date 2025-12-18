"""
Stubbed integration tests for AutoCRMService (CRM auto-population).
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class FakeConnection:
    def __init__(self):
        self.fetchrow = AsyncMock()
        self.fetchval = AsyncMock()
        self.execute = AsyncMock()

    @asynccontextmanager
    async def transaction(self):
        yield self


class FakePool:
    def __init__(self, conn: FakeConnection):
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


def build_extraction(confidence=0.95, create_practice=True):
    extracted = {
        "client": {
            "full_name": "Test Client",
            "email": "client@example.com",
            "phone": "+628123456789",
            "whatsapp": None,
            "nationality": "ID",
            "confidence": confidence,
        },
        "practice_intent": {
            "detected": True,
            "practice_type_code": "visa_service",
            "details": "Need visa renewal",
        },
        "summary": "Client asked about visa renewal",
        "sentiment": "positive",
        "extracted_entities": {"country": "Indonesia"},
        "action_items": ["schedule follow-up"],
        "urgency": "urgent",
    }
    return extracted, create_practice


@pytest.mark.integration
class TestAutoCRMService:
    @pytest.mark.asyncio
    async def test_process_conversation_without_pool_returns_error(self):
        from services.auto_crm_service import AutoCRMService

        service = AutoCRMService(db_pool=None)
        result = await service.process_conversation(
            conversation_id=1,
            messages=[{"role": "user", "content": "hello"}],
            user_email="user@example.com",
        )

        assert result["success"] is False
        assert "Database pool not available" in result["error"]

    @pytest.mark.asyncio
    async def test_process_conversation_creates_client_and_practice(self):
        from services.auto_crm_service import AutoCRMService

        conn = FakeConnection()
        # existing client lookup -> None, re-check -> None, practice type -> dict, existing practice -> None
        conn.fetchrow.side_effect = [
            None,
            None,
            {"id": 10, "base_price": 500.0},
            None,
        ]
        conn.fetchval.side_effect = [
            123,  # inserted client id
            456,  # inserted practice id
            789,  # interaction id
        ]
        pool = FakePool(conn)

        extracted, create_practice = build_extraction()

        extractor = MagicMock()
        extractor.extract_from_conversation = AsyncMock(return_value=extracted)
        extractor.should_create_practice = AsyncMock(return_value=create_practice)

        with patch("services.auto_crm_service.get_extractor", return_value=extractor):
            service = AutoCRMService(db_pool=pool)
            result = await service.process_conversation(
                conversation_id=99,
                messages=[{"role": "user", "content": "Need visa"}],
                user_email="client@example.com",
            )

        assert result["success"] is True
        assert result["client_created"] is True
        assert result["practice_created"] is True
        conn.fetchval.assert_awaited()
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_conversation_skips_practice_when_not_requested(self):
        from services.auto_crm_service import AutoCRMService

        conn = FakeConnection()
        conn.fetchrow.side_effect = [None, None]
        conn.fetchval.side_effect = [
            321,  # client id
            654,  # interaction id
        ]
        pool = FakePool(conn)

        extracted, _ = build_extraction(create_practice=False)
        extractor = MagicMock()
        extractor.extract_from_conversation = AsyncMock(return_value=extracted)
        extractor.should_create_practice = AsyncMock(return_value=False)

        with patch("services.auto_crm_service.get_extractor", return_value=extractor):
            service = AutoCRMService(db_pool=pool)
            result = await service.process_conversation(
                conversation_id=5,
                messages=[{"role": "user", "content": "hello"}],
                user_email="client@example.com",
            )

        assert result["practice_id"] is None
        assert result["practice_created"] is False

    @pytest.mark.asyncio
    async def test_process_email_interaction_creates_conversation_then_processes(self):
        from services.auto_crm_service import AutoCRMService

        conn = FakeConnection()
        conn.fetchval.return_value = 42
        pool = FakePool(conn)

        service = AutoCRMService(db_pool=pool)
        service.process_conversation = AsyncMock(return_value={"success": True, "client_id": 1})

        result = await service.process_email_interaction(
            email_data={
                "subject": "Need help",
                "sender": "User <user@example.com>",
                "body": "Please contact me.",
                "id": "msg-1",
            },
            team_member="agent@example.com",
        )

        assert result["success"] is True
        service.process_conversation.assert_awaited_once()
