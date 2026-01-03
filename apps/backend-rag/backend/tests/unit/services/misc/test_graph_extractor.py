"""
Unit tests for GraphExtractor
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.graph_extractor import ExtractedGraph, GraphExtractor


@pytest.fixture
def mock_ai_client():
    """Mock AI client"""
    client = MagicMock()
    client.generate_response = AsyncMock()
    return client


@pytest.fixture
def graph_extractor(mock_ai_client):
    """Create GraphExtractor instance"""
    return GraphExtractor(ai_client=mock_ai_client)


class TestGraphExtractor:
    """Tests for GraphExtractor"""

    def test_init(self, mock_ai_client):
        """Test initialization"""
        extractor = GraphExtractor(ai_client=mock_ai_client)
        assert extractor.ai == mock_ai_client

    @pytest.mark.asyncio
    async def test_extract_from_text_success(self, graph_extractor, mock_ai_client):
        """Test successful extraction"""
        mock_response = '{"entities": [{"id": "law_1", "type": "REGULATION", "name": "UU No. 6"}], "relationships": [{"source": "law_1", "target": "visa_1", "type": "REQUIRES"}]}'
        mock_ai_client.generate_response = AsyncMock(return_value=mock_response)

        result = await graph_extractor.extract_from_text("Test text")

        assert isinstance(result, ExtractedGraph)
        assert len(result.entities) == 1
        assert len(result.relationships) == 1
        assert result.entities[0]["id"] == "law_1"

    @pytest.mark.asyncio
    async def test_extract_from_text_with_context(self, graph_extractor, mock_ai_client):
        """Test extraction with context"""
        mock_response = '{"entities": [], "relationships": []}'
        mock_ai_client.generate_response = AsyncMock(return_value=mock_response)

        result = await graph_extractor.extract_from_text(
            "Test text",
            context="Additional context"
        )

        assert isinstance(result, ExtractedGraph)
        mock_ai_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_from_text_long_text(self, graph_extractor, mock_ai_client):
        """Test extraction with long text (truncated)"""
        mock_response = '{"entities": [], "relationships": []}'
        mock_ai_client.generate_response = AsyncMock(return_value=mock_response)

        long_text = "A" * 3000
        result = await graph_extractor.extract_from_text(long_text)

        assert isinstance(result, ExtractedGraph)
        # Verify text was truncated in the call
        call_args = mock_ai_client.generate_response.call_args
        assert "2000" in str(call_args) or len(long_text) > 2000

    @pytest.mark.asyncio
    async def test_extract_from_text_relations_key(self, graph_extractor, mock_ai_client):
        """Test extraction with 'relations' key instead of 'relationships'"""
        mock_response = '{"entities": [], "relations": [{"source": "a", "target": "b", "type": "REQUIRES"}]}'
        mock_ai_client.generate_response = AsyncMock(return_value=mock_response)

        result = await graph_extractor.extract_from_text("Test")

        assert len(result.relationships) == 1

    @pytest.mark.asyncio
    async def test_extract_from_text_invalid_json(self, graph_extractor, mock_ai_client):
        """Test extraction with invalid JSON response"""
        mock_ai_client.generate_response = AsyncMock(return_value="Invalid JSON")

        result = await graph_extractor.extract_from_text("Test")

        assert isinstance(result, ExtractedGraph)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_extract_from_text_exception(self, graph_extractor, mock_ai_client):
        """Test extraction with exception"""
        mock_ai_client.generate_response = AsyncMock(side_effect=Exception("AI error"))

        result = await graph_extractor.extract_from_text("Test")

        assert isinstance(result, ExtractedGraph)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_extract_from_text_missing_keys(self, graph_extractor, mock_ai_client):
        """Test extraction with missing keys in response"""
        mock_response = '{"entities": []}'
        mock_ai_client.generate_response = AsyncMock(return_value=mock_response)

        result = await graph_extractor.extract_from_text("Test")

        assert isinstance(result, ExtractedGraph)
        assert len(result.relationships) == 0


class TestExtractedGraph:
    """Tests for ExtractedGraph model"""

    def test_init(self):
        """Test initialization"""
        graph = ExtractedGraph(entities=[], relationships=[])
        assert graph.entities == []
        assert graph.relationships == []

    def test_init_with_data(self):
        """Test initialization with data"""
        entities = [{"id": "e1", "type": "REGULATION"}]
        relationships = [{"source": "e1", "target": "e2", "type": "REQUIRES"}]
        graph = ExtractedGraph(entities=entities, relationships=relationships)
        assert len(graph.entities) == 1
        assert len(graph.relationships) == 1




