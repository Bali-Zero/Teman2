"""
Integration tests for Identity Service
Tests user identity and profile management
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestIdentityServiceIntegration:
    """Integration tests for Identity Service"""

    @pytest.mark.asyncio
    async def test_identity_service_initialization(self, postgres_container):
        """Test identity service initialization"""
        from app.modules.identity.service import IdentityService

        service = IdentityService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_authenticate_user(self, postgres_container):
        """Test user authentication"""
        # Patch asyncpg.connect since IdentityService calls it directly
        with patch(
            "app.modules.identity.service.asyncpg.connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_conn = AsyncMock()

            # Mock fetchrow for successful user lookup
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "name": "Test User",
                    "email": "test@example.com",
                    "pin_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj.kP/j.kP/.",  # Example hash
                    "role": "admin",
                    "department": "tech",
                    "language": "en",
                    "personalized_response": False,
                    "is_active": True,
                    "last_login": None,
                    "failed_attempts": 0,
                    "locked_until": None,
                    "created_at": None,
                    "updated_at": None,
                }
            )

            # Mock execute for updates
            mock_conn.execute = AsyncMock()

            # Mock close
            mock_conn.close = AsyncMock()

            mock_connect.return_value = mock_conn

            from app.modules.identity.service import IdentityService

            service = IdentityService()

            # Mock verify_password to return True (bypass bcrypt for test speed/simplicity)
            with patch.object(service, "verify_password", return_value=True):
                user = await service.authenticate_user("test@example.com", "123456")

            assert user is not None
            assert user.email == "test@example.com"
            assert user.role == "admin"
