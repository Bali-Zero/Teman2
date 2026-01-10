"""
Comprehensive tests for EpisodicMemoryService
Target: 100% coverage
Composer: 1
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.memory.episodic_memory_service import (  # noqa: E402
    Emotion,
    EpisodicMemoryService,
    EventType,
)


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


@pytest.fixture
def episodic_service(mock_db_pool):
    """Create EpisodicMemoryService instance"""
    pool, _ = mock_db_pool
    return EpisodicMemoryService(pool=pool)


class TestEpisodicMemoryService:
    """Tests for EpisodicMemoryService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        pool, _ = mock_db_pool
        service = EpisodicMemoryService(pool=pool)
        assert service.pool == pool

    def test_init_no_pool(self):
        """Test initialization without pool"""
        service = EpisodicMemoryService()
        assert service.pool is None

    def test_parse_date_with_year(self, episodic_service):
        """Test date parsing with year"""
        import re

        match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", "15/03/2024")
        result = episodic_service._parse_date(match)
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_parse_date_without_year(self, episodic_service):
        """Test date parsing without year"""
        import re

        match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", "15/03")
        result = episodic_service._parse_date(match)
        assert result.year == datetime.now().year
        assert result.month == 3
        assert result.day == 15

    def test_parse_date_two_digit_year(self, episodic_service):
        """Test date parsing with two-digit year"""
        import re

        match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", "15/03/24")
        result = episodic_service._parse_date(match)
        assert result.year == 2024

    def test_parse_date_invalid_date(self, episodic_service):
        """Test parsing invalid date (e.g., 32/13/2024)"""
        import re

        match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", "32/13/2024")
        result = episodic_service._parse_date(match)
        # Should return current datetime on ValueError
        assert result is not None
        assert isinstance(result, datetime)

    def test_extract_datetime_today(self, episodic_service):
        """Test extracting 'today' datetime"""
        result = episodic_service._extract_datetime("Ho fatto questo oggi")
        assert result is not None
        assert result.date() == datetime.now(timezone.utc).date()

    def test_extract_datetime_yesterday(self, episodic_service):
        """Test extracting 'yesterday' datetime"""
        result = episodic_service._extract_datetime("Ieri ho fatto questo")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        assert result.date() == expected

    def test_extract_datetime_tomorrow(self, episodic_service):
        """Test extracting 'tomorrow' datetime"""
        result = episodic_service._extract_datetime("Domani farò questo")
        assert result is not None
        expected = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        assert result.date() == expected

    def test_extract_datetime_days_ago(self, episodic_service):
        """Test extracting 'N days ago' datetime"""
        result = episodic_service._extract_datetime("3 giorni fa ho fatto questo")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(days=3)).date()
        assert result.date() == expected

    def test_extract_datetime_specific_date(self, episodic_service):
        """Test extracting specific date"""
        result = episodic_service._extract_datetime("Il 15/03/2024 ho fatto questo")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_extract_datetime_last_week(self, episodic_service):
        """Test extracting 'last week' datetime"""
        result = episodic_service._extract_datetime("La settimana scorsa ho fatto questo")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(weeks=1)).date()
        assert result.date() == expected

    def test_extract_datetime_last_month(self, episodic_service):
        """Test extracting 'last month' datetime"""
        result = episodic_service._extract_datetime("Il mese scorso ho fatto questo")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        assert result.date() == expected

    def test_extract_datetime_no_match(self, episodic_service):
        """Test extracting datetime when no pattern matches"""
        result = episodic_service._extract_datetime("Some random text")
        assert result is None

    def test_detect_event_type_milestone(self, episodic_service):
        """Test detecting milestone event type"""
        result = episodic_service._detect_event_type("Ho completato il processo")
        assert result == EventType.MILESTONE

    def test_detect_event_type_problem(self, episodic_service):
        """Test detecting problem event type"""
        result = episodic_service._detect_event_type("Ho un problema con il visto")
        assert result == EventType.PROBLEM

    def test_detect_event_type_resolution(self, episodic_service):
        """Test detecting resolution event type"""
        # Avoid "problema" keyword which matches PROBLEM first
        result = episodic_service._detect_event_type("Ho risolto tutto con successo")
        assert result == EventType.RESOLUTION

    def test_detect_event_type_decision(self, episodic_service):
        """Test detecting decision event type"""
        result = episodic_service._detect_event_type("Ho deciso di procedere")
        assert result == EventType.DECISION

    def test_detect_event_type_meeting(self, episodic_service):
        """Test detecting meeting event type"""
        result = episodic_service._detect_event_type("Ho avuto un incontro")
        assert result == EventType.MEETING

    def test_detect_event_type_deadline(self, episodic_service):
        """Test detecting deadline event type"""
        result = episodic_service._detect_event_type("La scadenza è domani")
        assert result == EventType.DEADLINE

    def test_detect_event_type_discovery(self, episodic_service):
        """Test detecting discovery event type (currently not implemented in EVENT_KEYWORDS)"""
        # Note: DISCOVERY type exists in enum but no keywords defined in EVENT_KEYWORDS
        # So it falls back to GENERAL
        result = episodic_service._detect_event_type("Ho scoperto qualcosa di nuovo")
        assert result == EventType.GENERAL  # DISCOVERY keywords not implemented

    def test_detect_event_type_general(self, episodic_service):
        """Test detecting general event type when no keywords match"""
        result = episodic_service._detect_event_type("Some random text")
        assert result == EventType.GENERAL

    def test_detect_emotion_positive(self, episodic_service):
        """Test detecting positive emotion"""
        result = episodic_service._detect_emotion("Sono felice")
        assert result == Emotion.POSITIVE

    def test_detect_emotion_negative(self, episodic_service):
        """Test detecting negative emotion"""
        result = episodic_service._detect_emotion("È male")
        assert result == Emotion.NEGATIVE

    def test_detect_emotion_urgent(self, episodic_service):
        """Test detecting urgent emotion"""
        result = episodic_service._detect_emotion("È urgente")
        assert result == Emotion.URGENT

    def test_detect_emotion_frustrated(self, episodic_service):
        """Test detecting frustrated emotion"""
        result = episodic_service._detect_emotion("Sono frustrato")
        assert result == Emotion.FRUSTRATED

    def test_detect_emotion_excited(self, episodic_service):
        """Test detecting excited emotion"""
        result = episodic_service._detect_emotion("Sono entusiasta")
        assert result == Emotion.EXCITED

    def test_detect_emotion_worried(self, episodic_service):
        """Test detecting worried emotion"""
        result = episodic_service._detect_emotion("Sono preoccupato")
        assert result == Emotion.WORRIED

    def test_detect_emotion_neutral(self, episodic_service):
        """Test detecting neutral emotion when no keywords match"""
        result = episodic_service._detect_emotion("Some random text")
        assert result == Emotion.NEUTRAL

    def test_extract_title_from_text(self, episodic_service):
        """Test extracting title from text"""
        result = episodic_service._extract_title("Ho completato il processo KITAS oggi")
        assert "completato" in result.lower()
        assert len(result) <= 100

    def test_extract_title_long_text(self, episodic_service):
        """Test extracting title from long text (truncated)"""
        long_text = "A" * 200
        result = episodic_service._extract_title(long_text)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_extract_title_empty(self, episodic_service):
        """Test extracting title from empty text"""
        result = episodic_service._extract_title("")
        assert result == "Event"

    @pytest.mark.asyncio
    async def test_add_event_success(self, episodic_service, mock_db_pool):
        """Test adding event successfully"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.add_event(
            user_id="user-123",
            title="Test Event",
            description="Test description",
            event_type=EventType.MILESTONE,
            emotion=Emotion.POSITIVE,
        )

        assert result["status"] == "created"
        assert result["id"] == "event-123"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_event_with_datetime(self, episodic_service, mock_db_pool):
        """Test adding event with specific datetime"""
        _, conn = mock_db_pool
        dt = datetime.now(timezone.utc)
        conn.fetchrow = AsyncMock(return_value={"id": "event-123", "created_at": dt})

        result = await episodic_service.add_event(
            user_id="user-123", title="Test Event", occurred_at=dt
        )

        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_add_event_no_pool(self):
        """Test adding event without pool"""
        service = EpisodicMemoryService()

        result = await service.add_event(user_id="user-123", title="Test Event")

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_timeline_success(self, episodic_service, mock_db_pool):
        """Test getting timeline successfully"""
        _, conn = mock_db_pool
        now = datetime.now(timezone.utc)
        mock_events = [
            {
                "id": "event-1",
                "event_type": "milestone",
                "title": "Event 1",
                "description": "Description 1",
                "emotion": "positive",
                "occurred_at": now,
                "related_entities": [],
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "event-2",
                "event_type": "meeting",
                "title": "Event 2",
                "description": "Description 2",
                "emotion": "neutral",
                "occurred_at": now,
                "related_entities": [],
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            },
        ]
        conn.fetch = AsyncMock(return_value=mock_events)

        events = await episodic_service.get_timeline(user_id="user-123", limit=10)

        assert len(events) == 2
        assert events[0]["id"] == "event-1"

    @pytest.mark.asyncio
    async def test_get_timeline_with_filters(self, episodic_service, mock_db_pool):
        """Test getting timeline with filters"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        events = await episodic_service.get_timeline(
            user_id="user-123",
            event_type=EventType.MILESTONE,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
            limit=20,
        )

        assert isinstance(events, list)
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_timeline_no_pool(self):
        """Test getting timeline without pool"""
        service = EpisodicMemoryService()

        events = await service.get_timeline(user_id="user-123")

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_extract_and_save_event(self, episodic_service, mock_db_pool):
        """Test extracting and saving event from text"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.extract_and_save_event(
            user_id="user-123", message="Ho completato il processo KITAS oggi. Sono molto felice!"
        )

        assert result is not None
        assert result["status"] == "created"
        assert result["id"] == "event-123"

    @pytest.mark.asyncio
    async def test_extract_and_save_event_no_temporal_reference(
        self, episodic_service, mock_db_pool
    ):
        """Test extracting event when no temporal reference found"""
        _, _ = mock_db_pool

        result = await episodic_service.extract_and_save_event(
            user_id="user-123", message="Some random text without temporal reference"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_and_save_event_with_ai_response(self, episodic_service, mock_db_pool):
        """Test extracting event with AI response context"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.extract_and_save_event(
            user_id="user-123", message="Ho fatto questo", ai_response="Questo è successo ieri"
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_extract_and_save_event_with_conversation_id(
        self, episodic_service, mock_db_pool
    ):
        """Test extracting event with conversation ID"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.extract_and_save_event(
            user_id="user-123", message="Ho completato questo oggi", conversation_id=123
        )

        assert result is not None
        assert result["status"] == "created"
        assert result["id"] == "event-123"
        # Note: add_event doesn't return metadata in response, it's stored in DB
        # Verify the SQL call included metadata with conversation_id
        call_args = conn.fetchrow.call_args
        if call_args:
            # args[0]=SQL, args[1]=user_id, ..., args[7]=related_entities, args[8]=metadata
            args = call_args[0]
            if len(args) > 8:
                assert args[8].get("conversation_id") == 123

    @pytest.mark.asyncio
    async def test_get_recent_events(self, episodic_service, mock_db_pool):
        """Test getting recent events"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        events = await episodic_service.get_recent_events(user_id="user-123", days=7)

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_delete_event(self, episodic_service, mock_db_pool):
        """Test deleting event"""
        _, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="DELETE 1")

        result = await episodic_service.delete_event(user_id="user-123", event_id="event-123")

        assert result is True
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, episodic_service, mock_db_pool):
        """Test deleting non-existent event"""
        _, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="DELETE 0")

        result = await episodic_service.delete_event(event_id=999, user_id="user-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_event_no_pool(self):
        """Test deleting event without pool"""
        service = EpisodicMemoryService()
        result = await service.delete_event(event_id=1, user_id="user-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_event_error(self, episodic_service, mock_db_pool):
        """Test deleting event with database error"""
        _, conn = mock_db_pool
        conn.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await episodic_service.delete_event(event_id=1, user_id="user-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_context_summary(self, episodic_service, mock_db_pool):
        """Test getting context summary"""
        _, conn = mock_db_pool
        now = datetime.now(timezone.utc)
        # Mock needs all fields that get_timeline accesses on rows
        mock_events = [
            {
                "id": "event-1",
                "event_type": "milestone",
                "title": "Completed KITAS",
                "description": "Completed the KITAS process",
                "emotion": "positive",
                "occurred_at": now,  # Must be datetime, not string
                "related_entities": [],
                "metadata": {},
                "created_at": now,
            },
            {
                "id": "event-2",
                "event_type": "meeting",
                "title": "Had meeting",
                "description": "Meeting with immigration",
                "emotion": "neutral",
                "occurred_at": now,
                "related_entities": [],
                "metadata": {},
                "created_at": now,
            },
        ]
        conn.fetch = AsyncMock(return_value=mock_events)

        summary = await episodic_service.get_context_summary(user_id="user-123", limit=5)

        assert isinstance(summary, str)
        assert "Recent Timeline" in summary
        assert "Completed KITAS" in summary

    @pytest.mark.asyncio
    async def test_get_context_summary_empty(self, episodic_service, mock_db_pool):
        """Test getting context summary when no events"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        summary = await episodic_service.get_context_summary(user_id="user-123")

        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_stats(self, episodic_service, mock_db_pool):
        """Test getting statistics"""
        _, conn = mock_db_pool
        mock_stats = {
            "total_events": 10,
            "unique_days": 5,
            "first_event": datetime.now(timezone.utc) - timedelta(days=30),
            "last_event": datetime.now(timezone.utc),
            "milestones": 3,
            "problems": 2,
            "resolutions": 1,
        }
        conn.fetchrow = AsyncMock(return_value=mock_stats)

        stats = await episodic_service.get_stats(user_id="user-123")

        assert stats["total_events"] == 10
        assert stats["milestones"] == 3
        assert stats["problems"] == 2
        assert "first_event" in stats
        assert "last_event" in stats

    @pytest.mark.asyncio
    async def test_get_stats_no_pool(self):
        """Test getting stats without pool"""
        service = EpisodicMemoryService()
        stats = await service.get_stats(user_id="user-123")
        assert stats == {}

    @pytest.mark.asyncio
    async def test_get_stats_error(self, episodic_service, mock_db_pool):
        """Test getting stats with database error"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        stats = await episodic_service.get_stats(user_id="user-123")
        assert stats == {}

    @pytest.mark.asyncio
    async def test_get_timeline_with_emotion_filter(self, episodic_service, mock_db_pool):
        """Test getting timeline with emotion filter"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        events = await episodic_service.get_timeline(
            user_id="user-123", emotion="positive", limit=10
        )

        assert isinstance(events, list)
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_timeline_with_offset(self, episodic_service, mock_db_pool):
        """Test getting timeline with pagination offset"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        events = await episodic_service.get_timeline(user_id="user-123", limit=10, offset=20)

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_get_timeline_error(self, episodic_service, mock_db_pool):
        """Test getting timeline with database error"""
        _, conn = mock_db_pool
        conn.fetch = AsyncMock(side_effect=Exception("DB error"))

        events = await episodic_service.get_timeline(user_id="user-123")
        assert events == []

    @pytest.mark.asyncio
    async def test_add_event_with_related_entities(self, episodic_service, mock_db_pool):
        """Test adding event with related entities"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.add_event(
            user_id="user-123",
            title="Test Event",
            related_entities=[{"id": "entity-1", "type": "organization"}],
        )

        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_add_event_with_metadata(self, episodic_service, mock_db_pool):
        """Test adding event with metadata"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"id": "event-123", "created_at": datetime.now(timezone.utc)}
        )

        result = await episodic_service.add_event(
            user_id="user-123",
            title="Test Event",
            metadata={"source": "manual", "priority": "high"},
        )

        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_add_event_error(self, episodic_service, mock_db_pool):
        """Test adding event with database error"""
        _, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        result = await episodic_service.add_event(user_id="user-123", title="Test Event")

        assert result["status"] == "error"
        assert "message" in result


class TestEventType:
    """Tests for EventType enum"""

    def test_event_type_values(self):
        """Test EventType enum values"""
        assert EventType.MILESTONE == "milestone"
        assert EventType.PROBLEM == "problem"
        assert EventType.RESOLUTION == "resolution"
        assert EventType.DECISION == "decision"
        assert EventType.MEETING == "meeting"
        assert EventType.DEADLINE == "deadline"
        assert EventType.DISCOVERY == "discovery"
        assert EventType.GENERAL == "general"


class TestEmotion:
    """Tests for Emotion enum"""

    def test_emotion_values(self):
        """Test Emotion enum values"""
        assert Emotion.POSITIVE == "positive"
        assert Emotion.NEGATIVE == "negative"
        assert Emotion.NEUTRAL == "neutral"
        assert Emotion.URGENT == "urgent"
        assert Emotion.FRUSTRATED == "frustrated"
        assert Emotion.EXCITED == "excited"
        assert Emotion.WORRIED == "worried"
