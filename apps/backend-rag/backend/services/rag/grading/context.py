"""GradingContext — adapter between backend orchestrator state and grader interface.

The backend-rag orchestrator uses dicts and TypedDicts for state,
while graders need structured access to specific fields. This dataclass
bridges the gap without coupling graders to the orchestrator internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedDoc:
    """Minimal representation of a retrieved document for grading."""

    content: str = ""
    score: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStep:
    """A single reasoning step (thought or observation)."""

    step_type: str = "thought"  # "thought" | "observation"
    content: str = ""


@dataclass
class GradingContext:
    """Structured context for graders.

    Populated by the orchestrator before calling graders.
    All fields have safe defaults so graders handle missing data gracefully.
    """

    # Answer
    answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    confidence_overall: float = 0.5

    # Retrieval
    retrieved_documents: list[RetrievedDoc] = field(default_factory=list)

    # Reasoning
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)

    # Knowledge Graph
    kg_entities: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Safely convert a value to float, returning default on failure."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    def from_search_results(
        cls,
        results: list[dict[str, Any]],
    ) -> GradingContext:
        """Build context from raw search results (for retrieval grading)."""
        docs = [
            RetrievedDoc(
                content=r.get("content", r.get("text", "")),
                score=cls._safe_float(r.get("score", r.get("relevance_score", 0.0))),
                source=r.get("source", r.get("collection", "")),
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]
        return cls(retrieved_documents=docs)

    @classmethod
    def from_core_result(
        cls,
        result: dict[str, Any],
        search_results: list[dict[str, Any]] | None = None,
        kg_context: dict[str, Any] | None = None,
    ) -> GradingContext:
        """Build full context from OrchestratorCore result dict."""
        docs = []
        if search_results:
            docs = [
                RetrievedDoc(
                    content=r.get("content", r.get("text", "")),
                    score=cls._safe_float(r.get("score", r.get("relevance_score", 0.0))),
                    source=r.get("source", r.get("collection", "")),
                    metadata=r.get("metadata", {}),
                )
                for r in search_results
            ]

        # Parse reasoning trace into steps (defensive: handle unexpected types)
        steps: list[ReasoningStep] = []
        trace = result.get("reasoning_trace", [])
        if isinstance(trace, list):
            for entry in trace:
                if isinstance(entry, dict):
                    steps.append(ReasoningStep(
                        step_type=entry.get("type", "thought"),
                        content=entry.get("content", str(entry)),
                    ))
                elif isinstance(entry, str):
                    steps.append(ReasoningStep(content=entry))
                else:
                    # Unexpected type — convert to string safely
                    steps.append(ReasoningStep(content=str(entry)))

        kg_entities = []
        if kg_context:
            kg_entities = kg_context.get("entities_found", [])

        return cls(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            confidence_overall=float(result.get("confidence", 0.5)),
            retrieved_documents=docs,
            reasoning_steps=steps,
            kg_entities=kg_entities,
        )
