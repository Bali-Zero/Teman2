"""
Consiglio v1 — Multi-LLM deliberation with groupthink detection.

SYMBIOSIS Pilastro 4 (Confronto): "L'intelligenza non nasce dal consenso
di un LLM che si da' ragione da solo, ma dallo scontro tra prospettive diverse."

This package implements periodic council sessions where 3+ LLM agents
(Claude, Gemini, DeepSeek, Ollama) deliberate on a topic in parallel,
consensus is scored, groupthink is detected, and a moderator synthesizes
the final decision.
"""
from mata_garuda.council.models import (
    AgentVote,
    ConsensusResult,
    CouncilDecision,
    Dissent,
    Topic,
)
from mata_garuda.council.orchestrator import CouncilOrchestrator

__all__ = [
    "AgentVote",
    "ConsensusResult",
    "CouncilDecision",
    "CouncilOrchestrator",
    "Dissent",
    "Topic",
]
