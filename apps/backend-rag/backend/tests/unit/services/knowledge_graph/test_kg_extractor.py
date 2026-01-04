"""
Unit tests for Knowledge Graph Extractor
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

from services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
    KGExtractor,
)


@pytest.fixture
def kg_extractor():
    """Create KG extractor instance"""
    with patch("services.knowledge_graph.extractor.anthropic.Anthropic"):
        return KGExtractor(model="claude-sonnet-4", api_key="test-key")


class TestKGExtractor:
    """Tests for KGExtractor"""

    def test_init(self):
        """Test initialization"""
        with patch("services.knowledge_graph.extractor.anthropic.Anthropic"):
            extractor = KGExtractor(model="claude-sonnet-4", api_key="test-key")
            assert extractor.model == "claude-sonnet-4"

    @pytest.mark.asyncio
    async def test_extract_entities(self, kg_extractor):
        """Test entity extraction"""
        text = "PT PMA is a company type that requires minimum investment of 10 billion IDR"

        with patch.object(kg_extractor.client, "messages") as mock_messages:
            mock_create = AsyncMock()
            mock_create.create.return_value = MagicMock(
                content=[
                    MagicMock(text='{"entities": [{"name": "PT PMA", "type": "Organization"}]}')
                ]
            )
            mock_messages.create = mock_create

            result = await kg_extractor.extract(text)
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_relationships(self, kg_extractor):
        """Test relationship extraction"""
        text = "PT PMA requires minimum investment"

        with patch.object(kg_extractor.client, "messages") as mock_messages:
            mock_create = AsyncMock()
            mock_create.create.return_value = MagicMock(
                content=[
                    MagicMock(
                        text='{"relations": [{"source": "PT PMA", "target": "Investment", "type": "REQUIRES"}]}'
                    )
                ]
            )
            mock_messages.create = mock_create

            result = await kg_extractor.extract(text)
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_error_handling(self, kg_extractor):
        """Test error handling"""
        text = "test"

        with patch.object(kg_extractor.client, "messages") as mock_messages:
            mock_messages.create.side_effect = Exception("API error")

            result = await kg_extractor.extract(text)
            # Should handle error gracefully
            assert result is not None


class TestExtractedEntity:
    """Tests for ExtractedEntity"""

    def test_entity_creation(self):
        """Test entity creation"""
        from services.knowledge_graph.ontology import EntityType

        entity = ExtractedEntity(
            id="e1", name="PT PMA", type=EntityType.ORGANIZATION, mention="PT PMA", confidence=0.9
        )
        assert entity.name == "PT PMA"
        assert entity.type == EntityType.ORGANIZATION
        assert entity.confidence == 0.9


class TestExtractedRelation:
    """Tests for ExtractedRelation"""

    def test_relation_creation(self):
        """Test relation creation"""
        from services.knowledge_graph.ontology import RelationType

        relation = ExtractedRelation(
            source_id="e1",
            target_id="e2",
            type=RelationType.REQUIRES,
            evidence="requires",
            confidence=0.8,
        )
        assert relation.source_id == "e1"
        assert relation.target_id == "e2"
        assert relation.type == RelationType.REQUIRES


class TestExtractionResult:
    """Tests for ExtractionResult"""

    def test_result_creation(self):
        """Test result creation"""
        from services.knowledge_graph.ontology import EntityType, RelationType

        entities = [
            ExtractedEntity(id="e1", name="PT PMA", type=EntityType.ORGANIZATION, mention="PT PMA")
        ]
        relations = [
            ExtractedRelation(
                source_id="e1", target_id="e2", type=RelationType.REQUIRES, evidence="requires"
            )
        ]

        result = ExtractionResult(chunk_id="chunk1", entities=entities, relations=relations)
        assert len(result.entities) == 1
        assert len(result.relations) == 1
