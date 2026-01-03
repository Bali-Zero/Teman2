"""
Unit tests for identity router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))



@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock()
    request.headers = {}
    return request


class TestIdentityRouter:
    """Tests for identity router"""

    @pytest.mark.asyncio
    async def test_get_user_profile(self, mock_request):
        """Test getting user profile"""
        with patch("app.modules.identity.router.get_current_user") as mock_get_user, \
             patch("app.modules.identity.router.get_database_pool") as mock_get_pool:
            mock_user = {"email": "test@example.com", "name": "Test User"}
            mock_get_user.return_value = mock_user

            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=mock_user)
            mock_pool.acquire = AsyncMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            # Import endpoint function
            from app.modules.identity.router import get_user_profile
            result = await get_user_profile(
                current_user=mock_user,
                db_pool=mock_pool
            )
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_update_user_profile(self, mock_request):
        """Test updating user profile"""
        with patch("app.modules.identity.router.get_current_user") as mock_get_user, \
             patch("app.modules.identity.router.get_database_pool") as mock_get_pool:
            mock_user = {"email": "test@example.com"}
            mock_get_user.return_value = mock_user

            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_pool.acquire = AsyncMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            # Import endpoint function
            from app.modules.identity.router import update_user_profile
            result = await update_user_profile(
                profile_data={"name": "Updated Name"},
                current_user=mock_user,
                db_pool=mock_pool
            )
            assert isinstance(result, dict)





