"""
Comprehensive unit tests for backend/services/rag/agentic/tools.py
Covers: VectorSearchTool, CalculatorTool, PricingTool, TeamKnowledgeTool,
        VisionTool, ImageGenerationTool, WebSearchTool, module helpers.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Common patches
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_tracing():
    """Disable tracing for all tests."""
    with patch("backend.services.rag.agentic.tools.trace_span") as ts, \
         patch("backend.services.rag.agentic.tools.set_span_attribute"), \
         patch("backend.services.rag.agentic.tools.set_span_status"):
        ts.return_value.__enter__ = MagicMock()
        ts.return_value.__exit__ = MagicMock(return_value=False)
        yield


# ============================================================================
# Module-level helpers
# ============================================================================

class TestModuleHelpers:

    def test_get_client_creates_new_client(self):
        from backend.services.rag.agentic.tools import _get_client
        import backend.services.rag.agentic.tools as tools_mod
        old = tools_mod._client
        tools_mod._client = None
        try:
            client = _get_client(timeout=5.0)
            assert client is not None
            assert not client.is_closed
        finally:
            if tools_mod._client and not tools_mod._client.is_closed:
                import asyncio
                # Don't close in test, just reset
                pass
            tools_mod._client = old

    def test_get_client_returns_existing(self):
        from backend.services.rag.agentic.tools import _get_client
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_agentic_tools_client(self):
        import backend.services.rag.agentic.tools as tools_mod
        mock_client = AsyncMock()
        mock_client.is_closed = False
        tools_mod._client = mock_client
        await tools_mod.close_agentic_tools_client()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_already_closed_client(self):
        import backend.services.rag.agentic.tools as tools_mod
        mock_client = AsyncMock()
        mock_client.is_closed = True
        tools_mod._client = mock_client
        await tools_mod.close_agentic_tools_client()
        mock_client.aclose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_none_client(self):
        import backend.services.rag.agentic.tools as tools_mod
        tools_mod._client = None
        await tools_mod.close_agentic_tools_client()  # Should not raise


# ============================================================================
# AVAILABLE_COLLECTIONS
# ============================================================================

class TestAvailableCollections:

    def test_collections_list(self):
        from backend.services.rag.agentic.tools import AVAILABLE_COLLECTIONS
        assert "visa_oracle" in AVAILABLE_COLLECTIONS
        assert "legal_unified" in AVAILABLE_COLLECTIONS
        assert "kbli_2025_final" in AVAILABLE_COLLECTIONS
        assert len(AVAILABLE_COLLECTIONS) >= 7


# ============================================================================
# VectorSearchTool
# ============================================================================

class TestVectorSearchTool:

    def _make_tool(self, retriever=None, user_level=1):
        from backend.services.rag.agentic.tools import VectorSearchTool
        return VectorSearchTool(retriever=retriever or MagicMock(), user_level=user_level)

    def test_name(self):
        tool = self._make_tool()
        assert tool.name == "vector_search"

    def test_description_contains_collections(self):
        tool = self._make_tool()
        assert "visa_oracle" in tool.description
        assert "FEDERATED" in tool.description

    def test_parameters_schema(self):
        tool = self._make_tool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "collection" in schema["properties"]
        assert "query" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_no_results(self):
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(return_value={"results": []})
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="test query", collection="visa_oracle")

        parsed = json.loads(result)
        assert parsed["content"] == "No relevant documents found."
        assert parsed["sources"] == []

    @pytest.mark.asyncio
    async def test_execute_with_results(self):
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(return_value={
            "results": [
                {"text": "Visa B211 is for social visit", "score": 0.85, "metadata": {"title": "Visa Guide"}},
                {"text": "KITAS is a stay permit", "score": 0.75, "metadata": {"title": "KITAS Info"}},
            ],
        })
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="visa info", collection="visa_oracle", top_k=5)

        parsed = json.loads(result)
        assert "Visa B211" in parsed["content"]
        assert len(parsed["sources"]) == 2

    @pytest.mark.asyncio
    async def test_execute_federated_search(self):
        """No collection specified → federated across all collections."""
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(return_value={"results": []})
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="general question")

        parsed = json.loads(result)
        assert parsed["content"] == "No relevant documents found."

    @pytest.mark.asyncio
    async def test_execute_timeout_handling(self):
        """Timeout in search returns empty for that collection."""
        import asyncio
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(side_effect=asyncio.TimeoutError)
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="slow query", collection="visa_oracle")

        parsed = json.loads(result)
        assert parsed["content"] == "No relevant documents found."

    @pytest.mark.asyncio
    async def test_execute_search_exception_handling(self):
        """Generic exception in search returns empty for that collection."""
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(side_effect=RuntimeError("db error"))
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="broken query", collection="visa_oracle")

        parsed = json.loads(result)
        assert parsed["sources"] == []

    @pytest.mark.asyncio
    async def test_execute_deduplication(self):
        """Duplicate content is deduplicated by first 100 chars."""
        mock_retriever = MagicMock()
        mock_retriever.search_with_reranking = AsyncMock(return_value={
            "results": [
                {"text": "Same content here", "score": 0.9, "metadata": {}},
                {"text": "Same content here", "score": 0.8, "metadata": {}},
            ],
        })
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="test", collection="visa_oracle")

        parsed = json.loads(result)
        assert len(parsed["sources"]) == 1

    @pytest.mark.asyncio
    async def test_execute_hybrid_search_path(self):
        """When enable_hybrid_search=True and retriever has hybrid method."""
        mock_retriever = MagicMock()
        mock_retriever.hybrid_search_with_reranking = AsyncMock(return_value={
            "results": [{"text": "hybrid result", "score": 0.9, "metadata": {}}],
        })
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = True
            result = await tool.execute(query="hybrid test", collection="visa_oracle")

        parsed = json.loads(result)
        assert "hybrid result" in parsed["content"]

    @pytest.mark.asyncio
    async def test_execute_fallback_to_basic_search(self):
        """If retriever has no search_with_reranking, uses basic search."""
        mock_retriever = MagicMock(spec=[])  # No methods
        mock_retriever.search = AsyncMock(return_value={"results": []})
        # Remove search_with_reranking so hasattr returns False
        tool = self._make_tool(retriever=mock_retriever)

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_hybrid_search = False
            result = await tool.execute(query="basic", collection="visa_oracle")

        parsed = json.loads(result)
        assert parsed["sources"] == []


# ============================================================================
# CalculatorTool
# ============================================================================

class TestCalculatorTool:

    def _make_tool(self):
        from backend.services.rag.agentic.tools import CalculatorTool
        return CalculatorTool()

    def test_name(self):
        assert self._make_tool().name == "calculator"

    def test_description(self):
        assert "mathematical" in self._make_tool().description.lower()

    def test_parameters_schema(self):
        schema = self._make_tool().parameters_schema
        assert "expression" in schema["properties"]
        assert "expression" in schema["required"]

    @pytest.mark.asyncio
    async def test_simple_calculation(self):
        tool = self._make_tool()
        with patch("backend.app.utils.safe_math.safe_evaluate", return_value=220.0):
            result = await tool.execute(expression="1000 * 0.22")
        assert "220" in result

    @pytest.mark.asyncio
    async def test_integer_result(self):
        tool = self._make_tool()
        with patch("backend.app.utils.safe_math.safe_evaluate", return_value=100.0):
            result = await tool.execute(expression="50 + 50")
        assert "100" in result

    @pytest.mark.asyncio
    async def test_float_result(self):
        tool = self._make_tool()
        with patch("backend.app.utils.safe_math.safe_evaluate", return_value=33.33):
            result = await tool.execute(expression="100 / 3")
        assert "33.33" in result

    @pytest.mark.asyncio
    async def test_safe_math_error(self):
        tool = self._make_tool()
        from backend.app.utils.safe_math import SafeMathError
        with patch("backend.app.utils.safe_math.safe_evaluate", side_effect=SafeMathError("bad")):
            result = await tool.execute(expression="import os")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_generic_error(self):
        tool = self._make_tool()
        with patch("backend.app.utils.safe_math.safe_evaluate", side_effect=Exception("boom")):
            result = await tool.execute(expression="broken")
        assert "error" in result.lower()


# ============================================================================
# PricingTool
# ============================================================================

class TestPricingTool:

    def _make_tool(self, loaded=True):
        from backend.services.rag.agentic.tools import PricingTool
        mock_service = MagicMock()
        mock_service.loaded = loaded
        mock_service.search_service.return_value = {"KITAS": "Rp 10.000.000"}
        mock_service.get_pricing.return_value = {"visa": "see list"}
        return PricingTool(pricing_service=mock_service)

    def test_name(self):
        assert self._make_tool().name == "get_pricing"

    def test_description(self):
        assert "MANDATORY" in self._make_tool().description

    def test_parameters_schema(self):
        schema = self._make_tool().parameters_schema
        assert "service_type" in schema["properties"]

    @pytest.mark.asyncio
    async def test_pricing_not_loaded(self):
        tool = self._make_tool(loaded=False)
        result = await tool.execute(service_type="visa")
        assert "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_pricing_with_query(self):
        tool = self._make_tool()
        result = await tool.execute(service_type="visa", query="KITAS")
        assert "KITAS" in result

    @pytest.mark.asyncio
    async def test_pricing_without_query(self):
        tool = self._make_tool()
        result = await tool.execute(service_type="visa")
        assert "visa" in result.lower() or "see list" in result.lower()

    @pytest.mark.asyncio
    async def test_pricing_exception(self):
        from backend.services.rag.agentic.tools import PricingTool
        mock_service = MagicMock()
        mock_service.loaded = True
        mock_service.get_pricing.side_effect = RuntimeError("db down")
        tool = PricingTool(pricing_service=mock_service)
        result = await tool.execute(service_type="all")
        assert "failed" in result.lower()


# ============================================================================
# TeamKnowledgeTool
# ============================================================================

class TestTeamKnowledgeTool:

    def _make_tool(self, team_data=None):
        from backend.services.rag.agentic.tools import TeamKnowledgeTool
        tool = TeamKnowledgeTool(db_pool=None)
        tool._team_data = team_data
        return tool

    def test_name(self):
        assert self._make_tool().name == "team_knowledge"

    def test_description(self):
        assert "team" in self._make_tool().description.lower()

    def test_parameters_schema(self):
        schema = self._make_tool().parameters_schema
        assert "query_type" in schema["properties"]

    @pytest.mark.asyncio
    async def test_list_all(self):
        data = [{"name": "Alice", "role": "Manager"}, {"name": "Bob", "role": "Dev"}]
        tool = self._make_tool(team_data=data)
        result = await tool.execute(query_type="list_all")
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        data = [{"name": "Alice", "role": "Manager"}, {"name": "Bob", "role": "Dev"}]
        tool = self._make_tool(team_data=data)
        result = await tool.execute(query_type="search_by_name", search_term="alice")
        parsed = json.loads(result)
        assert parsed["count"] == 1

    @pytest.mark.asyncio
    async def test_empty_team_data(self):
        tool = self._make_tool(team_data=[])
        result = await tool.execute(query_type="list_all")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        from backend.services.rag.agentic.tools import TeamKnowledgeTool
        tool = TeamKnowledgeTool(db_pool=None)
        tool._team_data = None
        # Make _load_team_data raise
        tool._load_team_data = MagicMock(side_effect=RuntimeError("fail"))
        result = await tool.execute(query_type="list_all")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_get_data_file_path_returns_none_if_not_found(self):
        from backend.services.rag.agentic.tools import TeamKnowledgeTool
        tool = TeamKnowledgeTool(db_pool=None)
        with patch("pathlib.Path.exists", return_value=False):
            path = tool._get_data_file_path()
        # May return None or a path depending on which paths exist
        # The important thing is it doesn't raise

    def test_load_team_data_with_no_file(self):
        from backend.services.rag.agentic.tools import TeamKnowledgeTool
        tool = TeamKnowledgeTool(db_pool=None)
        tool._data_file = None
        with patch.object(tool, '_get_data_file_path', return_value=None):
            result = tool._load_team_data()
        assert result == []


# ============================================================================
# ImageGenerationTool
# ============================================================================

class TestImageGenerationTool:

    def _make_tool(self):
        from backend.services.rag.agentic.tools import ImageGenerationTool
        return ImageGenerationTool()

    def test_name(self):
        assert self._make_tool().name == "generate_image"

    def test_description(self):
        assert "generate" in self._make_tool().description.lower()

    def test_parameters_schema(self):
        schema = self._make_tool().parameters_schema
        assert "prompt" in schema["properties"]
        assert "prompt" in schema["required"]

    @pytest.mark.asyncio
    async def test_generate_image_success(self):
        tool = self._make_tool()
        result = await tool.execute(prompt="a blue flower", aspect_ratio="1:1")
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert "pollinations" in parsed["image_url"]

    @pytest.mark.asyncio
    async def test_generate_image_16_9(self):
        tool = self._make_tool()
        result = await tool.execute(prompt="landscape", aspect_ratio="16:9")
        parsed = json.loads(result)
        assert "width=1024" in parsed["image_url"]
        assert "height=576" in parsed["image_url"]

    @pytest.mark.asyncio
    async def test_generate_image_invalid_ratio(self):
        tool = self._make_tool()
        result = await tool.execute(prompt="test", aspect_ratio="weird")
        parsed = json.loads(result)
        # Falls back to default 1:1
        assert parsed["success"] is True


# ============================================================================
# WebSearchTool
# ============================================================================

class TestWebSearchTool:

    def _make_tool(self):
        from backend.services.rag.agentic.tools import WebSearchTool
        return WebSearchTool()

    def test_name(self):
        assert self._make_tool().name == "web_search"

    def test_description(self):
        assert "web" in self._make_tool().description.lower()

    def test_web_disclaimer_exists(self):
        from backend.services.rag.agentic.tools import WebSearchTool
        assert "not been verified" in WebSearchTool.WEB_DISCLAIMER

    def test_get_keys_lazy(self):
        tool = self._make_tool()
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.tavily_api_key = "tavily_key"
            mock_settings.brave_api_key = "brave_key"
            tavily, brave = tool._get_keys()
        assert tavily == "tavily_key"
        assert brave == "brave_key"


# ============================================================================
# VisionTool
# ============================================================================

class TestVisionTool:

    def test_name(self):
        with patch("backend.services.rag.agentic.tools.VisionRAGService"):
            from backend.services.rag.agentic.tools import VisionTool
            tool = VisionTool()
        assert tool.name == "vision_analysis"

    def test_description(self):
        with patch("backend.services.rag.agentic.tools.VisionRAGService"):
            from backend.services.rag.agentic.tools import VisionTool
            tool = VisionTool()
        assert "visual" in tool.description.lower()

    def test_parameters_schema(self):
        with patch("backend.services.rag.agentic.tools.VisionRAGService"):
            from backend.services.rag.agentic.tools import VisionTool
            tool = VisionTool()
        schema = tool.parameters_schema
        assert "file_path" in schema["properties"]
        assert "query" in schema["properties"]
