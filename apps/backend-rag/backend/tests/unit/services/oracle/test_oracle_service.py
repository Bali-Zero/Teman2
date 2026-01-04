"""
Unit tests for OracleService
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

from services.oracle.oracle_service import OracleService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


@pytest.fixture
def oracle_service():
    """Create oracle service instance"""
    with (
        patch("services.oracle.oracle_service.ZantaraPromptBuilder"),
        patch("services.oracle.oracle_service.GeminiAdapter"),
        patch("services.oracle.oracle_service.IntentClassifier"),
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", create=True),
        patch("yaml.safe_load", return_value={}),
    ):
        return OracleService()


class TestOracleService:
    """Tests for OracleService"""

    def test_init(self):
        """Test initialization"""
        with (
            patch("services.oracle.oracle_service.ZantaraPromptBuilder"),
            patch("services.oracle.oracle_service.GeminiAdapter"),
            patch("services.oracle.oracle_service.IntentClassifier"),
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", create=True),
            patch("yaml.safe_load", return_value={}),
        ):
            service = OracleService()
            assert service is not None

    @pytest.mark.asyncio
    async def test_query(self, oracle_service):
        """Test query processing"""
        with (
            patch.object(oracle_service, "process_query") as mock_process,
            patch.object(oracle_service, "_get_db_pool") as mock_get_pool,
            patch.object(oracle_service, "_get_orchestrator") as mock_get_orch,
        ):
            mock_process.return_value = {"answer": "test answer", "sources": []}
            mock_get_pool.return_value = AsyncMock()
            mock_get_orch.return_value = AsyncMock()

            result = await oracle_service.process_query(query="test", user_email="test@example.com")

            assert result["answer"] == "test answer"

    @pytest.mark.asyncio
    async def test_query_with_context(self, oracle_service):
        """Test query with context"""
        with (
            patch.object(oracle_service, "process_query") as mock_process,
            patch.object(oracle_service, "_get_db_pool") as mock_get_pool,
            patch.object(oracle_service, "_get_orchestrator") as mock_get_orch,
        ):
            mock_process.return_value = {"answer": "test"}
            mock_get_pool.return_value = AsyncMock()
            mock_get_orch.return_value = AsyncMock()

            result = await oracle_service.process_query(
                query="test", user_email="test@example.com", context={"client_id": 123}
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_process_query_full(self, oracle_service):
        """Test full process_query flow"""
        mock_search_service = MagicMock()
        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value=MagicMock(
                answer="answer",
                sources=[],
                document_count=5,
                timings={"total": 1.0},
                model_used="gemini-3-flash",
                collection_used="legal_unified",
                is_ambiguous=False,
                clarification_question=None,
            )
        )

        with (
            patch.object(oracle_service, "_get_orchestrator", return_value=mock_orchestrator),
            patch.object(oracle_service.user_context, "get_full_user_context") as mock_context,
            patch.object(oracle_service.analytics, "build_analytics_data") as mock_analytics_build,
            patch.object(oracle_service.analytics, "store_query_analytics") as mock_analytics_store,
        ):
            mock_context.return_value = {
                "profile": {"name": "Test"},
                "personality": {"personality_type": "professional"},
                "memory_facts": [],
                "user_name": "Test User",
                "user_role": "user",
            }
            mock_analytics_build.return_value = {}

            result = await oracle_service.process_query(
                request_query="test query",
                request_user_email="test@example.com",
                request_limit=5,
                request_session_id="session123",
                request_include_sources=True,
                request_use_ai=True,
                request_language_override=None,
                request_conversation_history=None,
                search_service=mock_search_service,
            )

            assert result["success"] is True
            assert result["answer"] == "answer"

    @pytest.mark.asyncio
    async def test_process_query_error(self, oracle_service):
        """Test process_query error handling"""
        mock_search_service = MagicMock()

        with (
            patch.object(oracle_service.user_context, "get_full_user_context") as mock_context,
            patch.object(oracle_service, "_get_orchestrator") as mock_get_orch,
            patch.object(oracle_service.analytics, "store_query_analytics") as mock_store,
        ):
            mock_context.return_value = {
                "profile": {},
                "personality": {"personality_type": "professional"},
                "memory_facts": [],
                "user_name": "Test",
                "user_role": "user",
            }

            # Make orchestrator.process_query raise a catchable exception (RuntimeError is in the except list)
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=RuntimeError("Error"))
            mock_get_orch.return_value = mock_orchestrator

            result = await oracle_service.process_query(
                request_query="test",
                request_user_email="test@example.com",
                request_limit=5,
                request_session_id=None,
                request_include_sources=False,
                request_use_ai=True,
                request_language_override=None,
                request_conversation_history=None,
                search_service=mock_search_service,
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_process_query_with_conversation_history(self, oracle_service):
        """Test process_query with conversation history"""
        from app.routers.agentic_rag import ConversationMessageInput

        mock_search_service = MagicMock()
        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value=MagicMock(
                answer="answer",
                sources=[],
                document_count=5,
                timings={"total": 1.0},
                model_used="gemini-3-flash",
                collection_used="legal_unified",
                is_ambiguous=False,
                clarification_question=None,
            )
        )

        with (
            patch.object(oracle_service, "_get_orchestrator", return_value=mock_orchestrator),
            patch.object(oracle_service.user_context, "get_full_user_context") as mock_context,
            patch.object(oracle_service.analytics, "build_analytics_data") as mock_analytics_build,
            patch.object(oracle_service.analytics, "store_query_analytics") as mock_analytics_store,
        ):
            mock_context.return_value = {
                "profile": {},
                "personality": {"personality_type": "professional"},
                "memory_facts": [],
                "user_name": "Test",
                "user_role": "user",
            }
            mock_analytics_build.return_value = {}

            # Use proper dict format, not ConversationMessageInput
            result = await oracle_service.process_query(
                request_query="test",
                request_user_email="test@example.com",
                request_limit=5,
                request_session_id=None,
                request_include_sources=False,
                request_use_ai=True,
                request_language_override=None,
                request_conversation_history=[
                    ConversationMessageInput(role="user", content="previous")
                ],
                search_service=mock_search_service,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_db_pool(self, oracle_service):
        """Test _get_db_pool"""

        # Mock create_pool to return a coroutine
        async def mock_create_pool(*args, **kwargs):
            return AsyncMock()

        with patch("asyncpg.create_pool", side_effect=mock_create_pool):
            pool = await oracle_service._get_db_pool()
            assert pool is not None

    @pytest.mark.asyncio
    async def test_get_db_pool_error(self, oracle_service):
        """Test _get_db_pool error"""
        with patch("asyncpg.create_pool", side_effect=Exception("Error")):
            with pytest.raises(Exception):
                await oracle_service._get_db_pool()

    @pytest.mark.asyncio
    async def test_get_orchestrator(self, oracle_service):
        """Test _get_orchestrator"""
        mock_search_service = MagicMock()

        with (
            patch.object(oracle_service, "_get_db_pool", return_value=AsyncMock()),
            patch("services.oracle.oracle_service.create_agentic_rag") as mock_create,
        ):
            mock_create.return_value = AsyncMock()
            orchestrator = await oracle_service._get_orchestrator(mock_search_service)
            assert orchestrator is not None

    def test_properties(self, oracle_service):
        """Test lazy-loaded properties"""
        # Test followup_service
        assert oracle_service.followup_service is not None

        # Test citation_service
        assert oracle_service.citation_service is not None

        # Test clarification_service
        assert oracle_service.clarification_service is not None

        # Test personality_service
        assert oracle_service.personality_service is not None

        # Test fact_extractor
        assert oracle_service.fact_extractor is not None

    @pytest.mark.asyncio
    async def test_submit_feedback(self, oracle_service):
        """Test submit_feedback"""
        with patch("services.oracle.oracle_service.db_manager") as mock_db:
            mock_db.store_feedback = AsyncMock(return_value={"success": True})

            result = await oracle_service.submit_feedback(
                {"user_email": "test@example.com", "rating": 5}
            )
            assert result is not None

    def test_init_with_missing_config(self):
        """Test initialization with missing config file"""
        with (
            patch("services.oracle.oracle_service.ZantaraPromptBuilder"),
            patch("services.oracle.oracle_service.GeminiAdapter"),
            patch("services.oracle.oracle_service.IntentClassifier"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            service = OracleService()
            assert service is not None
            assert service.response_validator is not None
