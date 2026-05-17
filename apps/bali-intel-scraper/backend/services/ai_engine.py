"""
AI processing engine with batching and caching.

Provides:
- Batch processing for efficiency
- Model response caching
- Multiple provider support (OpenAI, Anthropic)
- Rate limiting
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.core.logger import get_logger, LogAction
from backend.core.cache import cache, CacheStrategy
from backend.core.rate_limiter import limit_ai_request
from config.settings import settings

logger = get_logger(__name__, component="ai_engine")


class AIProvider(Enum):
    """Supported AI providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class AIRequest:
    """AI processing request."""

    content: str
    task_type: str
    provider: AIProvider = AIProvider.OPENAI
    model: str | None = None
    max_tokens: int = 4000
    temperature: float = 0.1
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AIResponse:
    """AI processing response."""

    content: str
    usage: dict[str, int]
    model: str
    finish_reason: str
    latency_ms: float
    cached: bool = False


class AIBatchProcessor:
    """Batch processor for AI requests."""

    def __init__(
        self,
        max_batch_size: int = 10,
        max_wait_time: float = 5.0,
        provider: AIProvider = AIProvider.OPENAI,
    ):
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.provider = provider

        self._batch: list[AIRequest] = []
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    async def add_request(self, request: AIRequest) -> AIResponse:
        """Add request to batch and wait for result."""
        future = asyncio.get_event_loop().create_future()
        request_id = id(request)

        async with self._lock:
            self._batch.append(request)
            self._pending[request_id] = future

            # Start flush timer if not running
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._delayed_flush())

            # Flush immediately if batch is full
            if len(self._batch) >= self.max_batch_size:
                if self._flush_task and not self._flush_task.done():
                    self._flush_task.cancel()
                asyncio.create_task(self._flush_batch())

        # Wait for result
        return await future

    async def _delayed_flush(self) -> None:
        """Flush batch after delay."""
        try:
            await asyncio.sleep(self.max_wait_time)
            await self._flush_batch()
        except asyncio.CancelledError:
            pass

    async def _flush_batch(self) -> None:
        """Process current batch."""
        async with self._lock:
            if not self._batch:
                return

            batch = self._batch.copy()
            pending = self._pending.copy()

            self._batch.clear()
            self._pending.clear()

        try:
            results = await self._process_batch(batch)

            # Fulfill futures
            for request, result in zip(batch, results):
                request_id = id(request)
                future = pending.get(request_id)
                if future and not future.done():
                    future.set_result(result)

        except Exception as e:
            # Fail all pending requests
            for _, future in pending.items():
                if not future.done():
                    future.set_exception(e)

    async def _process_batch(self, requests: list[AIRequest]) -> list[AIResponse]:
        """Process batch of requests."""
        # For now, process sequentially
        # In production, this could use batch APIs
        results = []

        for request in requests:
            if self.provider == AIProvider.OPENAI:
                result = await self._call_openai(request)
            else:
                result = await self._call_anthropic(request)

            results.append(result)

        return results

    async def _call_openai(self, request: AIRequest) -> AIResponse:
        """Call OpenAI API."""
        import openai

        await limit_ai_request("openai")

        client = openai.AsyncOpenAI(api_key=settings.ai.openai_api_key)

        start_time = asyncio.get_event_loop().time()

        response = await client.chat.completions.create(
            model=request.model or settings.ai.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(request.task_type),
                },
                {"role": "user", "content": request.content},
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        latency = (asyncio.get_event_loop().time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            model=response.model,
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency,
        )

    async def _call_anthropic(self, request: AIRequest) -> AIResponse:
        """Call Anthropic API."""
        import anthropic

        await limit_ai_request("anthropic")

        client = anthropic.AsyncAnthropic(api_key=settings.ai.anthropic_api_key)

        start_time = asyncio.get_event_loop().time()

        response = await client.messages.create(
            model=request.model or settings.ai.anthropic_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=self._get_system_prompt(request.task_type),
            messages=[{"role": "user", "content": request.content}],
        )

        latency = (asyncio.get_event_loop().time() - start_time) * 1000

        return AIResponse(
            content=response.content[0].text,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
            model=response.model,
            finish_reason=response.stop_reason,
            latency_ms=latency,
        )

    def _get_system_prompt(self, task_type: str) -> str:
        """Get system prompt for task type."""
        prompts = {
            "analyze": "You are a news analysis assistant. Analyze the provided content and extract key information.",
            "summarize": "You are a summarization assistant. Provide a concise summary of the content.",
            "classify": "You are a classification assistant. Classify the content into relevant categories.",
            "sentiment": "You are a sentiment analysis assistant. Analyze the sentiment of the content.",
            "extract_entities": "You are an entity extraction assistant. Extract named entities from the content.",
            "translate": "You are a translation assistant. Translate the content accurately.",
        }
        return prompts.get(task_type, "You are a helpful assistant.")


class AIEngine:
    """Main AI processing engine."""

    def __init__(self):
        self._batch_processors: dict[AIProvider, AIBatchProcessor] = {}

    def _get_processor(self, provider: AIProvider) -> AIBatchProcessor:
        """Get or create batch processor for provider."""
        if provider not in self._batch_processors:
            self._batch_processors[provider] = AIBatchProcessor(provider=provider)
        return self._batch_processors[provider]

    async def process(
        self,
        content: str,
        task_type: str = "analyze",
        provider: AIProvider = AIProvider.OPENAI,
        use_cache: bool = True,
        **options,
    ) -> AIResponse:
        """
        Process content with AI.

        Args:
            content: Content to process
            task_type: Type of processing task
            provider: AI provider to use
            use_cache: Whether to use response caching
            **options: Additional options

        Returns:
            AI processing response
        """
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(content, task_type, provider)
            cached = await cache.get(cache_key)

            if cached:
                logger.debug(
                    f"AI cache hit for {task_type}", metadata={"task_type": task_type}
                )
                return AIResponse(**{**cached, "cached": True})

        # Create request
        request = AIRequest(
            content=content, task_type=task_type, provider=provider, **options
        )

        # Process
        processor = self._get_processor(provider)
        response = await processor.add_request(request)

        # Cache result
        if use_cache:
            await cache.set(
                cache_key,
                {
                    "content": response.content,
                    "usage": response.usage,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "latency_ms": response.latency_ms,
                    "cached": False,
                },
                strategy=CacheStrategy.TTL_MEDIUM,
            )

        logger.info(
            "AI processing complete",
            action=LogAction.ANALYZE,
            metadata={
                "task_type": task_type,
                "provider": provider.value,
                "tokens": response.usage.get("total_tokens"),
                "cached": False,
            },
        )

        return response

    async def process_batch(
        self,
        items: list[dict[str, Any]],
        task_type: str = "analyze",
        provider: AIProvider = AIProvider.OPENAI,
    ) -> list[AIResponse]:
        """Process multiple items in batch."""
        tasks = [
            self.process(
                item.get("content", ""), task_type, provider, **item.get("options", {})
            )
            for item in items
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    def _get_cache_key(self, content: str, task_type: str, provider: AIProvider) -> str:
        """Generate cache key for request."""
        import hashlib

        content_hash = hashlib.sha256(content[:1000].encode()).hexdigest()[:16]
        return f"ai:{provider.value}:{task_type}:{content_hash}"

    async def health_check(self) -> dict[str, Any]:
        """Check AI engine health."""
        return {
            "status": "healthy",
            "providers": list(self._batch_processors.keys()),
            "batch_sizes": {
                provider.value: len(processor._batch)
                for provider, processor in self._batch_processors.items()
            },
        }


# Global engine instance
ai_engine = AIEngine()


async def process_content(content: str, task_type: str = "analyze", **options) -> str:
    """Quick function to process content."""
    response = await ai_engine.process(content, task_type, **options)
    return response.content


__all__ = [
    "AIEngine",
    "AIRequest",
    "AIResponse",
    "AIProvider",
    "AIBatchProcessor",
    "ai_engine",
    "process_content",
]
