"""Visa planner — temporary stub, filled in a later task."""

from __future__ import annotations

from typing import Any


def make_visa_subgraph(services: Any):
    """Temporary stub — real implementation added in Task 9."""

    async def _stub(state: Any) -> dict[str, Any]:
        return {
            "retrieved_documents": [],
            "kg_entities": [],
            "kg_relationships": [],
            "domain": "general",
            "current_node": "subgraph_visa",
        }

    return _stub
