from __future__ import annotations

from backend.services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.services.knowledge_graph.ontology import EntityType, RelationType


def test_extracted_entity_defaults_and_custom_fields_are_preserved() -> None:
    entity = ExtractedEntity(
        id="e1",
        type=EntityType.KITAS,
        name="KITAS",
        mention="KITAS investor",
        attributes={"category": "immigration"},
        start_pos=10,
        end_pos=23,
    )

    assert entity.id == "e1"
    assert entity.type == EntityType.KITAS
    assert entity.confidence == 0.8
    assert entity.attributes == {"category": "immigration"}
    assert entity.start_pos == 10
    assert entity.end_pos == 23


def test_extracted_entity_uses_independent_default_attribute_dicts() -> None:
    first = ExtractedEntity("e1", EntityType.NIB, "NIB", "NIB")
    second = ExtractedEntity("e2", EntityType.OSS, "OSS", "OSS")

    first.attributes["issuer"] = "OSS"

    assert second.attributes == {}


def test_extracted_relation_defaults_and_attributes_are_preserved() -> None:
    relation = ExtractedRelation(
        source_id="kitas",
        target_id="passport",
        type=RelationType.REQUIRES,
        evidence="KITAS requires passport copy",
        attributes={"source": "article"},
    )

    assert relation.source_id == "kitas"
    assert relation.target_id == "passport"
    assert relation.type == RelationType.REQUIRES
    assert relation.confidence == 0.7
    assert relation.attributes == {"source": "article"}


def test_extraction_result_defaults_are_independent() -> None:
    first = ExtractionResult(chunk_id="chunk-1")
    second = ExtractionResult(chunk_id="chunk-2")

    first.entities.append(ExtractedEntity("e1", EntityType.KITAS, "KITAS", "KITAS"))
    first.relations.append(
        ExtractedRelation("e1", "e2", RelationType.REQUIRES, "KITAS requires sponsor"),
    )
    first.metadata["source"] = "visa"

    assert second.entities == []
    assert second.relations == []
    assert second.metadata == {}


def test_extraction_result_can_hold_full_chunk_payload() -> None:
    entity = ExtractedEntity("e1", EntityType.KBLI, "62010", "KBLI 62010")
    relation = ExtractedRelation("e1", "sector", RelationType.BELONGS_TO, "KBLI belongs to ICT")

    result = ExtractionResult(
        chunk_id="chunk-1",
        entities=[entity],
        relations=[relation],
        raw_text="KBLI 62010 belongs to ICT sector.",
        metadata={"collection": "kbli_2025_final"},
    )

    assert result.chunk_id == "chunk-1"
    assert result.entities == [entity]
    assert result.relations == [relation]
    assert result.raw_text.startswith("KBLI 62010")
    assert result.metadata == {"collection": "kbli_2025_final"}
