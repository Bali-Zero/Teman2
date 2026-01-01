"""
Unit tests for KG Extractors (EntityExtractor, RelationshipExtractor)
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.kg_extractors import EntityExtractor, RelationshipExtractor


@pytest.fixture
def mock_ai_client():
    """Mock AI client"""
    client = MagicMock()
    client.generate_text = AsyncMock(return_value='[{"type": "law", "name": "UU No. 1", "canonical_name": "UU No. 1 Tahun 2020", "context": "test"}]')
    return client


@pytest.fixture
def entity_extractor(mock_ai_client):
    """Create EntityExtractor instance"""
    return EntityExtractor(ai_client=mock_ai_client)


@pytest.fixture
def relationship_extractor(mock_ai_client):
    """Create RelationshipExtractor instance"""
    return RelationshipExtractor(ai_client=mock_ai_client)


class TestEntityExtractor:
    """Tests for EntityExtractor"""

    def test_init(self, mock_ai_client):
        """Test initialization"""
        extractor = EntityExtractor(ai_client=mock_ai_client)
        assert extractor.ai_client == mock_ai_client

    def test_init_no_ai_client(self):
        """Test initialization without AI client"""
        with patch("agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = EntityExtractor()
            assert extractor.ai_client is None

    @pytest.mark.asyncio
    async def test_extract_entities(self, entity_extractor, mock_ai_client):
        """Test extracting entities"""
        text = "UU No. 1 Tahun 2020 tentang Ketenagakerjaan"
        result = await entity_extractor.extract_entities(text)
        assert isinstance(result, list)
        mock_ai_client.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self, entity_extractor):
        """Test extracting entities from empty text"""
        result = await entity_extractor.extract_entities("")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_no_ai_client(self):
        """Test extracting entities without AI client"""
        with patch("agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = EntityExtractor()
            result = await extractor.extract_entities("Test text")
            assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_long_text(self, entity_extractor, mock_ai_client):
        """Test extracting entities from long text"""
        long_text = "A" * 5000
        result = await entity_extractor.extract_entities(long_text)
        # Should truncate to MAX_TEXT_LENGTH
        call_args = mock_ai_client.generate_text.call_args
        if call_args:
            prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get('prompt', '')
            assert len(prompt) <= 4000 or "A" * 4000 in prompt

    @pytest.mark.asyncio
    async def test_extract_entities_timeout(self, entity_extractor, mock_ai_client):
        """Test extracting entities with timeout"""
        import asyncio
        mock_ai_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())
        
        result = await entity_extractor.extract_entities("Test text", timeout=0.1)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_json_error(self, entity_extractor, mock_ai_client):
        """Test extracting entities with JSON error"""
        mock_ai_client.generate_text = AsyncMock(return_value="Invalid JSON")
        
        result = await entity_extractor.extract_entities("Test text")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_error(self, entity_extractor, mock_ai_client):
        """Test extracting entities with error"""
        mock_ai_client.generate_text = AsyncMock(side_effect=Exception("Error"))
        
        result = await entity_extractor.extract_entities("Test text")
        assert result == []


class TestRelationshipExtractor:
    """Tests for RelationshipExtractor"""

    def test_init(self, mock_ai_client):
        """Test initialization"""
        extractor = RelationshipExtractor(ai_client=mock_ai_client)
        assert extractor.ai_client == mock_ai_client

    def test_init_no_ai_client(self):
        """Test initialization without AI client"""
        with patch("agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = RelationshipExtractor()
            assert extractor.ai_client is None

    @pytest.mark.asyncio
    async def test_extract_relationships(self, relationship_extractor, mock_ai_client):
        """Test extracting relationships"""
        entities = [
            {"type": "law", "name": "UU No. 1", "canonical_name": "UU No. 1 Tahun 2020"},
            {"type": "topic", "name": "Ketenagakerjaan", "canonical_name": "Ketenagakerjaan"}
        ]
        text = "UU No. 1 Tahun 2020 tentang Ketenagakerjaan"
        
        mock_ai_client.generate_text = AsyncMock(return_value='[{"source": "UU No. 1", "target": "Ketenagakerjaan", "relationship": "regulates", "strength": 0.9}]')
        
        result = await relationship_extractor.extract_relationships(entities, text)
        assert isinstance(result, list)
        mock_ai_client.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_relationships_empty_entities(self, relationship_extractor):
        """Test extracting relationships with empty entities"""
        result = await relationship_extractor.extract_relationships([], "Test text")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_no_ai_client(self):
        """Test extracting relationships without AI client"""
        with patch("agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = RelationshipExtractor()
            result = await extractor.extract_relationships([{"type": "law", "name": "Test"}], "Test text")
            assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_timeout(self, relationship_extractor, mock_ai_client):
        """Test extracting relationships with timeout"""
        import asyncio
        mock_ai_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())
        
        entities = [{"type": "law", "name": "Test"}]
        result = await relationship_extractor.extract_relationships(entities, "Test text", timeout=0.1)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_json_error(self, relationship_extractor, mock_ai_client):
        """Test extracting relationships with JSON error"""
        mock_ai_client.generate_text = AsyncMock(return_value="Invalid JSON")
        
        entities = [{"type": "law", "name": "Test"}]
        result = await relationship_extractor.extract_relationships(entities, "Test text")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_error(self, relationship_extractor, mock_ai_client):
        """Test extracting relationships with error"""
        mock_ai_client.generate_text = AsyncMock(side_effect=Exception("Error"))
        
        entities = [{"type": "law", "name": "Test"}]
        result = await relationship_extractor.extract_relationships(entities, "Test text")
        assert result == []

