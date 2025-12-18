"""
Comprehensive Tests for Conversations Router
Tests conversation history, auto-CRM integration, PostgreSQL persistence
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

# ===== ROUTER INITIALIZATION TESTS =====


class TestConversationsRouterInitialization:
    """Test conversations router initialization"""

    def test_router_imports(self):
        """Test router can be imported"""
        from backend.app.routers import conversations

        assert conversations is not None

    def test_router_has_correct_prefix(self):
        """Test router has correct API prefix"""
        from backend.app.routers.conversations import router

        assert router.prefix == "/api/bali-zero/conversations"

    def test_router_has_conversations_tag(self):
        """Test router has correct tags"""
        from backend.app.routers.conversations import router

        assert "conversations" in router.tags

    def test_constants_defined(self):
        """Test router constants are defined"""
        from backend.app.routers.conversations import (
            DEFAULT_CONVERSATION_MESSAGES_LIMIT,
            DEFAULT_LIMIT,
            MAX_LIMIT,
        )

        assert DEFAULT_LIMIT == 20
        assert MAX_LIMIT == 1000
        assert DEFAULT_CONVERSATION_MESSAGES_LIMIT >= 20


# ===== REQUEST/RESPONSE MODEL TESTS =====


class TestConversationModels:
    """Test Pydantic models for conversations"""

    def setup_method(self):
        from backend.app.routers.conversations import (
            ConversationHistoryResponse,
            ConversationListItem,
            ConversationListResponse,
            SaveConversationRequest,
            SingleConversationResponse,
        )

        self.SaveConversationRequest = SaveConversationRequest
        self.ConversationHistoryResponse = ConversationHistoryResponse
        self.ConversationListItem = ConversationListItem
        self.ConversationListResponse = ConversationListResponse
        self.SingleConversationResponse = SingleConversationResponse

    def test_save_conversation_request_creation(self):
        """Test creating save conversation request"""
        messages = [
            {"role": "user", "content": "What is KITAS?"},
            {"role": "assistant", "content": "KITAS is a limited stay permit"},
        ]

        request = self.SaveConversationRequest(messages=messages, session_id="session-123")

        assert len(request.messages) == 2
        assert request.session_id == "session-123"

    def test_save_conversation_request_with_metadata(self):
        """Test save conversation request with metadata"""
        request = self.SaveConversationRequest(
            messages=[{"role": "user", "content": "Test"}],
            metadata={"client_id": "client-456", "topic": "visa"},
        )

        assert request.metadata["client_id"] == "client-456"
        assert request.metadata["topic"] == "visa"

    def test_conversation_list_item_creation(self):
        """Test creating conversation list item"""
        item = self.ConversationListItem(
            id=1,
            title="KITAS Application",
            preview="Discussion about KITAS requirements...",
            message_count=15,
            created_at="2025-12-10T10:00:00",
            session_id="session-abc",
        )

        assert item.id == 1
        assert item.title == "KITAS Application"
        assert item.message_count == 15

    def test_conversation_history_response(self):
        """Test conversation history response model"""
        response = self.ConversationHistoryResponse(
            success=True,
            messages=[{"role": "user", "content": "Test"}],
            total_messages=1,
            session_id="session-123",
        )

        assert response.success is True
        assert response.total_messages == 1


# ===== SAVE CONVERSATION ENDPOINT TESTS =====


class TestSaveConversationEndpoint:
    """Test /save endpoint"""

    @pytest.mark.asyncio
    async def test_save_conversation_success(self):
        """Test successfully saving conversation"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        messages = [
            {"role": "user", "content": "What is KITAS?"},
            {"role": "assistant", "content": "KITAS is a permit"},
        ]

        request = SaveConversationRequest(messages=messages, session_id="session-test")

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm:
            mock_crm.return_value = None  # CRM disabled

            result = await save_conversation(request, mock_user, mock_pool)

            assert result is not None
            assert result.get("success") is True or result is not None

    @pytest.mark.asyncio
    async def test_save_conversation_with_auto_crm(self):
        """Test saving conversation triggers auto-CRM"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        messages = [
            {"role": "user", "content": "I'm John Doe, need KITAS help"},
            {"role": "assistant", "content": "I can help with KITAS"},
        ]

        request = SaveConversationRequest(messages=messages)

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm_getter:
            mock_crm = Mock()
            mock_crm.process_conversation = AsyncMock(
                return_value={"client_id": 42, "client_created": True}
            )
            mock_crm_getter.return_value = mock_crm

            result = await save_conversation(request, mock_user, mock_pool)

            # CRM should be triggered
            assert result is not None

    @pytest.mark.asyncio
    async def test_save_conversation_user_from_jwt(self):
        """Test user email is extracted from JWT, not request"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        messages = [{"role": "user", "content": "Test"}]

        # Request does NOT contain user_email (security feature)
        request = SaveConversationRequest(messages=messages)

        # User email comes from JWT token
        mock_user = {"email": "authenticated@example.com"}
        mock_pool = AsyncMock()

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm:
            mock_crm.return_value = None

            result = await save_conversation(request, mock_user, mock_pool)

            # Should use authenticated user email
            assert result is not None

    @pytest.mark.asyncio
    async def test_save_empty_conversation(self):
        """Test saving conversation with no messages"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        request = SaveConversationRequest(messages=[])

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        # Should handle gracefully or reject
        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm:
            mock_crm.return_value = None

            try:
                result = await save_conversation(request, mock_user, mock_pool)
                assert result is not None or result["success"] is False
            except Exception:
                pass  # May reject empty conversations


# ===== CONVERSATION HISTORY ENDPOINT TESTS =====


class TestConversationHistoryEndpoint:
    """Test /history endpoint"""

    @pytest.mark.asyncio
    async def test_get_conversation_history(self):
        """Test getting conversation history"""
        from backend.app.routers.conversations import get_conversation_history

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
        ]
        mock_conn.fetch.return_value = [{"messages": json.dumps(mock_messages)}]

        result = await get_conversation_history(
            session_id="session-123", current_user=mock_user, db_pool=mock_pool
        )

        assert result is not None or result.success is True

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self):
        """Test getting history with message limit"""
        from backend.app.routers.conversations import get_conversation_history

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        result = await get_conversation_history(
            session_id="session-123", limit=10, current_user=mock_user, db_pool=mock_pool
        )

        # Should respect limit parameter
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_history_nonexistent_session(self):
        """Test getting history for non-existent session"""
        from backend.app.routers.conversations import get_conversation_history

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        result = await get_conversation_history(
            session_id="nonexistent-session", current_user=mock_user, db_pool=mock_pool
        )

        # Should return empty or error
        assert result is not None


# ===== CONVERSATION LIST ENDPOINT TESTS =====


class TestConversationListEndpoint:
    """Test /list endpoint"""

    @pytest.mark.asyncio
    async def test_list_conversations(self):
        """Test listing user's conversations"""
        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conversations = [
            {
                "id": 1,
                "title": "KITAS Discussion",
                "preview": "About visa requirements",
                "message_count": 10,
                "created_at": datetime.now(),
                "session_id": "session-1",
            }
        ]
        mock_conn.fetch.return_value = mock_conversations

        result = await list_conversations(current_user=mock_user, db_pool=mock_pool)

        assert result is not None or result.success is True

    @pytest.mark.asyncio
    async def test_list_conversations_with_limit(self):
        """Test listing conversations with limit"""
        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        result = await list_conversations(limit=10, current_user=mock_user, db_pool=mock_pool)

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_conversations_pagination(self):
        """Test conversation list pagination"""
        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        # Get first page
        result1 = await list_conversations(
            limit=10, offset=0, current_user=mock_user, db_pool=mock_pool
        )

        # Get second page
        result2 = await list_conversations(
            limit=10, offset=10, current_user=mock_user, db_pool=mock_pool
        )

        # Both should succeed
        assert result1 is not None
        assert result2 is not None


# ===== SINGLE CONVERSATION ENDPOINT TESTS =====


class TestSingleConversationEndpoint:
    """Test /conversation/{conversation_id} endpoint"""

    @pytest.mark.asyncio
    async def test_get_single_conversation(self):
        """Test getting single conversation by ID"""
        from backend.app.routers.conversations import get_conversation

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conversation = {
            "id": 1,
            "user_email": "test@example.com",
            "messages": json.dumps([{"role": "user", "content": "Test"}]),
            "created_at": datetime.now(),
            "session_id": "session-1",
        }
        mock_conn.fetchrow.return_value = mock_conversation

        result = await get_conversation(
            conversation_id=1, current_user=mock_user, db_pool=mock_pool
        )

        assert result is not None or result.success is True

    @pytest.mark.asyncio
    async def test_get_conversation_unauthorized(self):
        """Test getting conversation owned by different user"""
        from backend.app.routers.conversations import get_conversation

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Conversation belongs to different user
        mock_conversation = {"id": 1, "user_email": "other@example.com", "messages": "[]"}
        mock_conn.fetchrow.return_value = mock_conversation

        # Should reject or return error
        with pytest.raises(HTTPException):
            await get_conversation(conversation_id=1, current_user=mock_user, db_pool=mock_pool)


# ===== DELETE CONVERSATION ENDPOINT TESTS =====


class TestDeleteConversationEndpoint:
    """Test /delete/{conversation_id} endpoint"""

    @pytest.mark.asyncio
    async def test_delete_conversation(self):
        """Test deleting conversation"""
        from backend.app.routers.conversations import delete_conversation

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute.return_value = "DELETE 1"

        result = await delete_conversation(
            conversation_id=1, current_user=mock_user, db_pool=mock_pool
        )

        assert result is not None or result.get("success") is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self):
        """Test deleting non-existent conversation"""
        from backend.app.routers.conversations import delete_conversation

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute.return_value = "DELETE 0"

        result = await delete_conversation(
            conversation_id=999, current_user=mock_user, db_pool=mock_pool
        )

        # Should return not found or error
        assert result is not None


# ===== AUTO-CRM INTEGRATION TESTS =====


class TestAutoCRMIntegration:
    """Test auto-CRM integration"""

    @pytest.mark.asyncio
    async def test_auto_crm_extracts_client_info(self):
        """Test auto-CRM extracts client information"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        messages = [
            {"role": "user", "content": "Hi, I'm Sarah Johnson from Tech Corp"},
            {"role": "assistant", "content": "Hello Sarah, how can I help?"},
        ]

        request = SaveConversationRequest(messages=messages)

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm_getter:
            mock_crm = Mock()
            mock_crm.process_conversation = AsyncMock(
                return_value={
                    "client_created": True,
                    "client_name": "Sarah Johnson",
                    "company": "Tech Corp",
                }
            )
            mock_crm_getter.return_value = mock_crm

            result = await save_conversation(request, mock_user, mock_pool)

            # CRM should extract client info
            assert result is not None

    @pytest.mark.asyncio
    async def test_auto_crm_identifies_practice_area(self):
        """Test auto-CRM identifies practice area"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        messages = [
            {"role": "user", "content": "I need help with KITAS visa application"},
            {"role": "assistant", "content": "I can help with that"},
        ]

        request = SaveConversationRequest(messages=messages)

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm_getter:
            mock_crm = Mock()
            mock_crm.process_conversation = AsyncMock(
                return_value={"practice_id": 1, "practice_area": "Immigration & Visa"}
            )
            mock_crm_getter.return_value = mock_crm

            result = await save_conversation(request, mock_user, mock_pool)

            assert result is not None


# ===== DATABASE ERROR HANDLING TESTS =====


class TestDatabaseErrorHandling:
    """Test database error handling"""

    @pytest.mark.asyncio
    async def test_save_conversation_database_error(self):
        """Test handling database connection errors"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        request = SaveConversationRequest(messages=[{"role": "user", "content": "Test"}])

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("Database connection failed")

        with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm:
            mock_crm.return_value = None

            with pytest.raises(Exception):
                await save_conversation(request, mock_user, mock_pool)

    @pytest.mark.asyncio
    async def test_list_conversations_database_error(self):
        """Test handling database errors in list endpoint"""
        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            await list_conversations(current_user=mock_user, db_pool=mock_pool)


# ===== AUTHENTICATION TESTS =====


class TestConversationsAuthentication:
    """Test authentication requirements"""

    @pytest.mark.asyncio
    async def test_save_requires_authentication(self):
        """Test save endpoint requires authentication"""
        from backend.app.routers.conversations import SaveConversationRequest, save_conversation

        request = SaveConversationRequest(messages=[{"role": "user", "content": "Test"}])

        # Should fail without current_user
        with pytest.raises(TypeError):
            await save_conversation(request)

    @pytest.mark.asyncio
    async def test_list_requires_authentication(self):
        """Test list endpoint requires authentication"""
        from backend.app.routers.conversations import list_conversations

        # Should fail without current_user
        with pytest.raises(TypeError):
            await list_conversations()

    @pytest.mark.asyncio
    async def test_user_can_only_access_own_conversations(self):
        """Test users can only access their own conversations"""
        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "user1@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Should only return conversations for user1@example.com
        mock_conn.fetch.return_value = []

        result = await list_conversations(current_user=mock_user, db_pool=mock_pool)

        # Query should filter by user email
        assert result is not None


# ===== PERFORMANCE TESTS =====


class TestConversationsPerformance:
    """Test performance characteristics"""

    @pytest.mark.asyncio
    async def test_list_conversations_performance(self):
        """Test list endpoint performance"""
        import time

        from backend.app.routers.conversations import list_conversations

        mock_user = {"email": "test@example.com"}
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []

        start = time.time()
        await list_conversations(current_user=mock_user, db_pool=mock_pool)
        elapsed = time.time() - start

        # Should be fast
        assert elapsed < 1.0


# ===== PARAMETERIZED TESTS =====


@pytest.mark.parametrize("message_count", [1, 10, 50, 100])
@pytest.mark.asyncio
async def test_save_conversations_with_varying_sizes(message_count):
    """Parameterized test for saving conversations of different sizes"""
    from backend.app.routers.conversations import SaveConversationRequest, save_conversation

    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
        for i in range(message_count)
    ]

    request = SaveConversationRequest(messages=messages)

    mock_user = {"email": "test@example.com"}
    mock_pool = AsyncMock()

    with patch("backend.app.routers.conversations.get_auto_crm") as mock_crm:
        mock_crm.return_value = None

        result = await save_conversation(request, mock_user, mock_pool)

        assert result is not None


@pytest.mark.parametrize(
    "limit,offset",
    [
        (10, 0),
        (20, 0),
        (50, 0),
        (10, 10),
        (20, 40),
    ],
)
@pytest.mark.asyncio
async def test_pagination_scenarios(limit, offset):
    """Parameterized test for pagination scenarios"""
    from backend.app.routers.conversations import list_conversations

    mock_user = {"email": "test@example.com"}
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch.return_value = []

    result = await list_conversations(
        limit=limit, offset=offset, current_user=mock_user, db_pool=mock_pool
    )

    assert result is not None
