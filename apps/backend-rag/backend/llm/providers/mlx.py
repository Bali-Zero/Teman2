"""
MLX LLM Provider

Local LLM provider for Apple Silicon via the MLX server's OpenAI-compatible
endpoint (`mlx_lm.server`, default http://localhost:8080/v1).

Unlike OllamaProvider (which speaks Ollama's native /api/generate), MLX exposes
the OpenAI Chat Completions contract, so this adapter sends a `messages` array to
`/v1/chat/completions` and reads `choices[].message.content` + `usage`.

Drop-in for the same `LLMProvider` interface (base.py): same `generate`/`stream`
signatures, same `LLMResponse` fields (`content`/`model`/`tokens_used`/
`finish_reason`/`provider`). Registered as "mlx" in provider_registry when MLX is
enabled. POC / hardening role: a third local failure-domain beside ollama_pro /
ollama_mini — see MODEL_TOPOLOGY.json.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from backend.llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class MLXProvider(LLMProvider):
    """
    LLMProvider adapter for an MLX OpenAI-compatible server (Apple Silicon, local).

    Usage:
        provider = MLXProvider(model="mlx-community/Qwen3-8B-4bit")
        response = await provider.generate([LLMMessage(role="user", content="Hi")])
    """

    def __init__(
        self,
        model: str = "mlx-community/Qwen3-8B-4bit",
        base_url: str = "http://localhost:8080",
    ) -> None:
        """
        Initialize MLX provider.

        Args:
            model: MLX model name served by mlx_lm.server (loaded server-side).
            base_url: MLX server base URL (default http://localhost:8080). The
                `/v1` suffix is appended internally — pass the bare host:port.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        # mlx_lm.server is OpenAI-compatible: chat lives under /v1/chat/completions.
        # Tolerate a base_url that already includes /v1 so callers can pass either.
        suffix = "" if self._base_url.endswith("/v1") else "/v1"
        self._chat_url = f"{self._base_url}{suffix}/chat/completions"
        self._available = False
        self._async_client: httpx.AsyncClient | None = None  # init before _init_client
        self._init_client()

    def _init_client(self) -> None:
        """Mark provider available; actual connectivity checked on first use."""
        self._available = True
        logger.info(
            "MLXProvider initialized: model=%s url=%s (connectivity verified on first request)",
            self._model,
            self._chat_url,
        )

    @property
    def name(self) -> str:
        return "mlx"

    @property
    def is_available(self) -> bool:
        return self._available

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create persistent async HTTP client (Golden Rule #10)."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=120.0)
        return self._async_client

    async def aclose(self) -> None:
        """Close the persistent HTTP client."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    @staticmethod
    def _to_openai_messages(messages: list[LLMMessage]) -> list[dict[str, str]]:
        """Map internal LLMMessage list to the OpenAI `messages` array."""
        return [{"role": m.role, "content": m.content} for m in messages]

    @staticmethod
    def _chat_template_kwargs(kwargs: dict) -> dict:
        """
        Build the MLX `chat_template_kwargs` block.

        Default `enable_thinking=False`: Qwen3 served by mlx_lm.server otherwise
        runs its reasoning mode on trivial agentic calls and returns a `reasoning`
        field with NO `content` (finish_reason="length") — i.e. an empty answer.
        Verified live 2026-06-20 against mlx_lm.server 0.31.3 on M5. Callers that
        explicitly want reasoning can pass `enable_thinking=True`.
        """
        enable_thinking = bool(kwargs.pop("enable_thinking", False))
        return {"enable_thinking": enable_thinking}

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response via MLX /v1/chat/completions (non-streaming)."""
        if not self.is_available:
            raise RuntimeError("MLX provider not available")

        # `think` is an Ollama-native option with no OpenAI equivalent — drop it
        # rather than forward an unsupported field to the MLX server.
        kwargs.pop("think", None)

        payload: dict[str, object] = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": self._chat_template_kwargs(kwargs),
        }

        try:
            client = await self._get_async_client()
            response = await client.post(self._chat_url, json=payload)

            if response.status_code != 200:
                raise RuntimeError(f"MLX API error: {response.status_code}")

            data = response.json()
            choices = data.get("choices") or [{}]
            message = choices[0].get("message") or {}
            content = (message.get("content") or "").strip()
            usage = data.get("usage") or {}

            return LLMResponse(
                content=content,
                model=data.get("model", self._model),
                tokens_used=usage.get("total_tokens"),
                finish_reason=choices[0].get("finish_reason"),
                provider=self.name,
            )

        except httpx.TimeoutException as exc:
            raise RuntimeError("MLX request timeout") from exc
        except httpx.ConnectError as exc:
            # MLX server not running locally — explicit, distinct from a 5xx.
            raise RuntimeError(f"MLX connection failed: {self._chat_url}") from exc
        except Exception as exc:
            logger.error("MLX generation error: %s", exc)
            raise RuntimeError(f"MLX generation failed: {exc}") from exc

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a response via MLX /v1/chat/completions (SSE delta chunks)."""
        if not self.is_available:
            raise RuntimeError("MLX provider not available")

        kwargs.pop("think", None)

        payload: dict[str, object] = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "stream": True,
            "chat_template_kwargs": self._chat_template_kwargs(kwargs),
        }

        try:
            client = await self._get_async_client()
            async with client.stream("POST", self._chat_url, json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"MLX API error: {response.status_code}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    # OpenAI SSE framing: "data: {json}" lines, ending with "[DONE]".
                    if line.startswith("data:"):
                        line = line[len("data:") :].strip()
                    if not line or line == "[DONE]":
                        if line == "[DONE]":
                            break
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or [{}]
                    delta = choices[0].get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield chunk

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise RuntimeError(f"MLX streaming connection error: {exc}") from exc
        except Exception as exc:
            logger.error("MLX streaming error: %s", exc)
            raise RuntimeError(f"MLX streaming failed: {exc}") from exc
