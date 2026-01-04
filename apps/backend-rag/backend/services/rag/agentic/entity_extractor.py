"""
Lightweight entity extraction for Agentic RAG.

This is intentionally heuristic-first to keep latency low and avoid unnecessary
LLM calls. It provides optional hooks for future LLM-backed extraction.
"""

from __future__ import annotations

import re
from typing import Any


class EntityExtractionService:
    def __init__(self, llm_gateway: Any | None = None):
        self._llm_gateway = llm_gateway

    async def extract_entities(self, query: str) -> dict[str, Any]:
        if not query:
            return {}

        query_lower = query.lower()

        visa_codes = re.findall(r"\b(e\d{2}[a-z]?)\b", query_lower)
        visa_type = None
        if visa_codes:
            visa_type = visa_codes[0].upper()
        elif "kitas" in query_lower:
            visa_type = "KITAS"
        elif "kitap" in query_lower:
            visa_type = "KITAP"
        elif "voa" in query_lower or "visa on arrival" in query_lower:
            visa_type = "VOA"

        nationality = None
        nationality_map = {
            "italy": "Italy",
            "italian": "Italy",
            "italiano": "Italy",
            "italiana": "Italy",
            "ukraine": "Ukraine",
            "ukrainian": "Ukraine",
            "ucraina": "Ukraine",
            "russia": "Russia",
            "russian": "Russia",
            "russo": "Russia",
            "usa": "USA",
            "american": "USA",
        }
        for marker, normalized in nationality_map.items():
            if marker in query_lower:
                nationality = normalized
                break

        budget = None
        # Simple budget detection: $50k / 50k USD / 50,000 / 50M IDR etc.
        budget_match = re.search(
            r"(?P<cur>\\$|usd|idr|rp)\\s*(?P<num>\\d{1,3}(?:[\\.,]\\d{3})*(?:[\\.,]\\d+)?)\\s*(?P<unit>k|m|million)?",
            query_lower,
        )
        if budget_match:
            budget = budget_match.group(0).strip()

        entities: dict[str, Any] = {}
        if visa_type:
            entities["visa_type"] = visa_type
        if nationality:
            entities["nationality"] = nationality
        if budget:
            entities["budget"] = budget

        return entities
