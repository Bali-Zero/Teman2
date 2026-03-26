"""
🧠 LLM Adapter - Qwen-First per Test Force (Enhanced 2026)

SOLO OLLAMA (Qwen) o MOCK - Niente fallback a Gemini!
- Ollama (Qwen 2.5) - Locale, veloce, privato - PRIMARY
- Mock Mode - Solo se Ollama completamente non disponibile

ENHANCED FEATURES (Best Practice 2026):
- Circuit Breaker Pattern: Evita chiamate quando Ollama è down
- Error Classification: Retry intelligente (transient vs permanent)
- Retry con Jitter: Evita thundering herd problem
- Auto-start Ollama: Tenta di avviare Ollama se non disponibile

Metriche e logging integrati.
"""

from __future__ import annotations

import asyncio
import logging
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM provider types - SOLO OLLAMA o MOCK"""

    OLLAMA = "ollama"
    MOCK = "mock"


class ErrorType(Enum):
    """Error classification for intelligent retry"""

    TRANSIENT = "transient"  # Retryable: timeout, connection error, service unavailable
    PERMANENT = "permanent"  # Not retryable: invalid prompt, auth error, model not found
    RATE_LIMIT = "rate_limit"  # Special: retry with longer backoff


class CircuitState(Enum):
    """Circuit Breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerState:
    """Circuit Breaker state tracking"""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    opened_at: float = 0.0

    def reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.opened_at = 0.0


@dataclass
class LLMMetrics:
    """Metrics for LLM operations"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_response_time: float = 0.0
    cache_hits: int = 0
    circuit_breaker_trips: int = 0  # Times circuit breaker opened
    permanent_errors: int = 0  # Errors that don't benefit from retry

    @property
    def success_rate(self) -> float:
        return (
            (self.successful_requests / self.total_requests * 100)
            if self.total_requests > 0
            else 0.0
        )

    @property
    def avg_response_time(self) -> float:
        return (
            (self.total_response_time / self.successful_requests)
            if self.successful_requests > 0
            else 0.0
        )


@dataclass
class LLMRequest:
    """LLM request with metadata"""

    prompt: str
    max_tokens: int = 4000
    temperature: float = 0.2
    provider: LLMProvider | None = None
    context: dict[str, Any] | None = None
    system: str | None = None  # System prompt (defines model behavior)


@dataclass
class LLMResponse:
    """LLM response with metadata"""

    text: str
    tokens_used: int = 0
    response_time: float = 0.0
    provider: LLMProvider = LLMProvider.MOCK
    cached: bool = False


class LLMAdapter:
    """
    Qwen-First LLM adapter for Test Force agents.

    AGGRESSIVE QWEN MODE:
    - Prova Ollama/Qwen fino a 10 volte con backoff esponenziale
    - Auto-start Ollama se non disponibile
    - Solo Mock come ultimo fallback (NON Gemini!)

    Features:
    - Aggressive retry for Qwen (up to 10 attempts)
    - Auto-start Ollama if not running
    - Request/response caching
    - Comprehensive metrics
    - Structured logging
    - Rate limiting
    """

    def __init__(
        self,
        primary_provider: LLMProvider = LLMProvider.OLLAMA,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:latest",  # Default Qwen model - can be overridden via env
        enable_cache: bool = True,
        cache_size: int = 100,
        rate_limit: int = 10,  # requests per minute
        max_retries: int = 10,  # Aggressive retry for Qwen
        retry_backoff_base: float = 1.5,  # Exponential backoff
        retry_jitter: float = 0.5,  # Jitter range (seconds) to avoid thundering herd
        auto_start_ollama: bool = True,  # Try to start Ollama if down
        # Circuit Breaker settings
        circuit_breaker_failure_threshold: int = 10,  # Failures before opening circuit (increased for slow but working Ollama)
        circuit_breaker_timeout: float = 30.0,  # Seconds before trying half-open (reduced for faster recovery)
        circuit_breaker_success_threshold: int = 2,  # Successes to close circuit
    ):
        self.primary_provider = primary_provider
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.retry_jitter = retry_jitter
        self.auto_start_ollama = auto_start_ollama

        # Circuit Breaker
        self.circuit_breaker = CircuitBreakerState()
        self.circuit_breaker_failure_threshold = circuit_breaker_failure_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.circuit_breaker_success_threshold = circuit_breaker_success_threshold

        # Caching
        self.enable_cache = enable_cache
        self.cache: dict[str, LLMResponse] = {}
        self.cache_size = cache_size

        # Metrics
        self.metrics = LLMMetrics()
        self.request_times: list[float] = []
        self.retry_count = 0  # Track retries

        # Rate limiting
        self.rate_limit = rate_limit
        self.request_count = 0
        self.last_reset = time.time()

        # HTTP client with longer timeout for large test generations (10 minutes)
        self.client = httpx.AsyncClient(timeout=600.0)

        logger.info("🔥 LLM Adapter initialized - QWEN-FIRST MODE (Enhanced)")
        logger.info(f"   Primary: {primary_provider.value}")
        logger.info(f"   Model: {ollama_model}")
        logger.info(f"   Max Retries: {max_retries}")
        logger.info(f"   Retry Jitter: {retry_jitter}s")
        logger.info(f"   Circuit Breaker: {circuit_breaker_failure_threshold} failures → OPEN")
        logger.info(f"   Auto-start Ollama: {auto_start_ollama}")

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type for intelligent retry decision"""
        error_str = str(error).lower()
        # error_type was unused

        # Permanent errors - don't retry
        if "model not found" in error_str or "invalid model" in error_str:
            return ErrorType.PERMANENT
        if "authentication" in error_str or "unauthorized" in error_str:
            return ErrorType.PERMANENT
        if "invalid prompt" in error_str or "malformed" in error_str:
            return ErrorType.PERMANENT

        # Rate limit errors - special handling
        if "rate limit" in error_str or "429" in error_str:
            return ErrorType.RATE_LIMIT

        # Transient errors - retryable
        if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
            return ErrorType.TRANSIENT
        if "timeout" in error_str or "connection" in error_str:
            return ErrorType.TRANSIENT
        if "service unavailable" in error_str or "503" in error_str:
            return ErrorType.TRANSIENT
        if "502" in error_str or "504" in error_str:  # Bad Gateway, Gateway Timeout
            return ErrorType.TRANSIENT

        # Default to transient (safer to retry)
        return ErrorType.TRANSIENT

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows request"""
        current_time = time.time()

        # Check if we should transition from OPEN to HALF_OPEN
        if self.circuit_breaker.state == CircuitState.OPEN:
            if current_time - self.circuit_breaker.opened_at >= self.circuit_breaker_timeout:
                logger.info("🔄 Circuit breaker: OPEN → HALF_OPEN (testing recovery)")
                self.circuit_breaker.state = CircuitState.HALF_OPEN
                self.circuit_breaker.success_count = 0
                self.circuit_breaker.failure_count = 0  # Reset failure count on recovery attempt
                return True
            else:
                # Allow one request every 30s even when OPEN (probe for recovery)
                time_since_open = current_time - self.circuit_breaker.opened_at
                if time_since_open >= 30.0 and (time_since_open % 30.0) < 5.0:
                    logger.info("🔍 Circuit breaker: Probing for recovery...")
                    self.circuit_breaker.state = CircuitState.HALF_OPEN
                    self.circuit_breaker.success_count = 0
                    return True
                logger.debug(
                    f"🚫 Circuit breaker OPEN - rejecting request "
                    f"({self.circuit_breaker_timeout - (current_time - self.circuit_breaker.opened_at):.1f}s remaining)"
                )
                return False

        # CLOSED or HALF_OPEN - allow request
        return True

    def _record_circuit_breaker_success(self):
        """Record successful request for circuit breaker"""
        if self.circuit_breaker.state == CircuitState.HALF_OPEN:
            self.circuit_breaker.success_count += 1
            if self.circuit_breaker.success_count >= self.circuit_breaker_success_threshold:
                logger.info("✅ Circuit breaker: HALF_OPEN → CLOSED (service recovered)")
                self.circuit_breaker.reset()
        elif self.circuit_breaker.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.circuit_breaker.failure_count > 0:
                self.circuit_breaker.failure_count = max(0, self.circuit_breaker.failure_count - 1)

    def _record_circuit_breaker_failure(self, error_type: ErrorType):
        """Record failed request for circuit breaker"""
        # Only count transient errors for circuit breaker
        if error_type == ErrorType.TRANSIENT:
            self.circuit_breaker.failure_count += 1
            self.circuit_breaker.last_failure_time = time.time()

            if self.circuit_breaker.state == CircuitState.HALF_OPEN:
                # Failed during half-open - go back to OPEN
                logger.warning("❌ Circuit breaker: HALF_OPEN → OPEN (recovery failed)")
                self.circuit_breaker.state = CircuitState.OPEN
                self.circuit_breaker.opened_at = time.time()
            elif (
                self.circuit_breaker.state == CircuitState.CLOSED
                and self.circuit_breaker.failure_count >= self.circuit_breaker_failure_threshold
            ):
                # Too many failures - open circuit
                logger.warning(
                    f"🚨 Circuit breaker: CLOSED → OPEN "
                    f"({self.circuit_breaker.failure_count} failures)"
                )
                self.circuit_breaker.state = CircuitState.OPEN
                self.circuit_breaker.opened_at = time.time()
                self.metrics.circuit_breaker_trips += 1

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Qwen with ENHANCED retry and circuit breaker.

        STRATEGY:
        1. Check cache first
        2. Check circuit breaker
        3. Try Qwen with intelligent retry (based on error type)
        4. If Ollama not available, try to start it
        5. Only use Mock if ALL retries fail or circuit breaker is OPEN

        Args:
            request: LLM request with prompt and parameters

        Returns:
            LLMResponse with generated text and metadata
        """
        start_time = time.time()

        # Rate limiting
        await self._check_rate_limit()

        # Check cache
        cache_key = self._get_cache_key(request)
        if self.enable_cache and cache_key in self.cache:
            self.metrics.cache_hits += 1
            cached_response = self.cache[cache_key]
            logger.debug(f"🎯 Cache hit for request: {request.prompt[:50]}...")
            return cached_response

        # Determine provider (force OLLAMA unless explicitly MOCK)
        provider = request.provider or self.primary_provider
        if provider == LLMProvider.MOCK:
            return await self._call_mock(request)

        # Check circuit breaker
        if not self._check_circuit_breaker():
            # Circuit breaker is OPEN - return mock immediately
            logger.warning("🚫 Circuit breaker OPEN - returning mock response")
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            return LLMResponse(
                text="# Mock response - Circuit breaker OPEN (Ollama unavailable)",
                provider=LLMProvider.MOCK,
                response_time=time.time() - start_time,
            )

        # ENHANCED QWEN MODE: Intelligent retry based on error type
        last_error = None
        last_error_type = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # Check Ollama health before retry (after first failure)
                if attempt > 1:
                    await self._ensure_ollama_available()

                response = await self._call_ollama(request)

                # Success! Update metrics and circuit breaker
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                self.metrics.total_tokens += response.tokens_used
                self.metrics.total_response_time += response.response_time
                self.retry_count = attempt - 1
                self._record_circuit_breaker_success()

                # Cache response
                if self.enable_cache:
                    self._cache_response(cache_key, response)

                if attempt > 1:
                    logger.info(
                        f"✅ Qwen succeeded after {attempt} attempts: {len(response.text)} chars, "
                        f"{response.response_time:.2f}s, {response.tokens_used} tokens"
                    )
                else:
                    logger.info(
                        f"✅ Qwen response: {len(response.text)} chars, "
                        f"{response.response_time:.2f}s, {response.tokens_used} tokens"
                    )

                return response

            except Exception as e:
                last_error = e
                last_error_type = self._classify_error(e)
                self.metrics.failed_requests += 1

                # Record circuit breaker failure
                self._record_circuit_breaker_failure(last_error_type)

                # Permanent errors - don't retry
                if last_error_type == ErrorType.PERMANENT:
                    self.metrics.permanent_errors += 1
                    logger.error(f"❌ Permanent error (no retry): {e}. Returning mock response.")
                    break  # Exit retry loop immediately

                # Check circuit breaker again (might have opened during retries)
                if not self._check_circuit_breaker():
                    logger.warning("🚫 Circuit breaker opened during retries")
                    break

                if attempt < self.max_retries:
                    # Calculate backoff with jitter
                    base_wait = self.retry_backoff_base ** (attempt - 1)
                    jitter = random.uniform(0, self.retry_jitter)
                    wait_time = base_wait + jitter

                    # Longer backoff for rate limits
                    if last_error_type == ErrorType.RATE_LIMIT:
                        wait_time *= 2

                    logger.warning(
                        f"🔄 Qwen attempt {attempt}/{self.max_retries} failed ({last_error_type.value}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Qwen failed after {self.max_retries} attempts: {e}")

        # All retries failed - return mock response
        logger.error(
            f"🚨 Qwen failed after {self.max_retries} attempts. "
            f"Last error ({last_error_type.value if last_error_type else 'unknown'}): {last_error}. "
            f"Returning mock response."
        )
        self.metrics.total_requests += 1

        return LLMResponse(
            text="# Mock response - Qwen unavailable after all retries",
            provider=LLMProvider.MOCK,
            response_time=time.time() - start_time,
        )

    async def _ensure_ollama_available(self):
        """Ensure Ollama is running - try to start it if needed"""
        if not self.auto_start_ollama:
            return

        try:
            # Quick health check
            response = await self.client.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            if response.status_code == 200:
                # Check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(
                    self.ollama_model in name or name in self.ollama_model for name in model_names
                ):
                    logger.debug("✅ Ollama is running and model available")
                    return
                else:
                    logger.warning(f"⚠️ Ollama running but model {self.ollama_model} not found")
        except Exception:
            pass  # Ollama not responding

        # Try to start Ollama
        logger.info("🚀 Attempting to start Ollama...")
        try:
            # Check if ollama command exists
            ollama_cmd = shutil.which("ollama")
            if not ollama_cmd:
                logger.warning("⚠️ Ollama command not found in PATH")
                return

            # Try to start Ollama (non-blocking)
            # Note: This is a best-effort attempt
            try:
                subprocess.Popen(
                    [ollama_cmd, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                logger.info("🚀 Ollama start command issued, waiting 5s...")
                await asyncio.sleep(5)  # Give it time to start

                # Verify it started
                response = await self.client.get(f"{self.ollama_url}/api/tags", timeout=2.0)
                if response.status_code == 200:
                    logger.info("✅ Ollama started successfully!")
                else:
                    logger.warning("⚠️ Ollama start command issued but not responding yet")
            except Exception as e:
                logger.warning(f"⚠️ Could not start Ollama: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Error checking/starting Ollama: {e}")

    async def _call_ollama(self, request: LLMRequest) -> LLMResponse:
        """Call Ollama API (Qwen) - Direct call, no retry logic here (handled in generate)"""
        start_time = time.time()

        payload = {
            "model": self.ollama_model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        # Add system prompt if provided (Qwen/Ollama supports system prompts)
        if request.system:
            payload["system"] = request.system

        try:
            response = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=600.0,  # Very long timeout for large test generations (10 min)
            )
            response.raise_for_status()

            data = response.json()
            text = data.get("response", "")

            if not text:
                raise ValueError("Empty response from Ollama")

            # Estimate tokens (rough approximation: 1 token ≈ 4 chars for code)
            tokens_used = len(text) // 4

            return LLMResponse(
                text=text,
                tokens_used=tokens_used,
                response_time=time.time() - start_time,
                provider=LLMProvider.OLLAMA,
            )
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Ollama timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama HTTP error {e.response.status_code}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}") from e

    async def _call_mock(self, request: LLMRequest) -> LLMResponse:
        """Mock response for testing"""
        start_time = time.time()

        mock_responses = [
            "# Generated test code (mock)",
            "def test_example():\n    assert True",
            "# Mock response for testing purposes",
        ]

        text = mock_responses[hash(request.prompt) % len(mock_responses)]

        return LLMResponse(
            text=text,
            tokens_used=len(text) // 4,
            response_time=time.time() - start_time,
            provider=LLMProvider.MOCK,
        )

    def _get_cache_key(self, request: LLMRequest) -> str:
        """Generate cache key for request"""
        import hashlib

        content = f"{request.prompt}:{request.max_tokens}:{request.temperature}"
        return hashlib.md5(content.encode()).hexdigest()

    def _cache_response(self, key: str, response: LLMResponse):
        """Cache response with LRU eviction"""
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry (simple LRU)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[key] = response

    async def _check_rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()

        # Reset counter every minute
        if current_time - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = current_time

        if self.request_count >= self.rate_limit:
            wait_time = 60 - (current_time - self.last_reset)
            if wait_time > 0:
                logger.warning(f"⏳ Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.request_count = 0

        self.request_count += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics"""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": self.metrics.success_rate,
            "total_tokens": self.metrics.total_tokens,
            "avg_response_time": self.metrics.avg_response_time,
            "cache_hits": self.metrics.cache_hits,
            "cache_hit_rate": (self.metrics.cache_hits / self.metrics.total_requests * 100)
            if self.metrics.total_requests > 0
            else 0,
            "cache_size": len(self.cache),
            "rate_limit_used": f"{self.request_count}/{self.rate_limit}/min",
            # Circuit Breaker metrics
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "circuit_breaker_trips": self.metrics.circuit_breaker_trips,
            "permanent_errors": self.metrics.permanent_errors,
        }

    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = LLMMetrics()
        self.request_count = 0
        self.cache.clear()
        logger.info("📊 LLM Adapter metrics reset")

    async def health_check(self) -> dict[str, bool]:
        """Check health of providers (Ollama and Mock only)"""
        health = {}

        # Check Ollama
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                # Also check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                health["ollama"] = any(
                    self.ollama_model in name or name in self.ollama_model for name in model_names
                )
                if not health["ollama"]:
                    logger.warning(f"⚠️ Ollama running but model {self.ollama_model} not found")
            else:
                health["ollama"] = False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            health["ollama"] = False

        health["mock"] = True  # Always available

        return health

    async def close(self):
        """Cleanup resources"""
        await self.client.aclose()
        logger.info("🧠 LLM Adapter closed")


# Singleton instance for Test Force
_llm_adapter: LLMAdapter | None = None


def get_llm_adapter() -> LLMAdapter:
    """Get singleton LLM adapter instance"""
    import os

    global _llm_adapter
    if _llm_adapter is None:
        # Read from environment if available
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        _llm_adapter = LLMAdapter(
            ollama_model=ollama_model,
            ollama_url=ollama_url,
        )
        logger.info(f"🔥 LLM Adapter singleton created with model: {ollama_model}")
    return _llm_adapter


async def close_llm_adapter():
    """Close singleton LLM adapter"""
    global _llm_adapter
    if _llm_adapter:
        await _llm_adapter.close()
        _llm_adapter = None
