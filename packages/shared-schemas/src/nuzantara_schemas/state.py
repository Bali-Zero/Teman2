"""Central GraphState — the single Pydantic model that flows through every LangGraph node."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from nuzantara_schemas.grading import ConfidenceScores, GradeResult
from nuzantara_schemas.tools import ToolCallRecord


class IntentType(StrEnum):
    GENERAL = "general"
    BUSINESS_SETUP = "business_setup"
    VISA = "visa"
    TAX = "tax"
    PROPERTY = "property"
    KBLI = "kbli"
    PRICING = "pricing"
    GREETING = "greeting"
    FOLLOWUP = "followup"


class ChannelType(StrEnum):
    WEB = "web"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"


class RetrievedDocument(BaseModel):
    """A document retrieved from vector store or KG."""

    id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = "vector"  # vector | kg | hybrid


class ReasoningStep(BaseModel):
    """A single step in Chain-of-Thought reasoning."""

    step_type: str  # thought | action | observation
    content: str
    tool_name: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TokenUsage(BaseModel):
    """Token usage for a single LLM call."""

    node: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class GraphState(BaseModel):
    """Central state model flowing through every LangGraph node.

    Every field is typed and validated. Nodes mutate specific sections
    and graders verify quality between major transitions.
    """

    # --- Identity (immutable after creation) ---
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    user_id: str = "anonymous"
    channel: ChannelType = ChannelType.WEB

    # --- Session / conversation memory ---
    session_id: str | None = None  # client-provided, links turns together
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Previous turns: [{'role': 'user'|'assistant', 'content': str}]",
    )

    # --- Understanding (set by understand node) ---
    intent: IntentType = IntentType.GENERAL
    domain: str | None = None
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    detected_language: str | None = None
    is_followup: bool = False

    # --- Retrieval (set by retrieve node) ---
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    kg_entities: list[dict[str, Any]] = Field(default_factory=list)
    kg_relationships: list[dict[str, Any]] = Field(default_factory=list)

    # --- Reasoning (set by reason node) ---
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)

    # --- Answer (set by synthesize node) ---
    answer: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)

    # --- Grading (set by grader nodes) ---
    grades: list[GradeResult] = Field(default_factory=list)
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)

    # --- Flow control ---
    correction_count: int = Field(default=0, ge=0)
    max_corrections: int = Field(default=2, ge=0, le=5)
    current_node: str = ""
    is_terminal: bool = False
    error: str | None = None

    # --- Token tracking ---
    token_usage: list[TokenUsage] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def enforce_correction_limit(self) -> GraphState:
        if self.correction_count > self.max_corrections:
            raise ValueError(
                f"correction_count ({self.correction_count}) exceeds "
                f"max_corrections ({self.max_corrections})"
            )
        return self

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.token_usage)

    @property
    def total_cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.token_usage)

    @property
    def last_grade(self) -> GradeResult | None:
        return self.grades[-1] if self.grades else None

    def add_token_usage(self, node: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.token_usage.append(
            TokenUsage(
                node=node,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
        )
