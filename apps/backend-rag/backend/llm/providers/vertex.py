"""
Vertex AI LLM Provider

Wraps the existing VertexAIService to implement the LLMProvider interface.
Note: VertexAIService is sync-only, so we wrap it accordingly.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class VertexProvider(LLMProvider):
    """
    LLMProvider adapter for Google Vertex AI.

    Used for specialized tasks like metadata extraction.
    Note: Currently sync-only, no streaming support.
    """

    def __init__(self, project_id: str = None, location: str = "us-central1"):
        """
        Initialize Vertex AI provider.

        Args:
            project_id: Google Cloud Project ID
            location: Vertex AI location (default: us-central1)
        """
        self._project_id = project_id
        self._location = location
        self._service = None
        self._available = False
        self._init_service()

    def _init_service(self):
        """Lazy initialize the underlying service."""
        try:
            from services.llm_clients.vertex_ai_service import VertexAIService

            self._service = VertexAIService(project_id=self._project_id, location=self._location)
            # Vertex AI availability depends on credentials
            self._available = True
            logger.info(f"VertexProvider initialized: project={self._project_id}")
        except ImportError:
            logger.warning("vertexai module not installed, VertexProvider disabled")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to initialize VertexProvider: {e}")
            self._available = False

    @property
    def name(self) -> str:
        return "vertex"

    @property
    def is_available(self) -> bool:
        return self._available and self._service is not None

    async def generate(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> LLMResponse:
        """
        Generate response using Vertex AI.

        Note: Vertex AI service is specialized for metadata extraction.
        For general chat, use Gemini or OpenRouter instead.
        """
        if not self.is_available:
            raise RuntimeError("Vertex AI provider not available")

        # Combine all messages into a single prompt
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.insert(0, msg.content)
            else:
                prompt_parts.append(f"{msg.role}: {msg.content}")

        full_prompt = "\n\n".join(prompt_parts)

        # Vertex AI's extract_metadata is async, use it directly
        # For general generation, we'd need to extend VertexAIService
        try:
            # Run the sync model.generate_content in a thread pool
            def _generate():
                self._service._ensure_initialized()
                response = self._service.model.generate_content(full_prompt)
                return response.text if response else ""

            content = await asyncio.get_event_loop().run_in_executor(None, _generate)

            return LLMResponse(
                content=content, model="gemini-pro", provider=self.name, finish_reason="stop"
            )
        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}")
            raise

    async def stream(
        self, messages: list[LLMMessage], temperature: float = 0.7, **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response using Vertex AI.

        Note: Vertex AI doesn't natively support streaming in our current setup.
        This yields the full response as a single chunk.
        """
        response = await self.generate(messages, temperature, **kwargs)
        yield response.content
