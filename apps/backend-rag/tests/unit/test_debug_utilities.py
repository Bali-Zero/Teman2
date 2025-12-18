"""
Unit tests for Debug Utilities
Tests debug context manager, RAG debugger, DB debugger, and Qdrant debugger
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.debug_context import DebugContext, debug_mode
from app.utils.rag_debugger import RAGPipelineDebugger, RAGPipelineStepContext
from app.utils.db_debugger import DatabaseQueryDebugger, QueryTraceContext
from app.utils.qdrant_debugger import QdrantDebugger, CollectionHealth


class TestDebugContext:
    """Tests for DebugContext"""

    def test_debug_context_enables_verbose_logging(self):
        """Test that debug context enables verbose logging"""
        import logging

        original_level = logging.getLogger().level

        with DebugContext(request_id="test-123", enable_verbose_logging=True):
            assert logging.getLogger().level == logging.DEBUG

        # Should restore original level
        assert logging.getLogger().level == original_level

    def test_debug_context_captures_api_calls(self):
        """Test that debug context captures API calls"""
        with DebugContext(request_id="test-123", capture_api_calls=True) as ctx:
            ctx.capture_api_call("GET", "https://api.example.com/test")

        assert len(ctx.api_calls) == 1
        assert ctx.api_calls[0]["method"] == "GET"
        assert ctx.api_calls[0]["url"] == "https://api.example.com/test"

    def test_debug_context_manager_convenience(self):
        """Test debug_mode convenience context manager"""
        with debug_mode(request_id="test-123") as ctx:
            assert ctx.request_id == "test-123"
            assert ctx.enable_verbose_logging is True

    def test_debug_context_get_state_snapshot(self):
        """Test getting state snapshot"""
        with DebugContext(request_id="test-123") as ctx:
            ctx.capture_api_call("GET", "https://api.example.com/test")
            snapshot = ctx.get_state_snapshot()

        assert snapshot["request_id"] == "test-123"
        assert snapshot["api_calls_count"] == 1


class TestRAGPipelineDebugger:
    """Tests for RAGPipelineDebugger"""

    def test_rag_debugger_initialization(self):
        """Test RAG debugger initialization"""
        debugger = RAGPipelineDebugger(query="test query", correlation_id="test-id")

        assert debugger.trace.query == "test query"
        assert debugger.trace.correlation_id == "test-id"

    def test_rag_debugger_add_step(self):
        """Test adding steps to RAG debugger"""
        debugger = RAGPipelineDebugger(query="test query")

        with debugger.step("embedding"):
            pass

        assert len(debugger.trace.steps) == 1
        assert debugger.trace.steps[0].step_name == "embedding"

    def test_rag_debugger_add_documents(self):
        """Test adding documents to trace"""
        debugger = RAGPipelineDebugger(query="test query")

        documents = [{"id": "1", "text": "doc1"}, {"id": "2", "text": "doc2"}]
        debugger.add_documents(documents, stage="retrieved")

        assert len(debugger.trace.documents_retrieved) == 2

    def test_rag_debugger_add_documents_reranked(self):
        """Test adding reranked documents to trace"""
        debugger = RAGPipelineDebugger(query="test query")

        documents = [{"id": "1", "text": "doc1"}, {"id": "2", "text": "doc2"}]
        debugger.add_documents(documents, stage="reranked")

        assert len(debugger.trace.documents_reranked) == 2
        assert len(debugger.trace.documents_retrieved) == 0

    def test_rag_debugger_add_confidence_scores(self):
        """Test adding confidence scores"""
        debugger = RAGPipelineDebugger(query="test query")

        scores = [0.9, 0.8, 0.7]
        debugger.add_confidence_scores(scores)

        assert len(debugger.trace.confidence_scores) == 3

    def test_rag_debugger_add_fallback(self):
        """Test adding fallback"""
        debugger = RAGPipelineDebugger(query="test query")

        debugger.add_fallback("gemini_fallback")

        assert "gemini_fallback" in debugger.trace.fallbacks_activated

    def test_rag_debugger_finish(self):
        """Test finishing debugger"""
        debugger = RAGPipelineDebugger(query="test query")

        with debugger.step("search"):
            pass

        trace = debugger.finish(response="test response")

        assert trace.final_response == "test response"
        assert trace.total_duration_ms is not None

    def test_rag_debugger_get_trace(self):
        """Test getting trace as dictionary"""
        debugger = RAGPipelineDebugger(query="test query")

        with debugger.step("embedding"):
            pass

        trace_dict = debugger.get_trace()

        assert isinstance(trace_dict, dict)
        assert trace_dict["query"] == "test query"
        assert len(trace_dict["steps"]) == 1


class TestDatabaseQueryDebugger:
    """Tests for DatabaseQueryDebugger"""

    def test_db_debugger_initialization(self):
        """Test database debugger initialization"""
        debugger = DatabaseQueryDebugger(slow_query_threshold_ms=500.0)

        assert debugger.slow_query_threshold_ms == 500.0

    def test_db_debugger_trace_query(self):
        """Test tracing a database query"""
        debugger = DatabaseQueryDebugger()

        with debugger.trace_query("SELECT * FROM users", params=(1,)) as trace:
            trace.rows_returned = 10

        assert trace.duration_ms is not None
        assert trace.query == "SELECT * FROM users"

    def test_db_debugger_trace_query_with_error(self):
        """Test tracing a database query that raises error"""
        debugger = DatabaseQueryDebugger()

        with pytest.raises(ValueError):
            with debugger.trace_query("SELECT * FROM users") as trace:
                raise ValueError("Query error")

        assert trace.error == "Query error"
        assert trace.duration_ms is not None

    def test_db_debugger_trace_query_slow(self):
        """Test tracing a slow query"""
        import time

        debugger = DatabaseQueryDebugger(slow_query_threshold_ms=100.0)

        with debugger.trace_query("SELECT * FROM large_table") as trace:
            time.sleep(0.15)  # Simulate slow query
            trace.rows_returned = 1000

        assert trace.duration_ms > 100.0

    def test_db_debugger_trace_query_with_connection_id(self):
        """Test tracing query with connection and transaction IDs"""
        debugger = DatabaseQueryDebugger()

        with debugger.trace_query(
            "SELECT * FROM users",
            connection_id="conn-123",
            transaction_id="txn-456",
        ) as trace:
            trace.rows_returned = 5

        assert trace.connection_id == "conn-123"
        assert trace.transaction_id == "txn-456"

    def test_db_debugger_max_queries_limit(self):
        """Test that query log respects max limit"""
        debugger = DatabaseQueryDebugger()

        # Add many queries
        from app.utils.db_debugger import _query_log, MAX_QUERIES_TO_TRACK

        DatabaseQueryDebugger.clear_logs()

        for i in range(MAX_QUERIES_TO_TRACK + 10):
            with debugger.trace_query(f"SELECT {i}"):
                pass

        # Should not exceed max
        assert len(_query_log) <= MAX_QUERIES_TO_TRACK

    def test_db_debugger_get_slow_queries(self):
        """Test getting slow queries"""
        debugger = DatabaseQueryDebugger()

        # Create a slow query trace
        with debugger.trace_query("SELECT * FROM large_table"):
            pass

        # Manually add slow query to storage
        from app.utils.db_debugger import _slow_queries

        _slow_queries.append(
            {
                "query": "SELECT * FROM large_table",
                "duration_ms": 1500.0,
                "rows_returned": 1000,
            }
        )

        slow_queries = DatabaseQueryDebugger.get_slow_queries(limit=10)
        assert len(slow_queries) > 0

    def test_db_debugger_analyze_query_patterns(self):
        """Test analyzing query patterns"""
        debugger = DatabaseQueryDebugger()

        # Add some queries to log
        from app.utils.db_debugger import _query_log

        _query_log.append(
            {
                "query": "SELECT * FROM users WHERE id = $1",
                "duration_ms": 50.0,
                "rows_returned": 1,
            }
        )

        analysis = DatabaseQueryDebugger.analyze_query_patterns()
        assert "slow_patterns" in analysis
        assert "n_plus_one_patterns" in analysis

    def test_db_debugger_clear_logs(self):
        """Test clearing query logs"""
        debugger = DatabaseQueryDebugger()

        # Add some queries
        from app.utils.db_debugger import _query_log

        _query_log.append({"query": "SELECT 1", "duration_ms": 10.0})

        count = DatabaseQueryDebugger.clear_logs()
        assert count > 0
        assert len(_query_log) == 0


class TestQdrantDebugger:
    """Tests for QdrantDebugger"""

    @pytest.mark.asyncio
    async def test_qdrant_debugger_initialization(self):
        """Test Qdrant debugger initialization"""
        debugger = QdrantDebugger(qdrant_url="http://localhost:6333")

        assert debugger.qdrant_url == "http://localhost:6333"

    @pytest.mark.asyncio
    async def test_get_collection_health(self):
        """Test getting collection health"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_instance.get = AsyncMock(
                return_value=MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(
                        return_value={
                            "result": {
                                "points_count": 1000,
                                "vectors_count": 1000,
                                "config": {"params": {"vectors": {"on_disk": False}}},
                                "status": "green",
                            }
                        }
                    ),
                )
            )

            health = await debugger.get_collection_health("test_collection")

            assert health.name == "test_collection"
            assert health.points_count == 1000
            assert health.status == "green"

    @pytest.mark.asyncio
    async def test_get_collection_health_error(self):
        """Test getting collection health with error"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception("Connection failed")

            health = await debugger.get_collection_health("test_collection")

            assert health.status == "error"
            assert health.error is not None

    @pytest.mark.asyncio
    async def test_get_all_collections_health(self):
        """Test getting all collections health"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Mock collections list
            mock_instance.get = AsyncMock(
                side_effect=[
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {"collections": [{"name": "coll1"}, {"name": "coll2"}]}
                            }
                        ),
                    ),
                    # Mock individual collection health
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {
                                    "points_count": 100,
                                    "vectors_count": 100,
                                    "config": {"params": {"vectors": {"on_disk": False}}},
                                    "status": "green",
                                }
                            }
                        ),
                    ),
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {
                                    "points_count": 200,
                                    "vectors_count": 200,
                                    "config": {"params": {"vectors": {"on_disk": False}}},
                                    "status": "green",
                                }
                            }
                        ),
                    ),
                ]
            )

            health_statuses = await debugger.get_all_collections_health()

            assert len(health_statuses) == 2

    @pytest.mark.asyncio
    async def test_get_all_collections_health_error(self):
        """Test getting all collections health with error"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception("Connection failed")

            health_statuses = await debugger.get_all_collections_health()

            assert len(health_statuses) == 0

    @pytest.mark.asyncio
    async def test_get_collection_stats(self):
        """Test getting collection stats"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_instance.get = AsyncMock(
                return_value=MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(
                        return_value={
                            "result": {
                                "points_count": 1000,
                                "vectors_count": 1000,
                                "status": "green",
                                "config": {},
                            }
                        }
                    ),
                )
            )

            stats = await debugger.get_collection_stats("test_collection")

            assert stats["name"] == "test_collection"
            assert stats["points_count"] == 1000

    @pytest.mark.asyncio
    async def test_get_collection_stats_error(self):
        """Test getting collection stats with error"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception("Connection failed")

            stats = await debugger.get_collection_stats("test_collection")

            assert stats["name"] == "test_collection"
            assert "error" in stats

    @pytest.mark.asyncio
    async def test_analyze_query_performance(self):
        """Test analyzing query performance"""
        debugger = QdrantDebugger()

        query_vector = [0.1] * 1536  # 1536-dim vector

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_instance.post = AsyncMock(
                return_value=MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"result": [{"id": 1}, {"id": 2}]}),
                )
            )

            performance = await debugger.analyze_query_performance(
                collection="test_collection", query_vector=query_vector, limit=10
            )

            assert performance.collection == "test_collection"
            assert performance.results_count == 2
            assert performance.vector_dimension == 1536

    @pytest.mark.asyncio
    async def test_analyze_query_performance_error(self):
        """Test analyzing query performance with error"""
        debugger = QdrantDebugger()

        query_vector = [0.1] * 1536

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception("Query failed")

            performance = await debugger.analyze_query_performance(
                collection="test_collection", query_vector=query_vector
            )

            assert performance.collection == "test_collection"
            assert performance.results_count == 0
            assert performance.error is not None

    @pytest.mark.asyncio
    async def test_inspect_document(self):
        """Test inspecting a document"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_instance.post = AsyncMock(
                return_value=MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(
                        return_value={
                            "result": [
                                {
                                    "id": "doc1",
                                    "payload": {"text": "test document"},
                                }
                            ]
                        }
                    ),
                )
            )

            document = await debugger.inspect_document("test_collection", "doc1")

            assert document is not None
            assert document["id"] == "doc1"

    @pytest.mark.asyncio
    async def test_inspect_document_not_found(self):
        """Test inspecting non-existent document"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_instance.post = AsyncMock(
                return_value=MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"result": []}),
                )
            )

            document = await debugger.inspect_document("test_collection", "non-existent")

            assert document is None

    @pytest.mark.asyncio
    async def test_inspect_document_error(self):
        """Test inspecting document with error"""
        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.side_effect = Exception("Connection failed")

            document = await debugger.inspect_document("test_collection", "doc1")

            assert document is None

