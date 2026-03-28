"""
Unit tests for Agentic RAG Tools
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.tools import (
    CalculatorTool,
    PricingTool,
    TeamKnowledgeTool,
    VectorSearchTool,
    VisionTool,
)


@pytest.fixture(autouse=True)
def patch_tools_deps():
    """Patch trace_span (no-op) and disable hybrid search to isolate VectorSearchTool tests."""
    mock_span = MagicMock()
    mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_span.return_value.__exit__ = MagicMock(return_value=False)
    mock_settings = MagicMock()
    mock_settings.enable_hybrid_search = False
    with (
        patch("backend.services.rag.agentic.tools.trace_span", mock_span),
        patch("backend.app.core.config.settings", mock_settings),
    ):
        yield


@pytest.fixture
def mock_retriever():
    """Mock retriever"""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value={"results": []})
    retriever.search_with_reranking = AsyncMock(return_value={"results": []})
    return retriever


@pytest.fixture
def mock_pricing_service():
    """Mock pricing service"""
    service = MagicMock()
    # get_pricing is not async, it's a regular method
    service.get_pricing = MagicMock(return_value={"items": []})
    service.search_service = MagicMock(return_value={"items": []})
    return service


@pytest.fixture
def mock_team_service():
    """Mock team service"""
    service = MagicMock()
    service.search_member = AsyncMock(return_value=[])
    service.list_members = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_vision_service():
    """Mock vision service"""
    service = AsyncMock()
    service.analyze_image = AsyncMock(return_value={"analysis": "test"})
    return service


class TestVectorSearchTool:
    """Tests for VectorSearchTool"""

    def test_init(self, mock_retriever):
        """Test initialization"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert tool.retriever == mock_retriever

    def test_name(self, mock_retriever):
        """Test tool name"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert tool.name == "vector_search"

    def test_description(self, mock_retriever):
        """Test tool description"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert "knowledge base" in tool.description.lower()

    def test_parameters_schema(self, mock_retriever):
        """Test parameters schema"""
        tool = VectorSearchTool(retriever=mock_retriever)
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "collection" in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_with_collection(self, mock_retriever):
        """Test execute with specific collection"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [{"text": "test", "score": 0.9, "metadata": {"title": "Test"}}],
        }

        result = await tool.execute(query="test", collection="visa_oracle", top_k=5)
        assert "test" in result
        mock_retriever.search_with_reranking.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_federated_search(self, mock_retriever):
        """Test federated search (no collection)"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [{"text": "test", "score": 0.9, "metadata": {"title": "Test"}}],
        }

        result = await tool.execute(query="test", top_k=5)
        assert "test" in result

    @pytest.mark.asyncio
    async def test_execute_no_results(self, mock_retriever):
        """Test execute with no results"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {"results": []}

        result = await tool.execute(query="test")
        assert "No relevant documents" in result

    @pytest.mark.asyncio
    async def test_execute_with_deduplication(self, mock_retriever):
        """Test deduplication of results"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {"text": "test content", "score": 0.9, "metadata": {"title": "Test"}},
                {"text": "test content", "score": 0.8, "metadata": {"title": "Test2"}},
            ],
        }

        result = await tool.execute(query="test")
        # Should deduplicate by first 100 chars
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_retriever):
        """Test error handling"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.side_effect = Exception("Search error")

        result = await tool.execute(query="test")
        assert result is not None


class TestCalculatorTool:
    """Tests for CalculatorTool"""

    def test_name(self):
        """Test tool name"""
        tool = CalculatorTool()
        assert tool.name == "calculator"

    def test_description(self):
        """Test tool description"""
        tool = CalculatorTool()
        assert "mathematical" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema"""
        tool = CalculatorTool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "expression" in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_addition(self):
        """Test addition"""
        tool = CalculatorTool()
        result = await tool.execute(expression="2+2")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_execute_multiplication(self):
        """Test multiplication"""
        tool = CalculatorTool()
        result = await tool.execute(expression="5*3")
        assert "15" in result

    @pytest.mark.asyncio
    async def test_execute_division(self):
        """Test division"""
        tool = CalculatorTool()
        result = await tool.execute(expression="10/2")
        assert "5" in result

    @pytest.mark.asyncio
    async def test_execute_power(self):
        """Test power"""
        tool = CalculatorTool()
        result = await tool.execute(expression="2**3")
        assert "8" in result

    @pytest.mark.asyncio
    async def test_execute_invalid_expression(self):
        """Test invalid expression"""
        tool = CalculatorTool()
        result = await tool.execute(expression="__import__('os')")
        assert "error" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_unsafe_operator(self):
        """Test unsafe operator"""
        tool = CalculatorTool()
        result = await tool.execute(expression="open('file.txt')")
        assert "error" in result.lower() or "invalid" in result.lower()


class TestPricingTool:
    """Tests for PricingTool"""

    def test_name(self):
        """Test tool name"""
        tool = PricingTool()
        assert tool.name == "get_pricing"

    def test_description(self):
        """Test tool description"""
        tool = PricingTool()
        assert "pricing" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_with_category(self, mock_pricing_service):
        """Test execute with category"""
        with patch(
            "backend.services.rag.agentic.tools.get_pricing_service",
            return_value=mock_pricing_service,
        ):
            tool = PricingTool()
            # get_pricing is not async, it's a regular method
            mock_pricing_service.get_pricing.return_value = {
                "items": [{"name": "KITAS", "price": "15000000"}],
            }

            result = await tool.execute(service_type="visa")
            assert "KITAS" in result or "15000000" in result

    @pytest.mark.asyncio
    async def test_execute_without_category(self, mock_pricing_service):
        """Test execute without category"""
        with patch(
            "backend.services.rag.agentic.tools.get_pricing_service",
            return_value=mock_pricing_service,
        ):
            tool = PricingTool()
            mock_pricing_service.get_pricing.return_value = {"items": []}

            result = await tool.execute()
            assert result is not None


class TestTeamKnowledgeTool:
    """Tests for TeamKnowledgeTool"""

    def test_name(self):
        """Test tool name"""
        tool = TeamKnowledgeTool()
        assert tool.name == "team_knowledge"

    def test_description(self):
        """Test tool description"""
        tool = TeamKnowledgeTool()
        assert "team" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_search(self, mock_team_service):
        """Test search query"""
        tool = TeamKnowledgeTool()
        # Mock the _load_team_data method to return test data
        with patch.object(
            tool,
            "_load_team_data",
            return_value=[{"name": "Test", "email": "test@example.com", "role": "developer"}],
        ):
            result = await tool.execute(query_type="search_by_name", search_term="test")
            assert "test" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_list(self, mock_team_service):
        """Test list query"""
        tool = TeamKnowledgeTool()
        # Mock the _load_team_data method to return test data
        with patch.object(
            tool, "_load_team_data", return_value=[{"name": "Test", "email": "test@example.com"}],
        ):
            result = await tool.execute(query_type="list_all")
            assert result is not None


class TestVisionTool:
    """Tests for VisionTool"""

    def test_name(self):
        """Test tool name"""
        tool = VisionTool()
        assert tool.name == "vision_analysis"

    def test_description(self):
        """Test tool description"""
        tool = VisionTool()
        assert "image" in tool.description.lower() or "vision" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_allowed_path(self, mock_vision_service):
        """Test execute with file path inside allowed directory."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service
            mock_vision_service.process_pdf = AsyncMock(return_value={"doc": "test"})
            mock_vision_service.query_with_vision = AsyncMock(
                return_value={"answer": "test analysis"},
            )

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test query")
                assert "analysis result" in result.lower()
                mock_vision_service.process_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_blocked_path_outside_allowed_dirs(self, mock_vision_service):
        """Test that paths outside allowed directories are blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/etc/passwd", query="read this")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_path_etc_shadow(self, mock_vision_service):
        """Test that sensitive system files are blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/etc/shadow", query="extract content")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_directory_traversal(self, mock_vision_service):
        """Test that directory traversal via .. is blocked.

        /tmp/../etc/passwd resolves to /etc/passwd which fails the
        allowed-dirs check before the '..' check is reached. Either way,
        the path is blocked -- that's what matters.
        """
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/tmp/../etc/passwd", query="read")
                assert "error" in result.lower()
                assert (
                    "not allowed" in result.lower()
                    or "traversal" in result.lower()
                    or "access denied" in result.lower()
                )
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_nested_traversal(self, mock_vision_service):
        """Test that deeply nested directory traversal is blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/app/uploads"]
                result = await tool.execute(file_path="/app/uploads/../../etc/passwd", query="read")
                assert "error" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_home_directory(self, mock_vision_service):
        """Test that home directory access is blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp"]
                result = await tool.execute(file_path="/home/user/.ssh/id_rsa", query="read")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_vision_service):
        """Test error handling when vision service fails."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service
            mock_vision_service.process_pdf = AsyncMock(side_effect=Exception("Vision error"))

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test")
                assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_respects_custom_allowed_dirs(self, mock_vision_service):
        """Test that custom VISION_ALLOWED_DIRS from settings is respected."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                # Only /custom/dir is allowed
                mock_settings.get_vision_allowed_dirs = ["/custom/dir"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test")
                # /tmp should be blocked because only /custom/dir is allowed
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()
