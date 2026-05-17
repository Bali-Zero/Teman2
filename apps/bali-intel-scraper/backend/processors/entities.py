"""
Named Entity Extraction processor.

Extracts people, organizations, locations, and other entities from text.
"""

import re
from dataclasses import dataclass
import json

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="entities")


@dataclass
class Entity:
    """Named entity."""

    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


class EntityExtractor:
    """Extract named entities from text."""

    # Common entity patterns
    PATTERNS = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "URL": r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?",
        "PHONE": r"\b(?:\+?62|0)[\s-]?[0-9]{1,4}[\s-]?[0-9]{1,4}[\s-]?[0-9]{1,4}\b",
        "MONEY": r"(?:Rp\.?|IDR)\s*[\d.,]+(?:\s*(?:ribu|juta|miliar|triliun))?",
        "DATE": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Januari|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    }

    # Location indicators
    LOCATION_INDICATORS = {
        "bali",
        "jakarta",
        "surabaya",
        "bandung",
        "yogyakarta",
        "medan",
        "makassar",
        "denpasar",
        "seminyak",
        "kuta",
        "ubud",
        "nusa dua",
        "indonesia",
        "singapore",
        "malaysia",
        "australia",
        "japan",
        "beach",
        "island",
        "mountain",
        "temple",
        "province",
        "city",
    }

    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai

    async def extract(self, text: str) -> dict[str, list[Entity]]:
        """Extract all entity types from text."""
        entities = {
            "PERSON": [],
            "ORGANIZATION": [],
            "LOCATION": [],
            "EMAIL": [],
            "URL": [],
            "PHONE": [],
            "MONEY": [],
            "DATE": [],
            "MISC": [],
        }

        # Pattern-based extraction
        for label, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities[label].append(
                    Entity(
                        text=match.group(),
                        label=label,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # AI-based extraction
        if self.use_ai and len(text) > 50:
            try:
                ai_entities = await self._extract_with_ai(text)
                for label, ents in ai_entities.items():
                    if label in entities:
                        entities[label].extend(ents)
                    else:
                        entities["MISC"].extend(ents)
            except Exception as e:
                logger.warning(
                    "AI entity extraction failed",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

        # Remove duplicates
        for label in entities:
            seen = set()
            unique = []
            for ent in entities[label]:
                key = (ent.text.lower(), ent.label)
                if key not in seen:
                    seen.add(key)
                    unique.append(ent)
            entities[label] = unique

        return entities

    async def _extract_with_ai(self, text: str) -> dict[str, list[Entity]]:
        """Extract entities using AI."""
        prompt = f"""Extract named entities from this text. Return JSON:
{{
    "PERSON": ["name1", "name2"],
    "ORGANIZATION": ["org1", "org2"],
    "LOCATION": ["loc1", "loc2"]
}}

Text: {text[:3000]}"""

        response = await ai_engine.process(
            prompt,
            task_type="extract_entities",
            provider=AIProvider.OPENAI,
            temperature=0.0,
            max_tokens=1000,
        )

        try:
            result = json.loads(response.content)
            entities = {}

            for label, names in result.items():
                entities[label] = []
                for name in names:
                    # Find positions in text
                    pattern = re.compile(re.escape(name), re.IGNORECASE)
                    for match in pattern.finditer(text):
                        entities[label].append(
                            Entity(
                                text=match.group(),
                                label=label,
                                start=match.start(),
                                end=match.end(),
                                confidence=0.9,
                            )
                        )

            return entities

        except json.JSONDecodeError:
            return {}

    async def extract_locations(self, text: str) -> list[Entity]:
        """Extract location entities specifically."""
        entities = await self.extract(text)
        return entities.get("LOCATION", [])

    async def extract_people(self, text: str) -> list[Entity]:
        """Extract person entities specifically."""
        entities = await self.extract(text)
        return entities.get("PERSON", [])

    async def extract_organizations(self, text: str) -> list[Entity]:
        """Extract organization entities specifically."""
        entities = await self.extract(text)
        return entities.get("ORGANIZATION", [])

    def format_for_indexing(
        self, entities: dict[str, list[Entity]]
    ) -> dict[str, list[str]]:
        """Format entities for search indexing."""
        return {label: [e.text for e in ents] for label, ents in entities.items()}


extractor = EntityExtractor()


async def extract_entities(text: str) -> dict[str, list[Entity]]:
    """Quick function to extract entities."""
    return await extractor.extract(text)


__all__ = [
    "EntityExtractor",
    "Entity",
    "extractor",
    "extract_entities",
]
