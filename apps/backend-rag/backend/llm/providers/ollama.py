"""
Ollama LLM Provider
Local LLM provider using Ollama API (Qwen 2.5, etc.)
"""

import logging
from collections.abc import AsyncIterator

import httpx

from backend.llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    LLMProvider adapter for Ollama (local LLM).

    Supports:
    - Qwen 2.5 (qwen2.5:latest)
    - Llama 3.2 (llama3.2:3b, llama3.2:7b)
    - Other Ollama models

    Usage:
        provider = OllamaProvider(model="qwen2.5:latest")
        response = await provider.generate([LLMMessage(role="user", content="Hello")])
    """

    def __init__(self, model: str = "qwen2.5:latest", base_url: str = "http://localhost:11434") -> None:
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (default: qwen2.5:latest)
            base_url: Ollama API base URL (default: http://localhost:11434)
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/api/generate"
        self._available = False
        self._async_client: httpx.AsyncClient | None = None  # S12: initialized before _init_client
        self._init_client()

    def _init_client(self) -> None:
        """Mark provider available; actual connectivity checked on first use."""
        self._available = True
        logger.info(f"OllamaProvider initialized: model={self._model} (connectivity verified on first request)")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def is_available(self) -> bool:
        return self._available

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create persistent async HTTP client."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=120.0)
        return self._async_client

    async def aclose(self) -> None:
        """Close the persistent HTTP client."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    async def generate(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096, **kwargs,
    ) -> LLMResponse:
        """Generate response using Ollama."""
        if not self.is_available:
            raise RuntimeError("Ollama provider not available")

        # Convert messages to Ollama prompt format
        # Ollama uses simple prompt string (combine all messages)
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        prompt = "\n\n".join(prompt_parts)

        try:
            client = await self._get_async_client()
            response = await client.post(
                self._api_url,
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("response", "").strip()

                # Estimate tokens (Ollama doesn't provide exact counts)
                prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
                completion_tokens = len(content.split()) * 1.3

                return LLMResponse(
                    content=content,
                    model=self._model,
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens),
                    total_tokens=int(prompt_tokens + completion_tokens),
                )
            else:
                raise RuntimeError(f"Ollama API error: {response.status_code}")

        except httpx.TimeoutException:
            raise RuntimeError("Ollama request timeout")
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise RuntimeError(f"Ollama generation failed: {e}")

    async def generate_stream(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096, **kwargs,
    ) -> AsyncIterator[LLMResponse]:
        """Generate streaming response using Ollama."""
        if not self.is_available:
            raise RuntimeError("Ollama provider not available")

        # Convert messages to prompt
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        prompt = "\n\n".join(prompt_parts)

        try:
            client = await self._get_async_client()
            async with client.stream(
                "POST",
                self._api_url,
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API error: {response.status_code}")

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        import json

                        data = json.loads(line)
                        chunk_content = data.get("response", "")
                        if chunk_content:
                            yield LLMResponse(
                                content=chunk_content,
                                model=self._model,
                                prompt_tokens=0,
                                completion_tokens=0,
                                total_tokens=0,
                            )
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise RuntimeError(f"Ollama streaming failed: {e}")

    async def stream(
        self, messages: list[LLMMessage], temperature: float = 0.7, **kwargs,
    ) -> AsyncIterator[str]:
        """Stream response - yields content chunks (LLMProvider interface)."""
        async for resp in self.generate_stream(messages, temperature=temperature, **kwargs):
            if resp.content:
                yield resp.content
