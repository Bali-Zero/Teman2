from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


def _convert_schema_to_gemini_format(schema: dict) -> dict:
    """Convert JSON Schema to Gemini-compatible format.

    Gemini requires:
    - Type values as uppercase strings (STRING, NUMBER, INTEGER, BOOLEAN, ARRAY, OBJECT)
    - Nested properties without explicit type when they have sub-properties

    Args:
        schema: Standard JSON Schema dict

    Returns:
        Gemini-compatible schema dict
    """
    if not isinstance(schema, dict):
        return schema

    result = {}

    # Convert type to uppercase
    if "type" in schema:
        type_value = schema["type"]
        # Map JSON Schema types to Gemini types
        type_mapping = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT"
        }
        result["type"] = type_mapping.get(type_value, type_value.upper() if isinstance(type_value, str) else type_value)

    # Recursively convert properties
    if "properties" in schema:
        result["properties"] = {
            key: _convert_schema_to_gemini_format(value)
            for key, value in schema["properties"].items()
        }

    # Copy other fields as-is
    for key in schema:
        if key not in ("type", "properties"):
            result[key] = schema[key]

    return result


class ToolType(Enum):
    RETRIEVAL = "retrieval"
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
    result: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class AgentStep:
    step_number: int
    thought: str
    action: Optional[ToolCall] = None
    observation: Optional[str] = None
    is_final: bool = False


@dataclass
class AgentState:
    query: str
    steps: list[AgentStep] = field(default_factory=list)
    context_gathered: list[str] = field(default_factory=list)
    final_answer: Optional[str] = None
    max_steps: int = 3  # Optimized: reduced from 5 to 3 for faster responses
    current_step: int = 0


class BaseTool(ABC):
    """Base class per tutti i tool"""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        pass

    def to_gemini_function_declaration(self) -> dict:
        """Convert tool to Gemini function declaration format.

        This method exports the tool definition in the format required by
        Gemini's native function calling API. The returned declaration is
        used to inform the model about available tools during generation.

        Returns:
            Dict with function declaration following Gemini schema:
                - name: Function identifier
                - description: What the function does
                - parameters: JSON schema with type, properties, required fields

        Example:
            >>> tool = VectorSearchTool(retriever)
            >>> declaration = tool.to_gemini_function_declaration()
            >>> print(declaration)
            {
                "name": "vector_search",
                "description": "Search the legal document knowledge base...",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {...},
                    "required": [...]
                }
            }
        """
        schema = self.parameters_schema
        # Convert schema to Gemini-compatible format
        gemini_schema = _convert_schema_to_gemini_format(schema)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": gemini_schema,
        }

    def to_gemini_tool(self) -> dict:
        """Legacy method - use to_gemini_function_declaration() instead."""
        return self.to_gemini_function_declaration()
