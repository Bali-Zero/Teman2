"""
Comprehensive Integration Tests for Collective Memory
Tests CollectiveMemoryWorkflow and CollectiveMemoryEmitter

Covers:
- Collective memory creation
- Memory sharing
- Team knowledge building
- Memory aggregation
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollectiveMemoryWorkflowIntegration:
    """Integration tests for CollectiveMemoryWorkflow"""

    @pytest.mark.asyncio
    async def test_collective_memory_workflow_initialization(self, db_pool):
        """Test CollectiveMemoryWorkflow initialization"""
        with (
            patch("services.collective_memory_workflow.MemoryServicePostgres") as mock_memory,
            patch("services.collective_memory_workflow.SearchService") as mock_search,
        ):
            from services.collective_memory_workflow import create_collective_memory_workflow

            workflow = create_collective_memory_workflow(
                memory_service=mock_memory.return_value,
                search_service=mock_search.return_value,
            )

            assert workflow is not None

    @pytest.mark.asyncio
    async def test_collective_memory_creation(self, db_pool):
        """Test collective memory creation"""

        async with db_pool.acquire() as conn:
            # Create collective_memory table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collective_memory (
                    id SERIAL PRIMARY KEY,
                    team_id VARCHAR(255),
                    memory_type VARCHAR(100),
                    content TEXT,
                    contributors TEXT[],
                    tags TEXT[],
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create collective memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO collective_memory (
                    team_id, memory_type, content, contributors, tags
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "team_collective_1",
                "best_practice",
                "Always verify client documents before submission",
                ["member1@team.com", "member2@team.com"],
                ["documentation", "best_practice", "workflow"],
            )

            assert memory_id is not None

            # Retrieve memory
            memory = await conn.fetchrow(
                """
                SELECT memory_type, content, contributors
                FROM collective_memory
                WHERE id = $1
                """,
                memory_id,
            )

            assert memory is not None
            assert len(memory["contributors"]) == 2

            # Cleanup
            await conn.execute("DELETE FROM collective_memory WHERE id = $1", memory_id)

    @pytest.mark.asyncio
    async def test_collective_memory_aggregation(self, db_pool):
        """Test collective memory aggregation"""

        async with db_pool.acquire() as conn:
            # Create multiple memories
            team_id = "team_aggregate_1"
            memories = [
                ("best_practice", "Practice A", ["member1"]),
                ("best_practice", "Practice B", ["member2"]),
                ("lesson_learned", "Lesson C", ["member3"]),
            ]

            for memory_type, content, contributors in memories:
                await conn.execute(
                    """
                    INSERT INTO collective_memory (
                        team_id, memory_type, content, contributors
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    team_id,
                    memory_type,
                    content,
                    contributors,
                )

            # Aggregate by type
            aggregated = await conn.fetch(
                """
                SELECT
                    memory_type,
                    COUNT(*) as count,
                    array_agg(DISTINCT unnest(contributors)) as all_contributors
                FROM collective_memory
                WHERE team_id = $1
                GROUP BY memory_type
                """,
                team_id,
            )

            assert len(aggregated) == 2  # Two types
            assert any(a["memory_type"] == "best_practice" for a in aggregated)

            # Cleanup
            await conn.execute("DELETE FROM collective_memory WHERE team_id = $1", team_id)

    @pytest.mark.asyncio
    async def test_collective_memory_usage_tracking(self, db_pool):
        """Test collective memory usage tracking"""

        async with db_pool.acquire() as conn:
            # Create memory with usage tracking
            memory_id = await conn.fetchval(
                """
                INSERT INTO collective_memory (
                    team_id, memory_type, content, usage_count
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "team_usage_1",
                "best_practice",
                "Test practice",
                0,
            )

            # Increment usage
            await conn.execute(
                """
                UPDATE collective_memory
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = $1
                """,
                memory_id,
            )

            # Verify usage
            memory = await conn.fetchrow(
                """
                SELECT usage_count FROM collective_memory WHERE id = $1
                """,
                memory_id,
            )

            assert memory["usage_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM collective_memory WHERE id = $1", memory_id)


@pytest.mark.integration
class TestCollectiveMemoryEmitterIntegration:
    """Integration tests for CollectiveMemoryEmitter"""

    @pytest.mark.asyncio
    async def test_collective_memory_emitter_initialization(self, db_pool):
        """Test CollectiveMemoryEmitter initialization"""
        with patch("services.collective_memory_emitter.MemoryServicePostgres") as mock_memory:
            from services.collective_memory_emitter import CollectiveMemoryEmitter

            emitter = CollectiveMemoryEmitter(memory_service=mock_memory.return_value)

            assert emitter is not None

    @pytest.mark.asyncio
    async def test_memory_emission(self, db_pool):
        """Test memory emission to collective memory"""

        async with db_pool.acquire() as conn:
            # Create individual memory
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS individual_memories (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    content TEXT,
                    should_share BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create shareable memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO individual_memories (
                    user_id, content, should_share
                )
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "user_emitter_123",
                "Client prefers email communication",
                True,
            )

            # Emit to collective memory
            collective_id = await conn.fetchval(
                """
                INSERT INTO collective_memory (
                    team_id, memory_type, content, contributors
                )
                SELECT
                    'team_shared',
                    'preference',
                    content,
                    ARRAY[user_id]
                FROM individual_memories
                WHERE id = $1 AND should_share = TRUE
                RETURNING id
                """,
                memory_id,
            )

            assert collective_id is not None

            # Cleanup
            await conn.execute("DELETE FROM collective_memory WHERE id = $1", collective_id)
            await conn.execute("DELETE FROM individual_memories WHERE id = $1", memory_id)
