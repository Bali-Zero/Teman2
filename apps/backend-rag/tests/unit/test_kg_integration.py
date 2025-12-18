"""
Unit tests for Knowledge Graph Integration with Memory System
Tests KG repository methods and MemoryContext integration
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestKnowledgeGraphRepositoryMethods:
    """Tests for new KG repository methods"""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return pool, conn

    @pytest.mark.asyncio
    async def test_get_user_related_entities_with_function(self, mock_pool):
        """Test get_user_related_entities when function exists"""
        from agents.services.kg_repository import KnowledgeGraphRepository

        pool, conn = mock_pool
        conn.fetchval = AsyncMock(return_value=True)  # Function exists
        # FIX: SQL function returns 'mention_count' not 'mentions'
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "entity-1",
                    "entity_type": "kbli",
                    "entity_name": "Software Development",
                    "mention_count": 5,
                },
                {
                    "entity_id": "entity-2",
                    "entity_type": "visa",
                    "entity_name": "KITAS",
                    "mention_count": 3,
                },
            ]
        )

        repo = KnowledgeGraphRepository(db_pool=pool)
        entities = await repo.get_user_related_entities(user_id="test@example.com", limit=10)

        assert len(entities) == 2
        assert entities[0]["type"] == "kbli"
        assert entities[0]["name"] == "Software Development"
        assert entities[0]["mentions"] == 5  # Python uses 'mentions' externally
        # FIX: entity_id is VARCHAR(64) not INTEGER
        assert entities[0]["entity_id"] == "entity-1"
        assert entities[1]["type"] == "visa"

    @pytest.mark.asyncio
    async def test_get_user_related_entities_fallback(self, mock_pool):
        """Test get_user_related_entities fallback when function doesn't exist"""
        from agents.services.kg_repository import KnowledgeGraphRepository

        pool, conn = mock_pool
        conn.fetchval = AsyncMock(return_value=False)  # Function doesn't exist
        # Fallback query returns entity_id as VARCHAR(64)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "entity-uuid-1",
                    "type": "kbli",
                    "name": "Software Development",
                    "mention_count": 5,
                },
            ]
        )

        repo = KnowledgeGraphRepository(db_pool=pool)
        entities = await repo.get_user_related_entities(user_id="test@example.com", limit=10)

        assert len(entities) == 1
        assert entities[0]["type"] == "kbli"
        assert entities[0]["entity_id"] == "entity-uuid-1"  # VARCHAR(64)

    @pytest.mark.asyncio
    async def test_get_user_related_entities_empty(self, mock_pool):
        """Test get_user_related_entities returns empty list on error"""
        from agents.services.kg_repository import KnowledgeGraphRepository

        pool, conn = mock_pool
        conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

        repo = KnowledgeGraphRepository(db_pool=pool)
        entities = await repo.get_user_related_entities(user_id="test@example.com")

        assert entities == []

    @pytest.mark.asyncio
    async def test_get_entity_context_for_query(self, mock_pool):
        """Test get_entity_context_for_query finds relevant entities"""
        from agents.services.kg_repository import KnowledgeGraphRepository

        pool, conn = mock_pool
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "kbli-62010",  # VARCHAR(64)
                    "type": "kbli",
                    "name": "Software Development",
                    "canonical_name": "software_development",
                    "metadata": {"code": "62010"},
                    "mention_count": 10,
                    "relationship_types": ["requires", "related_to"],
                },
            ]
        )

        repo = KnowledgeGraphRepository(db_pool=pool)
        entities = await repo.get_entity_context_for_query(query="software kbli", limit=5)

        assert len(entities) == 1
        assert entities[0]["type"] == "kbli"
        assert entities[0]["name"] == "Software Development"
        assert entities[0]["relationships"] == ["requires", "related_to"]
        assert entities[0]["entity_id"] == "kbli-62010"  # VARCHAR(64)

    @pytest.mark.asyncio
    async def test_get_entity_context_for_query_empty(self, mock_pool):
        """Test get_entity_context_for_query returns empty on error"""
        from agents.services.kg_repository import KnowledgeGraphRepository

        pool, conn = mock_pool
        conn.fetch = AsyncMock(side_effect=Exception("DB error"))

        repo = KnowledgeGraphRepository(db_pool=pool)
        entities = await repo.get_entity_context_for_query(query="test")

        assert entities == []


class TestMemoryContextWithKGEntities:
    """Tests for MemoryContext with KG entities"""

    def test_memory_context_includes_kg_entities(self):
        """Test MemoryContext includes kg_entities field"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            kg_entities=[
                {"type": "kbli", "name": "Software Development"},
                {"type": "visa", "name": "KITAS"},
            ],
        )

        assert len(context.kg_entities) == 2
        assert context.kg_entities[0]["type"] == "kbli"

    def test_memory_context_is_empty_with_only_kg_entities(self):
        """Test is_empty considers kg_entities"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            kg_entities=[{"type": "kbli", "name": "Test"}],
        )

        assert not context.is_empty()

    def test_memory_context_to_system_prompt_includes_kg(self):
        """Test to_system_prompt includes KG entities section"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            kg_entities=[
                {"type": "kbli", "name": "Software Development"},
                {"type": "visa", "name": "KITAS"},
            ],
            has_data=True,
        )

        prompt = context.to_system_prompt()

        assert "Related Concepts" in prompt
        assert "Kbli: Software Development" in prompt
        assert "Visa: KITAS" in prompt

    def test_memory_context_to_system_prompt_limits_entities(self):
        """Test to_system_prompt limits entities to 5"""
        from services.memory.models import MemoryContext

        entities = [{"type": f"type_{i}", "name": f"Entity {i}"} for i in range(10)]

        context = MemoryContext(
            user_id="test@example.com",
            kg_entities=entities,
            has_data=True,
        )

        prompt = context.to_system_prompt()

        # Should only include 5 entities
        assert "Entity 4" in prompt
        assert "Entity 5" not in prompt


class TestMemoryOrchestratorKGIntegration:
    """Tests for MemoryOrchestrator with KG integration"""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetchval = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=conn)
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return pool

    @pytest.mark.asyncio
    async def test_orchestrator_initializes_kg_repository(self, mock_pool):
        """Test MemoryOrchestrator initializes KG repository"""
        from services.memory.orchestrator import MemoryOrchestrator

        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        await orchestrator.initialize()

        assert orchestrator._kg_repository is not None

    @pytest.mark.asyncio
    async def test_get_user_context_includes_kg_entities(self, mock_pool):
        """Test get_user_context retrieves KG entities when query provided"""
        from services.memory.orchestrator import MemoryOrchestrator

        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        await orchestrator.initialize()

        # Mock the KG repository
        orchestrator._kg_repository.get_entity_context_for_query = AsyncMock(
            return_value=[{"type": "kbli", "name": "Software Development"}]
        )

        # Mock memory service
        orchestrator._memory_service = MagicMock()
        orchestrator._memory_service.pool = mock_pool
        orchestrator._memory_service.get_memory = AsyncMock(
            return_value=MagicMock(
                profile_facts=[],
                summary="",
                counters={},
                updated_at=datetime.now(timezone.utc),
            )
        )

        context = await orchestrator.get_user_context(
            user_email="test@example.com", query="software development kbli"
        )

        assert len(context.kg_entities) == 1
        assert context.kg_entities[0]["type"] == "kbli"

    @pytest.mark.asyncio
    async def test_get_user_context_no_kg_without_query(self, mock_pool):
        """Test get_user_context doesn't fetch KG entities without query"""
        from services.memory.orchestrator import MemoryOrchestrator

        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        await orchestrator.initialize()

        # Mock the KG repository
        mock_kg_method = AsyncMock(return_value=[])
        orchestrator._kg_repository.get_entity_context_for_query = mock_kg_method

        # Mock memory service
        orchestrator._memory_service = MagicMock()
        orchestrator._memory_service.pool = mock_pool
        orchestrator._memory_service.get_memory = AsyncMock(
            return_value=MagicMock(
                profile_facts=[],
                summary="",
                counters={},
                updated_at=datetime.now(timezone.utc),
            )
        )

        context = await orchestrator.get_user_context(
            user_email="test@example.com",
            query=None,  # No query
        )

        # KG method should not be called without query
        mock_kg_method.assert_not_called()


class TestContextManagerKGIntegration:
    """Tests for context_manager with KG entities"""

    @pytest.mark.asyncio
    async def test_get_user_context_includes_kg_in_result(self):
        """Test get_user_context includes kg_entities in returned dict"""
        from services.memory.models import MemoryContext
        from services.rag.agentic.context_manager import get_user_context

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_user_context = AsyncMock(
            return_value=MemoryContext(
                user_id="test@example.com",
                profile_facts=["User is Italian"],
                kg_entities=[{"type": "nationality", "name": "Italian"}],
                timeline_summary="### Recent Timeline",
            )
        )

        context = await get_user_context(
            db_pool=mock_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_orchestrator,
            query="test query",
        )

        assert "kg_entities" in context
        assert len(context["kg_entities"]) == 1
        assert context["kg_entities"][0]["type"] == "nationality"

    @pytest.mark.asyncio
    async def test_get_user_context_includes_timeline_summary(self):
        """Test get_user_context includes timeline_summary"""
        from services.memory.models import MemoryContext
        from services.rag.agentic.context_manager import get_user_context

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_user_context = AsyncMock(
            return_value=MemoryContext(
                user_id="test@example.com",
                timeline_summary="### Recent Timeline\n- Started PT PMA",
            )
        )

        context = await get_user_context(
            db_pool=mock_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_orchestrator,
            query="test query",
        )

        assert "timeline_summary" in context
        assert "Recent Timeline" in context["timeline_summary"]

    @pytest.mark.asyncio
    async def test_get_user_context_includes_memory_context_object(self):
        """Test get_user_context includes full memory_context object"""
        from services.memory.models import MemoryContext
        from services.rag.agentic.context_manager import get_user_context

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        expected_context = MemoryContext(
            user_id="test@example.com",
            profile_facts=["User is Italian"],
            kg_entities=[{"type": "nationality", "name": "Italian"}],
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_user_context = AsyncMock(return_value=expected_context)

        context = await get_user_context(
            db_pool=mock_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_orchestrator,
            query="test",
        )

        assert "memory_context" in context
        assert context["memory_context"] == expected_context
