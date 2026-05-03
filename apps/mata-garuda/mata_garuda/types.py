"""
Mata Garuda — Pydantic models per Agent, Response, Result.

Pattern estratto da HKUDS/AutoAgent autoagent/types.py, adattato:
- Rimossa dipendenza litellm.types
- Aggiunto genome_path su Agent per Lamarckian
- Default model = "claude" (CLI subprocess)
- Aggiunto layer per organizzazione (harvester/kognitif/analista/meta)

Riferimento: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md
"""
from __future__ import annotations

from typing import Callable, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


# Type alias per le funzioni-tool che gli agenti possono chiamare
AgentFunction = Callable[..., Union[str, "Agent", dict]]


class Agent(BaseModel):
    """Definizione di un agente Mata Garuda."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "Agent"
    model: str = "claude"  # CLI runtime: "claude" | "gemini" | "codex" | "deepseek"
    instructions: Union[str, Callable[[dict], str]] = "You are a helpful agent."
    functions: List[AgentFunction] = Field(default_factory=list)
    tool_choice: Optional[str] = None  # "required" forces tool use
    parallel_tool_calls: bool = False

    # Mata Garuda specific
    genome_path: Optional[str] = None  # path to GENOME.md
    layer: Optional[str] = None  # "harvester" | "kognitif" | "analista" | "meta"


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: str = ""
    agent: Optional[Agent] = None  # se settato, switch a questo agente
    context_variables: dict = Field(default_factory=dict)
    image: Optional[str] = None  # base64 encoded, per multimodal output


class RunOutcome(BaseModel):
    """Rich outcome of a single agent run, for multi-dimensional fitness."""

    agent_name: str
    success: bool
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None

    @property
    def efficiency(self) -> Optional[float]:
        """Tokens per millisecond — lower is more efficient."""
        if self.tokens_used and self.duration_ms and self.duration_ms > 0:
            return self.tokens_used / self.duration_ms
        return None
