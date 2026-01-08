"""
Comprehensive coverage tests for GoldenRouterService
Target: >99% coverage
Uses isolated module loading to avoid pydantic/settings issues
"""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import numpy as np
import pytest


class DummyEmbeddings:
    def __init__(self, embeddings=None):
        self._embeddings = embeddings or [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.calls = []

    async def generate_embeddings_async(self, queries):
        self.calls.append(("async", queries))
        return self._embeddings[: len(queries)]

    def generate_embeddings(self, queries):
        self.calls.append(("sync", queries))
        return self._embeddings[: len(queries)]

    def generate_query_embedding(self, query):
        return [0.1, 0.2, 0.3]


class DummyGoldenAnswerService:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    async def find_similar(self, query):
        self.calls.append(query)
        if self._error:
            raise self._error
        return self._result


# Setup module mocking before import
services_pkg = types.ModuleType("services")
services_pkg.__path__ = []
routing_pkg = types.ModuleType("services.routing")
routing_pkg.__path__ = []

app_module = types.ModuleType("app")
app_core_module = types.ModuleType("app.core")
app_config_module = types.ModuleType("app.core.config")

# Mock settings
settings_mock = SimpleNamespace(database_url="postgresql://test:test@localhost/test")
app_config_module.settings = settings_mock

sys.modules.update(
    {
        "services": services_pkg,
        "services.routing": routing_pkg,
        "app": app_module,
        "app.core": app_core_module,
        "app.core.config": app_config_module,
    }
)

# Load module
module_path = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "routing"
    / "golden_router_service.py"
)
spec = importlib.util.spec_from_file_location("services.routing.golden_router_service", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
GoldenRouterService = module.GoldenRouterService


def test_init():
    """Test initialization"""
    service = GoldenRouterService()
    assert service.embeddings is None
    assert service.golden_answer_service is None
    assert service.search_service is None
    assert service.db_pool is None
    assert service.routes_cache == []
    assert service.route_embeddings is None
    assert service.similarity_threshold == 0.85


def test_init_with_params():
    """Test initialization with parameters"""
    mock_embeddings = DummyEmbeddings()
    mock_golden_answer = DummyGoldenAnswerService()
    mock_search = MagicMock()

    service = GoldenRouterService(
        embeddings_generator=mock_embeddings,
        golden_answer_service=mock_golden_answer,
        search_service=mock_search,
    )
    assert service.embeddings == mock_embeddings
    assert service.golden_answer_service == mock_golden_answer
    assert service.search_service == mock_search


@pytest.mark.asyncio
async def test_get_db_pool():
    """Test getting database pool"""

    async def create_pool_mock(*args, **kwargs):
        return AsyncMock()

    with patch("asyncpg.create_pool", side_effect=create_pool_mock):
        service = GoldenRouterService()
        pool = await service._get_db_pool()

        assert pool is not None


@pytest.mark.asyncio
async def test_get_db_pool_cached():
    """Test getting database pool uses cache"""

    async def create_pool_mock(*args, **kwargs):
        return AsyncMock()

    with patch("asyncpg.create_pool", side_effect=create_pool_mock):
        service = GoldenRouterService()
        pool1 = await service._get_db_pool()
        pool2 = await service._get_db_pool()

        assert pool1 == pool2  # Should be same instance (cached)


@pytest.mark.asyncio
async def test_get_db_pool_error():
    """Test getting database pool handles errors"""

    async def create_pool_mock(*args, **kwargs):
        raise Exception("Connection failed")

    with patch("asyncpg.create_pool", side_effect=create_pool_mock):
        service = GoldenRouterService()

        with pytest.raises(Exception, match="Connection failed"):
            await service._get_db_pool()


@pytest.mark.asyncio
async def test_initialize_empty_routes():
    """Test initialization with no routes in database"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    # Create async context manager
    async def acquire():
        return mock_conn

    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        service = GoldenRouterService()
        await service.initialize()

        assert service.routes_cache == []
        assert service.route_embeddings is None
        mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_with_routes():
    """Test initialization with routes in database"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()

    mock_row = MagicMock()
    mock_row.__getitem__.side_effect = lambda key: {
        "route_id": "route1",
        "canonical_query": "test query",
        "document_ids": ["doc1"],
        "chapter_ids": ["ch1"],
        "collections": ["collection1"],
        "routing_hints": '{"hint": "value"}',
    }[key]
    mock_conn.fetch = AsyncMock(return_value=[mock_row])

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        with patch("asyncio.create_task") as mock_create_task:
            service = GoldenRouterService()
            await service.initialize()

            assert len(service.routes_cache) == 1
            assert service.routes_cache[0]["route_id"] == "route1"
            mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_routing_hints_not_string():
    """Test initialize when routing_hints is not a string (already dict)"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()

    mock_row = MagicMock()
    mock_row.__getitem__.side_effect = lambda key: {
        "route_id": "route1",
        "canonical_query": "test query",
        "document_ids": ["doc1"],
        "chapter_ids": ["ch1"],
        "collections": ["collection1"],
        "routing_hints": {"hint": "value"},  # Already a dict
    }[key]
    mock_conn.fetch = AsyncMock(return_value=[mock_row])

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        with patch("asyncio.create_task"):
            service = GoldenRouterService()
            await service.initialize()

            assert len(service.routes_cache) == 1
            assert service.routes_cache[0]["hints"] == {"hint": "value"}


@pytest.mark.asyncio
async def test_route_no_routes():
    """Test routing with no routes cached"""
    service = GoldenRouterService()
    service.routes_cache = []
    service.route_embeddings = None

    result = await service.route("test query")
    assert result is None


@pytest.mark.asyncio
async def test_route_no_embeddings():
    """Test routing with routes but no embeddings"""
    service = GoldenRouterService()
    service.routes_cache = [{"route_id": "route1"}]
    service.route_embeddings = None

    result = await service.route("test query")
    assert result is None


@pytest.mark.asyncio
async def test_route_no_embeddings_generator():
    """Test routing with routes and embeddings but no embeddings generator"""
    service = GoldenRouterService()
    service.routes_cache = [{"route_id": "route1"}]
    service.route_embeddings = np.array([[0.1, 0.2, 0.3]])
    service.embeddings = None

    result = await service.route("test query")
    assert result is None


@pytest.mark.asyncio
async def test_route_with_golden_answer_service():
    """Test routing using golden_answer_service"""
    mock_golden_answer = DummyGoldenAnswerService(
        result={"answer": "test answer", "similarity": 0.90}
    )

    service = GoldenRouterService(golden_answer_service=mock_golden_answer)
    result = await service.route("test query", user_id="user1")

    assert result is not None
    assert result["answer"] == "test answer"
    assert result["similarity"] == 0.90


@pytest.mark.asyncio
async def test_route_with_golden_answer_service_low_similarity():
    """Test routing with golden_answer_service but low similarity"""
    mock_golden_answer = DummyGoldenAnswerService(
        result={"answer": "test answer", "similarity": 0.50}  # Below threshold 0.85
    )

    service = GoldenRouterService(golden_answer_service=mock_golden_answer)
    service.routes_cache = []
    service.route_embeddings = None

    result = await service.route("test query")
    assert result is None


@pytest.mark.asyncio
async def test_route_with_golden_answer_service_no_result():
    """Test routing with golden_answer_service returning None"""
    mock_golden_answer = DummyGoldenAnswerService(result=None)
    service = GoldenRouterService(golden_answer_service=mock_golden_answer)
    service.routes_cache = []
    service.route_embeddings = None

    result = await service.route("test query")
    assert result is None


@pytest.mark.asyncio
async def test_route_with_golden_answer_service_exception():
    """Test routing with golden_answer_service raising exception"""
    mock_golden_answer = DummyGoldenAnswerService(error=RuntimeError("boom"))
    service = GoldenRouterService(golden_answer_service=mock_golden_answer)
    service.routes_cache = []
    service.route_embeddings = None

    result = await service.route("test query")
    assert result is None  # Should fallback gracefully


@pytest.mark.asyncio
async def test_route_match_found():
    """Test routing with successful match"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    service.routes_cache = [
        {
            "route_id": "route1",
            "canonical_query": "test query",
            "document_ids": ["doc1"],
            "chapter_ids": ["ch1"],
            "collections": ["coll1"],
            "hints": {"hint": "value"},
        }
    ]
    # Create embeddings matrix - same embedding for query and route (high similarity)
    query_emb = np.array([0.1, 0.2, 0.3])
    route_emb = np.array([[0.1, 0.2, 0.3]])  # Same = cosine similarity = 1.0
    service.route_embeddings = route_emb

    with patch.object(service, "_update_usage_stats", new_callable=AsyncMock):
        result = await service.route("test query")

    assert result is not None
    assert result["route_id"] == "route1"
    assert result["score"] >= 0.85  # Should be 1.0


@pytest.mark.asyncio
async def test_route_below_threshold():
    """Test routing with match below threshold"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    service.routes_cache = [
        {
            "route_id": "route1",
            "canonical_query": "test query",
            "document_ids": ["doc1"],
            "chapter_ids": ["ch1"],
            "collections": ["coll1"],
            "hints": {"hint": "value"},
        }
    ]
    # Create embeddings matrix - orthogonal vectors (cosine similarity = 0)
    query_emb = np.array([1.0, 0.0, 0.0])
    route_emb = np.array([[0.0, 1.0, 0.0]])  # Orthogonal = cosine similarity = 0
    service.route_embeddings = route_emb

    result = await service.route("test query")

    assert result is None  # Below threshold


@pytest.mark.asyncio
async def test_generate_embeddings_background_from_cache():
    """Test _generate_embeddings_background loading from cache"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1", "query2"]
    cache_data = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=str(cache_data).replace("'", '"'))):
            with patch("json.load", return_value=cache_data):
                await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    assert len(service.route_embeddings) == 2


@pytest.mark.asyncio
async def test_generate_embeddings_background_cache_mismatch():
    """Test _generate_embeddings_background with cache mismatch"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1", "query2"]
    cache_data = [[0.1, 0.2, 0.3]]  # Only 1, but queries has 2

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=str(cache_data))):
            with patch("json.load", return_value=cache_data):
                with patch.object(
                    embeddings, "generate_embeddings_async", new_callable=AsyncMock
                ) as mock_gen:
                    mock_gen.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
                    await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    mock_gen.assert_called_once()  # Should regenerate


@pytest.mark.asyncio
async def test_generate_embeddings_background_cache_invalid_json():
    """Test _generate_embeddings_background with invalid JSON cache (covers line 130: ValueError)"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("json.load", side_effect=ValueError("Invalid JSON")):
                with patch.object(
                    embeddings, "generate_embeddings_async", new_callable=AsyncMock
                ) as mock_gen:
                    mock_gen.return_value = [[0.1, 0.2, 0.3]]
                    await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    mock_gen.assert_called_once()  # Should regenerate


@pytest.mark.asyncio
async def test_generate_embeddings_background_cache_generic_exception():
    """Test _generate_embeddings_background with generic exception loading cache (covers lines 131-132)"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=True):
        # First attempt to open raises OSError (caught by first except), but we need a generic Exception
        # Use json.load to raise a generic Exception (not ValueError/TypeError/JSONDecodeError)
        with patch("builtins.open", mock_open(read_data="test")):
            with patch("json.load", side_effect=Exception("Generic error")):
                with patch.object(
                    embeddings, "generate_embeddings_async", new_callable=AsyncMock
                ) as mock_gen:
                    mock_gen.return_value = [[0.1, 0.2, 0.3]]
                    with patch("json.dump"):
                        await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    mock_gen.assert_called_once()  # Should regenerate


@pytest.mark.asyncio
async def test_generate_embeddings_background_fresh():
    """Test _generate_embeddings_background generating fresh embeddings"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1", "query2"]

    with patch("os.path.exists", return_value=False):
        with patch.object(
            embeddings, "generate_embeddings_async", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            with patch("builtins.open", mock_open()):
                with patch("json.dump"):
                    await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    mock_gen.assert_called_once_with(queries)


@pytest.mark.asyncio
async def test_generate_embeddings_background_sync_fallback():
    """Test _generate_embeddings_background with sync fallback"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=False):
        with patch.object(
            embeddings, "generate_embeddings_async", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = None  # Returns None
            with patch.object(embeddings, "generate_embeddings", return_value=[[0.1, 0.2, 0.3]]):
                with patch("asyncio.get_running_loop") as mock_loop:
                    mock_executor = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
                    mock_loop.return_value.run_in_executor = mock_executor
                    with patch("builtins.open", mock_open()):
                        with patch("json.dump"):
                            await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None
    mock_async.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embeddings_background_save_cache_error():
    """Test _generate_embeddings_background with save cache error (covers line 155: generic Exception on save)"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=False):
        with patch.object(
            embeddings, "generate_embeddings_async", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = [[0.1, 0.2, 0.3]]
            # json.dump raises a generic Exception (not TypeError/ValueError)
            with patch("builtins.open", mock_open()):
                with patch("json.dump", side_effect=Exception("Generic save error")):
                    # Should not raise, just log warning
                    await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None


@pytest.mark.asyncio
async def test_generate_embeddings_background_save_cache_type_error():
    """Test _generate_embeddings_background with TypeError on save (covers line 153: TypeError/ValueError)"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=False):
        with patch.object(
            embeddings, "generate_embeddings_async", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = [[0.1, 0.2, 0.3]]
            with patch("builtins.open", mock_open()):
                with patch("json.dump", side_effect=TypeError("Not serializable")):
                    # Should not raise, just log warning
                    await service._generate_embeddings_background(queries)

    assert service.route_embeddings is not None


@pytest.mark.asyncio
async def test_generate_embeddings_background_exception():
    """Test _generate_embeddings_background exception handling"""
    embeddings = DummyEmbeddings()
    service = GoldenRouterService(embeddings_generator=embeddings)
    queries = ["query1"]

    with patch("os.path.exists", return_value=False):
        with patch.object(
            embeddings, "generate_embeddings_async", side_effect=RuntimeError("boom")
        ):
            # Should not raise, just log error
            await service._generate_embeddings_background(queries)

    # Should still be None if exception occurs
    assert service.route_embeddings is None


@pytest.mark.asyncio
async def test_update_usage_stats():
    """Test updating route usage statistics"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        service = GoldenRouterService()
        await service._update_usage_stats("route1")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE golden_routes" in call_args[0][0]
        assert call_args[0][1] == "route1"


@pytest.mark.asyncio
async def test_update_usage_stats_error():
    """Test updating route usage stats handles errors"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        service = GoldenRouterService()
        # Should not raise, just log warning
        await service._update_usage_stats("route1")


@pytest.mark.asyncio
async def test_add_route():
    """Test adding a new route"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        with patch.object(GoldenRouterService, "initialize", new_callable=AsyncMock) as mock_init:
            service = GoldenRouterService()
            route_id = await service.add_route(
                canonical_query="test query",
                document_ids=["doc1"],
                chapter_ids=["ch1"],
                collections=["collection1"],
            )

            assert route_id.startswith("route_")
            assert len(route_id) > 6  # route_ + 8 hex chars
            mock_conn.execute.assert_called_once()
            mock_init.assert_called_once()


@pytest.mark.asyncio
async def test_add_route_with_defaults():
    """Test adding route with default collections"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Create async context manager
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch.object(GoldenRouterService, "_get_db_pool", return_value=mock_pool):
        with patch.object(GoldenRouterService, "initialize", new_callable=AsyncMock):
            service = GoldenRouterService()
            route_id = await service.add_route(
                canonical_query="test query",
                document_ids=["doc1"],
            )

            assert route_id.startswith("route_")
            # Verify execute was called with correct arguments
            assert mock_conn.execute.called
            # Get all call arguments
            call = mock_conn.execute.call_args
            # call.args is tuple of positional args: (sql, route_id, canonical_query, document_ids, chapter_ids, collections)
            # call.args[0] is SQL, call.args[1] is route_id, etc.
            # Collections is the 5th positional arg (index 5) after SQL
            args = call[0]  # positional arguments
            assert args[5] == ["legal_unified"]  # collections should default to ["legal_unified"]


@pytest.mark.asyncio
async def test_close():
    """Test closing the service"""
    mock_pool = AsyncMock()
    service = GoldenRouterService()
    service.db_pool = mock_pool

    await service.close()

    mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_no_pool():
    """Test closing when no pool exists"""
    service = GoldenRouterService()
    service.db_pool = None

    # Should not raise
    await service.close()
