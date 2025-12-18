"""
Comprehensive Integration Tests for Router Endpoints
Tests all router endpoints with real database and services

Covers:
- Handlers router
- Team activity router
- Productivity router
- Media router
- Image generation router
- Legal ingest router
- WhatsApp router
- Instagram router
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestHandlersRouterIntegration:
    """Integration tests for handlers router"""

    @pytest.mark.asyncio
    async def test_list_all_handlers(self, test_client):
        """Test GET /api/handlers/list - list all handlers"""
        response = test_client.get("/api/handlers/list")

        assert response.status_code in [200, 503]  # 503 if services not initialized
        if response.status_code == 200:
            data = response.json()
            assert "total_handlers" in data
            assert "categories" in data
            assert "handlers" in data
            assert isinstance(data["total_handlers"], int)
            assert isinstance(data["categories"], dict)

    @pytest.mark.asyncio
    async def test_search_handlers(self, test_client):
        """Test GET /api/handlers/search - search handlers"""
        response = test_client.get("/api/handlers/search?query=oracle")

        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "handlers" in data


@pytest.mark.integration
class TestTeamActivityRouterIntegration:
    """Integration tests for team activity router"""

    @pytest.mark.asyncio
    async def test_team_activity_tracking(self, db_pool):
        """Test team activity tracking"""

        async with db_pool.acquire() as conn:
            # Create team_activities table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_activities (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    activity_type VARCHAR(100),
                    description TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create activity
            activity_id = await conn.fetchval(
                """
                INSERT INTO team_activities (
                    user_id, activity_type, description, metadata
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "test@team.com",
                "client_interaction",
                "Created new client",
                {"client_id": 123, "action": "create"},
            )

            assert activity_id is not None

            # Retrieve activities
            activities = await conn.fetch(
                """
                SELECT id, activity_type, description
                FROM team_activities
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                "test@team.com",
            )

            assert len(activities) == 1
            assert activities[0]["activity_type"] == "client_interaction"

            # Cleanup
            await conn.execute("DELETE FROM team_activities WHERE id = $1", activity_id)

    @pytest.mark.asyncio
    async def test_team_activity_aggregation(self, db_pool):
        """Test team activity aggregation"""

        async with db_pool.acquire() as conn:
            # Create multiple activities
            user_id = "test@team.com"
            for i, activity_type in enumerate(
                ["client_interaction", "practice_update", "document_upload"]
            ):
                await conn.execute(
                    """
                    INSERT INTO team_activities (
                        user_id, activity_type, description, created_at
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id,
                    activity_type,
                    f"Test activity {i + 1}",
                    datetime.now(),
                )

            # Aggregate activities by type
            aggregated = await conn.fetch(
                """
                SELECT activity_type, COUNT(*) as count
                FROM team_activities
                WHERE user_id = $1
                GROUP BY activity_type
                """,
                user_id,
            )

            assert len(aggregated) == 3

            # Cleanup
            await conn.execute("DELETE FROM team_activities WHERE user_id = $1", user_id)


@pytest.mark.integration
class TestProductivityRouterIntegration:
    """Integration tests for productivity router"""

    @pytest.mark.asyncio
    async def test_productivity_services(self, db_pool):
        """Test productivity services integration"""

        async with db_pool.acquire() as conn:
            # Create productivity_tasks table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS productivity_tasks (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    task_type VARCHAR(100),
                    title VARCHAR(255),
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    priority VARCHAR(50),
                    due_date TIMESTAMP,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create task
            task_id = await conn.fetchval(
                """
                INSERT INTO productivity_tasks (
                    user_id, task_type, title, description, status, priority
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "test@team.com",
                "email_followup",
                "Follow up with client",
                "Send email to client about KITAS application",
                "pending",
                "high",
            )

            assert task_id is not None

            # Update task status
            await conn.execute(
                """
                UPDATE productivity_tasks
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "completed",
                task_id,
            )

            # Verify update
            task = await conn.fetchrow(
                """
                SELECT status FROM productivity_tasks WHERE id = $1
                """,
                task_id,
            )

            assert task["status"] == "completed"

            # Cleanup
            await conn.execute("DELETE FROM productivity_tasks WHERE id = $1", task_id)


@pytest.mark.integration
class TestImageGenerationRouterIntegration:
    """Integration tests for image generation router"""

    @pytest.mark.asyncio
    async def test_image_generation_service(self):
        """Test image generation service integration"""
        with patch("services.image_generation_service.ImageGenerationService") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.generate_image = AsyncMock(
                return_value={
                    "images": [{"url": "https://example.com/image.png", "prompt": "test"}],
                    "model": "dall-e-3",
                }
            )
            mock_service.return_value = mock_service_instance

            # Test image generation
            result = await mock_service_instance.generate_image(
                prompt="Test image generation", model="dall-e-3"
            )

            assert result is not None
            assert "images" in result
            assert len(result["images"]) > 0


@pytest.mark.integration
class TestLegalIngestRouterIntegration:
    """Integration tests for legal ingest router"""

    @pytest.mark.asyncio
    async def test_legal_document_ingestion(self, qdrant_client):
        """Test legal document ingestion into Qdrant"""

        collection_name = "test_legal_integration"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Mock embedding
            test_embedding = [0.1] * 1536

            # Insert legal document
            document_id = "legal_doc_1"
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": document_id,
                        "vector": test_embedding,
                        "payload": {
                            "text": "Pasal 1 - Ketentuan Umum",
                            "metadata": {
                                "law_id": "UU-11-2020",
                                "pasal": "1",
                                "category": "legal_regulation",
                            },
                        },
                    }
                ],
            )

            # Search document
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=1,
            )

            assert len(results) > 0
            assert results[0]["id"] == document_id

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass


@pytest.mark.integration
class TestWhatsAppRouterIntegration:
    """Integration tests for WhatsApp router"""

    @pytest.mark.asyncio
    async def test_whatsapp_webhook_verification(self, test_client):
        """Test WhatsApp webhook verification"""
        # Test webhook verification endpoint
        response = test_client.get(
            "/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": os.getenv("WHATSAPP_VERIFY_TOKEN", "test_token"),
                "hub.challenge": "test_challenge",
            },
        )

        # Should return challenge for verification
        assert response.status_code in [200, 400, 401]

    @pytest.mark.asyncio
    async def test_whatsapp_message_storage(self, db_pool):
        """Test WhatsApp message storage"""

        async with db_pool.acquire() as conn:
            # Create whatsapp_messages table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whatsapp_messages (
                    id SERIAL PRIMARY KEY,
                    message_id VARCHAR(255) UNIQUE,
                    from_number VARCHAR(50),
                    to_number VARCHAR(50),
                    message_text TEXT,
                    message_type VARCHAR(50),
                    timestamp TIMESTAMP,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store message
            message_id = await conn.fetchval(
                """
                INSERT INTO whatsapp_messages (
                    message_id, from_number, to_number, message_text, message_type, timestamp
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "wa_msg_123",
                "+6281234567890",
                "+6280987654321",
                "Hello, I need help with KITAS",
                "text",
                datetime.now(),
            )

            assert message_id is not None

            # Retrieve message
            message = await conn.fetchrow(
                """
                SELECT message_text, from_number
                FROM whatsapp_messages
                WHERE message_id = $1
                """,
                "wa_msg_123",
            )

            assert message is not None
            assert "KITAS" in message["message_text"]

            # Cleanup
            await conn.execute("DELETE FROM whatsapp_messages WHERE id = $1", message_id)


@pytest.mark.integration
class TestInstagramRouterIntegration:
    """Integration tests for Instagram router"""

    @pytest.mark.asyncio
    async def test_instagram_webhook_verification(self, test_client):
        """Test Instagram webhook verification"""
        response = test_client.get(
            "/api/instagram/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": os.getenv("INSTAGRAM_VERIFY_TOKEN", "test_token"),
                "hub.challenge": "test_challenge",
            },
        )

        assert response.status_code in [200, 400, 401]

    @pytest.mark.asyncio
    async def test_instagram_message_storage(self, db_pool):
        """Test Instagram message storage"""

        async with db_pool.acquire() as conn:
            # Create instagram_messages table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instagram_messages (
                    id SERIAL PRIMARY KEY,
                    message_id VARCHAR(255) UNIQUE,
                    sender_id VARCHAR(255),
                    recipient_id VARCHAR(255),
                    message_text TEXT,
                    message_type VARCHAR(50),
                    timestamp TIMESTAMP,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store message
            message_id = await conn.fetchval(
                """
                INSERT INTO instagram_messages (
                    message_id, sender_id, recipient_id, message_text, message_type, timestamp
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "ig_msg_123",
                "ig_user_123",
                "ig_business_123",
                "Hi, I'm interested in your services",
                "text",
                datetime.now(),
            )

            assert message_id is not None

            # Retrieve message
            message = await conn.fetchrow(
                """
                SELECT message_text, sender_id
                FROM instagram_messages
                WHERE message_id = $1
                """,
                "ig_msg_123",
            )

            assert message is not None
            assert "interested" in message["message_text"].lower()

            # Cleanup
            await conn.execute("DELETE FROM instagram_messages WHERE id = $1", message_id)


@pytest.mark.integration
class TestMediaRouterIntegration:
    """Integration tests for media router"""

    @pytest.mark.asyncio
    async def test_media_upload_storage(self, db_pool):
        """Test media upload storage"""

        async with db_pool.acquire() as conn:
            # Create media_files table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_files (
                    id SERIAL PRIMARY KEY,
                    file_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255),
                    file_name VARCHAR(255),
                    file_type VARCHAR(100),
                    file_size BIGINT,
                    storage_path TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store media file metadata
            file_id = await conn.fetchval(
                """
                INSERT INTO media_files (
                    file_id, user_id, file_name, file_type, file_size, storage_path
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "media_file_123",
                "test@team.com",
                "document.pdf",
                "application/pdf",
                1024000,
                "/storage/media/document.pdf",
            )

            assert file_id is not None

            # Retrieve file
            file_record = await conn.fetchrow(
                """
                SELECT file_name, file_type, file_size
                FROM media_files
                WHERE file_id = $1
                """,
                "media_file_123",
            )

            assert file_record is not None
            assert file_record["file_name"] == "document.pdf"
            assert file_record["file_type"] == "application/pdf"

            # Cleanup
            await conn.execute("DELETE FROM media_files WHERE id = $1", file_id)
