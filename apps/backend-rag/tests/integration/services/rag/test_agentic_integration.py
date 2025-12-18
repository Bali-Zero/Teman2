"""
Integration Tests for Agentic RAG Service
Tests agentic.py with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAgenticIntegration:
    """Comprehensive integration tests for agentic.py"""

    @pytest_asyncio.fixture
    async def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_pool

    @pytest_asyncio.fixture
    async def mock_retriever(self):
        """Create mock retriever"""
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(
            return_value={"results": [{"text": "Test document"}]}
        )
        return mock_retriever

    @pytest_asyncio.fixture
    async def orchestrator(self, mock_db_pool, mock_retriever):
        """Create AgenticRAGOrchestrator instance"""
        with patch("services.rag.agentic.genai.configure"):
            with patch("services.rag.agentic.genai.GenerativeModel") as mock_model:
                mock_model_instance = MagicMock()
                mock_chat = MagicMock()
                mock_chat.send_message_async = AsyncMock()
                mock_response = MagicMock()
                mock_response.text = "Test response"
                mock_chat.send_message_async.return_value = mock_response
                mock_model_instance.start_chat.return_value = mock_chat
                mock_model.return_value = mock_model_instance

                from services.rag.agentic import AgenticRAGOrchestrator

                orchestrator = AgenticRAGOrchestrator(
                    retriever=mock_retriever,
                    db_pool=mock_db_pool,
                )
                orchestrator.model_flash = mock_model_instance
                orchestrator.model_flash_lite = mock_model_instance
                return orchestrator

    def test_is_out_of_domain_personal_data(self):
        """Test out-of-domain detection for personal data queries"""
        from services.rag.agentic import is_out_of_domain

        is_ood, category = is_out_of_domain("codice fiscale di Mario Rossi")
        assert is_ood is True
        assert category == "personal_data"

    def test_is_out_of_domain_realtime_info(self):
        """Test out-of-domain detection for realtime info queries"""
        from services.rag.agentic import is_out_of_domain

        is_ood, category = is_out_of_domain("che tempo fa a Bali?")
        assert is_ood is True
        assert category == "realtime_info"

    def test_is_out_of_domain_off_topic(self):
        """Test out-of-domain detection for off-topic queries"""
        from services.rag.agentic import is_out_of_domain

        is_ood, category = is_out_of_domain("ricetta per la pasta")
        assert is_ood is True
        assert category == "off_topic"

    def test_is_out_of_domain_in_domain(self):
        """Test out-of-domain detection for in-domain queries"""
        from services.rag.agentic import is_out_of_domain

        is_ood, category = is_out_of_domain("Come ottenere un KITAS?")
        assert is_ood is False
        assert category is None

    def test_clean_response_removes_thoughts(self):
        """Test that clean_response removes THOUGHT markers"""
        from services.rag.agentic import clean_response

        response = "THOUGHT: I need to think about this.\nFinal Answer: Test answer"
        cleaned = clean_response(response)
        assert "THOUGHT" not in cleaned
        assert "Test answer" in cleaned

    def test_clean_response_removes_observations(self):
        """Test that clean_response removes Observation markers"""
        from services.rag.agentic import clean_response

        response = "Observation: No data found.\nFinal Answer: Test"
        cleaned = clean_response(response)
        assert "Observation" not in cleaned

    def test_clean_response_removes_okay_patterns(self):
        """Test that clean_response removes 'Okay, since...' patterns"""
        from services.rag.agentic import clean_response

        response = "Okay, since there's no observation, I'll provide a general answer.\nTest answer"
        cleaned = clean_response(response)
        assert "Okay, since" not in cleaned

    def test_clean_response_truncates_long(self):
        """Test that clean_response truncates very long responses"""
        from services.rag.agentic import clean_response

        long_response = "A" * 2000
        cleaned = clean_response(long_response)
        assert len(cleaned) <= 1000

    def test_vector_search_tool_initialization(self, mock_retriever):
        """Test VectorSearchTool initialization"""
        from services.rag.agentic import VectorSearchTool

        tool = VectorSearchTool(mock_retriever)
        assert tool.name == "vector_search"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_vector_search_tool_execute(self, mock_retriever):
        """Test VectorSearchTool execution"""
        from services.rag.agentic import VectorSearchTool

        tool = VectorSearchTool(mock_retriever)
        result = await tool.execute(query="test query", collection="legal_unified", top_k=5)

        assert result is not None
        assert isinstance(result, str)
        mock_retriever.search_with_reranking.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search_tool_no_results(self, mock_retriever):
        """Test VectorSearchTool when no results found"""
        from services.rag.agentic import VectorSearchTool

        mock_retriever.search_with_reranking = AsyncMock(return_value={"results": []})

        tool = VectorSearchTool(mock_retriever)
        result = await tool.execute(query="test", collection="legal_unified")

        assert "No relevant documents" in result

    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization"""
        from services.rag.agentic import WebSearchTool

        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_web_search_tool_no_client(self):
        """Test WebSearchTool when client not available"""
        from services.rag.agentic import WebSearchTool

        tool = WebSearchTool(client=None)
        result = await tool.execute(query="test query")

        assert "vector_search" in result.lower() or "not available" in result.lower()

    def test_database_query_tool_initialization(self, mock_db_pool):
        """Test DatabaseQueryTool initialization"""
        from services.rag.agentic import DatabaseQueryTool

        tool = DatabaseQueryTool(mock_db_pool)
        assert tool.name == "database_query"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_database_query_tool_no_db(self):
        """Test DatabaseQueryTool when database not available"""
        from services.rag.agentic import DatabaseQueryTool

        tool = DatabaseQueryTool(db_pool=None)
        result = await tool.execute(search_term="test", query_type="full_text")

        assert "not available" in result.lower()

    def test_calculator_tool_initialization(self):
        """Test CalculatorTool initialization"""
        from services.rag.agentic import CalculatorTool

        tool = CalculatorTool()
        assert tool.name == "calculator"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_calculator_tool_execute(self):
        """Test CalculatorTool execution"""
        from services.rag.agentic import CalculatorTool

        tool = CalculatorTool()
        result = await tool.execute(expression="2 + 2")

        assert result is not None
        assert "4" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_calculator_tool_invalid_expression(self):
        """Test CalculatorTool with invalid expression"""
        from services.rag.agentic import CalculatorTool

        tool = CalculatorTool()
        result = await tool.execute(expression="invalid expression!!!")

        assert "error" in result.lower() or "invalid" in result.lower()

    def test_pricing_tool_initialization(self):
        """Test PricingTool initialization"""
        from services.rag.agentic import PricingTool

        tool = PricingTool()
        assert tool.name == "get_pricing"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_pricing_tool_execute(self):
        """Test PricingTool execution"""
        with patch("services.rag.agentic.get_pricing_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_pricing = MagicMock(
                return_value={"visa": [{"name": "E33G", "price": 15000000}]}
            )
            mock_get_service.return_value = mock_service

            from services.rag.agentic import PricingTool

            tool = PricingTool()
            result = await tool.execute(service_type="visa")

            assert result is not None
            assert isinstance(result, str)

    def test_vision_tool_initialization(self):
        """Test VisionTool initialization"""
        from services.rag.agentic import VisionTool

        tool = VisionTool()
        assert tool.name == "vision_analyze"
        assert tool.description is not None

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test AgenticRAGOrchestrator initialization"""
        assert orchestrator is not None
        assert orchestrator.retriever is not None

    @pytest.mark.asyncio
    async def test_get_user_context_with_profile(self, orchestrator, mock_db_pool):
        """Test getting user context with profile and MemoryOrchestrator"""
        from unittest.mock import AsyncMock

        from services.memory.models import MemoryContext

        # Mock database to return profile
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": "test-user",
                "name": "Test User",
                "role": "Developer",
                "department": "tech",
                "team": "backend",
                "preferred_language": "en",
                "notes": "Test notes",
                "emotional_preferences": None,
            }
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock MemoryOrchestrator
        mock_memory_orch = AsyncMock()
        mock_memory_orch.get_user_context = AsyncMock(
            return_value=MemoryContext(
                user_id="test-user",
                profile_facts=["User likes Python", "Works on backend"],
                collective_facts=["Team uses FastAPI"],
                summary="Active developer",
                counters={"conversations": 10},
                has_data=True,
            )
        )
        orchestrator._get_memory_orchestrator = AsyncMock(return_value=mock_memory_orch)

        context = await orchestrator._get_user_context("test-user")

        assert context is not None
        assert context["profile"] is not None
        assert context["profile"]["name"] == "Test User"
        assert context["facts"] == ["User likes Python", "Works on backend"]
        assert context["collective_facts"] == ["Team uses FastAPI"]
        assert context["summary"] == "Active developer"
        mock_memory_orch.get_user_context.assert_called_once_with("test-user")

    @pytest.mark.asyncio
    async def test_get_user_context_anonymous(self, orchestrator):
        """Test getting user context for anonymous user"""
        context = await orchestrator._get_user_context("anonymous")

        assert context is not None
        assert context["profile"] is None
        assert context["facts"] == []

    @pytest.mark.asyncio
    async def test_search_memory_vector_identity_intent(self, orchestrator):
        """Test _search_memory_vector is called for identity intent"""
        from unittest.mock import AsyncMock

        # Mock memory vector search
        mock_results = [
            {"text": "User memory 1", "metadata": {"userId": "test@example.com"}, "score": 0.9},
            {"text": "User memory 2", "metadata": {"userId": "test@example.com"}, "score": 0.8},
        ]
        orchestrator._search_memory_vector = AsyncMock(return_value=mock_results)

        # Mock other dependencies
        orchestrator.intent_classifier = AsyncMock()
        orchestrator.intent_classifier.classify_intent = AsyncMock(
            return_value={"category": "identity", "suggested_ai": "fast"}
        )
        orchestrator._get_user_context = AsyncMock(
            return_value={"profile": None, "history": [], "facts": []}
        )
        orchestrator._build_system_prompt = MagicMock(return_value="System prompt")
        orchestrator._send_message_with_fallback = AsyncMock(
            return_value=("Response text", "gemini-2.0-flash")
        )

        result = await orchestrator.process_query(
            query="Who am I?",
            user_id="test@example.com",
        )

        # Verify memory vector was searched for identity intent
        orchestrator._search_memory_vector.assert_called_once_with("Who am I?", "test@example.com")
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_memory_vector_not_called_for_business(self, orchestrator):
        """Test _search_memory_vector is NOT called for business intent"""
        from unittest.mock import AsyncMock

        orchestrator._search_memory_vector = AsyncMock()

        # Mock business intent
        orchestrator.intent_classifier = AsyncMock()
        orchestrator.intent_classifier.classify_intent = AsyncMock(
            return_value={"category": "business_simple", "suggested_ai": "fast"}
        )
        orchestrator._get_user_context = AsyncMock(
            return_value={"profile": None, "history": [], "facts": []}
        )
        orchestrator._build_system_prompt = MagicMock(return_value="System prompt")
        orchestrator._send_message_with_fallback = AsyncMock(
            return_value=("Response text", "gemini-2.0-flash")
        )

        result = await orchestrator.process_query(
            query="What is PT PMA?",
            user_id="test@example.com",
        )

        # Verify memory vector was NOT searched for business intent
        orchestrator._search_memory_vector.assert_not_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_profile(self, orchestrator):
        """Test building system prompt with user profile"""
        context = {
            "profile": {
                "name": "Test User",
                "role": "Developer",
                "department": "tech",
                "notes": "Test notes",
            },
            "facts": ["User prefers English"],
            "entities": {},
        }

        prompt = orchestrator._build_system_prompt("test-user", context, query="test")

        assert prompt is not None
        assert "Test User" in prompt
        assert "Developer" in prompt

    @pytest.mark.asyncio
    async def test_build_system_prompt_without_profile(self, orchestrator):
        """Test building system prompt without profile"""
        context = {"profile": None, "facts": [], "entities": {}}

        prompt = orchestrator._build_system_prompt("test-user", context, query="test")

        assert prompt is not None
        assert "Profile not found" in prompt or "new guest" in prompt

    @pytest.mark.asyncio
    async def test_process_query_basic(self, orchestrator):
        """Test processing a basic query"""
        with patch.object(
            orchestrator, "_send_message_with_fallback", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = "Test answer"

            result = await orchestrator.process_query(
                query="What is PT PMA?",
                user_id="test-user",
                conversation_history=[],
            )

            assert result is not None
            assert "answer" in result or "error" in result

    @pytest.mark.asyncio
    async def test_process_query_out_of_domain(self, orchestrator):
        """Test processing out-of-domain query"""
        result = await orchestrator.process_query(
            query="che tempo fa?",
            user_id="test-user",
            conversation_history=[],
        )

        # Should detect out-of-domain and return appropriate response
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_query_with_tool_call(self, orchestrator, mock_retriever):
        """Test processing query that triggers tool call"""
        with patch.object(
            orchestrator, "_send_message_with_fallback", new_callable=AsyncMock
        ) as mock_send:
            # Mock response that includes tool call
            mock_response = MagicMock()
            mock_response.text = "I'll search for that."
            mock_response.candidates = [
                MagicMock(
                    content=MagicMock(
                        parts=[
                            MagicMock(
                                function_call=MagicMock(
                                    name="vector_search",
                                    args={"query": "PT PMA", "collection": "legal_unified"},
                                )
                            )
                        ]
                    )
                )
            ]
            mock_send.return_value = mock_response

            result = await orchestrator.process_query(
                query="What is PT PMA?",
                user_id="test-user",
                conversation_history=[],
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_stream_query_basic(self, orchestrator):
        """Test streaming a basic query"""
        with patch.object(
            orchestrator, "_send_message_with_fallback", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = "Test streaming answer"

            chunks = []
            async for chunk in orchestrator.stream_query(
                query="What is PT PMA?",
                user_id="test-user",
                conversation_history=[],
            ):
                chunks.append(chunk)

            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_send_message_with_fallback_gemini_success(self, orchestrator):
        """Test sending message with Gemini (success)"""
        mock_response = MagicMock()
        mock_response.text = "Test response"
        orchestrator.model_flash.start_chat.return_value.send_message_async = AsyncMock(
            return_value=mock_response
        )

        result = await orchestrator._send_message_with_fallback("test message", "system prompt")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_send_message_with_fallback_openrouter(self, orchestrator):
        """Test sending message with OpenRouter fallback"""
        # Mock Gemini to raise ResourceExhausted
        orchestrator.model_flash.start_chat.return_value.send_message_async = AsyncMock(
            side_effect=ResourceExhausted("Quota exceeded")
        )

        with patch.object(
            orchestrator, "_call_openrouter", new_callable=AsyncMock
        ) as mock_openrouter:
            mock_openrouter.return_value = "OpenRouter response"

            result = await orchestrator._send_message_with_fallback("test message", "system prompt")

            assert result == "OpenRouter response"
            mock_openrouter.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_openrouter(self, orchestrator):
        """Test calling OpenRouter API"""
        with patch("services.rag.agentic.OpenRouterClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_completion = AsyncMock(
                return_value={"choices": [{"message": {"content": "OpenRouter answer"}}]}
            )
            mock_client_class.return_value = mock_client

            result = await orchestrator._call_openrouter(
                messages=[{"role": "user", "content": "test"}], system_prompt="system"
            )

            assert result is not None
            assert "OpenRouter answer" in result

    def test_tool_to_gemini_format(self, mock_retriever):
        """Test converting tool to Gemini format"""
        from services.rag.agentic import VectorSearchTool

        tool = VectorSearchTool(mock_retriever)
        gemini_tool = tool.to_gemini_tool()

        assert gemini_tool["name"] == "vector_search"
        assert "description" in gemini_tool
        assert "parameters" in gemini_tool
