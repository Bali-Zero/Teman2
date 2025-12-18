"""
ZANTARA MEDIA - Content Repository Tests
Tests for database operations
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from uuid import UUID

from app.db.content_repository import ContentRepository
from app.models import ContentStatus, ContentType, ContentCategory


@pytest.mark.asyncio
class TestContentRepository:
    """Test content repository database operations."""

    @pytest.fixture
    async def repository(self, mock_db_pool):
        """Create repository with mocked pool."""
        repo = ContentRepository()
        repo._pool = mock_db_pool
        return repo

    async def test_create_content(self, repository, mock_db_pool):
        """Test creating content."""
        # Mock database response
        mock_row = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "Test Article",
            "slug": "test-article",
            "body": "Test body",
            "summary": "Test summary",
            "type": "ARTICLE",
            "category": "IMMIGRATION",
            "status": "DRAFT",
            "created_at": datetime.utcnow(),
        }

        # Configure the mock connection stored in the pool
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Create content
        result = await repository.create_content(
            title="Test Article",
            slug="test-article",
            body="Test body",
            summary="Test summary",
            content_type=ContentType.ARTICLE,
            category=ContentCategory.IMMIGRATION,
            tags=["test"],
            word_count=2,
            reading_time_minutes=1,
        )

        # Assertions
        assert result["title"] == "Test Article"
        assert result["slug"] == "test-article"
        assert result["status"] == "DRAFT"
        mock_db_pool._mock_conn.fetchrow.assert_called_once()

    async def test_get_content_by_id(self, repository, mock_db_pool):
        """Test fetching content by ID."""
        content_id = UUID("123e4567-e89b-12d3-a456-426614174000")

        mock_row = {
            "id": str(content_id),
            "title": "Test Article",
            "status": "PUBLISHED",
        }

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await repository.get_content_by_id(content_id)

        assert result["id"] == str(content_id)
        assert result["title"] == "Test Article"
        assert result["status"] == "PUBLISHED"

    async def test_get_content_by_id_not_found(self, repository, mock_db_pool):
        """Test fetching non-existent content."""
        content_id = UUID("123e4567-e89b-12d3-a456-426614174000")

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await repository.get_content_by_id(content_id)

        assert result is None

    async def test_list_content(self, repository, mock_db_pool):
        """Test listing content with filters."""
        mock_rows = [
            {"id": "1", "title": "Article 1", "status": "PUBLISHED"},
            {"id": "2", "title": "Article 2", "status": "PUBLISHED"},
        ]

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=mock_rows)

        result = await repository.list_content(status=ContentStatus.PUBLISHED, limit=10)

        assert len(result) == 2
        assert result[0]["title"] == "Article 1"
        assert result[1]["title"] == "Article 2"

    async def test_update_content_status(self, repository, mock_db_pool):
        """Test updating content status."""
        content_id = UUID("123e4567-e89b-12d3-a456-426614174000")

        mock_row = {
            "id": str(content_id),
            "status": "PUBLISHED",
            "published_at": datetime.utcnow(),
        }

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await repository.update_content_status(
            content_id=content_id, status=ContentStatus.PUBLISHED
        )

        assert result["status"] == "PUBLISHED"
        assert "published_at" in result

    async def test_create_intel_signal(self, repository, mock_db_pool):
        """Test creating intel signal."""
        mock_row = {
            "id": "signal-123",
            "title": "Test Signal",
            "category": "IMMIGRATION",
            "processed": False,
        }

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await repository.create_intel_signal(
            title="Test Signal",
            summary="Test summary",
            category=ContentCategory.IMMIGRATION,
            source_name="Test Source",
            priority=8,
        )

        assert result["title"] == "Test Signal"
        assert result["category"] == "IMMIGRATION"
        assert result["processed"] is False

    async def test_get_pending_intel_signals(self, repository, mock_db_pool):
        """Test fetching pending intel signals."""
        mock_rows = [
            {"id": "1", "title": "Signal 1", "priority": 9},
            {"id": "2", "title": "Signal 2", "priority": 8},
        ]

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=mock_rows)

        result = await repository.get_pending_intel_signals(limit=10, min_priority=7)

        assert len(result) == 2
        assert result[0]["priority"] == 9
        assert result[1]["priority"] == 8

    async def test_mark_intel_signal_processed(self, repository, mock_db_pool):
        """Test marking signal as processed."""
        signal_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        content_id = UUID("456e4567-e89b-12d3-a456-426614174000")

        mock_row = {
            "id": str(signal_id),
            "processed": True,
            "action_taken": "content_created",
            "content_id": str(content_id),
        }

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await repository.mark_intel_signal_processed(
            signal_id=signal_id, action="content_created", content_id=content_id
        )

        assert result["processed"] is True
        assert result["action_taken"] == "content_created"
        assert result["content_id"] == str(content_id)
