"""
🧠 LLM Adapter - Unificato per Test Force

Supporta:
1. Ollama (Qwen 2.5) - Locale, veloce, privato
2. Gemini API - Cloud fallback
3. Mock Mode - Testing senza LLM

Metriche e logging integrati.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM provider types"""
    OLLAMA = "ollama"
    GEMINI = "gemini"
    MOCK = "mock"


@dataclass
class LLMMetrics:
    """Metrics for LLM operations"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_response_time: float = 0.0
    cache_hits: int = 0
    
    @property
    def success_rate(self) -> float:
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0
    
    @property
    def avg_response_time(self) -> float:
        return (self.total_response_time / self.successful_requests) if self.successful_requests > 0 else 0.0


@dataclass
class LLMRequest:
    """LLM request with metadata"""
    prompt: str
    max_tokens: int = 4000
    temperature: float = 0.2
    provider: Optional[LLMProvider] = None
    context: Optional[Dict[str, Any]] = None


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
    Unified LLM adapter for Test Force agents.
    
    Features:
    - Automatic fallback (Ollama → Gemini → Mock)
    - Request/response caching
    - Comprehensive metrics
    - Structured logging
    - Rate limiting
    """
    
    def __init__(
        self,
        primary_provider: LLMProvider = LLMProvider.OLLAMA,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5-coder:7b-instruct-q4_K_M",
        gemini_api_key: Optional[str] = None,
        enable_cache: bool = True,
        cache_size: int = 100,
        rate_limit: int = 10  # requests per minute
    ):
        self.primary_provider = primary_provider
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.gemini_api_key = gemini_api_key
        
        # Caching
        self.enable_cache = enable_cache
        self.cache: Dict[str, LLMResponse] = {}
        self.cache_size = cache_size
        
        # Metrics
        self.metrics = LLMMetrics()
        self.request_times: List[float] = []
        
        # Rate limiting
        self.rate_limit = rate_limit
        self.request_count = 0
        self.last_reset = time.time()
        
        # HTTP client
        self.client = httpx.AsyncClient(timeout=120.0)
        
        logger.info(f"🧠 LLM Adapter initialized with {primary_provider.value} as primary")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using LLM with automatic fallback.
        
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
        
        # Try providers in order
        providers = self._get_provider_order(request.provider or self.primary_provider)
        
        for provider in providers:
            try:
                response = await self._call_provider(provider, request)
                
                # Update metrics
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                self.metrics.total_tokens += response.tokens_used
                self.metrics.total_response_time += response.response_time
                
                # Cache response
                if self.enable_cache:
                    self._cache_response(cache_key, response)
                
                logger.info(
                    f"✅ {provider.value} response: {len(response.text)} chars, "
                    f"{response.response_time:.2f}s, {response.tokens_used} tokens"
                )
                
                return response
                
            except Exception as e:
                logger.warning(f"❌ {provider.value} failed: {e}")
                self.metrics.failed_requests += 1
                continue
        
        # All providers failed - return mock response
        logger.error("🚨 All LLM providers failed, returning mock response")
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        
        return LLMResponse(
            text="# Mock response - all LLM providers failed",
            provider=LLMProvider.MOCK,
            response_time=time.time() - start_time
        )
    
    async def _call_provider(self, provider: LLMProvider, request: LLMRequest) -> LLMResponse:
        """Call specific LLM provider"""
        if provider == LLMProvider.OLLAMA:
            return await self._call_ollama(request)
        elif provider == LLMProvider.GEMINI:
            return await self._call_gemini(request)
        elif provider == LLMProvider.MOCK:
            return await self._call_mock(request)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def _call_ollama(self, request: LLMRequest) -> LLMResponse:
        """Call Ollama API"""
        start_time = time.time()
        
        payload = {
            "model": self.ollama_model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }
        
        response = await self.client.post(
            f"{self.ollama_url}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        text = data.get("response", "")
        
        # Estimate tokens (rough approximation: 1 token ≈ 4 chars for code)
        tokens_used = len(text) // 4
        
        return LLMResponse(
            text=text,
            tokens_used=tokens_used,
            response_time=time.time() - start_time,
            provider=LLMProvider.OLLAMA
        )
    
    async def _call_gemini(self, request: LLMRequest) -> LLMResponse:
        """Call Gemini API (fallback)"""
        if not self.gemini_api_key:
            raise ValueError("Gemini API key not configured")
        
        start_time = time.time()
        
        # Use existing ZantaraAIClient for Gemini
        try:
            from backend.llm.zantara_ai_client import ZantaraAIClient
            
            client = ZantaraAIClient()
            response = await client.chat_async(
                messages=[{"role": "user", "content": request.prompt}],
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            text = response.get("text", "")
            tokens_used = response.get("tokens_used", len(text) // 4)
            
            return LLMResponse(
                text=text,
                tokens_used=tokens_used,
                response_time=time.time() - start_time,
                provider=LLMProvider.GEMINI
            )
            
        except ImportError:
            raise ValueError("ZantaraAIClient not available")
    
    async def _call_mock(self, request: LLMRequest) -> LLMResponse:
        """Mock response for testing"""
        start_time = time.time()
        
        mock_responses = [
            "# Generated test code (mock)",
            "def test_example():\n    assert True",
            "# Mock response for testing purposes"
        ]
        
        text = mock_responses[hash(request.prompt) % len(mock_responses)]
        
        return LLMResponse(
            text=text,
            tokens_used=len(text) // 4,
            response_time=time.time() - start_time,
            provider=LLMProvider.MOCK
        )
    
    def _get_provider_order(self, primary: LLMProvider) -> List[LLMProvider]:
        """Get provider fallback order"""
        if primary == LLMProvider.OLLAMA:
            return [LLMProvider.OLLAMA, LLMProvider.GEMINI, LLMProvider.MOCK]
        elif primary == LLMProvider.GEMINI:
            return [LLMProvider.GEMINI, LLMProvider.OLLAMA, LLMProvider.MOCK]
        else:
            return [LLMProvider.MOCK]
    
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
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": self.metrics.success_rate,
            "total_tokens": self.metrics.total_tokens,
            "avg_response_time": self.metrics.avg_response_time,
            "cache_hits": self.metrics.cache_hits,
            "cache_hit_rate": (self.metrics.cache_hits / self.metrics.total_requests * 100) if self.metrics.total_requests > 0 else 0,
            "cache_size": len(self.cache),
            "rate_limit_used": f"{self.request_count}/{self.rate_limit}/min"
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = LLMMetrics()
        self.request_count = 0
        self.cache.clear()
        logger.info("📊 LLM Adapter metrics reset")
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        health = {}
        
        # Check Ollama
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags")
            health["ollama"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            health["ollama"] = False
        
        # Check Gemini
        try:
            if self.gemini_api_key:
                from backend.llm.zantara_ai_client import ZantaraAIClient
                client = ZantaraAIClient()
                # Simple health check - just try to import
                health["gemini"] = True
            else:
                health["gemini"] = False
        except Exception:
            health["gemini"] = False
        
        health["mock"] = True  # Always available
        
        return health
    
    async def close(self):
        """Cleanup resources"""
        await self.client.aclose()
        logger.info("🧠 LLM Adapter closed")


# Singleton instance for Test Force
_llm_adapter: Optional[LLMAdapter] = None


def get_llm_adapter() -> LLMAdapter:
    """Get singleton LLM adapter instance"""
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = LLMAdapter()
    return _llm_adapter


async def close_llm_adapter():
    """Close singleton LLM adapter"""
    global _llm_adapter
    if _llm_adapter:
        await _llm_adapter.close()
        _llm_adapter = None
