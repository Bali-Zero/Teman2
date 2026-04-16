"""
Consiglio v1 — Data models.

All models use Pydantic BaseModel, matching the pattern in types.py.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Topic(BaseModel):
    """What the council deliberates on."""

    id: str
    title: str
    description: str
    category: Literal["architecture", "operational", "strategic", "escalation"]
    source: str = "cli"  # "cli" | "cron" | "escalation" | "mos"
    constraints: list[str] = Field(default_factory=list)
    created_at: str = ""


class AgentVote(BaseModel):
    """One agent's response to a topic."""

    agent_name: str
    runtime: str = ""  # "claude_cli" | "gemini_cli" | "deepseek_api" | "ollama_local"
    position: str = ""
    confidence: float = 0.5
    key_arguments: list[str] = Field(default_factory=list)
    risks_identified: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    success: bool = True
    error: str = ""


class ConsensusResult(BaseModel):
    """Output of the consensus scoring phase."""

    score: float = 0.0
    method: Literal["llm_judge", "jaccard"] = "jaccard"
    pairwise_scores: dict[str, float] = Field(default_factory=dict)
    avg_response_time: float = 0.0
    groupthink_detected: bool = False
    groupthink_reason: str = ""


class Dissent(BaseModel):
    """A minority position that diverges from the majority."""

    agent_name: str
    position: str
    divergence_score: float = 0.0  # 1.0 - agreement with majority


class CouncilDecision(BaseModel):
    """Final output of a council run."""

    id: str
    topic: Topic
    votes: list[AgentVote] = Field(default_factory=list)
    consensus: Optional[ConsensusResult] = None
    dissents: list[Dissent] = Field(default_factory=list)
    synthesis: str = ""
    action_items: list[str] = Field(default_factory=list)
    requires_zero_approval: bool = False
    escalation_reason: str = ""
    status: Literal["pending", "approved", "rejected", "auto_approved", "abstain"] = "pending"
    decided_at: str = ""
    approved_at: str = ""
