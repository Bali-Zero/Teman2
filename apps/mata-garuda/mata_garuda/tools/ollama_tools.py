"""
Mata Garuda — Ollama CLI helper tools.

Thin subprocess wrapper around `ollama run <model>` and the local
`http://localhost:11434/api/generate` endpoint. No Python SDK — CLI-only
per Legge 1 (SYMBIOSIS).

Used by Layer 2 workers (classifier, NER, embedder, contradiction,
semantic_diff) as a shared entry point, so model names, timeouts, and
JSON-extraction heuristics live in one place.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.ollama")

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
OLLAMA_EMBED_ENDPOINT = "http://localhost:11434/api/embeddings"
OLLAMA_TAGS_ENDPOINT = "http://localhost:11434/api/tags"

DEFAULT_TIMEOUT_S = 60
DEFAULT_EMBED_TIMEOUT_S = 30
DEFAULT_TAGS_TIMEOUT_S = 5


def generate(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.1,
    num_predict: int = 200,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> str | None:
    """Run a single prompt through Ollama via local HTTP API.

    Uses `curl` subprocess (not httpx/requests) to stay aligned with the
    CLI-only + minimal-deps posture of Mata Garuda. Returns the raw text
    response, or None on any failure (timeout, network, parse).
    """
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
    )

    try:
        result = subprocess.run(
            ["curl", "-s", OLLAMA_ENDPOINT, "-d", payload],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"[ollama] generate failed ({model}): {e}")
        return None

    if result.returncode != 0:
        logger.warning(f"[ollama] generate non-zero ({model}): {result.stderr[:200]}")
        return None

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.warning(f"[ollama] generate: invalid JSON envelope ({model}): {e}")
        return None

    return response.get("response")


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from an LLM response.

    LLMs often wrap JSON in fenced code blocks or add prose. This helper
    scans for the first `{...}` span that parses cleanly, handling both
    single-line and multi-line objects.
    """
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Find balanced braces heuristically
    start = text.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(text)):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : end + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)

    return None


def generate_json(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.1,
    num_predict: int = 300,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any] | None:
    """Run `generate()` and extract a JSON object from the response."""
    raw = generate(
        model,
        prompt,
        temperature=temperature,
        num_predict=num_predict,
        timeout=timeout,
    )
    if raw is None:
        return None
    return extract_json(raw)


def embed(
    model: str,
    text: str,
    *,
    timeout: int = DEFAULT_EMBED_TIMEOUT_S,
) -> list[float] | None:
    """Return an embedding vector for `text`, or None if unavailable.

    Uses Ollama's `/api/embeddings` endpoint. Returns None on any failure
    so callers can degrade gracefully (skip field, add `embedding_status`).
    """
    payload = json.dumps({"model": model, "prompt": text})
    try:
        result = subprocess.run(
            ["curl", "-s", OLLAMA_EMBED_ENDPOINT, "-d", payload],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"[ollama] embed failed ({model}): {e}")
        return None

    if result.returncode != 0:
        return None

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    vec = response.get("embedding")
    if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
        return vec
    return None


def list_local_models(timeout: int = DEFAULT_TAGS_TIMEOUT_S) -> list[str]:
    """Return tags of locally pulled Ollama models, or [] if Ollama is down."""
    try:
        result = subprocess.run(
            ["curl", "-s", OLLAMA_TAGS_ENDPOINT],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode != 0:
        return []

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    return [m.get("name", "") for m in response.get("models", []) if m.get("name")]


def has_model(name: str) -> bool:
    """True iff `name` is among the locally pulled Ollama tags."""
    return name in list_local_models()
