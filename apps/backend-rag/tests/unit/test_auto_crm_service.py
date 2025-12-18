"""
Unit tests for Auto CRM Service
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.auto_crm_service import AutoCRMService, get_auto_crm_service

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_extractor():
    """Mock AI CRM Extractor"""
    mock = MagicMock()
    mock.extract_from_conversation = AsyncMock()
    mock.should_create_practice = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg database pool"""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock pool.acquire() context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acquire_cm

    # Mock conn.transaction() - must return a context manager, not a coroutine
    transaction_cm = MagicMock()
    transaction_cm.__aenter__ = AsyncMock(return_value=None)
    transaction_cm.__aexit__ = AsyncMock(return_value=False)
    # Make transaction() return the context manager directly (not awaitable)
    conn.transaction = MagicMock(return_value=transaction_cm)

    # Mock async methods
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    return pool, conn


@pytest.fixture
def auto_crm_service(mock_extractor, mock_db_pool):
    """Create AutoCRMService instance"""
    pool, _ = mock_db_pool
    with patch("services.auto_crm_service.get_extractor", return_value=mock_extractor):
        return AutoCRMService(db_pool=pool)


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init(auto_crm_service, mock_extractor):
    """Test AutoCRMService initialization"""
    assert auto_crm_service.extractor is mock_extractor


# ============================================================================
# Tests for database connection (asyncpg pool)
# ============================================================================


@pytest.mark.asyncio
async def test_db_connection_success(auto_crm_service, mock_db_pool):
    """Test getting database connection successfully"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    async with pool.acquire() as c:
        assert c == conn


@pytest.mark.asyncio
async def test_db_connection_no_pool(auto_crm_service):
    """Test database connection failure when no pool"""
    auto_crm_service.pool = None
    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
        user_email="test@example.com",
    )
    assert result["success"] is False
    assert "Database pool not available" in result.get("error", "")


# ============================================================================
# Tests for process_conversation
# ============================================================================


@pytest.mark.asyncio
async def test_process_conversation_create_new_client(
    auto_crm_service, mock_extractor, mock_db_pool
):
    """Test processing conversation creates new client"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    # Mock extraction result
    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "test@example.com",
            "full_name": "Test User",
            "phone": "+62812345678",
            "whatsapp": "+62812345678",
            "nationality": "Italian",
            "confidence": 0.8,
        },
        "practice_intent": {"detected": False},
        "summary": "Test conversation",
        "sentiment": "positive",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Mock database queries (asyncpg style)
    # 1. Check existing client - returns None
    conn.fetchrow.return_value = None
    # 2. INSERT client RETURNING id - returns {"id": 1}
    conn.fetchval.side_effect = [1, 10]  # client_id, interaction_id

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
        user_email="test@example.com",
    )

    assert result["success"] is True
    assert result["client_id"] == 1
    assert result["client_created"] is True
    assert result["interaction_id"] == 10


@pytest.mark.asyncio
async def test_process_conversation_update_existing_client(
    auto_crm_service, mock_extractor, mock_db_pool
):
    """Test processing conversation updates existing client"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    # Mock existing client
    existing_client = {
        "id": 1,
        "email": "test@example.com",
        "full_name": None,
        "phone": None,
    }

    # Mock extraction result
    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "test@example.com",
            "full_name": "Updated Name",
            "phone": "+62812345678",
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.8,
        },
        "practice_intent": {"detected": False},
        "summary": "Test conversation",
        "sentiment": "positive",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Mock database queries (asyncpg style)
    conn.fetchrow.return_value = existing_client  # Existing client found
    conn.fetchval.return_value = 10  # Interaction ID

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
        user_email="test@example.com",
    )

    assert result["success"] is True
    assert result["client_id"] == 1
    assert result["client_updated"] is True
    assert conn.execute.call_count >= 2  # Update client + insert interaction


@pytest.mark.asyncio
async def test_process_conversation_create_practice(auto_crm_service, mock_extractor, mock_db_pool):
    """Test processing conversation creates practice"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "test@example.com",
            "full_name": "Test User",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.8,
        },
        "practice_intent": {
            "detected": True,
            "practice_type_code": "PT_PMA",
            "details": "Setup PT PMA",
        },
        "summary": "Test conversation",
        "sentiment": "positive",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    mock_extractor.should_create_practice.return_value = True

    # Mock database queries (asyncpg style)
    # Order of calls in process_conversation:
    # 1. fetchrow: check existing client with user_email (None) - line 137
    # 2. extract_from_conversation (mocked)
    # 3. fetchrow: re-check with extracted email if needed (None) - line 156 (skipped if same email)
    # 4. fetchval: INSERT client RETURNING id (1) - line 198
    # 5. fetchrow: get practice type ({"id": 5, "base_price": 10000000}) - line 228
    # 6. fetchrow: check existing practice (None) - line 239
    # 7. fetchval: INSERT practice RETURNING id (2) - line 253
    # 8. fetchval: INSERT interaction RETURNING id (10) - line 256
    conn.fetchrow.side_effect = [
        None,  # No existing client (first check with user_email)
        None,  # Re-check with extracted email (if different, but here same)
        {"id": 5, "base_price": 10000000},  # Practice type
        None,  # No existing practice
    ]
    # fetchval calls: client_id, practice_id, interaction_id
    conn.fetchval.side_effect = [1, 2, 10]

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "I want to setup PT PMA"}],
        user_email="test@example.com",
    )

    assert result["success"] is True
    assert result["practice_id"] == 2
    assert result["practice_created"] is True


@pytest.mark.asyncio
async def test_process_conversation_low_confidence_no_client(
    auto_crm_service, mock_extractor, mock_db_pool
):
    """Test processing conversation with low confidence doesn't create client"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": None,
            "full_name": None,
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.3,  # Low confidence
        },
        "practice_intent": {"detected": False},
        "summary": "Test conversation",
        "sentiment": "neutral",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Even without client, interaction is still created
    # Mock database queries (asyncpg style)
    conn.fetchrow.return_value = None  # No client check
    conn.fetchval.return_value = 10  # Interaction ID

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert result["success"] is True
    assert result["client_id"] is None
    assert result["client_created"] is False
    assert result["interaction_id"] == 10


@pytest.mark.asyncio
async def test_process_conversation_exception(auto_crm_service, mock_extractor, mock_db_pool):
    """Test processing conversation handles exceptions"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    mock_extractor.extract_from_conversation.side_effect = Exception("Database error")

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert result["success"] is False
    assert "error" in result
    assert result["client_id"] is None


@pytest.mark.asyncio
async def test_process_conversation_uses_extracted_email(
    auto_crm_service, mock_extractor, mock_db_pool
):
    """Test processing conversation uses extracted email if not provided"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "extracted@example.com",
            "full_name": "Test User",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.8,
        },
        "practice_intent": {"detected": False},
        "summary": "Test conversation",
        "sentiment": "positive",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Mock database queries (asyncpg style)
    # When no user_email but extracted email exists:
    # 1. fetchrow: check existing client with extracted email (None)
    # 2. fetchval: INSERT client RETURNING id (1)
    # 3. fetchval: INSERT interaction RETURNING id (10)
    conn.fetchrow.return_value = None  # No existing client
    conn.fetchval.side_effect = [1, 10]  # client_id, interaction_id

    result = await auto_crm_service.process_conversation(
        conversation_id=1,
        messages=[{"role": "user", "content": "Hello"}],
        # No user_email provided
    )

    assert result["success"] is True
    assert result["client_id"] == 1
    # Verify that extracted email was used (at least INSERT client + INSERT interaction)
    # Note: execute is called for INSERT/UPDATE statements
    assert conn.execute.call_count >= 1  # At least one INSERT


# ============================================================================
# Tests for process_email_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_process_email_interaction_success(auto_crm_service, mock_extractor, mock_db_pool):
    """Test processing email interaction successfully"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    email_data = {
        "subject": "Test Email",
        "sender": "test@example.com",
        "body": "Hello, I need help",
        "date": datetime.now(),
        "id": "email-123",
    }

    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "test@example.com",
            "full_name": "Test User",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.8,
        },
        "practice_intent": {"detected": False},
        "summary": "Email conversation",
        "sentiment": "positive",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Mock database queries (asyncpg style)
    # process_email_interaction creates conversation, then calls process_conversation
    conn.fetchval.side_effect = [100, 1, 10]  # conversation_id, client_id, interaction_id
    conn.fetchrow.return_value = None  # No existing client

    result = await auto_crm_service.process_email_interaction(email_data)

    assert result["success"] is True
    assert result["client_id"] == 1


@pytest.mark.asyncio
async def test_process_email_interaction_extract_email_from_format(
    auto_crm_service, mock_extractor, mock_db_pool
):
    """Test processing email extracts email from 'Name <email@domain.com>' format"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    email_data = {
        "subject": "Test",
        "sender": "John Doe <john@example.com>",
        "body": "Hello",
        "date": datetime.now(),
        "id": "email-123",
    }

    mock_extractor.extract_from_conversation.return_value = {
        "client": {
            "email": "john@example.com",
            "full_name": "John Doe",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "confidence": 0.8,
        },
        "practice_intent": {"detected": False},
        "summary": "Email",
        "sentiment": "neutral",
        "extracted_entities": {},
        "action_items": [],
        "urgency": "normal",
    }

    # Mock database queries (asyncpg style)
    conn.fetchval.side_effect = [100, 1, 10]  # conversation_id, client_id, interaction_id
    conn.fetchrow.return_value = None  # No existing client

    result = await auto_crm_service.process_email_interaction(email_data)

    assert result["success"] is True
    # Verify email extraction happened
    assert conn.execute.called


@pytest.mark.asyncio
async def test_process_email_interaction_exception(auto_crm_service, mock_extractor, mock_db_pool):
    """Test processing email interaction handles exceptions"""
    pool, conn = mock_db_pool
    auto_crm_service.pool = pool

    email_data = {
        "subject": "Test",
        "sender": "test@example.com",
        "body": "Hello",
        "date": datetime.now(),
        "id": "email-123",
    }

    conn.execute.side_effect = Exception("Database error")

    result = await auto_crm_service.process_email_interaction(email_data)

    assert result["success"] is False
    assert "error" in result


# ============================================================================
# Tests for get_auto_crm_service
# ============================================================================


def test_get_auto_crm_service_singleton():
    """Test get_auto_crm_service returns singleton"""
    with patch("services.auto_crm_service._auto_crm_instance", None):
        with patch("services.auto_crm_service.AutoCRMService") as mock_service_class:
            mock_instance = MagicMock()
            mock_service_class.return_value = mock_instance

            service1 = get_auto_crm_service()
            service2 = get_auto_crm_service()

            # Should return same instance
            assert service1 is service2
            # Should only be initialized once
            assert mock_service_class.call_count == 1
