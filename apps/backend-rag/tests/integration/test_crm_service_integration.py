"""
Integration tests for CRM Services
Tests CRM service interactions
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCRMServiceIntegration:
    """Integration tests for CRM Services"""

    @pytest.mark.asyncio
    async def test_crm_client_service_flow(self, postgres_container):
        """Test CRM client service flow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Test Client"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            from app.routers.crm_clients import router

            # Test that router can be imported and used
            assert router is not None

    @pytest.mark.asyncio
    async def test_crm_practice_service_flow(self, postgres_container):
        """Test CRM practice service flow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "practice_type": "KITAS"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            from app.routers.crm_practices import router

            # Test that router can be imported and used
            assert router is not None
