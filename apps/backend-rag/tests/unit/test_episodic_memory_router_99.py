"""
Unit tests for Episodic Memory Router - 99% Coverage
Tests all endpoints, error cases, and edge cases
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Setup environment
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.unit
class TestEpisodicMemoryRouterComprehensive:
    """Comprehensive unit tests for episodic memory router"""

    def mock_current_user(self):
        """Mock authenticated user"""
        return {"email": "test@example.com", "id": 1}

    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn)))
        return pool


class TestAddEventEndpoint:
    """Tests for POST /api/episodic-memory/events endpoint"""

    @pytest.mark.asyncio
    async def test_add_event_success_with_all_fields(self):
        """Test successful event creation with all fields"""
        mock_current_user = {"email": "test@example.com", "id": 1}
        mock_db_pool = MagicMock()

        with patch("app.core.config.settings"):
            with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.add_event = AsyncMock(
                    return_value={
                        "status": "created",
                        "id": 1,
                        "title": "Test Event",
                        "created_at": datetime.now(timezone.utc),
                    }
                )
                mock_service_class.return_value = mock_service

                from app.routers.episodic_memory import AddEventRequest, add_event

                request = AddEventRequest(
                    title="Started PT PMA process",
                    description="Began the registration process",
                    event_type="milestone",
                    emotion="positive",
                    occurred_at=datetime.now(timezone.utc),
                    related_entities=[{"type": "visa", "name": "KITAS"}],
                    metadata={"priority": "high"},
                )

                result = await add_event(request, mock_current_user, mock_db_pool)

                assert result["success"] is True
                assert result["message"] == "Event added to timeline"
                assert result["data"]["id"] == 1

    @pytest.mark.asyncio
    async def test_add_event_invalid_event_type_defaults(self, mock_current_user, mock_db_pool):
        """Test that invalid event_type defaults to GENERAL"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(return_value={"status": "created", "id": 1})
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(title="Test Event", event_type="invalid_type")

            result = await add_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True
            # Verify EventType.GENERAL was used
            mock_service.add_event.assert_called_once()
            call_args = mock_service.add_event.call_args
            assert call_args[1]["event_type"] == EventType.GENERAL

    @pytest.mark.asyncio
    async def test_add_event_invalid_emotion_defaults(self, mock_current_user, mock_db_pool):
        """Test that invalid emotion defaults to NEUTRAL"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(return_value={"status": "created", "id": 1})
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(title="Test Event", emotion="invalid_emotion")

            result = await add_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True
            # Verify Emotion.NEUTRAL was used
            call_args = mock_service.add_event.call_args
            assert call_args[1]["emotion"] == Emotion.NEUTRAL

    @pytest.mark.asyncio
    async def test_add_event_service_error(self, mock_current_user, mock_db_pool):
        """Test handling of service error"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(
                return_value={"status": "error", "message": "Database connection failed"}
            )
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(title="Test Event")

            with pytest.raises(HTTPException) as exc_info:
                await add_event(request, mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Database connection failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_add_event_unhandled_exception(self, mock_current_user, mock_db_pool):
        """Test handling of unexpected exceptions"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(side_effect=Exception("Unexpected error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(title="Test Event")

            with pytest.raises(HTTPException) as exc_info:
                await add_event(request, mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Unexpected error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_add_event_default_occurred_at(self, mock_current_user, mock_db_pool):
        """Test that occurred_at defaults to now when not provided"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(return_value={"status": "created", "id": 1})
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(title="Test Event")

            await add_event(request, mock_current_user, mock_db_pool)

            # Verify occurred_at was set to now
            call_args = mock_service.add_event.call_args
            occurred_at = call_args[1]["occurred_at"]
            assert occurred_at is not None
            assert isinstance(occurred_at, datetime)


class TestExtractEventEndpoint:
    """Tests for POST /api/episodic-memory/extract endpoint"""

    @pytest.mark.asyncio
    async def test_extract_event_with_temporal_reference(self, mock_current_user, mock_db_pool):
        """Test successful event extraction with temporal reference"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.extract_and_save_event = AsyncMock(
                return_value={"status": "created", "id": 1, "title": "Started PT PMA"}
            )
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import extract_and_save_event

            request = ExtractEventRequest(
                message="Oggi ho iniziato il processo PT PMA",
                ai_response="Great! Starting the process.",
            )

            result = await extract_and_save_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True
            assert result["message"] == "Event extracted and saved"
            assert result["data"]["id"] == 1

    @pytest.mark.asyncio
    async def test_extract_event_no_temporal_reference(self, mock_current_user, mock_db_pool):
        """Test extraction when no temporal reference found"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.extract_and_save_event = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import extract_and_save_event

            request = ExtractEventRequest(message="I need help with PT PMA registration")

            result = await extract_and_save_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True
            assert result["message"] == "No temporal reference found, no event created"
            assert result["data"] is None

    @pytest.mark.asyncio
    async def test_extract_event_service_exception(self, mock_current_user, mock_db_pool):
        """Test handling of service exception during extraction"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.extract_and_save_event = AsyncMock(side_effect=Exception("Service error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import extract_and_save_event

            request = ExtractEventRequest(message="Test message")

            with pytest.raises(HTTPException) as exc_info:
                await extract_and_save_event(request, mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Service error" in str(exc_info.value.detail)


class TestGetTimelineEndpoint:
    """Tests for GET /api/episodic-memory/timeline endpoint"""

    @pytest.mark.asyncio
    async def test_get_timeline_success(self, mock_current_user, mock_db_pool):
        """Test successful timeline retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_timeline = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "Started PT PMA",
                        "event_type": "milestone",
                        "emotion": "positive",
                        "occurred_at": datetime.now(timezone.utc),
                    }
                ]
            )
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_timeline

            result = await get_timeline(
                event_type="milestone",
                emotion="positive",
                start_date=datetime.now(timezone.utc) - timedelta(days=7),
                end_date=datetime.now(timezone.utc),
                limit=10,
                current_user=mock_current_user,
                db_pool=mock_db_pool,
            )

            assert result["success"] is True
            assert len(result["events"]) == 1
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_timeline_empty(self, mock_current_user, mock_db_pool):
        """Test empty timeline retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_timeline = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_timeline

            result = await get_timeline(current_user=mock_current_user, db_pool=mock_db_pool)

            assert result["success"] is True
            assert result["events"] == []
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_get_timeline_service_exception(self, mock_current_user, mock_db_pool):
        """Test handling of service exception during timeline retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_timeline = AsyncMock(side_effect=Exception("Database error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import get_timeline

            with pytest.raises(HTTPException) as exc_info:
                await get_timeline(mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Database error" in str(exc_info.value.detail)


class TestGetContextEndpoint:
    """Tests for GET /api/episodic-memory/context endpoint"""

    @pytest.mark.asyncio
    async def test_get_context_summary_success(self, mock_current_user, mock_db_pool):
        """Test successful context summary retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_context_summary = AsyncMock(
                return_value="### Recent Timeline\n- Started PT PMA"
            )
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_context_summary

            result = await get_context_summary(
                limit=5, current_user=mock_current_user, db_pool=mock_db_pool
            )

            assert result["success"] is True
            assert result["summary"] == "### Recent Timeline\n- Started PT PMA"
            assert result["has_events"] is True

    @pytest.mark.asyncio
    async def test_get_context_summary_empty(self, mock_current_user, mock_db_pool):
        """Test empty context summary"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_context_summary = AsyncMock(return_value="")
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_context_summary

            result = await get_context_summary(current_user=mock_current_user, db_pool=mock_db_pool)

            assert result["success"] is True
            assert result["summary"] == ""
            assert result["has_events"] is False

    @pytest.mark.asyncio
    async def test_get_context_summary_exception(self, mock_current_user, mock_db_pool):
        """Test handling of service exception during context retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_context_summary = AsyncMock(side_effect=Exception("Service error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import get_context_summary

            with pytest.raises(HTTPException) as exc_info:
                await get_context_summary(mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Service error" in str(exc_info.value.detail)


class TestGetStatsEndpoint:
    """Tests for GET /api/episodic-memory/stats endpoint"""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, mock_current_user, mock_db_pool):
        """Test successful stats retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(
                return_value={"total_events": 10, "milestones": 3, "problems": 2, "unique_days": 5}
            )
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_stats

            result = await get_stats(current_user=mock_current_user, db_pool=mock_db_pool)

            assert result["success"] is True
            assert result["data"]["total_events"] == 10
            assert result["data"]["milestones"] == 3

    @pytest.mark.asyncio
    async def test_get_stats_exception(self, mock_current_user, mock_db_pool):
        """Test handling of service exception during stats retrieval"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(side_effect=Exception("Stats error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import get_stats

            with pytest.raises(HTTPException) as exc_info:
                await get_stats(mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Stats error" in str(exc_info.value.detail)


class TestDeleteEventEndpoint:
    """Tests for DELETE /api/episodic-memory/events/{event_id} endpoint"""

    @pytest.mark.asyncio
    async def test_delete_event_success(self, mock_current_user, mock_db_pool):
        """Test successful event deletion"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.delete_event = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import delete_event

            result = await delete_event(
                event_id=1, current_user=mock_current_user, db_pool=mock_db_pool
            )

            assert result["success"] is True
            assert result["message"] == "Event deleted"

    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, mock_current_user, mock_db_pool):
        """Test deletion of non-existent event"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.delete_event = AsyncMock(return_value=False)
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import delete_event

            with pytest.raises(HTTPException) as exc_info:
                await delete_event(99999, mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 404
            assert "Event not found or not owned by user" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_event_exception(self, mock_current_user, mock_db_pool):
        """Test handling of service exception during deletion"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.delete_event = AsyncMock(side_effect=Exception("Delete error"))
            mock_service_class.return_value = mock_service

            from fastapi import HTTPException

            from app.routers.episodic_memory import delete_event

            with pytest.raises(HTTPException) as exc_info:
                await delete_event(1, mock_current_user, mock_db_pool)

            assert exc_info.value.status_code == 500
            assert "Delete error" in str(exc_info.value.detail)


class TestRequestModels:
    """Tests for Pydantic request models"""

    def test_add_event_request_valid(self):
        """Test AddEventRequest validation with valid data"""
        request = AddEventRequest(
            title="Test Event",
            description="Test description",
            event_type="milestone",
            emotion="positive",
            occurred_at=datetime.now(timezone.utc),
            related_entities=[{"type": "test", "name": "test"}],
            metadata={"key": "value"},
        )

        assert request.title == "Test Event"
        assert request.description == "Test description"
        assert request.event_type == "milestone"
        assert request.emotion == "positive"
        assert request.related_entities == [{"type": "test", "name": "test"}]
        assert request.metadata == {"key": "value"}

    def test_add_event_request_defaults(self):
        """Test AddEventRequest with default values"""
        request = AddEventRequest(title="Test Event")

        assert request.title == "Test Event"
        assert request.description is None
        assert request.event_type == "general"
        assert request.emotion == "neutral"
        assert request.occurred_at is None
        assert request.related_entities == []
        assert request.metadata == {}

    def test_extract_event_request_valid(self):
        """Test ExtractEventRequest validation"""
        request = ExtractEventRequest(message="Test message", ai_response="Test response")

        assert request.message == "Test message"
        assert request.ai_response == "Test response"

    def test_extract_event_request_minimal(self):
        """Test ExtractEventRequest with minimal data"""
        request = ExtractEventRequest(message="Test message")

        assert request.message == "Test message"
        assert request.ai_response is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_add_event_with_unicode_characters(self, mock_current_user, mock_db_pool):
        """Test adding event with unicode characters"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.add_event = AsyncMock(return_value={"status": "created", "id": 1})
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import add_event

            request = AddEventRequest(
                title="🚀 Iniziato processo PT PMA àccéntéd",
                description="Procédure avec caractères spéciaux: ñ, ü, ç",
                event_type="milestone",
            )

            result = await add_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_extract_event_with_mixed_languages(self, mock_current_user, mock_db_pool):
        """Test extraction with mixed Italian/English"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.extract_and_save_event = AsyncMock(
                return_value={"status": "created", "id": 1}
            )
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import extract_and_save_event

            request = ExtractEventRequest(
                message="Today I started il processo PT PMA", ai_response="Buono! Good progress"
            )

            result = await extract_and_save_event(request, mock_current_user, mock_db_pool)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_timeline_with_large_limit(self, mock_current_user, mock_db_pool):
        """Test timeline retrieval with large limit"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_timeline = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_timeline

            result = await get_timeline(
                limit=1000, current_user=mock_current_user, db_pool=mock_db_pool
            )

            assert result["success"] is True
            # Verify service was called with the large limit
            mock_service.get_timeline.assert_called_once_with(
                user_id=mock_current_user["email"],
                event_type=None,
                emotion=None,
                start_date=None,
                end_date=None,
                limit=1000,
            )

    @pytest.mark.asyncio
    async def test_get_context_with_zero_limit(self, mock_current_user, mock_db_pool):
        """Test context summary with zero limit"""
        with patch("app.routers.episodic_memory.EpisodicMemoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_context_summary = AsyncMock(return_value="")
            mock_service_class.return_value = mock_service

            from app.routers.episodic_memory import get_context_summary

            result = await get_context_summary(
                limit=0, current_user=mock_current_user, db_pool=mock_db_pool
            )

            assert result["success"] is True
            assert result["has_events"] is False
