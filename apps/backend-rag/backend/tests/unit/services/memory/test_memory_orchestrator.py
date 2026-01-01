"""
Unit tests for MemoryOrchestrator
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory.orchestrator import MemoryOrchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    return pool


@pytest.fixture
def memory_orchestrator(mock_db_pool):
    """Create memory orchestrator instance"""
    return MemoryOrchestrator(db_pool=mock_db_pool)


class TestMemoryOrchestrator:
    """Tests for MemoryOrchestrator"""

    @pytest.mark.asyncio
    async def test_init(self, mock_db_pool):
        """Test initialization"""
        orchestrator = MemoryOrchestrator(db_pool=mock_db_pool)
        assert orchestrator.db_pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_initialize(self, memory_orchestrator):
        """Test initialization"""
        # Mock MemoryServicePostgres properly
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())  # Return a mock memory object
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True

    @pytest.mark.asyncio
    async def test_get_user_context(self, memory_orchestrator):
        """Test getting user context"""
        user_email = "test@example.com"
        
        # Mock initialization
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            # Create a mock UserMemory-like object
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            context = await memory_orchestrator.get_user_context(user_email)
            assert context is not None

    @pytest.mark.asyncio
    async def test_process_conversation(self, memory_orchestrator):
        """Test processing conversation"""
        # Mock initialization
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.save_fact = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service
            
            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(return_value=[])
            mock_extractor_class.return_value = mock_extractor
            
            await memory_orchestrator.initialize()
            
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="test",
                ai_response="response"
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_facts(self, memory_orchestrator):
        """Test fact extraction"""
        # Mock initialization
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service
            
            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(return_value=[
                {"content": "User interested in KITAS", "type": "general", "confidence": 0.8}
            ])
            mock_extractor_class.return_value = mock_extractor
            
            await memory_orchestrator.initialize()
            
            # Use process_conversation which internally calls extract_facts
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="I am interested in KITAS",
                ai_response="KITAS is a work permit"
            )
            assert result is not None
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_initialize_with_database_url(self):
        """Test initialization with database_url"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = None
            mock_service.connect = AsyncMock()
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            orchestrator = MemoryOrchestrator(database_url="postgresql://test")
            await orchestrator.initialize()
            assert orchestrator.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_critical_failure(self, memory_orchestrator):
        """Test initialization with critical failure"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service_class.side_effect = Exception("Critical error")
            
            with pytest.raises(RuntimeError):
                await memory_orchestrator.initialize()

    @pytest.mark.asyncio
    async def test_initialize_degraded_mode(self, memory_orchestrator):
        """Test initialization in degraded mode"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor", side_effect=Exception("Non-critical")), \
             patch("services.memory.orchestrator.CollectiveMemoryService", side_effect=Exception("Non-critical")):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True
            assert memory_orchestrator._status.value == "degraded"

    @pytest.mark.asyncio
    async def test_get_user_context_empty_email(self, memory_orchestrator):
        """Test getting context with empty email"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            context = await memory_orchestrator.get_user_context("")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_get_user_context_with_query(self, memory_orchestrator):
        """Test getting context with query for collective memory"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class, \
             patch("services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class, \
             patch("services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class:
            mock_memory = MagicMock()
            mock_memory.profile_facts = ["fact1"]
            mock_memory.summary = "summary"
            mock_memory.counters = {"conversations": 5}
            mock_memory.updated_at = None
            
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service
            
            mock_collective = MagicMock()
            mock_collective.get_relevant_context = AsyncMock(return_value=["collective fact"])
            mock_collective_class.return_value = mock_collective
            
            mock_episodic = MagicMock()
            mock_episodic.get_context_summary = AsyncMock(return_value="timeline")
            mock_episodic_class.return_value = mock_episodic
            
            mock_kg = MagicMock()
            mock_kg.get_entity_context_for_query = AsyncMock(return_value=[{"id": "entity1"}])
            mock_kg_class.return_value = mock_kg
            
            await memory_orchestrator.initialize()
            
            context = await memory_orchestrator.get_user_context("test@example.com", query="test query")
            assert context.has_data is True

    @pytest.mark.asyncio
    async def test_get_user_context_degraded_mode(self, memory_orchestrator):
        """Test getting context in degraded mode"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor", side_effect=Exception("Non-critical")):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context is not None

    @pytest.mark.asyncio
    async def test_get_user_context_error_handling(self, memory_orchestrator):
        """Test error handling in get_user_context"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            # First call succeeds (for initialization), second fails
            mock_service.get_memory = AsyncMock(side_effect=[MagicMock(), Exception("Error")])
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_process_conversation_with_facts(self, memory_orchestrator):
        """Test processing conversation with extracted facts"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class, \
             patch("services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service
            
            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(return_value=[
                {"content": "Fact 1", "type": "general", "confidence": 0.9}
            ])
            mock_extractor_class.return_value = mock_extractor
            
            mock_episodic = MagicMock()
            mock_episodic.extract_and_save_event = AsyncMock(return_value={"status": "created", "title": "Event"})
            mock_episodic_class.return_value = mock_episodic
            
            await memory_orchestrator.initialize()
            
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="test",
                ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_empty_email(self, memory_orchestrator):
        """Test processing conversation with empty email"""
        result = await memory_orchestrator.process_conversation(
            user_email="",
            user_message="test",
            ai_response="response"
        )
        assert result.facts_extracted == 0

    @pytest.mark.asyncio
    async def test_process_conversation_no_extractor(self, memory_orchestrator):
        """Test processing conversation without extractor"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor", side_effect=Exception("No extractor")):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="test",
                ai_response="response"
            )
            assert result.facts_extracted == 0

    @pytest.mark.asyncio
    async def test_process_conversation_lock_timeout(self, memory_orchestrator):
        """Test processing conversation with lock timeout"""
        import asyncio
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            # Create a lock that's already acquired
            lock = memory_orchestrator._write_locks["test@example.com"]
            await lock.acquire()
            
            try:
                result = await memory_orchestrator.process_conversation(
                    user_email="test@example.com",
                    user_message="test",
                    ai_response="response"
                )
                # Should handle timeout gracefully
                assert result is not None
            finally:
                lock.release()

    @pytest.mark.asyncio
    async def test_process_conversation_error(self, memory_orchestrator):
        """Test error handling in process_conversation"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class, \
             patch("services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service
            
            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(side_effect=Exception("Error"))
            mock_extractor_class.return_value = mock_extractor
            
            await memory_orchestrator.initialize()
            
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="test",
                ai_response="response"
            )
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_get_stats(self, memory_orchestrator):
        """Test getting stats"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_stats = AsyncMock(return_value={
                "total_users": 10,
                "total_facts": 100,
                "total_conversations": 50
            })
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            stats = await memory_orchestrator.get_stats()
            assert stats.total_users == 10

    @pytest.mark.asyncio
    async def test_search_facts(self, memory_orchestrator):
        """Test searching facts"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.search = AsyncMock(return_value=[{"content": "fact1"}])
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            results = await memory_orchestrator.search_facts("test query")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_get_relevant_facts_for_query(self, memory_orchestrator):
        """Test getting relevant facts for query"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_relevant_facts = AsyncMock(return_value=["fact1", "fact2"])
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            
            facts = await memory_orchestrator.get_relevant_facts_for_query("test@example.com", "query")
            assert len(facts) > 0

    @pytest.mark.asyncio
    async def test_close(self, memory_orchestrator):
        """Test closing orchestrator"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            await memory_orchestrator.close()
            
            assert memory_orchestrator.is_initialized is False

    @pytest.mark.asyncio
    async def test_close_error(self, memory_orchestrator):
        """Test closing with error"""
        with patch("services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.close = AsyncMock(side_effect=Exception("Error"))
            mock_service_class.return_value = mock_service
            
            await memory_orchestrator.initialize()
            await memory_orchestrator.close()
            # Should handle error gracefully

    def test_ensure_initialized_not_initialized(self, memory_orchestrator):
        """Test ensure_initialized when not initialized"""
        with pytest.raises(RuntimeError):
            memory_orchestrator._ensure_initialized()

    def test_properties(self, memory_orchestrator):
        """Test properties"""
        assert memory_orchestrator.is_initialized is False
        assert memory_orchestrator.db_pool is not None

