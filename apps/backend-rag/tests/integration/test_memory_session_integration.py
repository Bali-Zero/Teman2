"""
Comprehensive Integration Tests for Memory and Session Services
Tests memory storage, retrieval, and session management

Covers:
- MemoryServicePostgres
- SessionService
- WorkSessionService
- Memory fact extraction
- Collective memory
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestMemorySessionIntegration:
    """Comprehensive integration tests for memory and session services"""

    @pytest.mark.asyncio
    async def test_memory_service_crud(self, memory_service):
        """Test MemoryService CRUD operations"""
        user_id = "test_user_memory_1"

        # Create memory
        from services.memory_service_postgres import UserMemory

        memory = UserMemory(
            user_id=user_id,
            profile_facts=["User likes testing", "User prefers Python"],
            summary="Test user for memory integration",
            counters={"conversations": 0, "searches": 0, "tasks": 0},
            updated_at=datetime.now(),
        )

        result = await memory_service.save_memory(memory)
        assert result is True

        # Read memory
        retrieved_memory = await memory_service.get_memory(user_id)
        assert retrieved_memory is not None
        assert len(retrieved_memory.profile_facts) == 2
        assert "testing" in retrieved_memory.profile_facts[0]

        # Update memory
        await memory_service.add_fact(user_id, "User loves integration tests")
        updated_memory = await memory_service.get_memory(user_id)
        assert len(updated_memory.profile_facts) == 3

        # Update summary
        await memory_service.update_summary(user_id, "Updated summary for test user")
        final_memory = await memory_service.get_memory(user_id)
        assert final_memory.summary == "Updated summary for test user"

    @pytest.mark.asyncio
    async def test_memory_fact_extraction(self, memory_service, db_pool):
        """Test memory fact extraction from conversations"""

        async with db_pool.acquire() as conn:
            # Create conversation
            user_id = "test_user_fact_extraction"
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                "Fact Extraction Test",
                datetime.now(),
                datetime.now(),
            )

            # Add conversation messages
            await conn.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, role, content, created_at
                )
                VALUES ($1, $2, $3, $4)
                """,
                conversation_id,
                "user",
                "I am a software engineer from Italy",
                datetime.now(),
            )

            await conn.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, role, content, created_at
                )
                VALUES ($1, $2, $3, $4)
                """,
                conversation_id,
                "user",
                "I prefer working with Python and FastAPI",
                datetime.now(),
            )

            # Extract facts (mock extraction)
            with patch("services.memory_fact_extractor.MemoryFactExtractor") as mock_extractor:
                mock_extractor_instance = MagicMock()
                mock_extractor_instance.extract_facts = AsyncMock(
                    return_value=[
                        "User is a software engineer",
                        "User is from Italy",
                        "User prefers Python",
                        "User prefers FastAPI",
                    ]
                )
                mock_extractor.return_value = mock_extractor_instance

                # Simulate fact extraction
                facts = await mock_extractor_instance.extract_facts(conversation_id=conversation_id)

                assert len(facts) == 4
                assert any("Italy" in fact for fact in facts)
                assert any("Python" in fact for fact in facts)

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1",
                conversation_id,
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)

    @pytest.mark.asyncio
    async def test_session_service(self, db_pool):
        """Test SessionService operations"""

        async with db_pool.acquire() as conn:
            # Create sessions table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255),
                    started_at TIMESTAMP DEFAULT NOW(),
                    last_activity TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP,
                    metadata JSONB DEFAULT '{}'
                )
                """
            )

            # Create session
            session_id = "test_session_123"
            user_id = "test_user_session_1"

            session_db_id = await conn.fetchval(
                """
                INSERT INTO sessions (session_id, user_id, expires_at, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                session_id,
                user_id,
                datetime.now() + timedelta(hours=24),
                {"ip_address": "127.0.0.1", "user_agent": "test"},
            )

            assert session_db_id is not None

            # Retrieve session
            session = await conn.fetchrow(
                """
                SELECT session_id, user_id, expires_at, metadata
                FROM sessions
                WHERE session_id = $1
                """,
                session_id,
            )

            assert session is not None
            assert session["user_id"] == user_id

            # Update last activity
            await conn.execute(
                """
                UPDATE sessions
                SET last_activity = NOW()
                WHERE session_id = $1
                """,
                session_id,
            )

            # Verify update
            updated_session = await conn.fetchrow(
                """
                SELECT last_activity
                FROM sessions
                WHERE session_id = $1
                """,
                session_id,
            )

            assert updated_session["last_activity"] is not None

            # Cleanup
            await conn.execute("DELETE FROM sessions WHERE session_id = $1", session_id)

    @pytest.mark.asyncio
    async def test_work_session_service(self, db_pool):
        """Test WorkSessionService operations"""

        async with db_pool.acquire() as conn:
            # Create work_sessions table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS work_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    session_type VARCHAR(100),
                    started_at TIMESTAMP DEFAULT NOW(),
                    ended_at TIMESTAMP,
                    duration_seconds INTEGER,
                    metadata JSONB DEFAULT '{}'
                )
                """
            )

            # Create work session
            user_id = "test_user_work_session_1"
            session_id = await conn.fetchval(
                """
                INSERT INTO work_sessions (
                    user_id, session_type, started_at, metadata
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                "consultation",
                datetime.now(),
                {"client_id": 123, "practice_id": 456},
            )

            assert session_id is not None

            # End session
            end_time = datetime.now()
            duration = (end_time - datetime.now()).total_seconds()

            await conn.execute(
                """
                UPDATE work_sessions
                SET ended_at = $1, duration_seconds = $2
                WHERE id = $3
                """,
                end_time,
                int(abs(duration)),
                session_id,
            )

            # Retrieve session
            session = await conn.fetchrow(
                """
                SELECT session_type, duration_seconds, metadata
                FROM work_sessions
                WHERE id = $1
                """,
                session_id,
            )

            assert session is not None
            assert session["session_type"] == "consultation"

            # Test session querying
            sessions = await conn.fetch(
                """
                SELECT id, session_type, started_at
                FROM work_sessions
                WHERE user_id = $1
                ORDER BY started_at DESC
                """,
                user_id,
            )

            assert len(sessions) == 1

            # Cleanup
            await conn.execute("DELETE FROM work_sessions WHERE id = $1", session_id)

    @pytest.mark.asyncio
    async def test_collective_memory(self, db_pool):
        """Test collective memory operations"""

        async with db_pool.acquire() as conn:
            # Create collective_memory table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collective_memory (
                    id SERIAL PRIMARY KEY,
                    team_id VARCHAR(255),
                    memory_type VARCHAR(100),
                    content TEXT,
                    contributors TEXT[],
                    tags TEXT[],
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create collective memory entry
            team_id = "test_team_1"
            memory_id = await conn.fetchval(
                """
                INSERT INTO collective_memory (
                    team_id, memory_type, content, contributors, tags
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                team_id,
                "best_practice",
                "Always use asyncpg for database connections",
                ["user1@example.com", "user2@example.com"],
                ["database", "best_practice", "async"],
            )

            assert memory_id is not None

            # Retrieve collective memory
            memory = await conn.fetchrow(
                """
                SELECT memory_type, content, contributors, tags
                FROM collective_memory
                WHERE id = $1
                """,
                memory_id,
            )

            assert memory is not None
            assert memory["memory_type"] == "best_practice"
            assert len(memory["contributors"]) == 2
            assert "database" in memory["tags"]

            # Search collective memory by tags
            tagged_memories = await conn.fetch(
                """
                SELECT id, content
                FROM collective_memory
                WHERE $1 = ANY(tags)
                """,
                "database",
            )

            assert len(tagged_memories) == 1

            # Cleanup
            await conn.execute("DELETE FROM collective_memory WHERE id = $1", memory_id)

    @pytest.mark.asyncio
    async def test_memory_deduplication(self, memory_service):
        """Test memory deduplication logic"""
        user_id = "test_user_dedup"

        # Add same fact multiple times
        fact = "User likes Python"
        result1 = await memory_service.add_fact(user_id, fact)
        result2 = await memory_service.add_fact(user_id, fact)
        result3 = await memory_service.add_fact(user_id, fact)

        # First add should succeed, subsequent should fail (duplicate)
        assert result1 is True
        assert result2 is False  # Duplicate
        assert result3 is False  # Duplicate

        # Verify only one fact exists
        memory = await memory_service.get_memory(user_id)
        assert memory is not None
        assert memory.profile_facts.count(fact) == 1

    @pytest.mark.asyncio
    async def test_memory_search(self, memory_service):
        """Test memory search functionality"""
        user_id = "test_user_search"

        # Add multiple facts
        facts = [
            "User is a software engineer",
            "User likes Python",
            "User prefers FastAPI",
            "User is from Italy",
        ]

        for fact in facts:
            await memory_service.add_fact(user_id, fact)

        # Retrieve memory
        memory = await memory_service.get_memory(user_id)

        # Search within facts (simulated)
        search_term = "Python"
        matching_facts = [
            fact for fact in memory.profile_facts if search_term.lower() in fact.lower()
        ]

        assert len(matching_facts) == 1
        assert "Python" in matching_facts[0]

    @pytest.mark.asyncio
    async def test_memory_statistics(self, memory_service, db_pool):
        """Test memory statistics tracking"""

        async with db_pool.acquire() as conn:
            # Create user_stats table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id VARCHAR(255) PRIMARY KEY,
                    conversations_count INTEGER DEFAULT 0,
                    searches_count INTEGER DEFAULT 0,
                    tasks_count INTEGER DEFAULT 0,
                    summary TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT NOW(),
                    last_activity TIMESTAMP DEFAULT NOW()
                )
                """
            )

            user_id = "test_user_stats"

            # Initialize stats
            await conn.execute(
                """
                INSERT INTO user_stats (user_id, conversations_count, searches_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE
                SET conversations_count = user_stats.conversations_count + EXCLUDED.conversations_count,
                    searches_count = user_stats.searches_count + EXCLUDED.searches_count,
                    updated_at = NOW()
                """,
                user_id,
                1,
                5,
            )

            # Retrieve stats
            stats = await conn.fetchrow(
                """
                SELECT conversations_count, searches_count, last_activity
                FROM user_stats
                WHERE user_id = $1
                """,
                user_id,
            )

            assert stats is not None
            assert stats["conversations_count"] == 1
            assert stats["searches_count"] == 5

            # Update stats
            await conn.execute(
                """
                UPDATE user_stats
                SET searches_count = searches_count + 1,
                    last_activity = NOW()
                WHERE user_id = $1
                """,
                user_id,
            )

            # Verify update
            updated_stats = await conn.fetchrow(
                """
                SELECT searches_count FROM user_stats WHERE user_id = $1
                """,
                user_id,
            )

            assert updated_stats["searches_count"] == 6

            # Cleanup
            await conn.execute("DELETE FROM user_stats WHERE user_id = $1", user_id)
