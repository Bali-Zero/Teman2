"""Understand node — query analysis, intent classification, entity extraction."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState, IntentType

logger = structlog.get_logger()

UNDERSTAND_SYSTEM_PROMPT = """You are a query analyzer for an Indonesian business consulting platform.
Analyze the user's query and extract:
1. intent: one of [general, business_setup, visa, tax, property, kbli, pricing, greeting, followup]
2. domain: the specific domain area (e.g., "pt_pma", "kitas", "ppn", "hak_pakai") or null
3. entities: key entities mentioned (company names, visa types, KBLI codes, locations, etc.)
4. language: detected language code (en, id, it, etc.)
5. is_followup: true if this references a previous conversation

Respond in JSON format:
{
  "intent": "...",
  "domain": "...",
  "entities": {"key": "value"},
  "language": "...",
  "is_followup": false
}"""


def make_understand_node(services: Services):
    """Factory that creates an understand node with injected services."""

    async def understand_node(state: GraphState) -> dict[str, Any]:
        """Analyze the query to determine intent, entities, and language."""
        logger.info("understand_start", query=state.query[:100])

        try:
            result = await services.llm.generate_json(
                prompt=f"Analyze this query: {state.query}",
                system=UNDERSTAND_SYSTEM_PROMPT,
                temperature=0.0,
            )

            intent_str = result.get("intent", "general")
            try:
                intent = IntentType(intent_str)
            except ValueError:
                intent = IntentType.GENERAL

            updates: dict[str, Any] = {
                "intent": intent,
                "domain": result.get("domain"),
                "extracted_entities": result.get("entities", {}),
                "detected_language": result.get("language"),
                "is_followup": result.get("is_followup", False),
                "current_node": "understand",
            }

            logger.info(
                "understand_complete",
                intent=intent,
                domain=updates["domain"],
                language=updates["detected_language"],
            )
            return updates

        except Exception as e:
            logger.error("understand_failed", error=str(e))
            return {
                "intent": IntentType.GENERAL,
                "current_node": "understand",
                "error": f"Understanding failed: {e}",
            }

    return understand_node
