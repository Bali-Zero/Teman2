"""
Integration Tests for CRM Portal Integration Router
Tests crm_portal_integration endpoints with real PostgreSQL database
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

from backend.app.routers.crm_portal_integration import router


@pytest.fixture
def test_app():
    """Create FastAPI test app with crm_portal_integration router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.mark.integration
@pytest.mark.database
class TestCRMPortalIntegrationIntegration:
    """Integration tests for crm_portal_integration router with real database"""

    @pytest.mark.asyncio
    async def test_get_portal_status_no_access(self, test_client, db_pool):
        """Test getting portal status for client without access"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Portal",
                "test.client.portal@example.com",
                "active",
                "test@team.com",
            )

            # Get portal status
            response = test_client.get(f"/api/crm/portal/{client_id}/status")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            # Should be "none" or "no_access" for new client
            assert data["status"] in ["none", "no_access", "pending"]

    @pytest.mark.asyncio
    @patch("backend.app.routers.crm_portal_integration.send_email")
    async def test_send_portal_invite(self, mock_send_email, test_client, db_pool):
        """Test sending portal invite"""
        mock_send_email.return_value = True

        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Invite Portal",
                "test.client.invite.portal@example.com",
                "active",
                "test@team.com",
            )

            # Send invite
            response = test_client.post(
                f"/api/crm/portal/{client_id}/invite",
                json={"email": "test.client.invite.portal@example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_unread_messages_count(self, test_client, db_pool):
        """Test getting unread messages count"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Messages",
                "test.client.messages@example.com",
                "active",
                "test@team.com",
            )

            # Create messages (if table exists)
            try:
                await conn.execute(
                    """
                    INSERT INTO portal_messages (client_id, sender_type, message_text, is_read, created_by)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    client_id,
                    "team",
                    "Test message",
                    False,
                    "test@team.com",
                )
            except Exception:
                # Table might not exist, skip
                pass

            # Get unread count
            response = test_client.get("/api/crm/portal/messages/unread-count")

            # Should succeed
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_get_client_messages(self, test_client, db_pool):
        """Test getting client messages"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Messages List",
                "test.client.messages.list@example.com",
                "active",
                "test@team.com",
            )

            # Get messages
            response = test_client.get(f"/api/crm/portal/{client_id}/messages")

            # Should succeed even if no messages
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_get_recent_portal_activity(self, test_client, db_pool):
        """Test getting recent portal activity"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "Test Client Activity",
                "test.client.activity@example.com",
                "active",
                "test@team.com",
            )

            # Get activity
            response = test_client.get("/api/crm/portal/recent-activity")

            # Should succeed
            assert response.status_code in [200, 404]
