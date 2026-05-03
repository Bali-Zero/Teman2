"""Reason node — Chain-of-Thought reasoning over retrieved context."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState, ReasoningStep

logger = structlog.get_logger()

REASON_SYSTEM_PROMPT = """You are a reasoning engine for an Indonesian business consulting platform.

Given:
- A user query
- Retrieved documents (from vector search)
- Knowledge graph entities and relationships

Produce a chain-of-thought reasoning with explicit steps. Each step should be:
- "thought": your internal reasoning
- "observation": a fact derived from the context

Respond in JSON:
{
  "steps": [
    {"step_type": "thought", "content": "..."},
    {"step_type": "observation", "content": "..."}
  ]
}

Rules:
- Ground every observation in a retrieved document or KG entity
- If context is insufficient, say so explicitly
- For pricing questions, only use official pricing data
- Be specific about Indonesian regulations"""


def make_reason_node(services: Services):
    """Factory that creates a reason node with injected services."""

    async def reason_node(state: GraphState) -> dict[str, Any]:
        """Perform CoT reasoning over retrieved documents and KG data."""
        logger.info(
            "reason_start",
            doc_count=len(state.retrieved_documents),
            kg_entity_count=len(state.kg_entities),
            correction_count=state.correction_count,
        )

        retry_hint = ""
        if state.grades:
            last = state.grades[-1]
            if last.grader == "reasoning" and last.retry_hint:
                retry_hint = last.retry_hint

        # Build context from retrieved documents
        doc_context = "\n\n".join(
            f"[Doc {i+1}] (score: {doc.score:.2f})\n{doc.content}"
            for i, doc in enumerate(state.retrieved_documents[:5])
        )

        # Build KG context
        kg_context = ""
        if state.kg_entities:
            kg_parts = [
                f"[Entity] {e.get('label', e.get('entity_id', 'unknown'))}: "
                f"{e.get('description', '')}"
                for e in state.kg_entities[:5]
            ]
            kg_context = "\n".join(kg_parts)

        prompt_parts = [f"Query: {state.query}"]
        if doc_context:
            prompt_parts.append(f"\nRetrieved documents:\n{doc_context}")
        if kg_context:
            prompt_parts.append(f"\nKnowledge graph:\n{kg_context}")
        if retry_hint:
            prompt_parts.append(f"\nPrevious attempt feedback: {retry_hint}")

        prompt = "\n".join(prompt_parts)

        try:
            result = await services.llm.generate_json(
                prompt=prompt,
                system=REASON_SYSTEM_PROMPT,
                temperature=0.1,
            )

            steps_raw = result.get("steps", [])
            reasoning_steps = [
                ReasoningStep(
                    step_type=s.get("step_type", "thought"),
                    content=s.get("content", ""),
                    tool_name=s.get("tool_name"),
                    confidence=s.get("confidence"),
                )
                for s in steps_raw
            ]

            logger.info("reason_complete", step_count=len(reasoning_steps))

            return {
                "reasoning_steps": reasoning_steps,
                "current_node": "reason",
            }

        except Exception as e:
            logger.error("reason_failed", error=str(e))
            return {
                "reasoning_steps": [
                    ReasoningStep(
                        step_type="thought",
                        content=f"Reasoning failed: {e}. Proceeding with available context.",
                    )
                ],
                "current_node": "reason",
                "error": f"Reasoning failed: {e}",
            }

    return reason_node
