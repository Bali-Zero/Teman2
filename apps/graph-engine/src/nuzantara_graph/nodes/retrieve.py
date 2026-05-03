"""Retrieve node — vector search + KG traversal."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()


def make_retrieve_node(services: Services):
    """Factory that creates a retrieve node with injected services."""

    async def retrieve_node(state: GraphState) -> dict[str, Any]:
        """Retrieve relevant documents from vector store and KG."""
        logger.info(
            "retrieve_start",
            query=state.query[:100],
            intent=state.intent,
            correction_count=state.correction_count,
        )

        retry_hint = ""
        if state.grades:
            last = state.grades[-1]
            if last.grader == "retrieval" and last.retry_hint:
                retry_hint = last.retry_hint

        # Build search query — use entities to enrich the raw query
        search_query = state.query
        if retry_hint:
            search_query = f"{state.query} (focus: {retry_hint})"
        elif state.extracted_entities:
            entity_str = " ".join(str(v) for v in state.extracted_entities.values())
            search_query = f"{state.query} {entity_str}"

        try:
            # Vector search
            docs = await services.vector_store.search_by_text(
                query=search_query,
                top_k=10,
            )

            # KG traversal — look up entities extracted by understand node
            kg_entities: list[dict[str, Any]] = []
            kg_relationships: list[dict[str, Any]] = []

            entity_ids = [
                v for k, v in state.extracted_entities.items()
                if k in ("kbli_code", "company_type", "visa_type", "tax_type")
            ]
            if entity_ids:
                kg_entities = await services.kg_store.get_entities(
                    entity_ids=[str(eid) for eid in entity_ids]
                )
                for entity in kg_entities:
                    if "entity_id" in entity:
                        rels = await services.kg_store.get_relationships(
                            entity_id=entity["entity_id"]
                        )
                        kg_relationships.extend(rels)

            logger.info(
                "retrieve_complete",
                doc_count=len(docs),
                kg_entity_count=len(kg_entities),
                kg_rel_count=len(kg_relationships),
            )

            return {
                "retrieved_documents": docs,
                "kg_entities": kg_entities,
                "kg_relationships": kg_relationships,
                "current_node": "retrieve",
            }

        except Exception as e:
            logger.error("retrieve_failed", error=str(e))
            return {
                "retrieved_documents": [],
                "kg_entities": [],
                "kg_relationships": [],
                "current_node": "retrieve",
                "error": f"Retrieval failed: {e}",
            }

    return retrieve_node
