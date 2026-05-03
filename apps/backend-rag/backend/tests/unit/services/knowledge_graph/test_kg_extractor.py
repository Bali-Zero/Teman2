"""
Unit tests for Knowledge Graph data models (S05: KGExtractor class removed)
"""

import pytest

from backend.services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.services.knowledge_graph.ontology import EntityType, RelationType


class TestDataModels:
    def test_extracted_entity(self):
        entity = ExtractedEntity(
            id="e1", type=EntityType.UNDANG_UNDANG, name="UU No. 6 Tahun 2023",
            mention="UU No 6/2023", attributes={"number": 6, "year": 2023}, confidence=0.95,
        )
        assert entity.id == "e1"
        assert entity.type == EntityType.UNDANG_UNDANG
        assert entity.confidence == 0.95

    def test_extracted_entity_defaults(self):
        entity = ExtractedEntity(id="e1", type=EntityType.NIB, name="NIB", mention="NIB")
        assert entity.confidence == 0.8
        assert entity.attributes == {}
        assert entity.start_pos is None

    def test_extracted_relation(self):
        rel = ExtractedRelation(
            source_id="e1", target_id="e2", type=RelationType.REQUIRES,
            evidence="PT PMA wajib memiliki NIB", confidence=0.9,
        )
        assert rel.source_id == "e1"
        assert rel.type == RelationType.REQUIRES

    def test_extraction_result(self):
        result = ExtractionResult(chunk_id="chunk1", raw_text="test")
        assert result.entities == []
        assert result.relations == []
        assert result.metadata == {}
