"""
Unit tests for webhook_chat router

Tests cover:
- Anonymous user handling
- Authenticated user handling
- User ID format verification
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.webhook_chat import router


@pytest.fixture
def mock_orchestrator():
    """Mock AgenticRAGOrchestrator"""
    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(
        return_value=MagicMock(
            answer="Test answer",
            sources=[{"title": "Source 1", "url": "https://example.com"}],
        )
    )
    return orchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool with ConversationRepository"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def mock_conversation_repo():
    """Mock ConversationRepository"""
    repo = AsyncMock()
    repo.get_messages = AsyncMock(return_value=[])
    repo.save_messages = AsyncMock(return_value=123)
    return repo


@pytest.fixture
def test_app(mock_orchestrator, mock_db_pool, mock_conversation_repo):
    """Create FastAPI test app with mocked dependencies"""
    from backend.app.dependencies import get_current_user_optional, get_optional_database_pool, get_orchestrator

    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_optional_database_pool] = lambda: mock_db_pool

    return app


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)


class TestWebhookChatUserIDFormat:
    """Test user_id format for anonymous vs authenticated users"""

    def test_anonymous_user_id_format(self, test_app, mock_orchestrator):
        """Test anonymous user gets anonymous_{session_id[:8]} format"""
        from backend.app.dependencies import get_current_user_optional

        # Override to return None (anonymous)
        test_app.dependency_overrides[get_current_user_optional] = lambda: None

        client = TestClient(test_app)

        # Mock ConversationRepository
        from unittest.mock import patch

        with patch("backend.app.routers.webhook_chat.ConversationRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_messages = AsyncMock(return_value=[])
            mock_repo.save_messages = AsyncMock(return_value=123)
            mock_repo_class.return_value = mock_repo

            response = client.post(
                "/webhook/chat",
                json={
                    "query": "Test query",
                    "session_id": "session_123456",
                    "user_id": None,
                    "metadata": {},
                },
            )

            assert response.status_code == 200
            # Verify user_id passed to orchestrator
            mock_orchestrator.process_query.assert_called_once()
            call_kwargs = mock_orchestrator.process_query.call_args[1]
            user_id = call_kwargs["user_id"]
            # Should be anonymous_{session_id[:8]} = anonymous_session_
            assert user_id.startswith("anonymous_")
            assert "session_" in user_id

    def test_authenticated_user_uses_email(self, test_app, mock_orchestrator):
        """Test authenticated user uses email from JWT"""
        from backend.app.dependencies import get_current_user_optional

        mock_user = {"email": "test@example.com", "user_id": "123", "role": "user"}

        # Override to return authenticated user
        test_app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        client = TestClient(test_app)

        from unittest.mock import patch

        with patch("backend.app.routers.webhook_chat.ConversationRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_messages = AsyncMock(return_value=[])
            mock_repo.save_messages = AsyncMock(return_value=123)
            mock_repo_class.return_value = mock_repo

            response = client.post(
                "/webhook/chat",
                json={
                    "query": "Test query",
                    "session_id": "test_session",
                    "user_id": "should_be_ignored",
                    "metadata": {},
                },
            )

            assert response.status_code == 200
            # Verify email was used as user_id
            mock_orchestrator.process_query.assert_called_once()
            call_kwargs = mock_orchestrator.process_query.call_args[1]
            assert call_kwargs["user_id"] == "test@example.com"
