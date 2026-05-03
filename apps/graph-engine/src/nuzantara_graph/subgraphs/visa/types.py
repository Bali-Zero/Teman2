"""Planner types — SubQuestion, Chunk, NodeEvidence, PlannerState."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    """A single decomposed sub-question in the planner DAG."""

    idx: int = Field(ge=0)
    text: str
    needs_kb: bool = True
    depends_on: list[int] = Field(default_factory=list)


class Chunk(BaseModel):
    """A retrieved evidence chunk with a citable span.

    span_start/span_end are character offsets into the source document. When
    the vector store does not expose true offsets, we default to
    0..len(content) — this is declared as a known limitation in the
    architecture doc, not silently ignored.
    """

    doc_id: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    content: str

    def citation(self) -> str:
        return f"[{self.doc_id}:{self.span_start}-{self.span_end}]"


class NodeEvidence(BaseModel):
    """Evidence collected for one sub-question during execution."""

    sub_question: SubQuestion
    chunks: list[Chunk] = Field(default_factory=list)
    answer_fragment: str = ""
    grounded: bool = False
    contradiction_score: float = 0.0
    retries_used: int = 0


class PlannerState(BaseModel):
    """Internal state threaded through the visa StateGraph."""

    query: str
    rewritten_query: str = ""
    system_notes: list[Chunk] = Field(default_factory=list)
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    evidences: list[NodeEvidence] = Field(default_factory=list)
    final_answer: str = ""
    llm_call_count: int = Field(default=0, ge=0)
    max_llm_calls: int = Field(default=8, ge=1)
    max_sub_questions: int = Field(default=5, ge=1)
    max_depth: int = Field(default=3, ge=1)
    max_retries_per_node: int = Field(default=1, ge=0)
    dominant_visa: str = "general"
    error: str | None = None

    def budget_remaining(self) -> int:
        return self.max_llm_calls - self.llm_call_count

    def can_call_llm(self) -> bool:
        return self.llm_call_count < self.max_llm_calls
