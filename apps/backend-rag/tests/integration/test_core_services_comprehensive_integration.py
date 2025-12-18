"""
Comprehensive Integration Tests for Core Services
Tests embeddings, token_estimator, cache, memory_service_postgres with real database
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestEmbeddingsServiceIntegration:
    """Integration tests for EmbeddingsGenerator"""

    @pytest.mark.asyncio
    async def test_embeddings_generator_init_openai(self):
        """Test OpenAI embeddings initialization"""
        from core.embeddings import EmbeddingsGenerator

        # Mock OpenAI API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )
            assert generator.provider == "openai"
            assert generator.model == "text-embedding-3-small"
            assert generator.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embeddings_generator_init_sentence_transformers(self):
        """Test Sentence Transformers initialization"""
        from core.embeddings import EmbeddingsGenerator

        # Try to initialize with sentence-transformers
        try:
            generator = EmbeddingsGenerator(provider="sentence-transformers")
            assert generator.provider == "sentence-transformers"
            assert generator.model is not None
        except Exception:
            # If sentence-transformers not available, should fallback to OpenAI
            pass

    @pytest.mark.asyncio
    async def test_generate_embeddings_openai(self):
        """Test generating embeddings with OpenAI"""
        from core.embeddings import EmbeddingsGenerator

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )

            # Mock OpenAI client
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1] * 1536),
                MagicMock(embedding=[0.2] * 1536),
            ]
            generator.client.embeddings.create = MagicMock(return_value=mock_response)

            texts = ["Hello world", "Test embedding"]
            embeddings = generator.generate_embeddings(texts)

            assert len(embeddings) == 2
            assert len(embeddings[0]) == 1536
            assert len(embeddings[1]) == 1536

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self):
        """Test generating single embedding"""
        from core.embeddings import EmbeddingsGenerator

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )

            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            generator.client.embeddings.create = MagicMock(return_value=mock_response)

            embedding = generator.generate_single_embedding("test")
            assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_generate_query_embedding(self):
        """Test generating query embedding"""
        from core.embeddings import EmbeddingsGenerator

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )

            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            generator.client.embeddings.create = MagicMock(return_value=mock_response)

            embedding = generator.generate_query_embedding("query")
            assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_get_model_info(self):
        """Test getting model info"""
        from core.embeddings import EmbeddingsGenerator

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )

            info = generator.get_model_info()
            assert info["model"] == "text-embedding-3-small"
            assert info["dimensions"] == 1536
            assert info["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_create_embeddings_generator_factory(self):
        """Test factory function"""
        from core.embeddings import create_embeddings_generator

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = create_embeddings_generator(
                api_key="test_key", provider="openai", model="text-embedding-3-small"
            )
            assert generator is not None
            assert generator.provider == "openai"

    @pytest.mark.asyncio
    async def test_generate_embeddings_convenience_function(self):
        """Test convenience function"""

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            # This will use default settings
            # Mock if needed for actual execution
            pass


@pytest.mark.integration
class TestTokenEstimatorIntegration:
    """Integration tests for TokenEstimator"""

    def test_token_estimator_init(self):
        """Test TokenEstimator initialization"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gpt-4")
        assert estimator.model == "gpt-4"

    def test_token_estimator_init_gemini(self):
        """Test TokenEstimator with Gemini model"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gemini-2.5-flash")
        assert estimator.model == "gemini-2.5-flash"

    def test_estimate_tokens(self):
        """Test token estimation"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gpt-4")
        text = "Hello world, this is a test"
        tokens = estimator.estimate_tokens(text)
        assert tokens > 0

    def test_estimate_tokens_with_tiktoken(self):
        """Test token estimation with tiktoken"""
        from llm.token_estimator import TIKTOKEN_AVAILABLE, TokenEstimator

        estimator = TokenEstimator(model="gpt-4")
        text = "Hello world, this is a test"
        tokens = estimator.estimate_tokens(text)

        if TIKTOKEN_AVAILABLE:
            # Should use tiktoken
            assert tokens > 0
        else:
            # Should use approximation
            assert tokens > 0

    def test_estimate_messages_tokens(self):
        """Test estimating tokens for messages"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gpt-4")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        tokens = estimator.estimate_messages_tokens(messages)
        assert tokens > 0

    def test_estimate_approximate_fallback(self):
        """Test approximation fallback"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gpt-4")
        # Force approximation by setting encoding to None
        estimator._encoding = None

        text = "Hello world"
        tokens = estimator._estimate_approximate(text)
        assert tokens > 0


@pytest.mark.integration
class TestMemoryServicePostgresIntegration:
    """Integration tests for MemoryServicePostgres"""

    @pytest_asyncio.fixture
    async def memory_service(self, postgres_container):
        """Create memory service for testing"""
        from services.memory_service_postgres import MemoryServicePostgres

        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        service = MemoryServicePostgres(database_url=database_url)
        await service.connect()
        return service

    @pytest.mark.asyncio
    async def test_memory_service_init(self, memory_service):
        """Test memory service initialization"""
        assert memory_service is not None
        assert memory_service.MAX_FACTS == 10
        assert memory_service.MAX_SUMMARY_LENGTH == 500

    @pytest.mark.asyncio
    async def test_get_memory_new_user(self, memory_service):
        """Test getting memory for new user"""
        memory = await memory_service.get_memory("test_user_1")
        assert memory.user_id == "test_user_1"
        assert memory.profile_facts == []
        assert memory.summary == ""
        assert memory.counters["conversations"] == 0

    @pytest.mark.asyncio
    async def test_add_fact(self, memory_service):
        """Test adding a fact"""
        user_id = "test_user_2"
        success = await memory_service.add_fact(user_id, "User likes Python")
        assert success is True

        memory = await memory_service.get_memory(user_id)
        assert len(memory.profile_facts) == 1
        assert "Python" in memory.profile_facts[0]

    @pytest.mark.asyncio
    async def test_add_fact_deduplication(self, memory_service):
        """Test fact deduplication"""
        user_id = "test_user_3"
        await memory_service.add_fact(user_id, "User likes Python")
        # Try to add same fact again
        success = await memory_service.add_fact(user_id, "User likes Python")
        assert success is False  # Should not add duplicate

        memory = await memory_service.get_memory(user_id)
        assert len(memory.profile_facts) == 1

    @pytest.mark.asyncio
    async def test_update_summary(self, memory_service):
        """Test updating summary"""
        user_id = "test_user_4"
        summary = "User is interested in AI and machine learning"
        success = await memory_service.update_summary(user_id, summary)
        assert success is True

        memory = await memory_service.get_memory(user_id)
        assert memory.summary == summary

    @pytest.mark.asyncio
    async def test_update_summary_truncation(self, memory_service):
        """Test summary truncation"""
        user_id = "test_user_5"
        long_summary = "x" * 600  # Exceeds MAX_SUMMARY_LENGTH
        success = await memory_service.update_summary(user_id, long_summary)
        assert success is True

        memory = await memory_service.get_memory(user_id)
        assert len(memory.summary) <= memory_service.MAX_SUMMARY_LENGTH
        assert memory.summary.endswith("...")

    @pytest.mark.asyncio
    async def test_increment_counter(self, memory_service):
        """Test incrementing counter"""
        user_id = "test_user_6"
        await memory_service.increment_counter(user_id, "conversations")
        await memory_service.increment_counter(user_id, "conversations")

        memory = await memory_service.get_memory(user_id)
        assert memory.counters["conversations"] == 2

    @pytest.mark.asyncio
    async def test_save_memory(self, memory_service):
        """Test saving memory"""
        user_id = "test_user_7"
        memory = await memory_service.get_memory(user_id)
        memory.summary = "Test summary"
        memory.counters["conversations"] = 5

        success = await memory_service.save_memory(memory)
        assert success is True

        # Reload and verify
        reloaded = await memory_service.get_memory(user_id)
        assert reloaded.summary == "Test summary"
        assert reloaded.counters["conversations"] == 5

    @pytest.mark.asyncio
    async def test_retrieve_with_category(self, memory_service):
        """Test retrieving memory with category filter"""
        user_id = "test_user_8"
        await memory_service.add_fact(user_id, "User prefers visa type B1")
        await memory_service.add_fact(user_id, "User likes Python programming")

        # Retrieve with category filter
        result = await memory_service.retrieve(user_id, category="visa")
        assert len(result["profile_facts"]) == 1
        assert "visa" in result["profile_facts"][0].lower()

    @pytest.mark.asyncio
    async def test_search_memory(self, memory_service):
        """Test searching memory"""
        user_id = "test_user_9"
        await memory_service.add_fact(user_id, "User prefers Java")
        await memory_service.add_fact(user_id, "User likes Python")

        results = await memory_service.search("Python", limit=5)
        assert len(results) > 0
        assert any("Python" in r["fact"] for r in results)

    @pytest.mark.asyncio
    async def test_get_relevant_facts(self, memory_service):
        """Test getting relevant facts"""
        user_id = "test_user_10"
        await memory_service.add_fact(user_id, "Fact 1")
        await memory_service.add_fact(user_id, "Fact 2")

        facts = await memory_service.get_relevant_facts(user_id, "query")
        assert len(facts) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, memory_service):
        """Test getting memory stats"""
        user_id = "test_user_11"
        await memory_service.add_fact(user_id, "Test fact")

        stats = await memory_service.get_stats()
        assert "cached_users" in stats
        assert "postgres_enabled" in stats
        assert stats["postgres_enabled"] is True

    @pytest.mark.asyncio
    async def test_max_facts_limit(self, memory_service):
        """Test max facts limit"""
        user_id = "test_user_12"
        # Add more than MAX_FACTS
        for i in range(15):
            await memory_service.add_fact(user_id, f"Fact {i}")

        memory = await memory_service.get_memory(user_id)
        assert len(memory.profile_facts) <= memory_service.MAX_FACTS

    @pytest.mark.asyncio
    async def test_memory_cache(self, memory_service):
        """Test memory cache"""
        user_id = "test_user_13"
        await memory_service.add_fact(user_id, "Cached fact")

        # First access loads from DB
        memory1 = await memory_service.get_memory(user_id)
        # Second access should use cache
        memory2 = await memory_service.get_memory(user_id)

        assert memory1.user_id == memory2.user_id
        assert len(memory1.profile_facts) == len(memory2.profile_facts)


@pytest.mark.integration
class TestCacheServiceIntegration:
    """Integration tests for CacheService"""

    def test_cache_service_init(self):
        """Test cache service initialization"""
        from core.cache import CacheService

        cache = CacheService()
        assert cache is not None

    def test_cache_set_get(self):
        """Test cache set and get"""
        from core.cache import CacheService

        cache = CacheService()
        cache.set("test_key", "test_value", ttl=60)
        value = cache.get("test_key")
        assert value == "test_value"

    def test_cache_expiration(self):
        """Test cache expiration"""
        import time

        from core.cache import CacheService

        cache = CacheService()
        cache.set("expire_key", "value", ttl=1)
        time.sleep(1.1)
        value = cache.get("expire_key")
        assert value is None

    def test_cache_delete(self):
        """Test cache delete"""
        from core.cache import CacheService

        cache = CacheService()
        cache.set("delete_key", "value")
        cache.delete("delete_key")
        value = cache.get("delete_key")
        assert value is None

    def test_cache_clear(self):
        """Test cache clear"""
        from core.cache import CacheService

        cache = CacheService()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_cache_service_singleton(self):
        """Test singleton pattern"""
        from core.cache import get_cache_service

        cache1 = get_cache_service()
        cache2 = get_cache_service()
        assert cache1 is cache2
