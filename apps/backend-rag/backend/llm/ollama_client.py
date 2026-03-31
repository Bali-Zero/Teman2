"""
Ollama Local LLM Client

Async client for local Ollama models.
  - MODEL_FAST  = qwen3.5:9b       (<0.5s, classification/titles)
  - MODEL_HEAVY = deepseek-r1:32b  (~30s, reasoning tasks — war-room, CELL)
  - MODEL_KG    = qwen3.5:27b      (~5-8s, KG extraction — uses 2-step think fix)
  - MODEL_JSON  = gemma3:12b       (reliable JSON output, scoring)

NOTE: DeepSeek-R1:32b NOT suitable for KG batch (106s/chunk = 0.6 chunks/min).
      qwen3.5:27b with 2-step stop-at-</think> fix = ~8 chunks/min.
Used for cost-free tasks. Graceful fallback: if Ollama is unavailable, caller handles API fallback.
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Default models by task complexity
MODEL_FAST = "qwen3.5:9b"   # <0.5s, classification/titles/short tasks
MODEL_HEAVY = "deepseek-r1:32b"  # ~30s, reasoning tasks (war-room preprocessor, CELL reasoner)
MODEL_KG = "qwen3.5:27b"    # ~5-8s, KG extraction (2-step fix required, see kg_incremental_extraction.py)
MODEL_JSON = "gemma3:12b"   # Reliable JSON output, scoring

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


async def ollama_chat_kg(
    prompt: str,
    json_schema: dict[str, Any],
    model: str = MODEL_KG,
    timeout: float = 30.0,
) -> str | None:
    """
    KG extraction via qwen3.5:27b using native Ollama API with think:false.

    NOTE: think:false works ONLY on native Ollama /api/chat endpoint (not OpenAI-compat).
    This function uses the native endpoint directly, bypassing the vLLM issue #37414.

    Returns raw JSON string, or None if unavailable/failed.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "think": False,
                    "format": json_schema,
                    "options": {"temperature": 0},
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip() or None

    except httpx.ConnectError:
        logger.debug(f"Ollama not running at {OLLAMA_BASE_URL}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Ollama KG timeout ({timeout}s) for model {model}")
        return None
    except Exception as e:
        logger.warning(f"Ollama KG error ({model}): {e}")
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
