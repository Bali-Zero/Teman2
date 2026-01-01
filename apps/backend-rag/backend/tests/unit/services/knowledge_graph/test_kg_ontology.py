"""
Unit tests for Knowledge Graph Ontology
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.knowledge_graph.ontology import EntityType, RelationType


class TestEntityType:
    """Tests for EntityType enum"""

    def test_entity_types_exist(self):
        """Test that entity types are defined"""
        assert hasattr(EntityType, 'PERSON')
        assert hasattr(EntityType, 'ORGANIZATION')
        assert hasattr(EntityType, 'LOCATION')
        assert hasattr(EntityType, 'DOKUMEN')  # Document in Indonesian
        assert hasattr(EntityType, 'UNDANG_UNDANG')  # Law
        assert hasattr(EntityType, 'KITAS')  # Work permit

    def test_entity_type_values(self):
        """Test entity type values"""
        assert EntityType.PERSON.value == "person"  # lowercase
        assert EntityType.ORGANIZATION.value == "organization"  # lowercase
        assert EntityType.LOCATION.value == "location"  # lowercase
        assert EntityType.DOKUMEN.value == "dokumen"
        assert EntityType.UNDANG_UNDANG.value == "undang_undang"


class TestRelationType:
    """Tests for RelationType enum"""

    def test_relation_types_exist(self):
        """Test that relation types are defined"""
        assert hasattr(RelationType, 'LOCATED_IN')
        assert hasattr(RelationType, 'REQUIRES')
        assert hasattr(RelationType, 'PART_OF')
        assert hasattr(RelationType, 'ISSUED_BY')
        assert hasattr(RelationType, 'HAS_REQUIREMENT')

    def test_relation_type_values(self):
        """Test relation type values"""
        assert RelationType.LOCATED_IN.value == "LOCATED_IN"
        assert RelationType.REQUIRES.value == "REQUIRES"
        assert RelationType.PART_OF.value == "PART_OF"
        assert RelationType.ISSUED_BY.value == "ISSUED_BY"

