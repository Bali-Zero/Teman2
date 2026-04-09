"""
Mata Garuda — Pydantic models per Agent, Response, Result.

Pattern estratto da HKUDS/AutoAgent autoagent/types.py.
Differenze vs originale:
- Rimossa dipendenza litellm.types (usavamo solo Message stub)
- Aggiunto field `genome_path` su Agent per Lamarckian
- Default model = "claude" (CLI subprocess), non "gpt-4o"

Riferimento doc: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md
Status: POC reference code.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# Type alias per le funzioni-tool che gli agenti possono chiamare
AgentFunction = Callable[..., Union[str, "Agent", dict]]


class Agent(BaseModel):
    """Definizione di un agente Mata Garuda."""

    name: str = "Agent"
    model: str = "claude"  # CLI runtime: "claude" | "gemini" | "codex" | "deepseek"
    instructions: Union[str, Callable[[dict], str]] = "You are a helpful agent."
    functions: List[AgentFunction] = Field(default_factory=list)
    tool_choice: Optional[str] = None  # "required" forces tool use
    parallel_tool_calls: bool = False

    # Mata Garuda specific
    genome_path: Optional[str] = None  # path to GENOME.md, set at registration time
    layer: Optional[str] = None  # "harvester" | "kognitif" | "analista" | "meta"

    class Config:
        # Permettere Callable come field type
        arbitrary_types_allowed = True


class Response(BaseModel):
    """Output di un round di esecuzione agente."""

    messages: List[dict] = Field(default_factory=list)
    agent: Optional[Agent] = None
    context_variables: dict = Field(default_factory=dict)


class Result(BaseModel):
    """
    Wrapper per il return value di una funzione-tool.
    Permette di ritornare un nuovo agente (handoff) o aggiornare contesto.
    """

    value: str = ""
    agent: Optional[Agent] = None  # se settato, switch a questo agente
    context_variables: dict = Field(default_factory=dict)
    image: Optional[str] = None  # base64 encoded, per multimodal output
