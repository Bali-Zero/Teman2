"""
Agentic RAG schema models.

The wider codebase expects the AgenticRAGOrchestrator to return an object-like
result with attribute access (historically a Pydantic model).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoreResult(BaseModel):
    """Standard result object returned by AgenticRAGOrchestrator."""

    model_config = ConfigDict(protected_namespaces=())

    answer: str
    sources: list[Any] = Field(default_factory=list)

    # Core metadata
    model_used: str | None = None
    route_used: str | None = None
    collection_used: str | None = None
    cache_hit: bool | str = False

    # Quality / verification
    verification_status: str | None = None
    verification_score: float = 0.0
    evidence_score: float = 0.0

    # Ambiguity handling
    is_ambiguous: bool = False
    clarification_question: str | None = None

    # Context / steps / tools
    document_count: int = 0
    context_used: int = 0
    tools_called: list[str] = Field(default_factory=list)

    # Token usage tracking
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    # Extra structured outputs
    entities: dict[str, Any] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
