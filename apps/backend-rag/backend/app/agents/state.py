"""
Agent State Definitions

This module defines the state schemas used by LangGraph workflows.
All state classes inherit from TypedDict for type safety.
"""

from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


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
    documents: List[str]
    generation: str
    metadata: Optional[Dict[str, Any]]
    errors: Optional[List[str]]
    step_count: Optional[int]
    timestamp: Optional[datetime]


class RetrievalState(TypedDict, total=False):
    """
    Extended state for retrieval-specific workflows.

    Adds retrieval-specific fields to the base AgentState.
    """
    question: str
    documents: List[str]
    generation: str

    # Retrieval-specific
    query_vector: Optional[List[float]]
    collection_name: Optional[str]
    top_k: Optional[int]
    score_threshold: Optional[float]
    retrieved_scores: Optional[List[float]]


class GradingState(TypedDict, total=False):
    """
    State for document grading workflows.

    Tracks relevance scores and grading decisions.
    """
    question: str
    documents: List[str]
    generation: str

    # Grading-specific
    relevance_scores: Optional[List[float]]
    filtered_documents: Optional[List[str]]
    grading_decision: Optional[str]  # "relevant" | "irrelevant" | "mixed"


class WorkflowState(TypedDict, total=False):
    """
    Full workflow state combining all aspects.

    This is used for complex multi-step workflows that include
    retrieval, grading, and generation.
    """
    # Input
    question: str
    metadata: Optional[Dict[str, Any]]

    # Retrieval
    documents: List[str]
    retrieved_scores: Optional[List[float]]

    # Grading
    relevance_scores: Optional[List[float]]
    filtered_documents: Optional[List[str]]

    # Generation
    generation: str

    # Execution tracking
    errors: Optional[List[str]]
    step_count: Optional[int]
    timestamp: Optional[datetime]
    execution_path: Optional[List[str]]  # Track which nodes were executed
