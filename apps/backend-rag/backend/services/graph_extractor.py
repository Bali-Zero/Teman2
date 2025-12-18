"""
Graph Extractor - LLM-based Knowledge Extraction
================================================

Extracts structured knowledge (Entities & Relations) from unstructured text
using ZantaraAIClient (Gemini).

Usage:
    extractor = GraphExtractor(ai_client)
    graph_data = await extractor.extract_from_text(text_chunk)
"""

import json
import logging
from typing import Any, Dict, List

from llm.zantara_ai_client import ZantaraAIClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ExtractedGraph(BaseModel):
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]

class GraphExtractor:
    def __init__(self, ai_client: ZantaraAIClient):
        self.ai = ai_client

    async def extract_from_text(self, text: str, context: str = "") -> ExtractedGraph:
        """
        Uses LLM to extract knowledge graph elements from text.
        """
        system_prompt = """
        You are an expert Legal Knowledge Graph Architect for Indonesian Law.
        Your task is to extract structural relationships from the provided legal text.

        # Entities
        Extract key entities. Types: REGULATION, VISA, REQUIREMENT, OBLIGATION, PERMIT, AGENCY, COST, DURATION.
        Format: {"id": "unique_snake_case_id", "type": "TYPE", "name": "Natural Name", "description": "Context"}

        # Relationships
        Extract logical links. Types: REQUIRES, AMENDS, REVOKES, DEFINES, COSTS, VALID_FOR, ISSUED_BY.
        Format: {"source": "source_id", "target": "target_id", "type": "TYPE", "strength": 0.0-1.0}

        # Rules
        1. IDs must be unique, lowercase, snake_case (e.g., "law_12_2024").
        2. Be precise. Do not hallucinate relationships not in the text.
        3. Output MUST be valid JSON only.
        """

        user_prompt = f"""
        Context: {context}
        
        Text to Analyze:
        "{text[:2000]}"... (truncated)

        Extract the knowledge graph JSON.
        """

        try:
            # Call AI (assuming generate_response interface)
            response = await self.ai.generate_response(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON
            data = json.loads(response)
            
            # Validate simple structure
            entities = data.get("entities", [])
            relations = data.get("relationships", []) or data.get("relations", [])
            
            return ExtractedGraph(entities=entities, relationships=relations)

        except Exception as e:
            logger.error(f"Graph extraction failed: {e}")
            return ExtractedGraph(entities=[], relationships=[])
