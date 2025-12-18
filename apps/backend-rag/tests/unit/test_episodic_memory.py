"""
Unit tests for Episodic Memory Service
Tests timeline event storage, extraction, and retrieval
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.episodic_memory_service import (
    Emotion,
    EpisodicMemoryService,
    EventType,
)


class TestTemporalPatterns:
    """Tests for temporal pattern extraction"""

    def setup_method(self):
        self.service = EpisodicMemoryService(pool=None)

    def test_extract_today(self):
        """Test extraction of 'today' pattern"""
        result = self.service._extract_datetime("Ho iniziato oggi il processo")
        assert result is not None
        assert result.date() == datetime.now(timezone.utc).date()

    def test_extract_yesterday(self):
        """Test extraction of 'yesterday' pattern"""
        result = self.service._extract_datetime("Yesterday I submitted the documents")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        assert result.date() == expected

    def test_extract_days_ago(self):
        """Test extraction of 'N days ago' pattern"""
        result = self.service._extract_datetime("3 giorni fa ho ricevuto la risposta")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(days=3)).date()
        assert result.date() == expected

    def test_extract_last_week(self):
        """Test extraction of 'last week' pattern"""
        result = self.service._extract_datetime("La settimana scorsa ho incontrato il notaio")
        assert result is not None
        expected = (datetime.now(timezone.utc) - timedelta(weeks=1)).date()
        assert result.date() == expected

    def test_extract_specific_date(self):
        """Test extraction of DD/MM date format"""
        result = self.service._extract_datetime("Il 15/12 ho firmato il contratto")
        assert result is not None
        assert result.day == 15
        assert result.month == 12

    def test_extract_specific_date_with_year(self):
        """Test extraction of DD/MM/YYYY date format"""
        result = self.service._extract_datetime("On 20/01/2025 the deadline expires")
        assert result is not None
        assert result.day == 20
        assert result.month == 1
        assert result.year == 2025

    def test_no_temporal_reference(self):
        """Test that messages without temporal references return None"""
        result = self.service._extract_datetime("I need help with PT PMA registration")
        assert result is None


class TestEventTypeDetection:
    """Tests for event type classification"""

    def setup_method(self):
        self.service = EpisodicMemoryService(pool=None)

    def test_detect_milestone(self):
        """Test detection of milestone events"""
        result = self.service._detect_event_type("Ho completato la registrazione")
        assert result == EventType.MILESTONE

    def test_detect_problem(self):
        """Test detection of problem events"""
        result = self.service._detect_event_type("There's a problem with the KBLI code")
        assert result == EventType.PROBLEM

    def test_detect_resolution(self):
        """Test detection of resolution events"""
        result = self.service._detect_event_type("Il problema e stato risolto")
        assert result == EventType.RESOLUTION

    def test_detect_decision(self):
        """Test detection of decision events"""
        result = self.service._detect_event_type("I decided to go with option B")
        assert result == EventType.DECISION

    def test_detect_meeting(self):
        """Test detection of meeting events"""
        result = self.service._detect_event_type("Ho avuto un meeting con il consulente")
        assert result == EventType.MEETING

    def test_detect_deadline(self):
        """Test detection of deadline events"""
        result = self.service._detect_event_type("La scadenza e entro il 31 dicembre")
        assert result == EventType.DEADLINE

    def test_default_general(self):
        """Test that unclassified events default to GENERAL"""
        result = self.service._detect_event_type("Some random text here")
        assert result == EventType.GENERAL


class TestEmotionDetection:
    """Tests for emotion detection"""

    def setup_method(self):
        self.service = EpisodicMemoryService(pool=None)

    def test_detect_positive(self):
        """Test detection of positive emotions"""
        result = self.service._detect_emotion("Sono molto contento del risultato")
        assert result == Emotion.POSITIVE

    def test_detect_negative(self):
        """Test detection of negative emotions"""
        result = self.service._detect_emotion("Purtroppo non ha funzionato")
        assert result == Emotion.NEGATIVE

    def test_detect_urgent(self):
        """Test detection of urgency"""
        result = self.service._detect_emotion("This is urgent, I need it asap")
        assert result == Emotion.URGENT

    def test_detect_frustrated(self):
        """Test detection of frustration"""
        result = self.service._detect_emotion("I'm frustrated with this process")
        assert result == Emotion.FRUSTRATED

    def test_default_neutral(self):
        """Test that unclassified emotions default to NEUTRAL"""
        result = self.service._detect_emotion("I submitted the documents")
        assert result == Emotion.NEUTRAL


class TestTitleExtraction:
    """Tests for title extraction from text"""

    def setup_method(self):
        self.service = EpisodicMemoryService(pool=None)

    def test_extract_title_removes_temporal(self):
        """Test that temporal expressions are removed from title"""
        result = self.service._extract_title("Oggi ho firmato il contratto PT PMA")
        assert "oggi" not in result.lower()
        assert "firmato" in result.lower()

    def test_extract_title_truncates(self):
        """Test that long titles are truncated"""
        long_text = "A" * 200
        result = self.service._extract_title(long_text, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")

    def test_extract_title_first_sentence(self):
        """Test that only first sentence is used"""
        result = self.service._extract_title("First sentence. Second sentence. Third.")
        assert "Second" not in result


class TestAddEvent:
    """Tests for adding events to database"""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": datetime.now(timezone.utc)})
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn)))
        return pool

    @pytest.mark.asyncio
    async def test_add_event_success(self, mock_pool):
        """Test successful event creation"""
        service = EpisodicMemoryService(pool=mock_pool)

        result = await service.add_event(
            user_id="test@example.com",
            title="Started PT PMA process",
            event_type=EventType.MILESTONE,
            emotion=Emotion.POSITIVE,
        )

        assert result["status"] == "created"
        assert result["id"] == 1
        assert result["title"] == "Started PT PMA process"

    @pytest.mark.asyncio
    async def test_add_event_no_pool(self):
        """Test graceful handling when no pool available"""
        service = EpisodicMemoryService(pool=None)

        result = await service.add_event(
            user_id="test@example.com",
            title="Test event",
        )

        assert result["status"] == "error"
        assert "not available" in result["message"]


class TestGetTimeline:
    """Tests for timeline retrieval"""

    @pytest.fixture
    def mock_pool_with_events(self):
        pool = MagicMock()
        conn = AsyncMock()
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "event_type": "milestone",
                    "title": "Started PT PMA",
                    "description": "Began the process",
                    "emotion": "positive",
                    "occurred_at": now - timedelta(days=1),
                    "related_entities": [],
                    "metadata": {},
                    "created_at": now,
                },
                {
                    "id": 2,
                    "event_type": "problem",
                    "title": "KBLI issue",
                    "description": "Wrong code selected",
                    "emotion": "frustrated",
                    "occurred_at": now - timedelta(days=3),
                    "related_entities": [],
                    "metadata": {},
                    "created_at": now,
                },
            ]
        )
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn)))
        return pool

    @pytest.mark.asyncio
    async def test_get_timeline(self, mock_pool_with_events):
        """Test retrieving user timeline"""
        service = EpisodicMemoryService(pool=mock_pool_with_events)

        events = await service.get_timeline(
            user_id="test@example.com",
            limit=10,
        )

        assert len(events) == 2
        assert events[0]["title"] == "Started PT PMA"
        assert events[1]["event_type"] == "problem"

    @pytest.mark.asyncio
    async def test_get_timeline_empty(self):
        """Test empty timeline when no pool"""
        service = EpisodicMemoryService(pool=None)

        events = await service.get_timeline(user_id="test@example.com")

        assert events == []


class TestExtractAndSave:
    """Tests for automatic event extraction from conversations"""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": datetime.now(timezone.utc)})
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn)))
        return pool

    @pytest.mark.asyncio
    async def test_extract_with_temporal_reference(self, mock_pool):
        """Test extraction when message has temporal reference"""
        service = EpisodicMemoryService(pool=mock_pool)

        result = await service.extract_and_save_event(
            user_id="test@example.com",
            message="Oggi ho completato la registrazione della PT PMA",
        )

        assert result is not None
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_no_extraction_without_temporal(self, mock_pool):
        """Test no extraction when message has no temporal reference"""
        service = EpisodicMemoryService(pool=mock_pool)

        result = await service.extract_and_save_event(
            user_id="test@example.com",
            message="I need help with PT PMA registration",
        )

        assert result is None


class TestContextSummary:
    """Tests for context summary generation"""

    @pytest.fixture
    def mock_pool_with_events(self):
        pool = MagicMock()
        conn = AsyncMock()
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "event_type": "milestone",
                    "title": "Started PT PMA",
                    "description": "Began the process",
                    "emotion": "positive",
                    "occurred_at": now - timedelta(days=1),
                    "related_entities": [],
                    "metadata": {},
                    "created_at": now,
                },
            ]
        )
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn)))
        return pool

    @pytest.mark.asyncio
    async def test_context_summary_format(self, mock_pool_with_events):
        """Test that context summary is properly formatted"""
        service = EpisodicMemoryService(pool=mock_pool_with_events)

        summary = await service.get_context_summary(
            user_id="test@example.com",
            limit=5,
        )

        assert "### Recent Timeline" in summary
        assert "Started PT PMA" in summary
        assert "positive" in summary


class TestMemoryContextIntegration:
    """Tests for MemoryContext with episodic memory"""

    def test_memory_context_with_timeline(self):
        """Test MemoryContext includes timeline summary"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            profile_facts=["User is Italian"],
            timeline_summary="### Recent Timeline\n- Started PT PMA",
            has_data=True,
        )

        prompt = context.to_system_prompt()

        assert "User Context" in prompt
        assert "Personal Memory" in prompt
        assert "Recent Timeline" in prompt
        assert "Started PT PMA" in prompt

    def test_memory_context_is_empty_with_timeline(self):
        """Test is_empty considers timeline"""
        from services.memory.models import MemoryContext

        # Only timeline, no other data
        context = MemoryContext(
            user_id="test@example.com",
            timeline_summary="### Recent Timeline\n- Event",
        )

        assert not context.is_empty()

    def test_memory_context_is_empty_without_data(self):
        """Test is_empty when truly empty"""
        from services.memory.models import MemoryContext

        context = MemoryContext(user_id="test@example.com")

        assert context.is_empty()
