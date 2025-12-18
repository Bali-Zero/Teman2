import ast
import asyncio
import logging
import operator
import re
from typing import Any

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseTool:
    name: str | None = None
    description: str | None = None
    parameters: dict | None = None

    async def execute(self, **kwargs) -> Any:
        raise NotImplementedError


class SafeMathEvaluator:
    """
    Safe arithmetic evaluator using AST parsing.
    Supports: +, -, *, /, **, (), abs(), round()
    No eval() - parses and evaluates AST nodes directly.
    """

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    FUNCTIONS = {
        "abs": abs,
        "round": round,
    }

    def evaluate(self, expression: str) -> float:
        """Safely evaluate a mathematical expression."""
        expression = expression.strip()
        # Basic sanitization - only allow safe characters
        if not re.match(r"^[\d\s\+\-\*\/\.\(\)\,a-z]+$", expression.lower()):
            raise ValueError("Expression contains invalid characters")
        compact_expr = re.sub(r"\s+", "", expression)
        if "++" in compact_expr:
            raise ValueError("Invalid expression: consecutive operators")

        try:
            tree = ast.parse(expression, mode="eval")
            return self._eval_node(tree.body)
        except (SyntaxError, TypeError) as e:
            raise ValueError(f"Invalid expression: {e}") from e

    def _eval_node(self, node: ast.AST) -> float:
        """Recursively evaluate AST nodes."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int | float):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)

        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(operand)

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            func_name = node.func.id.lower()
            func = self.FUNCTIONS.get(func_name)
            if func is None:
                raise ValueError(f"Unknown function: {func_name}")
            args = [self._eval_node(arg) for arg in node.args]
            return func(*args)

        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")


class CalculatorTool(BaseTool):
    def __init__(self):
        self.name = "calculator"
        self.description = "Perform mathematical calculations."
        self.parameters = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate.",
                }
            },
            "required": ["expression"],
        }
        self._evaluator = SafeMathEvaluator()

    async def execute(self, expression: str) -> str:
        try:
            result = self._evaluator.evaluate(expression)
            return str(result)
        except Exception as e:
            return f"Error calculating: {str(e)}"


class AgenticRAGOrchestrator:
    def __init__(self, memory_service=None, search_service=None):
        # Tool-calling is currently disabled to avoid half-implemented flows.
        # Keep the registry for future enablement, but do not auto-trigger.
        self.tools = [CalculatorTool()]
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.memory_service = memory_service
        self.search_service = search_service

        # Configure Gemini only when a real key is provided
        self.model = None
        api_key = settings.google_api_key
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(settings.gemini_model_smart)
        else:
            logger.warning("AgenticRAGOrchestrator running without Gemini key; using mock mode")

    async def initialize(self):
        """Async initialization if needed."""
        return

    async def process_query(
        self, query: str, user_id: str = "anonymous", enable_vision: bool = False
    ) -> dict[str, Any]:
        """
        Process a query using the agentic RAG approach with Memory and Search.
        """
        _ = enable_vision  # unused for now; reserved for future multimodal support
        start_time = asyncio.get_event_loop().time()

        # If the model is not available (e.g., test/mock mode), return a safe stub
        if not self.model:
            return {
                "answer": "Agentic orchestrator running in mock mode (no LLM available).",
                "sources": [],
                "context_used": 0,
                "execution_time": asyncio.get_event_loop().time() - start_time,
                "route_used": "agentic_v2_mock",
                "steps": [],
                "status": "degraded",
            }

        # 1. Gather Context (Parallel)
        memory_task = (
            self.memory_service.get_memory(user_id) if self.memory_service else asyncio.sleep(0)
        )
        history_task = (
            self.memory_service.get_recent_history(user_id, limit=5)
            if self.memory_service
            else asyncio.sleep(0)
        )
        search_task = (
            self.search_service.search(query, user_level=3, limit=3)
            if self.search_service
            else asyncio.sleep(0)
        )

        results = await asyncio.gather(memory_task, history_task, search_task)

        user_memory = results[0] if self.memory_service else None
        history = results[1] if self.memory_service else []
        search_results = results[2] if self.search_service else {"results": []}

        # 2. Construct Context String
        context_str = ""

        # Add User Profile Context
        if user_memory:
            context_str += f"USER PROFILE:\n- ID: {user_id}\n"
            if user_memory.profile_facts:
                context_str += (
                    "- Facts:\n" + "\n".join([f"  * {f}" for f in user_memory.profile_facts]) + "\n"
                )
            if user_memory.summary:
                context_str += f"- Summary: {user_memory.summary}\n"
            context_str += "\n"

        # Add RAG Sources
        sources_list = []
        if search_results and search_results.get("results"):
            context_str += "RELEVANT KNOWLEDGE (RAG):\n"
            for i, res in enumerate(search_results["results"], 1):
                content = res.get("text", "")[:500]  # Truncate for prompt
                source_meta = res.get("metadata", {})
                title = source_meta.get("filename") or source_meta.get("title") or "Unknown Source"
                context_str += f"[{i}] {title}: {content}...\n"
                sources_list.append({"title": title, "content": content})
            context_str += "\n"

        # Add Conversation History
        if history:
            context_str += "RECENT CONVERSATION:\n"
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_str += f"{role.upper()}: {content}\n"
            context_str += "\n"

        try:
            # 3. Generate Response
            system_prompt = f"""
            You are Zantara, an intelligent AI assistant for the Nuzantara team.

            CONTEXT INFORMATION:
            {context_str}

            USER QUERY: {query}

            AVAILABLE TOOLS (read-only list):
            {[t.name for t in self.tools]}
            Note: tool-calling is currently disabled in this runtime; respond directly.

            INSTRUCTIONS:
            1. Answer the user's query based on the Context Information provided.
            2. If the user asks about themselves, use the User Profile section.
            3. If the user refers to previous messages, use the Recent Conversation section.
            4. If the answer requires specific knowledge, use the Relevant Knowledge section and cite sources if possible.
            5. Be helpful, professional, and concise.
            """

            response = await self.model.generate_content_async(system_prompt)
            text_response = response.text

            return {
                "answer": text_response,
                "sources": sources_list,
                "context_used": len(context_str),
                "execution_time": asyncio.get_event_loop().time() - start_time,
                "route_used": "agentic_v2",
                "steps": [],
            }

        except Exception as e:
            logger.error(f"Agentic RAG error: {e}")
            raise e
