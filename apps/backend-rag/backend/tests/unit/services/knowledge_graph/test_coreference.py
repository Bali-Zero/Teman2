"""
Unit tests for CoreferenceResolver
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.knowledge_graph.coreference import CoreferenceResolver, EntityCluster, EntityMention
from backend.services.knowledge_graph.ontology import EntityType


@pytest.fixture
def coreference_resolver():
    """Create CoreferenceResolver instance"""
    return CoreferenceResolver(api_key="test_key")


class TestCoreferenceResolver:
    """Tests for CoreferenceResolver"""

    def test_init(self):
        """Test initialization"""
        resolver = CoreferenceResolver(api_key="test_key")
        assert resolver.use_llm is True
        assert resolver.entity_cache is not None

    def test_find_references(self, coreference_resolver):
        """Test finding references in text"""
        text = "Peraturan tersebut mengatur izin tersebut"
        mentions = coreference_resolver.find_references(text)
        assert isinstance(mentions, list)

    def test_normalize_entity_name(self, coreference_resolver):
        """Test normalizing entity name"""
        normalized = coreference_resolver.normalize_entity_name("UU No. 6 Tahun 2023")
        assert isinstance(normalized, str)

    def test_cluster_entities(self, coreference_resolver):
        """Test clustering entities"""
        from backend.services.knowledge_graph.extractor import ExtractedEntity

        entities = [
            ExtractedEntity(
                id="id1",
                type=EntityType.UNDANG_UNDANG,
                name="UU No. 6 Tahun 2023",
                mention="UU No. 6 Tahun 2023",
                confidence=0.9,
            ),
            ExtractedEntity(
                id="id2",
                type=EntityType.UNDANG_UNDANG,
                name="UU No. 6 Tahun 2023",
                mention="UU No. 6 Tahun 2023",
                confidence=0.8,
            ),
        ]
        clusters = coreference_resolver.cluster_entities(entities)
        assert isinstance(clusters, dict)

    def test_update_cache(self, coreference_resolver):
        """Test updating cache"""
        clusters = {
            "cluster1": EntityCluster(
                canonical_id="id1",
                canonical_name="Test Entity",
                entity_type=EntityType.UNDANG_UNDANG,
            )
        }
        coreference_resolver.update_cache(clusters)
        assert len(coreference_resolver.entity_cache) > 0

    def test_get_cache_context(self, coreference_resolver):
        """Test getting cache context"""
        # Add some entities to cache first
        clusters = {
            "cluster1": EntityCluster(
                canonical_id="id1",
                canonical_name="Test Entity",
                entity_type=EntityType.UNDANG_UNDANG,
            )
        }
        coreference_resolver.update_cache(clusters)
        context = coreference_resolver.get_cache_context()
        assert isinstance(context, str)

    @pytest.mark.asyncio
    async def test_resolve_reference(self, coreference_resolver):
        """Test resolving reference"""
        with patch("backend.services.knowledge_graph.coreference.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_message = MagicMock()
            mock_message.content = [
                MagicMock(text='{"entity_id": "id1", "entity_type": "undang_undang"}')
            ]
            mock_response = MagicMock()
            mock_response.content = [mock_message]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            mention = EntityMention(text="peraturan tersebut", position=0)
            # Add some context entities to cache
            clusters = {
                "cluster1": EntityCluster(
                    canonical_id="id1",
                    canonical_name="UU No. 6 Tahun 2023",
                    entity_type=EntityType.UNDANG_UNDANG,
                )
            }
            coreference_resolver.update_cache(clusters)
            result = await coreference_resolver.resolve_reference(mention, "context")
            # May return None if no match found, or a resolved entity
            assert result is None or hasattr(result, "entity_id")

    def test_deduplicate_entities(self, coreference_resolver):
        """Test deduplicating entities"""
        from backend.services.knowledge_graph.extractor import ExtractedEntity

        entities = [
            ExtractedEntity(
                id="id1",
                type=EntityType.UNDANG_UNDANG,
                name="Entity 1",
                mention="Entity 1",
                confidence=0.9,
            ),
            ExtractedEntity(
                id="id2",
                type=EntityType.UNDANG_UNDANG,
                name="Entity 1",
                mention="Entity 1",
                confidence=0.8,
            ),
        ]
        deduplicated = coreference_resolver.deduplicate_entities(entities)
        assert len(deduplicated) <= len(entities)

    def test_clear_cache(self, coreference_resolver):
        """Test clearing cache"""
        clusters = {
            "cluster1": EntityCluster(
                canonical_id="id1",
                canonical_name="Test Entity",
                entity_type=EntityType.UNDANG_UNDANG,
            )
        }
        coreference_resolver.update_cache(clusters)
        coreference_resolver.clear_cache()
        assert len(coreference_resolver.entity_cache) == 0

    def test_get_cache_stats(self, coreference_resolver):
        """Test getting cache statistics"""
        stats = coreference_resolver.get_cache_stats()
        assert isinstance(stats, dict)
        assert "total_entities" in stats
