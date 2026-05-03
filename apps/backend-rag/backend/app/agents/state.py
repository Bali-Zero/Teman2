"""
Agent State Definitions

This module defines the state schemas used by LangGraph workflows.
All state classes inherit from TypedDict for type safety.
"""

from datetime import datetime
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """
    Core agent state for the RAG workflow.

    Attributes:
        question: User's input question
        documents: Retrieved documents (list of strings or dicts)
        generation: Final generated answer
        metadata: Additional context (user info, session, etc.)
        errors: List of errors encountered during execution
        step_count: Number of steps executed
        timestamp: When the state was created
    """

    question: str
    documents: list[str]
    generation: str
    metadata: dict[str, Any] | None
    errors: list[str] | None
    step_count: int | None
    timestamp: datetime | None


class RetrievalState(TypedDict, total=False):
    """
    Extended state for retrieval-specific workflows.

    Adds retrieval-specific fields to the base AgentState.
    """

    question: str
    documents: list[str]
    generation: str

    # Retrieval-specific
    query_vector: list[float] | None
    collection_name: str | None
    top_k: int | None
    score_threshold: float | None
    retrieved_scores: list[float] | None


class GradingState(TypedDict, total=False):
    """
    State for document grading workflows.

    Tracks relevance scores and grading decisions.
    """

    question: str
    documents: list[str]
    generation: str

    # Grading-specific
    relevance_scores: list[float] | None
    filtered_documents: list[str] | None
    grading_decision: str | None  # "relevant" | "irrelevant" | "mixed"


class WorkflowState(TypedDict, total=False):
    """
    Full workflow state combining all aspects.

    This is used for complex multi-step workflows that include
    retrieval, grading, and generation.
    """

    # Input
    question: str
    metadata: dict[str, Any] | None

    # Retrieval
    documents: list[str]
    retrieved_scores: list[float] | None

    # Grading
    relevance_scores: list[float] | None
    filtered_documents: list[str] | None

    # Generation
    generation: str

    # Execution tracking
    errors: list[str] | None
    step_count: int | None
    timestamp: datetime | None
    execution_path: list[str] | None  # Track which nodes were executed

    # Self-RAG reflection
    hallucination_check: str | None  # "passed" | "failed" | "skipped" | "no_docs"
    grounding_score: float | None  # 0.0-1.0 overlap between generation and docs
    reflection_retries: int | None  # Number of query rewrites performed
