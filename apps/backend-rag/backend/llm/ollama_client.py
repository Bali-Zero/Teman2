"""
Ollama Local LLM Client

Async client for local Ollama models.
  - MODEL_FAST  = qwen3.5:9b      (<0.5s, classification/titles)
  - MODEL_HEAVY = deepseek-r1:32b (~12-15s, complex reasoning/KG extraction)
  - MODEL_JSON  = gemma3:12b      (reliable JSON output)

Used for cost-free tasks. Graceful fallback: if Ollama is unavailable, caller handles API fallback.
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Default models by task complexity
MODEL_FAST = "qwen3.5:9b"  # <0.5s, classification/titles/short tasks
MODEL_HEAVY = "deepseek-r1:32b"  # ~12-15s, complex reasoning/KG extraction (replaces qwen3.5:27b)
MODEL_JSON = "gemma3:12b"  # Reliable JSON output, scoring

OLLAMA_BASE_URL = settings.ollama_url  # default: http://localhost:11434


async def ollama_generate(
    prompt: str,
    model: str = MODEL_FAST,
    temperature: float = 0.3,
    max_tokens: int = 256,
    timeout: float = 30.0,
    system: str | None = None,
) -> str | None:
    """
    Generate text from local Ollama model.

    Returns None if Ollama is unavailable (caller handles fallback).

    Args:
        prompt: User prompt
        model: Ollama model name
        temperature: Sampling temperature (low = deterministic)
        max_tokens: Max output tokens
        timeout: Request timeout in seconds
        system: Optional system prompt

    Returns:
        Generated text, or None if unavailable
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,  # Disable thinking for Qwen3.5 (returns content directly)
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

    except httpx.ConnectError:
        logger.debug(f"Ollama not running at {OLLAMA_BASE_URL}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Ollama timeout ({timeout}s) for model {model}")
        return None
    except Exception as e:
        logger.warning(f"Ollama error ({model}): {e}")
        return None


async def ollama_chat(
    messages: list[dict[str, str]],
    model: str = MODEL_FAST,
    temperature: float = 0.3,
    max_tokens: int = 256,
    timeout: float = 30.0,
) -> str | None:
    """
    Chat completion from local Ollama model (OpenAI-compatible format).

    Returns None if Ollama is unavailable.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,  # Disable thinking for Qwen3.5 (returns content directly)
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip()

    except httpx.ConnectError:
        logger.debug(f"Ollama not running at {OLLAMA_BASE_URL}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Ollama chat timeout ({timeout}s) for model {model}")
        return None
    except Exception as e:
        logger.warning(f"Ollama chat error ({model}): {e}")
        return None


async def is_ollama_available(model: str | None = None) -> bool:
    """Check if Ollama is running and optionally if a specific model is loaded."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code != 200:
                return False
            if model:
                models = [m["name"] for m in response.json().get("models", [])]
                return any(model in m for m in models)
            return True
    except Exception:
        return False
