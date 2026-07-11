from __future__ import annotations

from backend.services.knowledge_graph.ontology import (
    ENTITY_SCHEMAS,
    RELATION_SCHEMAS,
    EntityType,
    RelationType,
    get_all_entity_types,
    get_all_relation_types,
    get_entity_type_description,
    get_extraction_schema_prompt,
)


def test_get_entity_type_description_uses_schema_when_available() -> None:
    assert (
        get_entity_type_description(EntityType.UNDANG_UNDANG)
        == ENTITY_SCHEMAS[EntityType.UNDANG_UNDANG].description
    )
    assert get_entity_type_description(EntityType.DATE) == EntityType.DATE.value


def test_get_all_entity_types_returns_complete_enum_values() -> None:
    entity_types = get_all_entity_types()

    assert EntityType.KITAS.value in entity_types
    assert EntityType.KBLI.value in entity_types
    assert len(entity_types) == len(EntityType)
    assert len(entity_types) == len(set(entity_types))


def test_get_all_relation_types_returns_complete_enum_values() -> None:
    relation_types = get_all_relation_types()

    assert RelationType.REQUIRES.value in relation_types
    assert RelationType.ISSUED_BY.value in relation_types
    assert len(relation_types) == len(RelationType)
    assert len(relation_types) == len(set(relation_types))


def test_entity_schema_preserves_patterns_examples_and_attributes() -> None:
    schema = ENTITY_SCHEMAS[EntityType.UNDANG_UNDANG]

    assert schema.type == EntityType.UNDANG_UNDANG
    assert any("UU" in pattern for pattern in schema.patterns)
    assert any("UU No. 6 Tahun 2023" in example for example in schema.examples)
    assert {"number", "year", "title"}.issubset(set(schema.attributes))


def test_relation_schema_preserves_source_target_and_trigger_words() -> None:
    schema = RELATION_SCHEMAS[RelationType.REQUIRES]

    assert schema.type == RelationType.REQUIRES
    assert EntityType.KITAS in schema.source_types
    assert EntityType.DOKUMEN in schema.target_types
    assert schema.trigger_words
    assert schema.description


def test_get_extraction_schema_prompt_includes_entity_and_relation_sections() -> None:
    prompt = get_extraction_schema_prompt()

    assert "## ENTITY TYPES" in prompt
    assert "## RELATION TYPES" in prompt
    assert "- kitas" in prompt
    assert "- REQUIRES" in prompt
    assert "Indonesian Law" in prompt
