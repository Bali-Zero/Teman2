"""
🤖 Multi-AI Adapter - Route tasks to best AI

Integra:
- Qwen (Ollama) - Locale, test generation, privacy
- Gemini CLI - Code analysis, documentation, refactoring
- Claude Code (Anthropic) - Architecture, complex reasoning
- Cursor - IDE integration, code editing

Routes tasks to the best AI based on task type and requirements.
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AITool(Enum):
    """Available AI tools"""

    QWEN = "qwen"  # Ollama/Qwen - Locale
    GEMINI = "gemini"  # Gemini CLI
    CLAUDE = "claude"  # Anthropic Claude API
    CURSOR = "cursor"  # Cursor IDE


class TaskType(Enum):
    """Task types for routing"""

    TEST_GENERATION = "test_generation"
    CODE_ANALYSIS = "code_analysis"
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    CODE_REVIEW = "code_review"
    SIMPLE_TASK = "simple_task"
    PRIVACY_SENSITIVE = "privacy_sensitive"
    CODE_EDITING = "code_editing"


@dataclass
class AIRequest:
    """Request for AI generation"""

    task_type: TaskType
    prompt: str
    context: dict[str, Any] | None = None
    files: list[str] | None = None
    preferred_tool: AITool | None = None


@dataclass
class AIResponse:
    """Response from AI"""

    text: str
    tool_used: AITool
    tokens_used: int = 0
    response_time: float = 0.0
    metadata: dict[str, Any] | None = None


class GeminiAdapter:
    """Adapter for Gemini CLI"""

    def __init__(self, model: str = "gemini-2.0-flash-exp"):
        self.model = model
        self.gemini_cmd = "gemini"

    async def generate(self, prompt: str, context: dict[str, Any] | None = None) -> AIResponse:
        """Generate using Gemini CLI"""
        import time

        start_time = time.time()

        try:
            # Build command
            cmd = [self.gemini_cmd, prompt]

            # Add model if specified
            if self.model:
                cmd.extend(["-m", self.model])

            # Execute Gemini CLI
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300.0,  # 5 minutes
            )

            if result.returncode != 0:
                raise RuntimeError(f"Gemini CLI error: {result.stderr}")

            response_text = result.stdout.strip()

            return AIResponse(
                text=response_text,
                tool_used=AITool.GEMINI,
                response_time=time.time() - start_time,
                metadata={"model": self.model},
            )

        except subprocess.TimeoutExpired:
            raise RuntimeError("Gemini CLI timeout")
        except Exception as e:
            logger.error(f"❌ Gemini CLI failed: {e}")
            raise


class ClaudeAdapter:
    """Adapter for Anthropic Claude API"""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None

        if self.api_key:
            try:
                import anthropic

                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("⚠️ anthropic package not installed. Install with: pip install anthropic")
            except Exception as e:
                logger.warning(f"⚠️ Claude client initialization failed: {e}")

    async def generate(self, prompt: str, context: dict[str, Any] | None = None) -> AIResponse:
        """Generate using Claude API"""
        import time

        if not self.client:
            raise RuntimeError("Claude client not initialized. Set ANTHROPIC_API_KEY")

        start_time = time.time()

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            tokens_used = message.usage.input_tokens + message.usage.output_tokens

            return AIResponse(
                text=response_text,
                tool_used=AITool.CLAUDE,
                tokens_used=tokens_used,
                response_time=time.time() - start_time,
                metadata={"model": self.model},
            )

        except Exception as e:
            logger.error(f"❌ Claude API failed: {e}")
            raise


class CursorAdapter:
    """Adapter for Cursor IDE integration"""

    def __init__(self):
        self.cursor_cmd = "cursor"

    async def generate(self, prompt: str, files: list[str] | None = None) -> AIResponse:
        """Generate/edit using Cursor"""
        import time

        start_time = time.time()

        try:
            # Cursor can be used via CLI for file operations
            # For now, we'll use it for file context
            if files:
                # Open files in Cursor for context
                cmd = [self.cursor_cmd] + files
                subprocess.run(cmd, capture_output=True, timeout=10.0)

            # Note: Cursor is primarily IDE-based
            # For programmatic use, we'd need Cursor API/extension
            # This is a placeholder for future integration

            return AIResponse(
                text="Cursor integration requires IDE context. Use Cursor IDE directly for code editing.",
                tool_used=AITool.CURSOR,
                response_time=time.time() - start_time,
                metadata={"note": "IDE-based tool"},
            )

        except Exception as e:
            logger.warning(f"⚠️ Cursor integration limited: {e}")
            raise


class MultiAIAdapter:
    """
    Multi-AI Adapter - Routes tasks to best AI
    
    Strategy:
    - Qwen: Test generation, simple tasks, privacy-sensitive
    - Gemini: Code analysis, documentation, refactoring
    - Claude: Architecture, complex reasoning, design patterns
    - Cursor: Code editing (IDE-based)
    """

    def __init__(self, qwen_adapter=None):
        # Import Qwen adapter (existing)
        if qwen_adapter:
            self.qwen = qwen_adapter
        else:
            from backend.agents.services.llm_adapter import get_llm_adapter, LLMRequest, LLMProvider

            self.qwen_adapter_ref = get_llm_adapter()
            self.qwen = self.qwen_adapter_ref

        # Initialize other adapters
        self.gemini = GeminiAdapter()
        self.claude = ClaudeAdapter()
        self.cursor = CursorAdapter()

        # Routing map: task_type -> preferred AI
        self.routing_map = {
            TaskType.TEST_GENERATION: AITool.QWEN,
            TaskType.SIMPLE_TASK: AITool.QWEN,
            TaskType.PRIVACY_SENSITIVE: AITool.QWEN,
            TaskType.CODE_ANALYSIS: AITool.GEMINI,
            TaskType.DOCUMENTATION: AITool.GEMINI,
            TaskType.REFACTORING: AITool.GEMINI,
            TaskType.CODE_REVIEW: AITool.GEMINI,
            TaskType.ARCHITECTURE: AITool.CLAUDE,
            TaskType.CODE_EDITING: AITool.CURSOR,
        }

        logger.info("🤖 Multi-AI Adapter initialized")

    def _select_ai(self, request: AIRequest) -> tuple[AITool, Any]:
        """Select best AI for task"""
        # Use preferred tool if specified
        if request.preferred_tool:
            tool = request.preferred_tool
        else:
            tool = self.routing_map.get(request.task_type, AITool.QWEN)

        # Get adapter
        adapters = {
            AITool.QWEN: self.qwen,
            AITool.GEMINI: self.gemini,
            AITool.CLAUDE: self.claude,
            AITool.CURSOR: self.cursor,
        }

        adapter = adapters.get(tool)
        if not adapter:
            raise ValueError(f"Adapter not found for tool: {tool}")

        return tool, adapter

    async def generate(self, request: AIRequest) -> AIResponse:
        """Generate using best AI for task"""
        tool, adapter = self._select_ai(request)

        logger.info(f"🎯 Routing {request.task_type.value} to {tool.value}")

        try:
            # Route to appropriate adapter
            if tool == AITool.QWEN:
                # Use existing Qwen adapter
                from backend.agents.services.llm_adapter import LLMRequest, LLMProvider

                llm_request = LLMRequest(
                    prompt=request.prompt,
                    max_tokens=2000,
                    temperature=0.2,
                    provider=LLMProvider.OLLAMA,
                )
                response = await adapter.generate(llm_request)
                return AIResponse(
                    text=response.text,
                    tool_used=AITool.QWEN,
                    tokens_used=response.tokens_used,
                    response_time=response.response_time,
                )

            elif tool == AITool.GEMINI:
                return await adapter.generate(request.prompt, request.context)

            elif tool == AITool.CLAUDE:
                return await adapter.generate(request.prompt, request.context)

            elif tool == AITool.CURSOR:
                return await adapter.generate(request.prompt, request.files)

            else:
                raise ValueError(f"Unknown tool: {tool}")

        except Exception as e:
            logger.error(f"❌ {tool.value} failed: {e}")
            # Fallback to Qwen if available
            if tool != AITool.QWEN:
                logger.info(f"🔄 Falling back to Qwen...")
                try:
                    from backend.agents.services.llm_adapter import LLMRequest, LLMProvider

                    llm_request = LLMRequest(
                        prompt=request.prompt,
                        max_tokens=2000,
                        temperature=0.2,
                        provider=LLMProvider.OLLAMA,
                    )
                    response = await self.qwen.generate(llm_request)
                    return AIResponse(
                        text=response.text,
                        tool_used=AITool.QWEN,
                        tokens_used=response.tokens_used,
                        response_time=response.response_time,
                        metadata={"fallback": True},
                    )
                except Exception as e2:
                    logger.error(f"❌ Qwen fallback also failed: {e2}")
                    raise
            raise

    def get_available_tools(self) -> list[AITool]:
        """Get list of available AI tools"""
        available = [AITool.QWEN]  # Qwen always available

        # Check Gemini CLI
        try:
            result = subprocess.run(["gemini", "--version"], capture_output=True, timeout=5.0)
            if result.returncode == 0:
                available.append(AITool.GEMINI)
        except Exception:
            pass

        # Check Claude API
        if self.claude.client:
            available.append(AITool.CLAUDE)

        # Check Cursor
        try:
            result = subprocess.run(["cursor", "--version"], capture_output=True, timeout=5.0)
            if result.returncode == 0:
                available.append(AITool.CURSOR)
        except Exception:
            pass

        return available


# Singleton instance
_multi_ai_adapter: MultiAIAdapter | None = None


def get_multi_ai_adapter() -> MultiAIAdapter:
    """Get singleton Multi-AI adapter instance"""
    global _multi_ai_adapter
    if _multi_ai_adapter is None:
        _multi_ai_adapter = MultiAIAdapter()
    return _multi_ai_adapter
