"""
Unit tests for KnowledgeGraphBuilder
Tests knowledge graph building functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestKnowledgeGraphBuilder:
    """Unit tests for KnowledgeGraphBuilder"""

    def test_knowledge_graph_builder_init(self):
        """Test KnowledgeGraphBuilder initialization"""
        from backend.services.knowledge_graph_builder import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder()
        assert builder is not None

    def test_create_entity(self):
        """Test creating entity"""
        from backend.services.knowledge_graph_builder import Entity, EntityType

        entity = Entity(
            entity_id="kbli_56101",
            entity_type=EntityType.KBLI_CODE,
            name="Restaurant",
            description="Restaurant business",
        )

        assert entity.entity_id == "kbli_56101"
        assert entity.entity_type == EntityType.KBLI_CODE
        assert entity.name == "Restaurant"

    def test_create_relationship(self):
        """Test creating relationship"""
        from backend.services.knowledge_graph_builder import Relationship, RelationType

        relationship = Relationship(
            relationship_id="rel1",
            source_entity_id="kbli_56101",
            target_entity_id="nib",
            relationship_type=RelationType.REQUIRES,
        )

        assert relationship.source_entity_id == "kbli_56101"
        assert relationship.target_entity_id == "nib"
        assert relationship.relationship_type == RelationType.REQUIRES

    def test_entity_type_enum(self):
        """Test EntityType enum values"""
        from backend.services.knowledge_graph_builder import EntityType

        assert EntityType.KBLI_CODE == "kbli_code"
        assert EntityType.LEGAL_ENTITY == "legal_entity"
        assert EntityType.VISA_TYPE == "visa_type"

    def test_relation_type_enum(self):
        """Test RelationType enum values"""
        from backend.services.knowledge_graph_builder import RelationType

        assert RelationType.REQUIRES == "requires"
        assert RelationType.RELATED_TO == "related_to"
        assert RelationType.PART_OF == "part_of"
