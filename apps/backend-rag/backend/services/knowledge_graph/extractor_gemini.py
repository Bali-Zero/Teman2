"""
Gemini-based Knowledge Graph Extractor
Uses Google AI Studio for entity and relation extraction from Indonesian legal documents

Cost-effective alternative to Claude (~50x cheaper with Flash)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from google import genai

from .ontology import (
    EntityType,
    RelationType,
    ENTITY_SCHEMAS,
    RELATION_SCHEMAS,
)
from .extractor import ExtractedEntity, ExtractedRelation, ExtractionResult

logger = logging.getLogger(__name__)


class GeminiKGExtractor:
    """
    Gemini-based Knowledge Graph Extractor

    Uses Google's Gemini models via Google AI Studio for fast, cost-effective extraction.
    Gemini Flash is recommended for structured extraction tasks.
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        """
        Initialize Gemini KG Extractor with Google AI Studio

        Args:
            model: Gemini model to use (gemini-2.0-flash, gemini-2.5-flash, etc.)
            api_key: Google AI Studio API key (or GOOGLE_API_KEY / GOOGLE_IMAGEN_API_KEY env var)
            max_tokens: Max tokens for response
            temperature: Temperature for generation
        """
        self.model_name = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Get API key from env or parameter
        api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_IMAGEN_API_KEY")
        )

        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GOOGLE_IMAGEN_API_KEY not set")

        # Initialize client
        self.client = genai.Client(api_key=api_key)

        # Build schema prompt
        self.schema_prompt = self._build_schema_prompt()

        logger.info(f"GeminiKGExtractor initialized with Google AI Studio: model={model}")

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

    def _build_extraction_prompt(self, text: str) -> str:
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

## OUTPUT FORMAT
Return a JSON object with this exact structure:
{{
  "entities": [
    {{
      "id": "e1",
      "type": "undang_undang",
      "name": "UU No. 6 Tahun 2023",
      "mention": "UU No 6/2023",
      "attributes": {{"number": 6, "year": 2023}},
      "confidence": 0.95
    }}
  ],
  "relations": [
    {{
      "source_id": "e1",
      "target_id": "e2",
      "type": "REQUIRES",
      "evidence": "wajib memiliki",
      "confidence": 0.9
    }}
  ]
}}

Extract entities and relations now:"""

    async def extract(
        self, text: str, chunk_id: str = "", two_stage: bool = False
    ) -> ExtractionResult:
        """
        Extract entities and relations from text

        Args:
            text: Text to extract from
            chunk_id: ID of the chunk
            two_stage: Ignored for Gemini (always uses single-stage extraction)

        Returns:
            ExtractionResult with entities and relations
        """
        if not text or len(text.strip()) < 10:
            return ExtractionResult(chunk_id=chunk_id, raw_text=text)

        prompt = self._build_extraction_prompt(text)

        try:
            # Generate content with JSON mode
            import asyncio
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            content = response.text

            # Parse JSON from response
            try:
                # Try direct JSON parse first
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r"\{[\s\S]*\}", content)
                if not json_match:
                    logger.warning(f"No JSON found in response for chunk {chunk_id}")
                    return ExtractionResult(chunk_id=chunk_id, raw_text=text)
                data = json.loads(json_match.group())

            entities = self._parse_entities(data.get("entities", []))
            relations = self._parse_relations(data.get("relations", []))

            return ExtractionResult(
                chunk_id=chunk_id,
                entities=entities,
                relations=relations,
                raw_text=text,
            )

        except Exception as e:
            logger.error(f"Gemini extraction failed for chunk {chunk_id}: {e}")
            return ExtractionResult(chunk_id=chunk_id, raw_text=text)

    def _parse_entities(self, entities_data: list) -> list[ExtractedEntity]:
        """Parse entity data into ExtractedEntity objects"""
        entities = []
        for e in entities_data:
            try:
                type_str = e.get("type", "").lower()
                entity_type = None
                for et in EntityType:
                    if et.value == type_str:
                        entity_type = et
                        break

                if not entity_type:
                    for et in EntityType:
                        if type_str in et.value or et.value in type_str:
                            entity_type = et
                            break

                if not entity_type:
                    logger.debug(f"Unknown entity type: {type_str}")
                    continue

                entities.append(ExtractedEntity(
                    id=e.get("id", f"e{len(entities)+1}"),
                    type=entity_type,
                    name=e.get("name", ""),
                    mention=e.get("mention", e.get("name", "")),
                    attributes=e.get("attributes", {}),
                    confidence=float(e.get("confidence", 0.8)),
                ))
            except Exception as ex:
                logger.debug(f"Failed to parse entity: {ex}")

        return entities

    def _parse_relations(self, relations_data: list) -> list[ExtractedRelation]:
        """Parse relation data into ExtractedRelation objects"""
        relations = []
        for r in relations_data:
            try:
                type_str = r.get("type", "").upper()
                rel_type = None
                for rt in RelationType:
                    if rt.value == type_str:
                        rel_type = rt
                        break

                if not rel_type:
                    logger.debug(f"Unknown relation type: {type_str}")
                    continue

                relations.append(ExtractedRelation(
                    source_id=r.get("source_id", ""),
                    target_id=r.get("target_id", ""),
                    type=rel_type,
                    evidence=r.get("evidence", ""),
                    confidence=float(r.get("confidence", 0.7)),
                    attributes=r.get("attributes", {}),
                ))
            except Exception as ex:
                logger.debug(f"Failed to parse relation: {ex}")

        return relations
