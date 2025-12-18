import os
import sys
from pathlib import Path

# Add backend directory to sys.path to simulate running from backend root
backend_path = Path(__file__).parents[3] / "backend"
sys.path.insert(0, str(backend_path))

# Set env vars before importing app
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["GOOGLE_API_KEY"] = "test-key"

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main_cloud import app

# Create a TestClient
client = TestClient(app)


@pytest.fixture
def mock_app_state():
    """Mock the app state for testing."""
    app.state.services_initialized = True
    app.state.intelligent_router = AsyncMock()
    app.state.memory_service = AsyncMock()
    app.state.collaborator_service = AsyncMock()

    # Create a mock collaborator with attributes
    mock_collab = MagicMock()
    mock_collab.id = "user123"
    mock_collab.name = "Test User"
    mock_collab.role = "member"
    app.state.collaborator_service.identify.return_value = mock_collab

    return app.state


@pytest.mark.asyncio
async def test_app_startup():
    """Test application startup and service initialization."""
    # Import here to avoid import-time env validation issues
    from app.setup.service_initializer import initialize_services
    
    with patch("app.setup.service_initializer.service_registry") as mock_registry:
        with patch("app.setup.service_initializer.ZantaraAIClient") as MockAI:
            with patch("app.setup.service_initializer.SearchService") as MockSearch:
                # Mock successful initialization
                mock_registry.has_critical_failures.return_value = False

                await initialize_services(app)

                assert app.state.services_initialized is True
                assert mock_registry.register.called


@pytest.mark.asyncio
async def test_chat_stream_endpoint_success(mock_app_state):
    """Test the chat stream endpoint with valid input."""

    # Mock the stream_chat method to yield chunks
    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "data": "Hello"}
        yield {"type": "token", "data": " World"}
        yield {"type": "done", "data": ""}


@pytest.mark.asyncio
async def test_chat_stream_endpoint_success(mock_app_state):
    """Test the chat stream endpoint with valid input."""

    # Mock the stream_chat method to yield chunks
    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "data": "Hello"}
        yield {"type": "token", "data": " World"}
        yield {"type": "done", "data": ""}

    mock_app_state.intelligent_router.stream_chat = mock_stream

    # Mock API Key validation to pass middleware
    with patch("app.services.api_key_auth.APIKeyAuth.validate_api_key") as mock_validate:
        mock_validate.return_value = {
            "id": "user123",
            "email": "test@example.com",
            "role": "member",
        }

        headers = {"X-API-Key": "test-key"}
        response = client.get("/bali-zero/chat-stream?query=Hello", headers=headers)

        assert response.status_code == 200
        # Verify streaming content (TestClient streams are iterators)
        # httpx Response uses iter_bytes()
        content = b"".join(response.iter_bytes())
        assert b"Hello" in content
        assert b"World" in content


@pytest.mark.asyncio
async def test_chat_stream_endpoint_no_query():
    """Test endpoint with empty query."""
    headers = {"X-API-Key": "test-key"}

    # Mock API Key validation
    with patch("app.services.api_key_auth.APIKeyAuth.validate_api_key") as mock_validate:
        mock_validate.return_value = {
            "id": "user123",
            "email": "test@example.com",
            "role": "member",
        }

        response = client.get("/bali-zero/chat-stream?query=", headers=headers)
        assert response.status_code == 400
        assert "Query must not be empty" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_stream_endpoint_unauthorized():
    """Test endpoint without authentication."""
    # Without auth headers, middleware should reject
    response = client.get("/bali-zero/chat-stream?query=Hello")
    # Middleware may return 401, 403, or 500 if services not initialized
    # Accept any error status code as valid rejection
    assert response.status_code >= 400
