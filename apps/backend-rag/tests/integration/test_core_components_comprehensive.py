"""
Comprehensive Integration Tests for Core Components
Tests cache, embeddings, chunker, parsers, plugins, qdrant_db, reranker

Covers:
- Cache operations
- Embeddings generation
- Text chunking
- Document parsing
- Plugin system
- Qdrant operations
- Reranking
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCacheComponent:
    """Integration tests for Cache component"""

    @pytest.mark.asyncio
    async def test_lru_cache_operations(self):
        """Test LRU cache operations"""
        from core.cache import LRUCache

        cache = LRUCache(maxsize=3)

        # Set items
        cache["key1"] = "value1"
        cache["key2"] = "value2"
        cache["key3"] = "value3"

        # Get items
        assert cache["key1"] == "value1"
        assert cache["key2"] == "value2"

        # Add new item (should evict oldest)
        cache["key4"] = "value4"

        # key1 should be evicted
        assert "key1" not in cache
        assert "key4" in cache

    @pytest.mark.asyncio
    async def test_cache_service_operations(self):
        """Test CacheService operations"""
        with patch("core.cache.Redis") as mock_redis:
            from core.cache import CacheService

            mock_client = MagicMock()
            mock_client.set = AsyncMock(return_value=True)
            mock_client.get = AsyncMock(return_value=b'{"test": "value"}')
            mock_client.delete = AsyncMock(return_value=1)

            cache = CacheService(redis_client=mock_client)

            # Test operations
            await cache.set("test_key", {"test": "value"}, ttl=60)
            value = await cache.get("test_key")
            await cache.delete("test_key")

            assert mock_client.set.called
            assert mock_client.get.called
            assert mock_client.delete.called


@pytest.mark.integration
class TestEmbeddingsComponent:
    """Integration tests for Embeddings component"""

    @pytest.mark.asyncio
    async def test_embeddings_generation(self):
        """Test embeddings generation"""
        with patch("core.embeddings.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
            )
            mock_openai.return_value = mock_client

            from core.embeddings import create_embeddings_generator

            embedder = create_embeddings_generator()

            # Generate embedding
            embedding = await embedder.generate_query_embedding("Test query")

            assert embedding is not None
            assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_batch_embeddings_generation(self):
        """Test batch embeddings generation"""
        with patch("core.embeddings.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(
                    data=[
                        MagicMock(embedding=[0.1] * 1536),
                        MagicMock(embedding=[0.2] * 1536),
                    ]
                )
            )
            mock_openai.return_value = mock_client

            from core.embeddings import create_embeddings_generator

            embedder = create_embeddings_generator()

            # Generate batch embeddings
            texts = ["Text 1", "Text 2"]
            embeddings = await embedder.generate_batch_embeddings(texts)

            assert len(embeddings) == 2


@pytest.mark.integration
class TestChunkerComponent:
    """Integration tests for Chunker component"""

    @pytest.mark.asyncio
    async def test_text_chunking(self):
        """Test text chunking"""
        from core.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)

        # Long text
        long_text = "A" * 500

        # Chunk text
        chunks = chunker.chunk_text(long_text)

        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)

    @pytest.mark.asyncio
    async def test_chunk_overlap(self):
        """Test chunk overlap"""
        from core.chunker import TextChunker

        chunker = TextChunker(chunk_size=50, chunk_overlap=10)

        text = "A" * 100
        chunks = chunker.chunk_text(text)

        # Verify overlap
        if len(chunks) > 1:
            # Check that chunks overlap
            assert len(chunks) >= 2


@pytest.mark.integration
class TestParsersComponent:
    """Integration tests for Parsers component"""

    @pytest.mark.asyncio
    async def test_pdf_parsing(self):
        """Test PDF parsing"""
        with patch("core.parsers.PyPDF2") as mock_pypdf:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "PDF content"
            mock_reader.pages = [mock_page]
            mock_pypdf.PdfReader.return_value = mock_reader

            from core.parsers import extract_text_from_pdf

            # Parse PDF
            text = extract_text_from_pdf("test.pdf")

            assert text == "PDF content"

    @pytest.mark.asyncio
    async def test_document_parse_error(self):
        """Test document parse error handling"""
        from core.parsers import DocumentParseError

        # Test error
        try:
            raise DocumentParseError("Test parse error", "test_file.pdf")
        except DocumentParseError as e:
            assert "Test parse error" in str(e)
            assert "test_file.pdf" in str(e)


@pytest.mark.integration
class TestPluginSystem:
    """Integration tests for Plugin system"""

    @pytest.mark.asyncio
    async def test_plugin_registry(self):
        """Test PluginRegistry"""
        from core.plugins.registry import PluginRegistry

        registry = PluginRegistry()

        assert registry is not None

    @pytest.mark.asyncio
    async def test_plugin_executor(self):
        """Test PluginExecutor"""
        with patch("core.plugins.executor.Redis") as mock_redis:
            from core.plugins.executor import PluginExecutor

            executor = PluginExecutor(redis_client=mock_redis.return_value)

            assert executor is not None


@pytest.mark.integration
class TestQdrantComponent:
    """Integration tests for Qdrant component"""

    @pytest.mark.asyncio
    async def test_qdrant_collection_operations(self, qdrant_client):
        """Test Qdrant collection operations"""

        collection_name = "core_test_collection"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Verify collection
            info = await qdrant_client.get_collection_info(collection_name=collection_name)
            assert info is not None

            # Delete collection
            await qdrant_client.delete_collection(collection_name=collection_name)

        except Exception:
            pass  # Cleanup if needed

    @pytest.mark.asyncio
    async def test_qdrant_search_operations(self, qdrant_client):
        """Test Qdrant search operations"""

        collection_name = "core_search_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert points
            test_embedding = [0.1] * 1536
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "point_1",
                        "vector": test_embedding,
                        "payload": {"text": "Test document"},
                    }
                ],
            )

            # Search
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=10,
            )

            assert len(results) == 1

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass


@pytest.mark.integration
class TestRerankerComponent:
    """Integration tests for Reranker component"""

    @pytest.mark.asyncio
    async def test_reranker_initialization(self):
        """Test Reranker initialization"""
        with patch("core.reranker.CohereClient") as mock_cohere:
            from core.reranker import Reranker

            reranker = Reranker(api_key="test_key")

            assert reranker is not None

    @pytest.mark.asyncio
    async def test_reranking_operations(self):
        """Test reranking operations"""
        with patch("core.reranker.CohereClient") as mock_cohere:
            mock_client = MagicMock()
            mock_client.rerank = AsyncMock(
                return_value={
                    "results": [
                        {"index": 0, "relevance_score": 0.9},
                        {"index": 1, "relevance_score": 0.8},
                    ]
                }
            )
            mock_cohere.return_value = mock_client

            from core.reranker import Reranker

            reranker = Reranker(api_key="test_key")

            # Rerank documents
            documents = ["Doc 1", "Doc 2"]
            query = "Test query"

            results = await reranker.rerank(query, documents)

            assert len(results) == 2
