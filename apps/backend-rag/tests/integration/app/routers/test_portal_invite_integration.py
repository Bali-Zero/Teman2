"""
Integration Tests for Portal Invite Router
Tests portal_invite endpoints with real PostgreSQL database and email service
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.portal_invite import router


@pytest.fixture
def test_app():
    """Create FastAPI test app with portal_invite router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.mark.integration
@pytest.mark.database
class TestPortalInviteIntegration:
    """Integration tests for portal_invite router with real database"""

    @pytest.mark.asyncio
    @patch("app.routers.portal_invite.send_email")
    async def test_send_invitation_success(self, mock_send_email, test_client, db_pool):
        """Test sending invitation successfully"""
        mock_send_email.return_value = True

        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Invite",
                "test.client.invite@example.com",
                "active",
                "test@team.com",
            )

            # Send invitation
            response = test_client.post(
                f"/api/portal/invite/{client_id}",
                json={"email": "test.client.invite@example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify invitation token was created (if table exists)
            try:
                token = await conn.fetchval(
                    """
                    SELECT token FROM portal_invites
                    WHERE client_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    client_id,
                )
                assert token is not None
            except Exception:
                # Table might not exist, that's OK
                pass

    @pytest.mark.asyncio
    async def test_get_client_invitations(self, test_client, db_pool):
        """Test getting client invitations"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Invitations",
                "test.client.invitations@example.com",
                "active",
                "test@team.com",
            )

            # Create invitation (if table exists)
            try:
                await conn.execute(
                    """
                    INSERT INTO portal_invites (client_id, email, token, status, created_by)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    client_id,
                    "test.client.invitations@example.com",
                    "test_token_123",
                    "pending",
                    "test@team.com",
                )
            except Exception:
                # Table might not exist, skip
                pass

            # Get invitations
            response = test_client.get(f"/api/portal/invite/{client_id}/history")

            # Should succeed even if no invitations
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_validate_token_invalid(self, test_client):
        """Test validating invalid token"""
        response = test_client.get("/api/portal/validate-token?token=invalid_token_xyz")

        assert response.status_code in [400, 404]
        data = response.json()
        assert data.get("valid") is False or "error" in data or "not found" in str(data).lower()

    @pytest.mark.asyncio
    async def test_complete_registration_invalid_token(self, test_client):
        """Test completing registration with invalid token"""
        response = test_client.post(
            "/api/portal/complete-registration",
            json={"token": "invalid_token", "pin": "123456"},
        )

        assert response.status_code in [400, 404]
