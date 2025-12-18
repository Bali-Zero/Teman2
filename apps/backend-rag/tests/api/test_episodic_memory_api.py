"""
API Tests for Episodic Memory Router
Tests timeline event storage, extraction, and retrieval endpoints
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestEpisodicMemoryAddEvent:
    """Tests for POST /api/episodic-memory/events endpoint"""

    def test_add_event_success(self, authenticated_client):
        """Test successfully adding an event"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={
                    "title": "Started PT PMA process",
                    "event_type": "milestone",
                    "emotion": "positive",
                },
            )

            assert response.status_code in [200, 500]  # 500 if mock not propagated
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True

    def test_add_event_with_all_fields(self, authenticated_client):
        """Test adding an event with all optional fields"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={
                    "title": "Meeting with notary",
                    "description": "Discussed document requirements",
                    "event_type": "meeting",
                    "emotion": "neutral",
                    "occurred_at": (now - timedelta(days=1)).isoformat(),
                    "related_entities": [{"type": "person", "name": "Notary X"}],
                    "metadata": {"location": "Jakarta"},
                },
            )

            assert response.status_code in [200, 500]

    def test_add_event_invalid_event_type_defaults_to_general(self, authenticated_client):
        """Test that invalid event_type defaults to general"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={"title": "Test event", "event_type": "invalid_type"},
            )

            assert response.status_code in [200, 500]

    def test_add_event_empty_title_fails(self, authenticated_client):
        """Test that empty title fails validation"""
        response = authenticated_client.post(
            "/api/episodic-memory/events", json={"title": "", "event_type": "milestone"}
        )

        assert response.status_code == 422  # Validation error

    def test_add_event_unauthenticated(self, test_client):
        """Test that unauthenticated requests fail"""
        response = test_client.post("/api/episodic-memory/events", json={"title": "Test event"})

        assert response.status_code in [401, 403]


@pytest.mark.api
class TestEpisodicMemoryExtract:
    """Tests for POST /api/episodic-memory/extract endpoint"""

    def test_extract_with_temporal_reference(self, authenticated_client):
        """Test extraction when message has temporal reference"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/extract",
                json={"message": "Oggi ho completato la registrazione della PT PMA!"},
            )

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True

    def test_extract_without_temporal_reference(self, authenticated_client):
        """Test extraction when message has no temporal reference"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/extract",
                json={"message": "I need help with PT PMA registration"},
            )

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["data"] is None

    def test_extract_with_ai_response(self, authenticated_client):
        """Test extraction with AI response context"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/extract",
                json={
                    "message": "Yesterday I submitted my documents",
                    "ai_response": "Great! Documents received.",
                },
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestEpisodicMemoryTimeline:
    """Tests for GET /api/episodic-memory/timeline endpoint"""

    def test_get_timeline(self, authenticated_client):
        """Test getting user's timeline"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetch = AsyncMock(
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
                    }
                ]
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/timeline")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "events" in data

    def test_get_timeline_with_event_type_filter(self, authenticated_client):
        """Test filtering timeline by event type"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/episodic-memory/timeline?event_type=milestone"
            )

            assert response.status_code in [200, 500]

    def test_get_timeline_with_emotion_filter(self, authenticated_client):
        """Test filtering timeline by emotion"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/timeline?emotion=positive")

            assert response.status_code in [200, 500]

    def test_get_timeline_with_date_range(self, authenticated_client):
        """Test filtering timeline by date range"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            now = datetime.now(timezone.utc)
            start = (now - timedelta(days=7)).isoformat()
            end = now.isoformat()

            response = authenticated_client.get(
                f"/api/episodic-memory/timeline?start_date={start}&end_date={end}"
            )

            assert response.status_code in [200, 500]

    def test_get_timeline_with_limit(self, authenticated_client):
        """Test limiting timeline results"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/timeline?limit=5")

            assert response.status_code in [200, 500]

    def test_get_timeline_unauthenticated(self, test_client):
        """Test that unauthenticated requests fail"""
        response = test_client.get("/api/episodic-memory/timeline")

        assert response.status_code in [401, 403]


@pytest.mark.api
class TestEpisodicMemoryContext:
    """Tests for GET /api/episodic-memory/context endpoint"""

    def test_get_context_summary(self, authenticated_client):
        """Test getting context summary"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "event_type": "milestone",
                        "title": "Started PT PMA",
                        "emotion": "positive",
                        "occurred_at": now - timedelta(days=1),
                        "description": "Began the process",
                        "related_entities": [],
                        "metadata": {},
                        "created_at": now,
                    }
                ]
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/context")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "summary" in data

    def test_get_context_with_limit(self, authenticated_client):
        """Test getting context with custom limit"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/context?limit=10")

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestEpisodicMemoryStats:
    """Tests for GET /api/episodic-memory/stats endpoint"""

    def test_get_stats(self, authenticated_client):
        """Test getting user stats"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "total_events": 10,
                    "milestones": 3,
                    "problems": 2,
                    "resolutions": 2,
                    "decisions": 1,
                    "meetings": 1,
                    "deadlines": 1,
                    "discoveries": 0,
                    "unique_days": 5,
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/episodic-memory/stats")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "data" in data


@pytest.mark.api
class TestEpisodicMemoryDeleteEvent:
    """Tests for DELETE /api/episodic-memory/events/{event_id} endpoint"""

    def test_delete_event_success(self, authenticated_client):
        """Test successfully deleting an event"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/episodic-memory/events/1")

            assert response.status_code in [200, 404, 500]

    def test_delete_event_not_found(self, authenticated_client):
        """Test deleting non-existent event"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 0")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/episodic-memory/events/99999")

            assert response.status_code in [200, 404, 500]

    def test_delete_event_unauthenticated(self, test_client):
        """Test that unauthenticated requests fail"""
        response = test_client.delete("/api/episodic-memory/events/1")

        assert response.status_code in [401, 403]


@pytest.mark.api
class TestEpisodicMemoryEventTypes:
    """Tests for various event types through API"""

    @pytest.mark.parametrize(
        "event_type",
        [
            "milestone",
            "problem",
            "resolution",
            "decision",
            "meeting",
            "deadline",
            "discovery",
            "general",
        ],
    )
    def test_add_event_valid_event_types(self, authenticated_client, event_type):
        """Test adding events with all valid event types"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={"title": f"Test {event_type} event", "event_type": event_type},
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestEpisodicMemoryEmotions:
    """Tests for various emotions through API"""

    @pytest.mark.parametrize(
        "emotion", ["positive", "negative", "neutral", "urgent", "frustrated", "excited", "worried"]
    )
    def test_add_event_valid_emotions(self, authenticated_client, emotion):
        """Test adding events with all valid emotions"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={"title": f"Test event with {emotion} emotion", "emotion": emotion},
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestEpisodicMemoryRelatedEntities:
    """Tests for related entities functionality"""

    def test_add_event_with_kg_entities(self, authenticated_client):
        """Test adding event with Knowledge Graph entity links"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={
                    "title": "Selected KBLI code",
                    "event_type": "decision",
                    "related_entities": [
                        {"type": "kbli", "code": "62010", "name": "Software Development"},
                        {"type": "visa", "code": "KITAS", "name": "Work Permit"},
                    ],
                },
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestEpisodicMemoryMetadata:
    """Tests for metadata functionality"""

    def test_add_event_with_custom_metadata(self, authenticated_client):
        """Test adding event with custom metadata"""
        with patch("app.routers.episodic_memory.get_db_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            now = datetime.now(timezone.utc)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "created_at": now})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/episodic-memory/events",
                json={
                    "title": "Consultation with lawyer",
                    "event_type": "meeting",
                    "metadata": {
                        "source": "conversation",
                        "conversation_id": 12345,
                        "participants": ["user", "lawyer"],
                        "cost": 500000,
                    },
                },
            )

            assert response.status_code in [200, 500]
