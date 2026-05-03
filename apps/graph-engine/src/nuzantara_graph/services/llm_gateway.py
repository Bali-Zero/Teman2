"""LLM Gateway — cascade with circuit breaker pattern.

Supports Google Gemini models via the Gemini REST API (httpx).
Primary/fallback cascade with per-model circuit breakers.
All config read from Settings (no hardcoded keys).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from nuzantara_graph.config import Settings

logger = structlog.get_logger()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for LLM providers."""

    failure_count: int = 0
    failure_threshold: int = 3
    last_failure_time: float = 0.0
    cooldown_seconds: float = 60.0

    @property
    def is_open(self) -> bool:
        if self.failure_count < self.failure_threshold:
            return False
        return (time.time() - self.last_failure_time) < self.cooldown_seconds

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()

    def record_success(self) -> None:
        self.failure_count = 0


class LLMGateway:
    """LLM Gateway with cascade fallback and circuit breaker.

    Usage:
        gateway = LLMGateway.from_settings(settings)
        response = await gateway.generate(prompt="...", system="...")
    """

    def __init__(
        self,
        primary_model: str = "gemini-2.0-flash",
        fallback_model: str = "gemini-1.5-flash",
        google_api_key: str = "",
        openai_api_key: str = "",
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.google_api_key = google_api_key
        self.openai_api_key = openai_api_key
        self._breakers: dict[str, CircuitBreaker] = {}
        self._http_client: httpx.AsyncClient | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMGateway:
        return cls(
            primary_model=settings.primary_model,
            fallback_model=settings.fallback_model,
            google_api_key=settings.google_api_key,
            openai_api_key=settings.openai_api_key,
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    def _get_breaker(self, model: str) -> CircuitBreaker:
        if model not in self._breakers:
            self._breakers[model] = CircuitBreaker()
        return self._breakers[model]

    async def generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Generate a response, cascading to fallback on failure."""
        target_model = model or self.primary_model
        models_to_try = [target_model]
        if target_model != self.fallback_model:
            models_to_try.append(self.fallback_model)

        last_error: Exception | None = None
        for m in models_to_try:
            breaker = self._get_breaker(m)
            if breaker.is_open:
                logger.warning("circuit_breaker_open", model=m)
                continue

            try:
                response = await self._call_model(
                    model=m,
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
                breaker.record_success()
                return response
            except Exception as e:
                breaker.record_failure()
                last_error = e
                logger.error("llm_call_failed", model=m, error=str(e))

        raise RuntimeError(
            f"All models failed. Last error: {last_error}"
        )

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Generate and parse a JSON response."""
        response = await self.generate(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            response_format="json",
        )
        return json.loads(response.content)

    async def _call_model(
        self,
        model: str,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
        response_format: str | None,
    ) -> LLMResponse:
        """Call the Gemini REST API."""
        if not self.google_api_key:
            raise ValueError(
                "NUZANTARA_GOOGLE_API_KEY is required for LLM calls"
            )

        start_time = time.time()

        # Build request payload for Gemini API
        contents = []
        if system:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System instruction] {system}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}],
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if response_format == "json":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        # Make the API call
        client = await self._get_http_client()
        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={self.google_api_key}"

        resp = await client.post(url, json=payload)
        resp.raise_for_status()

        data = resp.json()
        latency_ms = (time.time() - start_time) * 1000

        # Extract response text
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"No candidates in Gemini response: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        # Extract token usage
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            content=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> dict[str, Any]:
        """Verify the LLM gateway can reach the Gemini API."""
        try:
            response = await self.generate(
                prompt="Say 'OK' in one word.",
                temperature=0.0,
                max_tokens=10,
            )
            return {
                "status": "healthy",
                "model": response.model,
                "latency_ms": round(response.latency_ms, 1),
                "ok": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "primary_model": self.primary_model,
                "error": str(e),
                "ok": False,
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
