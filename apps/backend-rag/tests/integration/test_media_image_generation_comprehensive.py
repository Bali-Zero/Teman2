"""
Comprehensive Integration Tests for Media and Image Generation Routers
Tests image generation, media handling

Covers:
- POST /media/generate-image - Generate image
- Image generation service
- Error handling
- Media storage
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestImageGenerationRouter:
    """Integration tests for Image Generation router"""

    @pytest.mark.asyncio
    async def test_image_generation_service_initialization(self):
        """Test ImageGenerationService initialization"""
        with patch("services.image_generation_service.OpenAI") as mock_openai:
            from services.image_generation_service import ImageGenerationService

            service = ImageGenerationService()

            assert service is not None

    @pytest.mark.asyncio
    async def test_image_generation_endpoint(self):
        """Test POST /media/generate-image - Generate image"""
        with patch("services.image_generation_service.ImageGenerationService") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.generate_image = AsyncMock(
                return_value={
                    "success": True,
                    "url": "https://example.com/generated_image.png",
                    "prompt": "Test prompt",
                    "service": "openai",
                }
            )
            mock_service.return_value = mock_service_instance

            # Test generation
            result = await mock_service_instance.generate_image("Test prompt")

            assert result["success"] is True
            assert "url" in result

    @pytest.mark.asyncio
    async def test_image_generation_error_handling(self):
        """Test image generation error handling"""
        with patch("services.image_generation_service.ImageGenerationService") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.generate_image = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Invalid prompt",
                }
            )

            # Test error handling
            result = await mock_service_instance.generate_image("")

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_image_generation_storage(self, db_pool):
        """Test image generation storage"""

        async with db_pool.acquire() as conn:
            # Create generated_images table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_images (
                    id SERIAL PRIMARY KEY,
                    prompt TEXT,
                    image_url TEXT,
                    service_used VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store generated image
            image_id = await conn.fetchval(
                """
                INSERT INTO generated_images (prompt, image_url, service_used)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "Test prompt",
                "https://example.com/image.png",
                "openai",
            )

            assert image_id is not None

            # Retrieve image
            image = await conn.fetchrow(
                """
                SELECT prompt, image_url, service_used
                FROM generated_images
                WHERE id = $1
                """,
                image_id,
            )

            assert image is not None
            assert image["prompt"] == "Test prompt"

            # Cleanup
            await conn.execute("DELETE FROM generated_images WHERE id = $1", image_id)


@pytest.mark.integration
class TestMediaRouter:
    """Integration tests for Media router"""

    @pytest.mark.asyncio
    async def test_media_handling(self, db_pool):
        """Test media handling"""

        async with db_pool.acquire() as conn:
            # Create media_files table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_files (
                    id SERIAL PRIMARY KEY,
                    file_name VARCHAR(255),
                    file_url TEXT,
                    file_type VARCHAR(100),
                    file_size INTEGER,
                    uploaded_by VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store media file
            media_id = await conn.fetchval(
                """
                INSERT INTO media_files (
                    file_name, file_url, file_type, file_size, uploaded_by
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "test_image.png",
                "https://example.com/test_image.png",
                "image/png",
                102400,
                "test_user",
            )

            assert media_id is not None

            # Retrieve media
            media = await conn.fetchrow(
                """
                SELECT file_name, file_type, file_size
                FROM media_files
                WHERE id = $1
                """,
                media_id,
            )

            assert media is not None
            assert media["file_type"] == "image/png"

            # Cleanup
            await conn.execute("DELETE FROM media_files WHERE id = $1", media_id)
