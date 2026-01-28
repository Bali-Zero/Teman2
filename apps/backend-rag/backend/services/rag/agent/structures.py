"""
RAG Agent data structures for Nuzantara.

This module defines the core data structures used by the agentic RAG system,
including tool definitions, execution state, and step tracking.

Classes:
    ToolType: Enumeration of available tool types.
    Tool: Definition of an executable tool.
    ToolCall: Record of a tool invocation and its result.
    AgentStep: Single step in agent reasoning chain.
    AgentState: Complete state of an agent execution.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Import BaseTool and helper from definitions to avoid duplication
from backend.services.tools.definitions import BaseTool, _convert_schema_to_gemini_format


class ToolType(str, Enum):
    """
    Enumeration of tool types available to the RAG agent.

    Attributes:
        VECTOR_SEARCH: Semantic search in vector database.
        WEB_SEARCH: External web search capability.
        CALCULATOR: Mathematical computation tool.
        DATE_LOOKUP: Date and time operations.
        DATABASE_QUERY: Direct database query execution.
        VISION: Image analysis and understanding.
        CODE_EXECUTION: Safe code execution sandbox.
        PRICING: Pricing calculation and lookup.
    """

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
    """
    Definition of an executable tool for the agent.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of tool functionality.
        tool_type: Category of tool from ToolType enum.
        parameters: JSON schema of tool parameters.
        function: Callable that executes the tool.
        requires_confirmation: Whether user confirmation is needed before execution.
    """

    name: str
    description: str
    tool_type: ToolType
    parameters: dict[str, Any]
    function: Callable
    requires_confirmation: bool = False


@dataclass
class ToolCall:
    """
    Record of a tool invocation and its result.

    Attributes:
        tool_name: Name of the invoked tool.
        arguments: Arguments passed to the tool.
        result: Output from tool execution, if successful.
        success: Whether the tool executed without errors.
        error: Error message if execution failed.
        execution_time: Duration of execution in seconds.
    """

    tool_name: str
    arguments: dict[str, Any]
    result: str | None = None
    success: bool = True
    error: str | None = None
    execution_time: float = 0.0


@dataclass
class AgentStep:
    """
    Single step in the agent's reasoning chain.

    Attributes:
        step_number: Sequential number of this step.
        thought: Agent's reasoning for this step.
        action: Tool call made in this step, if any.
        observation: Result observed after action.
        is_final: Whether this step produces the final answer.
    """

    step_number: int
    thought: str
    action: ToolCall | None = None
    observation: str | None = None
    is_final: bool = False


@dataclass
class AgentState:
    """
    Complete state of an agent execution session.

    Tracks the full reasoning chain from query to final answer,
    including all intermediate steps and gathered context.

    Attributes:
        query: Original user query being processed.
        steps: List of reasoning steps taken.
        context_gathered: Accumulated context from tool calls.
        final_answer: Generated answer, when complete.
        max_steps: Maximum allowed reasoning steps.
        current_step: Current step number in execution.
        skip_rag: Skip RAG evidence requirements for general tasks.
    """

    query: str
    steps: list[AgentStep] = field(default_factory=list)
    context_gathered: list[str] = field(default_factory=list)
    final_answer: str | None = None
    max_steps: int = 3
    current_step: int = 0
    skip_rag: bool = False


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
