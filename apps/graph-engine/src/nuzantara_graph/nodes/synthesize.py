"""Synthesize node — answer generation + confidence scoring."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.grading import ConfidenceScores
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()

SYNTHESIZE_SYSTEM_PROMPT = """You are Zantara, an expert AI assistant for Indonesian business consulting.

Given reasoning steps and retrieved context, produce a clear, accurate answer.

Respond in JSON:
{
  "answer": "Your complete answer here...",
  "sources": [{"title": "...", "id": "..."}],
  "confidence": {
    "retrieval_relevance": 0.0-1.0,
    "source_authority": 0.0-1.0,
    "reasoning_coherence": 0.0-1.0,
    "factual_grounding": 0.0-1.0,
    "domain_coverage": 0.0-1.0,
    "answer_completeness": 0.0-1.0
  }
}

Rules:
- Use Markdown formatting for readability
- Cite sources when stating facts
- Include disclaimers for legal/tax advice
- For pricing, only quote official prices
- Respond in the same language as the query"""

DIRECT_SYSTEM_PROMPT = """You are Zantara, a friendly AI assistant for Indonesian business consulting.
Respond naturally to greetings and simple queries. Keep it conversational.
Respond in the same language as the query.

Respond in JSON: {"answer": "..."}"""


def make_synthesize_node(services: Services):
    """Factory that creates a synthesize node with injected services."""

    async def synthesize_node(state: GraphState) -> dict[str, Any]:
        """Generate the final answer from reasoning steps and context."""
        logger.info(
            "synthesize_start",
            reasoning_steps=len(state.reasoning_steps),
            correction_count=state.correction_count,
        )

        retry_hint = ""
        if state.grades:
            last = state.grades[-1]
            if last.grader == "answer" and last.retry_hint:
                retry_hint = last.retry_hint

        # Build reasoning summary
        reasoning_text = "\n".join(
            f"- [{s.step_type}] {s.content}" for s in state.reasoning_steps
        )

        # Build doc references
        doc_refs = "\n".join(
            f"[{i+1}] {doc.content[:200]}..."
            for i, doc in enumerate(state.retrieved_documents[:5])
        )

        prompt_parts = [
            f"Query: {state.query}",
            f"\nReasoning:\n{reasoning_text}",
        ]
        if doc_refs:
            prompt_parts.append(f"\nSource documents:\n{doc_refs}")
        if retry_hint:
            prompt_parts.append(f"\nPrevious attempt feedback: {retry_hint}")

        prompt = "\n".join(prompt_parts)

        try:
            result = await services.llm.generate_json(
                prompt=prompt,
                system=SYNTHESIZE_SYSTEM_PROMPT,
                temperature=0.2,
            )

            answer = result.get("answer", "")
            sources = result.get("sources", [])
            conf_raw = result.get("confidence", {})

            confidence = ConfidenceScores(
                retrieval_relevance=_clamp(conf_raw.get("retrieval_relevance", 0.0)),
                source_authority=_clamp(conf_raw.get("source_authority", 0.0)),
                reasoning_coherence=_clamp(conf_raw.get("reasoning_coherence", 0.0)),
                factual_grounding=_clamp(conf_raw.get("factual_grounding", 0.0)),
                domain_coverage=_clamp(conf_raw.get("domain_coverage", 0.0)),
                answer_completeness=_clamp(conf_raw.get("answer_completeness", 0.0)),
            )

            logger.info(
                "synthesize_complete",
                answer_len=len(answer),
                confidence=confidence.overall,
            )

            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "current_node": "synthesize",
            }

        except Exception as e:
            logger.error("synthesize_failed", error=str(e))
            return {
                "answer": "I apologize, but I was unable to generate a complete answer. "
                         "Please try rephrasing your question.",
                "sources": [],
                "current_node": "synthesize",
                "error": f"Synthesis failed: {e}",
            }

    return synthesize_node


def make_synthesize_direct_node(services: Services):
    """Factory for direct synthesis (greetings, cache hits)."""

    async def synthesize_direct_node(state: GraphState) -> dict[str, Any]:
        """Generate a direct response for greetings/simple queries."""
        logger.info("synthesize_direct_start", intent=state.intent)

        try:
            result = await services.llm.generate_json(
                prompt=state.query,
                system=DIRECT_SYSTEM_PROMPT,
                temperature=0.5,
            )

            return {
                "answer": result.get("answer", "Hello! How can I help you?"),
                "is_terminal": True,
                "current_node": "synthesize_direct",
            }

        except Exception:
            return {
                "answer": "Hello! How can I help you with Indonesian business questions?",
                "is_terminal": True,
                "current_node": "synthesize_direct",
            }

    return synthesize_direct_node


def make_synthesize_fail_fast_node(services: Services):
    """Factory for fail-fast synthesis — grader detected critically low quality."""

    async def synthesize_fail_fast_node(state: GraphState) -> dict[str, Any]:
        """Generate a polite 'rephrase your question' response.

        This node fires when a grader returns FAIL (score < 0.2).
        Instead of wasting tokens on reasoning/synthesis over garbage,
        we tell the user their question needs clarification.
        """
        logger.info(
            "synthesize_fail_fast",
            last_grader=state.last_grade.grader if state.last_grade else "unknown",
            last_score=state.last_grade.score if state.last_grade else 0,
        )

        # Build context-aware fail message
        grader = state.last_grade.grader if state.last_grade else "quality"
        reason = state.last_grade.reason if state.last_grade else ""

        if grader == "retrieval":
            answer = (
                "I couldn't find relevant information for your question. "
                "Could you try rephrasing it with more specific details? "
                "For example, mention the specific business type (PT PMA, CV), "
                "visa category (KITAS, KITAP), or KBLI code you're interested in."
            )
        elif grader == "reasoning":
            answer = (
                "I found some information but couldn't put together a coherent answer. "
                "Could you try asking a more specific question? "
                "For example, instead of a broad question, ask about a specific requirement or process."
            )
        else:
            answer = (
                "I wasn't able to provide a reliable answer to your question. "
                "Could you try rephrasing it with more specific details?"
            )

        return {
            "answer": answer,
            "is_terminal": True,
            "current_node": "synthesize_fail_fast",
            "error": f"Fail-fast: {grader} grader scored below threshold. {reason}",
        }

    return synthesize_fail_fast_node


def _clamp(value: Any, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to [min_val, max_val], handling non-numeric inputs."""
    try:
        return max(min_val, min(max_val, float(value)))
    except (TypeError, ValueError):
        return 0.0
