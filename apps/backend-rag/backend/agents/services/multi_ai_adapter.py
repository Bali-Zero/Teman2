"""
🤖 Multi-AI Adapter - Route tasks to best AI

Integra:
- Qwen (Ollama) - Locale, test generation, privacy
- Gemini CLI - Code analysis, documentation, refactoring
- Claude Max (Opus) - Primary AI, architecture, complex reasoning
- Cursor - IDE integration, code editing
- Windsurf - IDE integration, AI-powered editing
- Google Colab - Jupyter notebook cloud
- Google Cloud Shell Editor - Cloud-based editor

Routes tasks to the best AI based on task type and requirements.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AITool(Enum):
    """Available AI tools"""

    QWEN = "qwen"  # Ollama/Qwen - Locale
    GEMINI = "gemini"  # Gemini CLI
    CLAUDE = "claude"  # Anthropic Claude API
    CURSOR = "cursor"  # Cursor IDE
    WINDSURF = "windsurf"  # Windsurf IDE
    GOOGLE_COLAB = "google_colab"  # Google Colab
    GOOGLE_CLOUD_SHELL = "google_cloud_shell"  # Google Cloud Shell Editor


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
    """Adapter for Gemini CLI

    Usa Gemini CLI che gestisce automaticamente l'autenticazione Google.
    Non serve API key separata se hai abbonamento/configurazione Google.
    """

    def __init__(self, model: str = "gemini-2.0-flash-exp") -> None:
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
    """Adapter for Anthropic Claude API - Claude Max (Opus)

    Usa abbonamento Claude invece di API key separata.
    L'API key può essere collegata all'account con abbonamento.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-3-opus-20240229") -> None:
        # Prova prima API key esplicita, poi env var, poi cerca in configurazioni comuni
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        self.model = model
        self.client = None

        # Prova a inizializzare anche senza API key esplicita
        # (potrebbe essere gestita dall'abbonamento)
        try:
            import anthropic

            if self.api_key:
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("✅ Claude Max configurato con API key")
            else:
                # Prova senza API key (potrebbe usare credenziali di sistema/abbonamento)
                try:
                    self.client = anthropic.Anthropic()
                    logger.info("✅ Claude Max configurato con abbonamento/credenziali di sistema")
                except Exception:
                    logger.info("ℹ️ Claude Max: configura ANTHROPIC_API_KEY o usa abbonamento")
        except ImportError:
            logger.warning("⚠️ anthropic package not installed. Install with: pip install anthropic")
        except Exception as e:
            logger.debug(f"Claude initialization: {e}")

    async def generate(self, prompt: str, context: dict[str, Any] | None = None) -> AIResponse:
        """Generate using Claude API (con abbonamento)"""
        import time

        if not self.client:
            raise RuntimeError(
                "Claude client not initialized. "
                "Configura ANTHROPIC_API_KEY o usa abbonamento Claude.",
            )

        start_time = time.time()

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8192,  # Claude Max supports up to 8192 tokens
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

    def __init__(self) -> None:
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

    Strategy (Claude Max Primary):
    - Claude Max (Opus): Primary for most tasks (code analysis, documentation, refactoring, architecture, code review)
    - Qwen: Test generation, privacy-sensitive tasks (local, fast)
    - Gemini: Fallback for code analysis/documentation if Claude unavailable
    - Cursor: Code editing (IDE-based)
    """

    def __init__(self, qwen_adapter=None, project_root: Path | None = None) -> None:
        # Import Qwen adapter (existing)
        if qwen_adapter:
            self.qwen = qwen_adapter
        else:
            from backend.agents.services.llm_adapter import get_llm_adapter

            self.qwen_adapter_ref = get_llm_adapter()
            self.qwen = self.qwen_adapter_ref

        # Initialize other adapters
        self.gemini = GeminiAdapter()
        # Claude Max (Opus) - Primary AI tool
        self.claude = ClaudeAdapter(model="claude-3-opus-20240229")

        # Cursor adapter (IDE integration)
        try:
            from backend.agents.services.cursor_adapter import get_cursor_adapter

            self.cursor = get_cursor_adapter(project_root)
        except Exception as e:
            logger.warning(f"⚠️ Cursor adapter not available: {e}")
            self.cursor = None

        # Windsurf adapter (IDE integration)
        try:
            from backend.agents.services.windsurf_adapter import get_windsurf_adapter

            self.windsurf = get_windsurf_adapter()
            if self.windsurf.is_available():
                logger.info("✅ Windsurf disponibile")
        except Exception as e:
            logger.warning(f"⚠️ Windsurf adapter not available: {e}")
            self.windsurf = None

        # Google Colab adapter
        try:
            from backend.agents.services.google_colab_adapter import get_colab_adapter

            self.google_colab = get_colab_adapter()
        except Exception as e:
            logger.warning(f"⚠️ Google Colab adapter not available: {e}")
            self.google_colab = None

        # Google Cloud Shell Editor adapter
        try:
            from backend.agents.services.google_cloud_shell_adapter import get_cloud_shell_adapter

            self.google_cloud_shell = get_cloud_shell_adapter()
        except Exception as e:
            logger.warning(f"⚠️ Google Cloud Shell adapter not available: {e}")
            self.google_cloud_shell = None

        # Routing map: task_type -> preferred AI
        # Claude Max (Opus) is primary for most tasks
        self.routing_map = {
            TaskType.TEST_GENERATION: AITool.QWEN,  # Keep Qwen for test generation (local, fast)
            TaskType.SIMPLE_TASK: AITool.CLAUDE,  # Claude Max for simple tasks
            TaskType.PRIVACY_SENSITIVE: AITool.QWEN,  # Keep Qwen for privacy-sensitive
            TaskType.CODE_ANALYSIS: AITool.CLAUDE,  # Claude Max for code analysis
            TaskType.DOCUMENTATION: AITool.CLAUDE,  # Claude Max for documentation
            TaskType.REFACTORING: AITool.CLAUDE,  # Claude Max for refactoring
            TaskType.CODE_REVIEW: AITool.CLAUDE,  # Claude Max for code review
            TaskType.ARCHITECTURE: AITool.CLAUDE,  # Claude Max for architecture
            TaskType.CODE_EDITING: AITool.CURSOR,  # Cursor for IDE-based editing
        }

        logger.info("🤖 Multi-AI Adapter initialized")

    def _select_ai(self, request: AIRequest) -> tuple[AITool, Any]:
        """Select best AI for task"""
        # Use preferred tool if specified
        if request.preferred_tool:
            tool = request.preferred_tool
        else:
            # Default to Claude Max for most tasks, fallback to Qwen
            tool = self.routing_map.get(request.task_type, AITool.CLAUDE)

        # Get adapter
        adapters = {
            AITool.QWEN: self.qwen,
            AITool.GEMINI: self.gemini,
            AITool.CLAUDE: self.claude,
            AITool.CURSOR: self.cursor if self.cursor else None,
            AITool.WINDSURF: self.windsurf
            if self.windsurf and self.windsurf.is_available()
            else None,
            AITool.GOOGLE_COLAB: self.google_colab
            if self.google_colab and self.google_colab.is_available()
            else None,
            AITool.GOOGLE_CLOUD_SHELL: self.google_cloud_shell
            if self.google_cloud_shell and self.google_cloud_shell.is_available()
            else None,
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
                from backend.agents.services.llm_adapter import LLMProvider, LLMRequest

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
                # Claude Max (Opus) - primary AI
                return await adapter.generate(request.prompt, request.context)

            elif tool == AITool.CURSOR:
                if adapter:
                    # Cursor is IDE-based, open file if provided
                    if request.files:
                        adapter.open_file(request.files[0])
                    return AIResponse(
                        text="File opened in Cursor IDE. Use Cursor IDE for AI-powered editing.",
                        tool_used=AITool.CURSOR,
                        metadata={"note": "IDE-based tool"},
                    )
                else:
                    raise RuntimeError("Cursor adapter not available")

            elif tool == AITool.WINDSURF:
                if adapter:
                    # Windsurf is IDE-based, open file if provided
                    if request.files:
                        adapter.open_file(request.files[0])
                    return AIResponse(
                        text="File opened in Windsurf IDE. Use Windsurf IDE for AI-powered editing.",
                        tool_used=AITool.WINDSURF,
                        metadata={"note": "IDE-based tool"},
                    )
                else:
                    raise RuntimeError("Windsurf adapter not available")

            elif tool == AITool.GOOGLE_COLAB:
                if adapter:
                    return await adapter.generate(request.prompt, request.context)
                else:
                    raise RuntimeError("Google Colab adapter not available")

            elif tool == AITool.GOOGLE_CLOUD_SHELL:
                if adapter:
                    return await adapter.generate(request.prompt, request.context)
                else:
                    raise RuntimeError("Google Cloud Shell adapter not available")

            else:
                raise ValueError(f"Unknown tool: {tool}")

        except Exception as e:
            logger.error(f"❌ {tool.value} failed: {e}")
            # Fallback to Qwen if available
            if tool != AITool.QWEN:
                logger.info("🔄 Falling back to Qwen...")
                try:
                    from backend.agents.services.llm_adapter import LLMProvider, LLMRequest

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

        # Check Windsurf
        if self.windsurf and self.windsurf.is_available():
            available.append(AITool.WINDSURF)

        # Check Google Colab
        if self.google_colab and self.google_colab.is_available():
            available.append(AITool.GOOGLE_COLAB)

        # Check Google Cloud Shell
        if self.google_cloud_shell and self.google_cloud_shell.is_available():
            available.append(AITool.GOOGLE_CLOUD_SHELL)

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
