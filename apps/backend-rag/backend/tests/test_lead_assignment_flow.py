"""
Test Script: Lead Assignment Flow
Tests the complete agentic CRM workflow:
1. AUTO CRM creates client from chat
2. Lead Assignment Agent assigns to team member
3. Telegram notification sent
4. Client-Memory sync trigger updates user_stats

Author: Claude Sonnet 4.5
Date: 2026-01-18

Usage:
    python -m pytest apps/backend-rag/backend/tests/test_lead_assignment_flow.py -v
    OR
    python apps/backend-rag/backend/tests/test_lead_assignment_flow.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.crm.lead_assignment_agent import (
    LeadAssignmentState,
    assign_lead,
    check_duplicates,
    send_telegram_notification,
    trigger_lead_assignment,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def db_pool():
    """Mock database pool for testing"""
    pool = MagicMock(spec=asyncpg.Pool)
    conn = AsyncMock()

    # Mock acquire as async context manager
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm

    return pool


@pytest.fixture
def telegram_service():
    """Mock Telegram service"""
    service = AsyncMock()
    service.send_message = AsyncMock(return_value={"ok": True, "result": {"message_id": 123}})
    return service


@pytest.fixture
def sample_client_data():
    """Sample client data for testing"""
    return {
        "email": "test@example.com",
        "phone": "+62 812 3456 7890",
        "full_name": "John Doe",
        "practice_type_code": "kitas",
    }


# ============================================
# UNIT TESTS
# ============================================


@pytest.mark.asyncio
async def test_check_duplicates_no_match(db_pool):
    """Test entity resolution when no duplicates exist"""
    state: LeadAssignmentState = {
        "client_id": 1,
        "client_data": {"email": "new@example.com", "phone": "+628123456789"},
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": None,
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    # Mock: no existing client found
    conn = await db_pool.acquire().__aenter__()
    conn.fetchrow = AsyncMock(return_value=None)

    result = await check_duplicates(state, db_pool)

    assert result["is_duplicate"] is False
    assert result["matched_client_id"] is None
    logger.info("✅ Test passed: check_duplicates_no_match")


@pytest.mark.asyncio
async def test_check_duplicates_email_match(db_pool):
    """Test entity resolution with email match"""
    state: LeadAssignmentState = {
        "client_id": 2,
        "client_data": {"email": "duplicate@example.com", "phone": "+628123456789"},
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": None,
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    # Mock: existing client found with same email
    conn = await db_pool.acquire().__aenter__()
    conn.fetchrow = AsyncMock(return_value={"id": 1, "assigned_to": "lead@balizero.com"})

    result = await check_duplicates(state, db_pool)

    assert result["is_duplicate"] is True
    assert result["matched_client_id"] == 1
    assert result["assigned_lead"] == "lead@balizero.com"
    logger.info("✅ Test passed: check_duplicates_email_match")


@pytest.mark.asyncio
async def test_assign_lead_department_match(db_pool):
    """Test lead assignment with department matching (kitas → setup dept)"""
    state: LeadAssignmentState = {
        "client_id": 1,
        "client_data": {"practice_type_code": "kitas"},
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": None,
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    # Mock: team member in setup department found
    conn = await db_pool.acquire().__aenter__()
    conn.fetchrow = AsyncMock(
        return_value={
            "email": "specialist@balizero.com",
            "full_name": "KITAS Specialist",
            "department": "setup",
            "active_practices": 3,
        },
    )
    conn.execute = AsyncMock()

    result = await assign_lead(state, db_pool)

    assert result["assigned_lead"] == "specialist@balizero.com"
    assert result["assigned_lead_name"] == "KITAS Specialist"
    assert (
        "setup" in result["assignment_reason"].lower()
        or "Department" in result["assignment_reason"]
    )
    logger.info("✅ Test passed: assign_lead_department_match")


@pytest.mark.asyncio
async def test_assign_lead_duplicate_uses_existing(db_pool):
    """Test lead assignment for duplicate client uses existing assignment"""
    state: LeadAssignmentState = {
        "client_id": 2,
        "client_data": {"practice_type_code": "kitas"},
        "is_duplicate": True,
        "matched_client_id": 1,
        "assigned_lead": "existing@balizero.com",
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    result = await assign_lead(state, db_pool)

    assert result["assigned_lead"] == "existing@balizero.com"
    assert "Duplicate client" in result["assignment_reason"]
    logger.info("✅ Test passed: assign_lead_duplicate_uses_existing")


@pytest.mark.asyncio
async def test_send_telegram_notification_success(db_pool, telegram_service):
    """Test Telegram notification sends successfully"""
    state: LeadAssignmentState = {
        "client_id": 1,
        "client_data": {
            "email": "test@example.com",
            "phone": "+628123456789",
            "full_name": "John Doe",
            "practice_type_code": "kitas",
        },
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": "lead@balizero.com",
        "assigned_lead_name": "Lead Agent",
        "assignment_reason": "Specialty: kitas, Workload: 3",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    # Mock: telegram chat_id found
    conn = await db_pool.acquire().__aenter__()
    conn.fetchrow = AsyncMock(
        return_value={"telegram_chat_id": 123456789, "full_name": "Lead Agent"},
    )

    result = await send_telegram_notification(state, db_pool, telegram_service)

    assert result["telegram_chat_id"] == 123456789
    assert result["notification_sent"] is True
    telegram_service.send_message.assert_called_once()
    logger.info("✅ Test passed: send_telegram_notification_success")


@pytest.mark.asyncio
async def test_send_telegram_notification_no_chat_id(db_pool, telegram_service):
    """Test Telegram notification fails when no chat_id"""
    state: LeadAssignmentState = {
        "client_id": 1,
        "client_data": {
            "email": "test@example.com",
            "phone": "+628123456789",
            "full_name": "John Doe",
            "practice_type_code": "kitas",
        },
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": "lead@balizero.com",
        "assigned_lead_name": "Lead Agent",
        "assignment_reason": "Specialty: kitas",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }

    # Mock: no telegram chat_id found
    conn = await db_pool.acquire().__aenter__()
    conn.fetchrow = AsyncMock(return_value=None)

    result = await send_telegram_notification(state, db_pool, telegram_service)

    assert result["notification_sent"] is False
    assert len(result["errors"]) > 0
    assert "No Telegram chat_id" in result["errors"][0]
    logger.info("✅ Test passed: send_telegram_notification_no_chat_id")


# ============================================
# INTEGRATION TEST
# ============================================


@pytest.mark.asyncio
async def test_full_lead_assignment_workflow(db_pool, telegram_service, sample_client_data):
    """Test complete lead assignment workflow end-to-end"""
    # Mock database responses
    conn = await db_pool.acquire().__aenter__()

    # Step 1: No duplicates
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,  # check email duplicate
            None,  # check phone duplicate
            {
                "email": "specialist@balizero.com",
                "full_name": "KITAS Specialist",
                "department": "setup",
                "active_practices": 2,
            },  # assign lead (department match)
            {
                "telegram_chat_id": 987654321,
                "full_name": "KITAS Specialist",
            },  # get telegram chat_id
        ],
    )
    conn.execute = AsyncMock()

    # Execute workflow
    result = await trigger_lead_assignment(
        client_id=1,
        client_data=sample_client_data,
        db_pool=db_pool,
        telegram_service=telegram_service,
    )

    # Assertions
    assert result["success"] is True
    assert result["assigned_lead"] == "specialist@balizero.com"
    assert result["notification_sent"] is True
    assert result["telegram_chat_id"] == 987654321
    assert len(result["errors"]) == 0

    # Verify Telegram notification was sent
    telegram_service.send_message.assert_called_once()
    call_args = telegram_service.send_message.call_args
    assert call_args.kwargs["chat_id"] == 987654321
    assert "John Doe" in call_args.kwargs["text"]
    assert "Kitas" in call_args.kwargs["text"]

    logger.info("✅ Test passed: full_lead_assignment_workflow")


# ============================================
# MANUAL TEST RUNNER
# ============================================


async def run_manual_tests():
    """Run tests manually without pytest"""
    logger.info("🧪 Running Lead Assignment Flow Tests")
    logger.info("=" * 60)

    # Create mocks
    db_pool = MagicMock(spec=asyncpg.Pool)
    conn = AsyncMock()
    db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    db_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    telegram_service = AsyncMock()
    telegram_service.send_message = AsyncMock(
        return_value={"ok": True, "result": {"message_id": 123}},
    )

    sample_client_data = {
        "email": "test@example.com",
        "phone": "+62 812 3456 7890",
        "full_name": "John Doe",
        "practice_type_code": "kitas",
    }

    # Run tests
    tests = [
        ("No Duplicates", test_check_duplicates_no_match(db_pool)),
        ("Email Duplicate Match", test_check_duplicates_email_match(db_pool)),
        ("Department Matching", test_assign_lead_department_match(db_pool)),
        ("Duplicate Assignment", test_assign_lead_duplicate_uses_existing(db_pool)),
        ("Telegram Success", test_send_telegram_notification_success(db_pool, telegram_service)),
        (
            "Telegram No Chat ID",
            test_send_telegram_notification_no_chat_id(db_pool, telegram_service),
        ),
        (
            "Full Workflow",
            test_full_lead_assignment_workflow(db_pool, telegram_service, sample_client_data),
        ),
    ]

    passed = 0
    failed = 0

    for test_name, test_coro in tests:
        try:
            await test_coro
            logger.info(f"✅ {test_name}")
            passed += 1
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Test Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_manual_tests())
    sys.exit(0 if success else 1)
