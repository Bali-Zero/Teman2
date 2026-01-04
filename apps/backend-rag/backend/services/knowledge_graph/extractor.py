"""
LLM-based Knowledge Graph Extractor
Uses Claude/GPT for entity and relation extraction from Indonesian legal documents

Based on:
- KGGen (Stanford, NeurIPS 2025)
- CORE-KG (arXiv 2025) for legal documents
- LLM-IE best practices
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .ontology import (
    ENTITY_SCHEMAS,
    RELATION_SCHEMAS,
    EntityType,
    RelationType,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Extracted entity from text"""

    id: str
    type: EntityType
    name: str
    mention: str  # Original text mention
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    start_pos: int | None = None
    end_pos: int | None = None


@dataclass
class ExtractedRelation:
    """Extracted relation between entities"""

    source_id: str
    target_id: str
    type: RelationType
    evidence: str  # Text evidence for relation
    confidence: float = 0.7
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of extraction from a chunk"""

    chunk_id: str
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class KGExtractor:
    """
    LLM-based Knowledge Graph Extractor

    Uses a two-stage approach:
    1. Entity Extraction: Extract entities with types and attributes
    2. Relation Extraction: Extract relations given entities

    Follows best practices from KGGen and CORE-KG papers.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,  # Low temperature for consistency
    ):
        """
        Initialize KG Extractor

        Args:
            model: Claude model to use
            api_key: Anthropic API key (defaults to env)
            max_tokens: Max tokens for response
            temperature: Temperature for generation (low for consistency)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        # Build schema prompt
        self.schema_prompt = self._build_schema_prompt()

        logger.info(f"KGExtractor initialized with model={model}")

    def _build_schema_prompt(self) -> str:
        """Build the schema description for prompts"""
        entity_types = []
        for et, schema in ENTITY_SCHEMAS.items():
            examples = ", ".join(schema.examples[:2]) if schema.examples else ""
            entity_types.append(f"  - {et.value}: {schema.description} (e.g., {examples})")

        relation_types = []
        for rt, schema in RELATION_SCHEMAS.items():
            triggers = ", ".join(schema.trigger_words[:3]) if schema.trigger_words else ""
            relation_types.append(f"  - {rt.value}: {schema.description} [triggers: {triggers}]")

        return f"""
## ENTITY TYPES (Indonesian Legal Domain)
{chr(10).join(entity_types)}

## RELATION TYPES
{chr(10).join(relation_types)}
"""

    def _build_entity_extraction_prompt(self, text: str) -> str:
        """Build prompt for entity extraction"""
        return f"""You are an expert in Indonesian law and legal document analysis.
Extract all entities from the following Indonesian legal text.

{self.schema_prompt}

## INSTRUCTIONS
1. Extract ALL entities matching the types above
2. For each entity, provide:
   - id: unique identifier (e.g., "e1", "e2")
   - type: entity type from the schema
   - name: canonical/normalized name
   - mention: exact text as it appears
   - attributes: relevant attributes (number, year, etc.)
   - confidence: 0.0-1.0

3. Be comprehensive - extract every regulation, permit, institution mentioned
4. Normalize names (e.g., "UU No 6/2023" -> "UU No. 6 Tahun 2023")
5. For regulations, always extract number and year as attributes

## TEXT TO ANALYZE
{text}

## OUTPUT FORMAT (JSON)
Return a JSON object with an "entities" array:
```json
{{
  "entities": [
    {{
      "id": "e1",
      "type": "undang_undang",
      "name": "UU No. 6 Tahun 2023",
      "mention": "UU No 6/2023",
      "attributes": {{"number": 6, "year": 2023, "about": "Cipta Kerja"}},
      "confidence": 0.95
    }}
  ]
}}
```

Extract entities now:"""

    def _build_relation_extraction_prompt(self, text: str, entities: list[ExtractedEntity]) -> str:
        """Build prompt for relation extraction given entities"""
        entity_list = []
        for e in entities:
            entity_list.append(f"  - {e.id}: [{e.type.value}] {e.name}")

        return f"""You are an expert in Indonesian law and legal document analysis.
Given the extracted entities, identify all relationships between them.

{self.schema_prompt}

## EXTRACTED ENTITIES
{chr(10).join(entity_list)}

## INSTRUCTIONS
1. Identify relationships between the entities above
2. For each relation, provide:
   - source_id: ID of source entity
   - target_id: ID of target entity
   - type: relation type from schema
   - evidence: text that supports this relation
   - confidence: 0.0-1.0

3. Look for:
   - Requirements (REQUIRES, PREREQUISITE_FOR)
   - Issuance (ISSUED_BY)
   - Legal hierarchy (IMPLEMENTS, AMENDS, REFERENCES)
   - Procedures (HAS_PROCEDURE, HAS_FEE, HAS_DURATION)
   - Applicability (APPLIES_TO)
   - Sanctions (PENALTY_FOR)

4. Only extract relations with clear textual evidence

## TEXT
{text}

## OUTPUT FORMAT (JSON)
Return a JSON object with a "relations" array:
```json
{{
  "relations": [
    {{
      "source_id": "e1",
      "target_id": "e2",
      "type": "REQUIRES",
      "evidence": "PT PMA wajib memiliki NIB",
      "confidence": 0.9
    }}
  ]
}}
```

Extract relations now:"""

    def _build_combined_extraction_prompt(self, text: str) -> str:
        """Build prompt for combined entity and relation extraction"""
        return f"""You are an expert in Indonesian law and legal document analysis.
Extract all entities AND relationships from the following Indonesian legal text.

{self.schema_prompt}

## INSTRUCTIONS

### Entity Extraction:
1. Extract ALL entities matching the types above
2. For each entity provide: id, type, name, mention, attributes, confidence
3. Normalize names (e.g., "UU No 6/2023" -> "UU No. 6 Tahun 2023")
4. For regulations, extract number and year as attributes

### Relation Extraction:
1. Identify relationships between extracted entities
2. For each relation provide: source_id, target_id, type, evidence, confidence
3. Only include relations with clear textual evidence

## TEXT TO ANALYZE
{text}

## OUTPUT FORMAT (JSON)
```json
{{
  "entities": [
    {{
      "id": "e1",
      "type": "undang_undang",
      "name": "UU No. 6 Tahun 2023",
      "mention": "UU No 6/2023",
      "attributes": {{"number": 6, "year": 2023}},
      "confidence": 0.95
    }},
    {{
      "id": "e2",
      "type": "nib",
      "name": "NIB",
      "mention": "NIB",
      "attributes": {{}},
      "confidence": 0.9
    }}
  ],
  "relations": [
    {{
      "source_id": "e1",
      "target_id": "e2",
      "type": "REFERENCES",
      "evidence": "sebagaimana dimaksud dalam",
      "confidence": 0.85
    }}
  ]
}}
```

Extract entities and relations now:"""

    async def extract_entities(self, text: str) -> list[ExtractedEntity]:
        """
        Extract entities from text using LLM

        Args:
            text: Text to extract from

        Returns:
            List of extracted entities
        """
        if not text or len(text.strip()) < 10:
            return []

        prompt = self._build_entity_extraction_prompt(text)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Parse JSON from response
            entities = self._parse_entities_response(content)
            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    async def extract_relations(
        self, text: str, entities: list[ExtractedEntity]
    ) -> list[ExtractedRelation]:
        """
        Extract relations given entities

        Args:
            text: Original text
            entities: Previously extracted entities

        Returns:
            List of extracted relations
        """
        if not entities or len(entities) < 2:
            return []

        prompt = self._build_relation_extraction_prompt(text, entities)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            relations = self._parse_relations_response(content)
            return relations

        except Exception as e:
            logger.error(f"Relation extraction failed: {e}")
            return []

    async def extract(
        self, text: str, chunk_id: str = "", two_stage: bool = False
    ) -> ExtractionResult:
        """
        Extract entities and relations from text

        Args:
            text: Text to extract from
            chunk_id: ID of the chunk
            two_stage: If True, use two-stage extraction (more accurate but slower)

        Returns:
            ExtractionResult with entities and relations
        """
        if not text or len(text.strip()) < 10:
            return ExtractionResult(chunk_id=chunk_id, raw_text=text)

        if two_stage:
            # Two-stage extraction: entities first, then relations
            entities = await self.extract_entities(text)
            relations = await self.extract_relations(text, entities) if entities else []
        else:
            # Combined extraction (faster, single LLM call)
            entities, relations = await self._extract_combined(text)

        return ExtractionResult(
            chunk_id=chunk_id,
            entities=entities,
            relations=relations,
            raw_text=text,
        )

    async def _extract_combined(
        self, text: str
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """Combined entity and relation extraction in single LLM call"""
        prompt = self._build_combined_extraction_prompt(text)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Parse JSON
            json_match = re.search(r"\{[\s\S]*\}", content)
            if not json_match:
                logger.warning("No JSON found in response")
                return [], []

            data = json.loads(json_match.group())

            entities = self._parse_entities_from_data(data.get("entities", []))
            relations = self._parse_relations_from_data(data.get("relations", []))

            return entities, relations

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return [], []
        except Exception as e:
            logger.error(f"Combined extraction failed: {e}")
            return [], []

    def _parse_entities_response(self, content: str) -> list[ExtractedEntity]:
        """Parse entities from LLM response"""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", content)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            return self._parse_entities_from_data(data.get("entities", []))

        except json.JSONDecodeError:
            logger.warning("Failed to parse entities JSON")
            return []

    def _parse_entities_from_data(self, entities_data: list) -> list[ExtractedEntity]:
        """Parse entity data into ExtractedEntity objects"""
        entities = []
        for e in entities_data:
            try:
                # Map string type to EntityType enum
                type_str = e.get("type", "").lower()
                entity_type = None
                for et in EntityType:
                    if et.value == type_str:
                        entity_type = et
                        break

                if not entity_type:
                    # Try partial match
                    for et in EntityType:
                        if type_str in et.value or et.value in type_str:
                            entity_type = et
                            break

                if not entity_type:
                    logger.debug(f"Unknown entity type: {type_str}")
                    continue

                entities.append(
                    ExtractedEntity(
                        id=e.get("id", f"e{len(entities) + 1}"),
                        type=entity_type,
                        name=e.get("name", ""),
                        mention=e.get("mention", e.get("name", "")),
                        attributes=e.get("attributes", {}),
                        confidence=float(e.get("confidence", 0.8)),
                    )
                )
            except Exception as ex:
                logger.debug(f"Failed to parse entity: {ex}")

        return entities

    def _parse_relations_response(self, content: str) -> list[ExtractedRelation]:
        """Parse relations from LLM response"""
        try:
            json_match = re.search(r"\{[\s\S]*\}", content)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            return self._parse_relations_from_data(data.get("relations", []))

        except json.JSONDecodeError:
            logger.warning("Failed to parse relations JSON")
            return []

    def _parse_relations_from_data(self, relations_data: list) -> list[ExtractedRelation]:
        """Parse relation data into ExtractedRelation objects"""
        relations = []
        for r in relations_data:
            try:
                # Map string type to RelationType enum
                type_str = r.get("type", "").upper()
                rel_type = None
                for rt in RelationType:
                    if rt.value == type_str:
                        rel_type = rt
                        break

                if not rel_type:
                    logger.debug(f"Unknown relation type: {type_str}")
                    continue

                relations.append(
                    ExtractedRelation(
                        source_id=r.get("source_id", ""),
                        target_id=r.get("target_id", ""),
                        type=rel_type,
                        evidence=r.get("evidence", ""),
                        confidence=float(r.get("confidence", 0.7)),
                        attributes=r.get("attributes", {}),
                    )
                )
            except Exception as ex:
                logger.debug(f"Failed to parse relation: {ex}")

        return relations

    async def extract_batch(
        self,
        texts: list[tuple[str, str]],  # List of (chunk_id, text)
        batch_size: int = 5,
    ) -> list[ExtractionResult]:
        """
        Extract from multiple texts

        Args:
            texts: List of (chunk_id, text) tuples
            batch_size: Not used for API calls, just for logging

        Returns:
            List of ExtractionResults
        """
        results = []
        for i, (chunk_id, text) in enumerate(texts):
            result = await self.extract(text, chunk_id)
            results.append(result)

            if (i + 1) % batch_size == 0:
                logger.info(f"Processed {i + 1}/{len(texts)} chunks")

        return results
