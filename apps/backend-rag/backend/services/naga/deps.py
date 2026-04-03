"""Naga dependency wiring — builds real callables for the orchestrator.

Two modes:
  - **local**: For CLI/testing — calls external APIs directly (Fly.io backend, Brave, Gemini CLI)
  - **server**: For FastAPI on Fly.io — calls own endpoints via localhost, uses Gemini CLI via subprocess

Usage::

    from backend.services.naga.deps import build_deps
    deps = build_deps(mode="server")
    orch = NagaOrchestrator(deps=deps)
"""

from __future__ import annotations

import asyncio
import logging
import os
from types import SimpleNamespace
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_BACKEND_URL_LOCAL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
_BACKEND_URL_SERVER = "http://localhost:8080"  # Self-call on Fly.io
_API_KEY = os.getenv("SCRAPER_API_KEY", "internal-scraper-key")
_GEMINI_MODEL = os.getenv("NAGA_GEMINI_MODEL", "gemini-3.1-pro-preview")

# Persistent httpx client (Rule 10: never create in loops)
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=90.0)
    return _client


# ---------------------------------------------------------------------------
# ask_legal — calls agentic RAG endpoint
# ---------------------------------------------------------------------------


async def _ask_legal(base_url: str, **kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    logger.info("[naga.deps] ask_legal: %s", query[:80])
    client = await _get_client()
    try:
        resp = await client.post(
            f"{base_url}/api/agentic-rag/query",
            json={"query": query, "language": "en"},
            headers={"X-API-Key": _API_KEY},
            timeout=90.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "answer": data.get("answer", data.get("response", "")),
                "sources": data.get("sources", []),
                "confidence": data.get("confidence", 0.7),
            }
        logger.warning("[naga.deps] ask_legal HTTP %d", resp.status_code)
    except Exception as e:
        logger.warning("[naga.deps] ask_legal failed: %s", e)
    return {"answer": "", "sources": [], "confidence": 0.0}


# ---------------------------------------------------------------------------
# search_intel — calls intel search endpoint
# ---------------------------------------------------------------------------


async def _search_intel(base_url: str, **kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    logger.info("[naga.deps] search_intel: %s", query[:80])
    client = await _get_client()
    try:
        resp = await client.get(
            f"{base_url}/api/intel/search",
            params={"q": query, "limit": 5},
            headers={"X-API-Key": _API_KEY},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("[naga.deps] search_intel failed: %s", e)
    return {"results": []}


# ---------------------------------------------------------------------------
# exa_search — web search (Brave free tier as proxy)
# ---------------------------------------------------------------------------


async def _exa_search(**kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    num_results = kwargs.get("numResults", 5)
    include_domains = kwargs.get("includeDomains", [])
    logger.info("[naga.deps] web_search: %s", query[:60])

    client = await _get_client()
    search_query = query
    if include_domains:
        domain_filter = " OR ".join(f"site:{d}" for d in include_domains[:3])
        search_query = f"{query} ({domain_filter})"

    brave_key = os.getenv("BRAVE_API_KEY", "")
    if not brave_key:
        logger.warning("[naga.deps] BRAVE_API_KEY not set — web search skipped")
        return {"results": []}

    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": search_query, "count": min(num_results, 10)},
            headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:num_results]:
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "text": item.get("description", ""),
                    "score": 0.7,
                })
            return {"results": results}
    except Exception as e:
        logger.warning("[naga.deps] web_search failed: %s", e)
    return {"results": []}


# ---------------------------------------------------------------------------
# brave_search — diversifier (returns empty to avoid duplicates)
# ---------------------------------------------------------------------------


async def _brave_search(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"web": {"results": []}}


# ---------------------------------------------------------------------------
# fetch — URL content fetching
# ---------------------------------------------------------------------------


async def _fetch(**kwargs: Any) -> dict:
    url = kwargs.get("url", "")
    max_length = kwargs.get("max_length", 50000)
    client = await _get_client()
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        return {"content": resp.text[:max_length]}
    except Exception as e:
        logger.warning("[naga.deps] fetch failed for %s: %s", url[:60], e)
        return {"content": ""}


# ---------------------------------------------------------------------------
# gemini_generate — Gemini CLI (free with AI Ultra)
# ---------------------------------------------------------------------------


async def _gemini_generate(prompt: str = "", **kwargs: Any) -> dict:  # noqa: ARG001
    logger.info("[naga.deps] gemini bulk read %d chars via %s", len(prompt), _GEMINI_MODEL)
    try:
        proc = await asyncio.create_subprocess_exec(
            "gemini", "-m", _GEMINI_MODEL,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=120.0,
        )
        output = stdout.decode("utf-8", errors="replace")

        # Strip Gemini CLI noise
        clean_lines = []
        for line in output.split("\n"):
            if any(skip in line for skip in [
                "Scheduling MCP", "Executing MCP", "MCP context",
                "Policy file error", "Pattern:", "Suggestion:",
                "Loaded cached", "Registering notification",
                "Server '", "capabilities", "experimental",
                "GOOGLE_API_KEY", "GEMINI_API_KEY", "Both ",
            ]):
                continue
            clean_lines.append(line)
        clean = "\n".join(clean_lines).strip()
        logger.info("[naga.deps] gemini response: %d chars", len(clean))
        return {"text": clean}

    except asyncio.TimeoutError:
        logger.error("[naga.deps] gemini timed out after 120s")
        return {"text": "{}"}
    except FileNotFoundError:
        logger.error("[naga.deps] gemini CLI not found")
        return {"text": "{}"}
    except Exception as e:
        logger.error("[naga.deps] gemini failed: %s", e)
        return {"text": "{}"}


# ---------------------------------------------------------------------------
# notebook_query — stub (requires nlm CLI)
# ---------------------------------------------------------------------------


async def _notebook_query(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"status": "success", "answer": "", "sources_used": []}


# ---------------------------------------------------------------------------
# recall_similar — stub
# ---------------------------------------------------------------------------


async def _recall_similar(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"episodes": []}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_deps(mode: str = "server") -> SimpleNamespace:
    """Build dependency namespace for NagaOrchestrator.

    Args:
        mode: "server" for Fly.io (self-call localhost:8080),
              "local" for CLI testing (call Fly.io externally).
    """
    base_url = _BACKEND_URL_SERVER if mode == "server" else _BACKEND_URL_LOCAL

    return SimpleNamespace(
        exa_search=_exa_search,
        brave_search=_brave_search,
        fetch=_fetch,
        ask_legal=lambda **kw: _ask_legal(base_url, **kw),
        search_intel=lambda **kw: _search_intel(base_url, **kw),
        notebook_query=_notebook_query,
        recall_similar=_recall_similar,
        gemini_generate=_gemini_generate,
    )
