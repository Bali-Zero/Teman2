"""
RAG Pipeline Debugger
Traces RAG pipeline execution: query → embedding → search → rerank → context → response
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RAGPipelineStep:
    """Single step in RAG pipeline"""

    step_name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, output_data: dict[str, Any] | None = None, error: str | None = None) -> None:
        """Mark step as finished."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.output_data = output_data
        self.error = error


@dataclass
class RAGPipelineTrace:
    """Complete trace of RAG pipeline execution"""

    query: str
    correlation_id: str | None = None
    steps: list[RAGPipelineStep] = field(default_factory=list)
    documents_retrieved: list[dict[str, Any]] = field(default_factory=list)
    documents_reranked: list[dict[str, Any]] = field(default_factory=list)
    confidence_scores: list[float] = field(default_factory=list)
    fallbacks_activated: list[str] = field(default_factory=list)
    final_response: str | None = None
    total_duration_ms: float | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    def add_step(self, step_name: str, **metadata) -> RAGPipelineStep:
        """Add a new step to the trace."""
        step = RAGPipelineStep(step_name=step_name, start_time=time.time(), metadata=metadata)
        self.steps.append(step)
        return step

    def finish(self, final_response: str | None = None) -> None:
        """Mark pipeline as finished."""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        self.final_response = final_response

    def to_dict(self) -> dict[str, Any]:
        """Convert trace to dictionary."""
        return {
            "query": self.query,
            "correlation_id": self.correlation_id,
            "steps": [
                {
                    "step_name": step.step_name,
                    "duration_ms": step.duration_ms,
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "error": step.error,
                    "metadata": step.metadata,
                }
                for step in self.steps
            ],
            "documents_retrieved": self.documents_retrieved,
            "documents_reranked": self.documents_reranked,
            "confidence_scores": self.confidence_scores,
            "fallbacks_activated": self.fallbacks_activated,
            "final_response": self.final_response,
            "total_duration_ms": self.total_duration_ms,
        }


class RAGPipelineDebugger:
    """
    Debugger for RAG pipeline execution.

    Usage:
        debugger = RAGPipelineDebugger(query="...", correlation_id="...")
        with debugger.step("embedding"):
            embedding = embed_query(query)
        with debugger.step("search"):
            results = search_service.search(query, embedding)
        trace = debugger.finish(response)
    """

    def __init__(self, query: str, correlation_id: str | None = None):
        """
        Initialize RAG pipeline debugger.

        Args:
            query: User query
            correlation_id: Optional correlation ID for request tracking
        """
        self.trace = RAGPipelineTrace(query=query, correlation_id=correlation_id)

    def step(self, step_name: str, **metadata):
        """
        Context manager for a pipeline step.

        Args:
            step_name: Step name (e.g., "embedding", "search", "rerank")
            **metadata: Additional step metadata

        Returns:
            Context manager for the step
        """
        return RAGPipelineStepContext(self.trace, step_name, **metadata)

    def add_documents(self, documents: list[dict[str, Any]], stage: str = "retrieved") -> None:
        """
        Add retrieved documents to trace.

        Args:
            documents: List of document dictionaries
            stage: Stage name ("retrieved" or "reranked")
        """
        if stage == "retrieved":
            self.trace.documents_retrieved.extend(documents)
        elif stage == "reranked":
            self.trace.documents_reranked.extend(documents)

    def add_confidence_scores(self, scores: list[float]) -> None:
        """
        Add confidence scores to trace.

        Args:
            scores: List of confidence scores
        """
        self.trace.confidence_scores.extend(scores)

    def add_fallback(self, fallback_name: str) -> None:
        """
        Record that a fallback was activated.

        Args:
            fallback_name: Name of the fallback (e.g., "gemini_fallback")
        """
        self.trace.fallbacks_activated.append(fallback_name)

    def finish(self, response: str | None = None) -> RAGPipelineTrace:
        """
        Finish debugging and return trace.

        Args:
            response: Final response text

        Returns:
            Complete trace
        """
        self.trace.finish(final_response=response)
        return self.trace

    def get_trace(self) -> dict[str, Any]:
        """
        Get trace as dictionary.

        Returns:
            Trace dictionary
        """
        return self.trace.to_dict()


class RAGPipelineStepContext:
    """Context manager for a single RAG pipeline step"""

    def __init__(self, trace: RAGPipelineTrace, step_name: str, **metadata):
        """
        Initialize step context.

        Args:
            trace: RAG pipeline trace
            step_name: Step name
            **metadata: Step metadata
        """
        self.trace = trace
        self.step = trace.add_step(step_name, **metadata)

    def __enter__(self):
        """Enter step context."""
        return self.step

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit step context."""
        error = str(exc_val) if exc_val else None
        self.step.finish(error=error)
        return False  # Don't suppress exceptions

