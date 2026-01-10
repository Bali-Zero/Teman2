from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Import BaseTool and helper from definitions to avoid duplication
from backend.services.tools.definitions import BaseTool, _convert_schema_to_gemini_format


class ToolType(str, Enum):
    VECTOR_SEARCH = "vector_search"
    WEB_SEARCH = "web_search"
    CALCULATOR = "calculator"
    DATE_LOOKUP = "date_lookup"
    DATABASE_QUERY = "database_query"
    VISION = "vision"
    CODE_EXECUTION = "code_execution"
    PRICING = "pricing"


@dataclass
class Tool:
    name: str
    description: str
    tool_type: ToolType
    parameters: dict[str, Any]
    function: Callable
    requires_confirmation: bool = False


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    result: str | None = None
    success: bool = True
    error: str | None = None
    execution_time: float = 0.0  # Duration in seconds for metrics


@dataclass
class AgentStep:
    step_number: int
    thought: str
    action: ToolCall | None = None
    observation: str | None = None
    is_final: bool = False


@dataclass
class AgentState:
    query: str
    steps: list[AgentStep] = field(default_factory=list)
    context_gathered: list[str] = field(default_factory=list)
    final_answer: str | None = None
    max_steps: int = 3
    current_step: int = 0
    skip_rag: bool = False  # Skip RAG evidence requirements for general tasks


# BaseTool and _convert_schema_to_gemini_format are imported from backend.services.tools.definitions
# to avoid code duplication. This maintains backward compatibility for existing imports.

__all__ = [
    "ToolType",
    "Tool",
    "ToolCall",
    "AgentStep",
    "AgentState",
    "BaseTool",
    "_convert_schema_to_gemini_format",
]
