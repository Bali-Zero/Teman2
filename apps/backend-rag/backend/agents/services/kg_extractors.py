"""
Knowledge Graph Extractors

Responsibility: Extract entities and relationships from text using AI.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Constants
MAX_TEXT_LENGTH = 4000

try:
    from llm.zantara_ai_client import ZantaraAIClient

    ZANTARA_AVAILABLE = True
except ImportError:
    ZantaraAIClient = None
    ZANTARA_AVAILABLE = False


class EntityExtractor:
    """Service for extracting entities from text using AI"""

    def __init__(self, ai_client: ZantaraAIClient | None = None):
        """
        Initialize EntityExtractor.

        Args:
            ai_client: ZantaraAIClient instance (if None, will create new)
        """
        self.ai_client = ai_client or (ZantaraAIClient() if ZANTARA_AVAILABLE else None)

    async def extract_entities(self, text: str, timeout: float = 30.0) -> list[dict[str, Any]]:
        """
        Extract entities from text using AI.

        Args:
            text: Text to extract entities from
            timeout: Maximum time to wait for AI extraction

        Returns:
            List of entity dictionaries
        """
        if not text:
            return []

        if not self.ai_client:
            logger.warning("ZantaraAIClient not available, cannot extract entities")
            return []

        # Limit text length
        text_snippet = text[:MAX_TEXT_LENGTH]

        prompt = f"""Extract structured entities from this legal/business conversation:

Text:
{text_snippet}

Extract:
1. **Laws/Regulations**: Specific laws, articles, regulations mentioned
2. **Topics**: Main legal/business topics (e.g., "Investment License", "Tax Compliance")
3. **Companies**: Company names mentioned
4. **Locations**: Cities, provinces, countries
5. **Practice Types**: Types of legal work (e.g., "Due Diligence", "Contract Review")
6. **Key Concepts**: Important legal concepts

Return JSON array:
[
  {{
    "type": "law|topic|company|location|practice_type|concept",
    "name": "exact mention",
    "canonical_name": "normalized version",
    "context": "brief context where mentioned"
  }}
]

Be precise. Only extract clear entities."""

        try:
            analysis_text = await asyncio.wait_for(
                self.ai_client.generate_text(prompt=prompt, max_tokens=2048, temperature=0.2),
                timeout=timeout,
            )

            # Extract JSON from response
            json_start = analysis_text.find("[")
            json_end = analysis_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(analysis_text[json_start:json_end])
            return []
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting entities after {timeout}s")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing entities JSON: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error extracting entities: {e}", exc_info=True)
            return []


class RelationshipExtractor:
    """Service for extracting relationships between entities using AI"""

    def __init__(self, ai_client: ZantaraAIClient | None = None):
        """
        Initialize RelationshipExtractor.

        Args:
            ai_client: ZantaraAIClient instance (if None, will create new)
        """
        self.ai_client = ai_client or (ZantaraAIClient() if ZANTARA_AVAILABLE else None)

    async def extract_relationships(
        self, entities: list[dict[str, Any]], text: str, timeout: float = 30.0
    ) -> list[dict[str, Any]]:
        """
        Extract relationships between entities.

        Args:
            entities: List of entity dictionaries
            text: Source text context
            timeout: Maximum time to wait for AI extraction

        Returns:
            List of relationship dictionaries
        """
        if len(entities) < 2:
            return []

        if not self.ai_client:
            logger.warning("ZantaraAIClient not available, cannot extract relationships")
            return []

        entity_names = [e["name"] for e in entities]
        text_snippet = text[:3000]

        prompt = f"""Given these entities from a legal conversation:
{json.dumps(entity_names, indent=2)}

And this context:
{text_snippet}

Identify meaningful relationships between entities.

Return JSON array:
[
  {{
    "source": "entity name",
    "target": "entity name",
    "relationship": "relates_to|requires|conflicts_with|example_of|governed_by",
    "strength": 0.8,
    "evidence": "quote from text showing this relationship"
  }}
]

Only include clear, meaningful relationships."""

        try:
            analysis_text = await asyncio.wait_for(
                self.ai_client.generate_text(prompt=prompt, max_tokens=2048, temperature=0.2),
                timeout=timeout,
            )

            # Extract JSON from response
            json_start = analysis_text.find("[")
            json_end = analysis_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(analysis_text[json_start:json_end])
            return []
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting relationships after {timeout}s")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing relationships JSON: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error extracting relationships: {e}", exc_info=True)
            return []










