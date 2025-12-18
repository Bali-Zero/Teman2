"""
Unit tests for Conversations Router
Tests for persistent conversation history with PostgreSQL + Auto-CRM population

Coverage: save, history, clear, stats endpoints with JWT authentication
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-minimum-32-characters-long"
    settings.jwt_algorithm = "HS256"
    settings.database_url = "postgresql://test:test@localhost:5432/test"
    return settings


@pytest.fixture
def valid_jwt_token(mock_settings):
    """Generate a valid JWT token for testing"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    # Use timezone-aware datetime and ensure expiration is in the future
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "test@example.com",  # sub should be the email/identifier
        "email": "test@example.com",
        "user_id": "test-user-id",
        "role": "member",
        "exp": int(exp.timestamp()),  # JWT expects integer timestamp
    }
    token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")
    return token


@pytest.fixture
def expired_jwt_token(mock_settings):
    """Generate an expired JWT token for testing"""
    from jose import jwt

    payload = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "exp": datetime.utcnow().timestamp() - 3600,
    }
    token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")
    return token


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_auto_crm():
    """Mock Auto-CRM service"""
    auto_crm = AsyncMock()
    auto_crm.process_conversation = AsyncMock(
        return_value={
            "success": True,
            "client_id": 42,
            "client_created": False,
            "client_updated": True,
            "practice_id": 15,
            "practice_created": True,
            "interaction_id": 88,
        }
    )
    return auto_crm


# ============================================================================
# Authentication Tests
# ============================================================================


class TestGetCurrentUser:
    """Tests for JWT authentication helper"""

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        """Test that missing credentials raise 401"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret"
            mock_settings.jwt_algorithm = "HS256"

            from app.routers.conversations import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=None)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, mock_settings, valid_jwt_token):
        """Test that valid token returns user dict"""
        with patch("app.core.config.settings", mock_settings):
            from fastapi.security import HTTPAuthorizationCredentials

            from app.routers.conversations import get_current_user

            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

            user = await get_current_user(credentials=credentials)

            assert user["email"] == "test@example.com"
            assert user["user_id"] == "test-user-id"
            assert user["role"] == "member"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, mock_settings):
        """Test that invalid token raises 401"""
        with patch("app.core.config.settings", mock_settings):
            from fastapi.security import HTTPAuthorizationCredentials

            from app.routers.conversations import get_current_user

            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid-token-not-jwt"
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials)

            assert exc_info.value.status_code == 401


# ============================================================================
# Save Conversation Tests
# ============================================================================


class TestSaveConversation:
    """Tests for POST /api/bali-zero/conversations/save endpoint"""

    @pytest.mark.asyncio
    async def test_save_conversation_success(self, mock_settings, mock_asyncpg_pool, mock_auto_crm):
        """Test successful conversation save"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 123})
        conn.execute = AsyncMock()

        with patch("app.routers.conversations.get_auto_crm", return_value=mock_auto_crm):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            request = SaveConversationRequest(
                messages=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
                session_id="test-session-123",
                metadata={"team_member": "Anton"},
            )

            current_user = {"email": "test@example.com", "user_id": "test-user"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            assert result["success"] is True
            assert result["conversation_id"] == 123
            assert result["messages_saved"] == 2
            assert result["user_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_save_uses_jwt_email_not_request(self, mock_settings, mock_asyncpg_pool):
        """Test that user email comes from JWT, not request body (security)"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 456})
        conn.execute = AsyncMock()

        with patch("app.routers.conversations.get_auto_crm", return_value=None):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            request = SaveConversationRequest(
                messages=[{"role": "user", "content": "Test"}],
            )

            current_user = {"email": "jwt-user@example.com", "user_id": "jwt-user"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            assert result["user_email"] == "jwt-user@example.com"

    @pytest.mark.asyncio
    async def test_save_db_error_raises_500(self, mock_settings, mock_asyncpg_pool):
        """Test that database errors raise 500"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

        from app.routers.conversations import SaveConversationRequest, save_conversation

        request = SaveConversationRequest(
            messages=[{"role": "user", "content": "Test"}],
        )

        current_user = {"email": "test@example.com", "user_id": "test"}

        with pytest.raises(HTTPException) as exc_info:
            await save_conversation(request=request, current_user=current_user, db_pool=pool)

        assert exc_info.value.status_code == 500


# ============================================================================
# Get History Tests
# ============================================================================


class TestGetConversationHistory:
    """Tests for GET /api/bali-zero/conversations/history endpoint"""

    @pytest.mark.asyncio
    async def test_get_history_success(self, mock_settings, mock_asyncpg_pool):
        """Test successful history retrieval"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"},
                ],
                "created_at": datetime.now(),
            }
        )

        from app.routers.conversations import get_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_history(
            limit=20, session_id=None, current_user=current_user, db_pool=pool
        )

        assert result.success is True
        assert len(result.messages) == 2
        assert result.total_messages == 2

    @pytest.mark.asyncio
    async def test_get_history_empty(self, mock_settings, mock_asyncpg_pool):
        """Test empty history returns success with empty list"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value=None)

        from app.routers.conversations import get_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_history(
            limit=20, session_id=None, current_user=current_user, db_pool=pool
        )

        assert result.success is True
        assert result.messages == []
        assert result.total_messages == 0


# ============================================================================
# Clear History Tests
# ============================================================================


class TestClearConversationHistory:
    """Tests for DELETE /api/bali-zero/conversations/clear endpoint"""

    @pytest.mark.asyncio
    async def test_clear_history_success(self, mock_settings, mock_asyncpg_pool):
        """Test successful history clear"""
        pool, conn = mock_asyncpg_pool
        # Mock execute to return status with rowcount
        conn.execute = AsyncMock(return_value="DELETE 5")

        from app.routers.conversations import clear_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await clear_conversation_history(
            session_id=None, current_user=current_user, db_pool=pool
        )

        assert result["success"] is True
        assert result["deleted_count"] == 5


# ============================================================================
# Stats Tests
# ============================================================================


class TestGetConversationStats:
    """Tests for GET /api/bali-zero/conversations/stats endpoint"""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, mock_settings, mock_asyncpg_pool):
        """Test successful stats retrieval"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "total_conversations": 10,
                "total_messages": 150,
                "last_conversation": datetime(2024, 1, 15, 12, 0, 0),
            }
        )

        from app.routers.conversations import get_conversation_stats

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_stats(current_user=current_user, db_pool=pool)

        assert result["success"] is True
        assert result["user_email"] == "test@example.com"
        assert result["total_conversations"] == 10
        assert result["total_messages"] == 150
        assert result["last_conversation"] is not None


# ============================================================================
# Additional Edge Cases and Validation Tests
# ============================================================================


class TestSaveConversationEdgeCases:
    """Additional edge cases for save conversation endpoint"""

    @pytest.mark.asyncio
    async def test_save_conversation_empty_messages(self, mock_settings, mock_asyncpg_pool):
        """Test saving conversation with empty messages list"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 789})

        from app.routers.conversations import SaveConversationRequest, save_conversation

        request = SaveConversationRequest(messages=[])

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await save_conversation(request=request, current_user=current_user, db_pool=pool)

        assert result["success"] is True
        assert result["messages_saved"] == 0

    @pytest.mark.asyncio
    async def test_save_conversation_very_long_messages(self, mock_settings, mock_asyncpg_pool):
        """Test saving conversation with very long messages"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 999})

        from app.routers.conversations import SaveConversationRequest, save_conversation

        long_content = "A" * 10000  # 10KB message
        request = SaveConversationRequest(messages=[{"role": "user", "content": long_content}])

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await save_conversation(request=request, current_user=current_user, db_pool=pool)

        assert result["success"] is True
        assert result["messages_saved"] == 1

    @pytest.mark.asyncio
    async def test_save_conversation_auto_crm_unavailable(self, mock_settings, mock_asyncpg_pool):
        """Test saving conversation when auto-CRM is unavailable"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 111})

        with patch("app.routers.conversations.get_auto_crm", return_value=None):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            request = SaveConversationRequest(
                messages=[{"role": "user", "content": "Test message"}]
            )

            current_user = {"email": "test@example.com", "user_id": "test"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            assert result["success"] is True
            assert result["crm"]["processed"] is False
            assert "reason" in result["crm"]

    @pytest.mark.asyncio
    async def test_save_conversation_auto_crm_error(
        self, mock_settings, mock_asyncpg_pool, mock_auto_crm
    ):
        """Test saving conversation when auto-CRM raises error"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 222})

        mock_auto_crm.process_conversation = AsyncMock(side_effect=Exception("CRM error"))

        with patch("app.routers.conversations.get_auto_crm", return_value=mock_auto_crm):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            request = SaveConversationRequest(messages=[{"role": "user", "content": "Test"}])

            current_user = {"email": "test@example.com", "user_id": "test"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            # Should still succeed even if CRM fails
            assert result["success"] is True
            assert result["crm"]["processed"] is False
            assert "error" in result["crm"]

    @pytest.mark.asyncio
    async def test_save_conversation_with_session_id(self, mock_settings, mock_asyncpg_pool):
        """Test saving conversation with explicit session_id"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 333})

        with patch("app.routers.conversations.get_auto_crm", return_value=None):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            request = SaveConversationRequest(
                messages=[{"role": "user", "content": "Test"}],
                session_id="custom-session-123",
            )

            current_user = {"email": "test@example.com", "user_id": "test"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            assert result["success"] is True
            # Verify session_id was used (check call args - $2 is session_id)
            call_args = conn.fetchrow.call_args[0]
            assert call_args[2] == "custom-session-123"

    @pytest.mark.asyncio
    async def test_save_conversation_with_metadata(self, mock_settings, mock_asyncpg_pool):
        """Test saving conversation with metadata"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value={"id": 444})

        with patch("app.routers.conversations.get_auto_crm", return_value=None):
            from app.routers.conversations import SaveConversationRequest, save_conversation

            metadata = {"team_member": "John", "source": "web", "priority": "high"}
            request = SaveConversationRequest(
                messages=[{"role": "user", "content": "Test"}], metadata=metadata
            )

            current_user = {"email": "test@example.com", "user_id": "test"}

            result = await save_conversation(
                request=request, current_user=current_user, db_pool=pool
            )

            assert result["success"] is True


class TestGetConversationHistoryEdgeCases:
    """Additional edge cases for get history endpoint"""

    @pytest.mark.asyncio
    async def test_get_history_with_limit_boundary(self, mock_settings, mock_asyncpg_pool):
        """Test getting history with limit at boundary"""
        pool, conn = mock_asyncpg_pool
        # Return many messages
        many_messages = [{"role": "user", "content": f"Message {i}"} for i in range(100)]
        conn.fetchrow = AsyncMock(
            return_value={"messages": many_messages, "created_at": datetime.now()}
        )

        from app.routers.conversations import get_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_history(
            limit=20, session_id=None, current_user=current_user, db_pool=pool
        )

        assert result.success is True
        assert len(result.messages) == 20  # Should be limited
        assert result.total_messages == 20

    @pytest.mark.asyncio
    async def test_get_history_with_session_id(self, mock_settings, mock_asyncpg_pool):
        """Test getting history filtered by session_id"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "messages": [{"role": "user", "content": "Session message"}],
                "created_at": datetime.now(),
            }
        )

        from app.routers.conversations import get_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_history(
            limit=20, session_id="session-123", current_user=current_user, db_pool=pool
        )

        assert result.success is True
        # Verify session_id was used in query ($2 is session_id)
        call_args = conn.fetchrow.call_args[0]
        assert call_args[2] == "session-123"

    @pytest.mark.asyncio
    async def test_get_history_max_limit(self, mock_settings, mock_asyncpg_pool):
        """Test getting history with maximum limit"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "messages": [{"role": "user", "content": "Test"}],
                "created_at": datetime.now(),
            }
        )

        from app.routers.conversations import get_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_history(
            limit=1000, session_id=None, current_user=current_user, db_pool=pool
        )

        assert result.success is True


class TestClearConversationHistoryEdgeCases:
    """Additional edge cases for clear history endpoint"""

    @pytest.mark.asyncio
    async def test_clear_history_with_session_id(self, mock_settings, mock_asyncpg_pool):
        """Test clearing history for specific session"""
        pool, conn = mock_asyncpg_pool
        conn.execute = AsyncMock(return_value="DELETE 3")

        from app.routers.conversations import clear_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await clear_conversation_history(
            session_id="session-123", current_user=current_user, db_pool=pool
        )

        assert result["success"] is True
        assert result["deleted_count"] == 3
        # Verify session_id was used in query ($2 is session_id)
        call_args = conn.execute.call_args[0]
        assert call_args[2] == "session-123"

    @pytest.mark.asyncio
    async def test_clear_history_all_conversations(self, mock_settings, mock_asyncpg_pool):
        """Test clearing all conversations for user"""
        pool, conn = mock_asyncpg_pool
        conn.execute = AsyncMock(return_value="DELETE 10")

        from app.routers.conversations import clear_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await clear_conversation_history(
            session_id=None, current_user=current_user, db_pool=pool
        )

        assert result["success"] is True
        assert result["deleted_count"] == 10

    @pytest.mark.asyncio
    async def test_clear_history_zero_deleted(self, mock_settings, mock_asyncpg_pool):
        """Test clearing history when no conversations exist"""
        pool, conn = mock_asyncpg_pool
        conn.execute = AsyncMock(return_value="DELETE 0")

        from app.routers.conversations import clear_conversation_history

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await clear_conversation_history(
            session_id=None, current_user=current_user, db_pool=pool
        )

        assert result["success"] is True
        assert result["deleted_count"] == 0


class TestGetConversationStatsEdgeCases:
    """Additional edge cases for stats endpoint"""

    @pytest.mark.asyncio
    async def test_get_stats_empty_stats(self, mock_settings, mock_asyncpg_pool):
        """Test getting stats when user has no conversations"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(return_value=None)

        from app.routers.conversations import get_conversation_stats

        current_user = {"email": "newuser@example.com", "user_id": "newuser"}

        result = await get_conversation_stats(current_user=current_user, db_pool=pool)

        assert result["success"] is True
        assert result["total_conversations"] == 0
        assert result["total_messages"] == 0
        assert result["last_conversation"] is None

    @pytest.mark.asyncio
    async def test_get_stats_with_null_values(self, mock_settings, mock_asyncpg_pool):
        """Test getting stats with null database values"""
        pool, conn = mock_asyncpg_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "total_conversations": None,
                "total_messages": None,
                "last_conversation": None,
            }
        )

        from app.routers.conversations import get_conversation_stats

        current_user = {"email": "test@example.com", "user_id": "test"}

        result = await get_conversation_stats(current_user=current_user, db_pool=pool)

        assert result["success"] is True
        assert result["total_conversations"] == 0
        assert result["total_messages"] == 0
        assert result["last_conversation"] is None
