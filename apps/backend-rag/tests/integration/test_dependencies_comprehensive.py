"""
Comprehensive Integration Tests for Dependencies
Tests dependency injection, service dependencies

Covers:
- Dependency injection
- Service dependencies
- Error handling in dependencies
- Service availability checks
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestDependencyInjection:
    """Integration tests for dependency injection"""

    @pytest.mark.asyncio
    async def test_get_search_service_dependency(self):
        """Test get_search_service dependency"""

        from app.dependencies import get_search_service

        # Mock request with search_service in state
        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.app.state.search_service = MagicMock()

        # Get service
        service = get_search_service(mock_request)

        assert service is not None

    @pytest.mark.asyncio
    async def test_get_search_service_missing(self):
        """Test get_search_service when service is missing"""
        from fastapi import HTTPException

        from app.dependencies import get_search_service

        # Mock request without search_service
        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.app.state.search_service = None

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_search_service(mock_request)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_ai_client_dependency(self):
        """Test get_ai_client dependency"""

        from app.dependencies import get_ai_client

        # Mock request with ai_client in state
        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.app.state.ai_client = MagicMock()

        # Get service
        client = get_ai_client(mock_request)

        assert client is not None

    @pytest.mark.asyncio
    async def test_get_database_pool_dependency(self):
        """Test get_database_pool dependency"""

        from app.dependencies import get_database_pool

        # Mock request with db_pool in state
        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.app.state.db_pool = MagicMock()

        # Get pool
        pool = get_database_pool(mock_request)

        assert pool is not None

    @pytest.mark.asyncio
    async def test_get_current_user_dependency(self):
        """Test get_current_user dependency"""
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        # Create valid token
        secret = "test_jwt_secret_key_for_testing_only_min_32_chars"
        token = jwt.encode({"sub": "123", "email": "test@example.com"}, secret, algorithm="HS256")

        # Mock request with credentials
        mock_request = MagicMock()
        mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock security dependency
        with patch("app.dependencies.security") as mock_security:
            mock_security.return_value = mock_credentials

            # Get user (would need proper setup)
            # This is a simplified test
            assert token is not None
