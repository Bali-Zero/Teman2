"""Tests for service wiring — from_settings, DI container, config reading."""

import pytest

from nuzantara_graph.config import Settings
from nuzantara_graph.services import Services, SemanticCache, EmbeddingsService
from nuzantara_graph.services.vector_store import VectorStore
from nuzantara_graph.services.kg_store import KGStore
from nuzantara_graph.services.llm_gateway import LLMGateway
from nuzantara_graph.services.cache import KEY_PREFIX


class TestVectorStoreFromSettings:
    def test_reads_url_from_settings(self):
        s = Settings(qdrant_url="http://qdrant.example.com:6333", qdrant_api_key="secret")
        store = VectorStore.from_settings(s)
        assert store.qdrant_url == "http://qdrant.example.com:6333"
        assert store.qdrant_api_key == "secret"

    def test_no_hardcoded_url(self):
        store = VectorStore()
        assert store.qdrant_url == ""

    def test_embeddings_injected(self):
        s = Settings(openai_api_key="sk-test")
        emb = EmbeddingsService.from_settings(s)
        store = VectorStore.from_settings(s, embeddings=emb)
        assert store._embeddings is emb

    @pytest.mark.asyncio
    async def test_search_by_text_without_embeddings_raises(self):
        store = VectorStore(qdrant_url="http://localhost:6333")
        with pytest.raises(RuntimeError, match="EmbeddingsService not configured"):
            await store.search_by_text("test query")


class TestKGStoreFromSettings:
    def test_reads_url_from_settings(self):
        s = Settings(database_url="postgresql://user:pass@db.example.com:5432/mydb")
        store = KGStore.from_settings(s)
        assert store.database_url == "postgresql://user:pass@db.example.com:5432/mydb"

    def test_no_hardcoded_url(self):
        store = KGStore()
        assert store.database_url == ""


class TestLLMGatewayFromSettings:
    def test_reads_models_from_settings(self):
        s = Settings(
            primary_model="gemini-2.5-pro",
            fallback_model="gemini-2.0-flash",
            google_api_key="test-key",
        )
        gw = LLMGateway.from_settings(s)
        assert gw.primary_model == "gemini-2.5-pro"
        assert gw.fallback_model == "gemini-2.0-flash"
        assert gw.google_api_key == "test-key"

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        gw = LLMGateway(google_api_key="")
        with pytest.raises(RuntimeError, match="All models failed"):
            await gw.generate(prompt="test")


class TestSemanticCacheFromSettings:
    def test_reads_url_from_settings(self):
        s = Settings(redis_url="redis://redis.example.com:6379/1", semantic_cache_ttl_seconds=7200)
        cache = SemanticCache.from_settings(s)
        assert cache.redis_url == "redis://redis.example.com:6379/1"
        assert cache.ttl_seconds == 7200

    def test_key_prefix_is_v6(self):
        assert KEY_PREFIX.startswith("v6:")

    def test_make_key_deterministic(self):
        key1 = SemanticCache._make_key("How to set up PT PMA?")
        key2 = SemanticCache._make_key("How to set up PT PMA?")
        assert key1 == key2
        assert key1.startswith(KEY_PREFIX)

    def test_make_key_normalizes(self):
        key1 = SemanticCache._make_key("  Hello World  ")
        key2 = SemanticCache._make_key("hello world")
        assert key1 == key2


class TestEmbeddingsFromSettings:
    def test_reads_api_key_from_settings(self):
        s = Settings(openai_api_key="sk-test-123")
        emb = EmbeddingsService.from_settings(s)
        assert emb.model == "text-embedding-3-small"
        assert emb.dimensions == 1536

    def test_no_api_key_raises(self):
        s = Settings(openai_api_key="")
        with pytest.raises(ValueError, match="NUZANTARA_OPENAI_API_KEY"):
            EmbeddingsService.from_settings(s)

    def test_frozen_model(self):
        from nuzantara_graph.services.embeddings import EMBEDDING_MODEL, EMBEDDING_DIMS
        assert EMBEDDING_MODEL == "text-embedding-3-small"
        assert EMBEDDING_DIMS == 1536


class TestServicesContainer:
    def test_from_settings_creates_all_services(self):
        s = Settings(
            qdrant_url="http://qdrant:6333",
            database_url="postgresql://u:p@pg:5432/db",
            redis_url="redis://redis:6379/0",
            google_api_key="gk",
            openai_api_key="sk-test",
        )
        svc = Services.from_settings(s)

        assert isinstance(svc.llm, LLMGateway)
        assert isinstance(svc.vector_store, VectorStore)
        assert isinstance(svc.kg_store, KGStore)
        assert isinstance(svc.cache, SemanticCache)
        assert isinstance(svc.embeddings, EmbeddingsService)

        # Verify endpoints come from settings, not hardcoded
        assert svc.vector_store.qdrant_url == "http://qdrant:6333"
        assert svc.kg_store.database_url == "postgresql://u:p@pg:5432/db"
        assert svc.cache.redis_url == "redis://redis:6379/0"
        assert svc.llm.google_api_key == "gk"

    def test_from_settings_without_openai_key_skips_embeddings(self):
        s = Settings(openai_api_key="")
        svc = Services.from_settings(s)
        assert svc.embeddings is None

    def test_default_constructor_has_no_hardcoded_urls(self):
        svc = Services()
        assert svc.vector_store.qdrant_url == ""
        assert svc.kg_store.database_url == ""
        assert svc.cache.redis_url == ""
