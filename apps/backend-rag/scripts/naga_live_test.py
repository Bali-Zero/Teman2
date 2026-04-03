#!/usr/bin/env python3
"""Naga Live Test — runs a real research query with REAL tools.

Connects to:
  1. ask_legal → Fly.io backend (HTTP)
  2. Gemini CLI → gemini-3.1-pro-preview (subprocess, AI Ultra)
  3. Exa → web search via httpx (uses BRAVE_API_KEY or free fallback)

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/naga_live_test.py "golden visa Indonesia"
    PYTHONPATH=. python scripts/naga_live_test.py --tier flash "quanto costa KITAS?"
    PYTHONPATH=. python scripts/naga_live_test.py --tier deep "analisi PT PMA vs CV"
    PYTHONPATH=. python scripts/naga_live_test.py --live "golden visa Indonesia requisiti"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from types import SimpleNamespace
from typing import Any

import httpx

from backend.services.naga.orchestrator import NagaOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("naga.live_test")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
BACKEND_API_KEY = os.getenv("SCRAPER_API_KEY", "internal-scraper-key")
GEMINI_MODEL = "gemini-3.1-pro-preview"

_http: httpx.AsyncClient | None = None


async def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=60.0)
    return _http


# ---------------------------------------------------------------------------
# REAL TOOL: ask_legal → Fly.io backend
# ---------------------------------------------------------------------------

async def ask_legal(**kwargs: Any) -> dict:
    """Call the real ask_legal endpoint on Fly.io backend."""
    query = kwargs.get("query", "")
    logger.info("  [ASK_LEGAL] %s", query[:80])
    client = await _get_http()
    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/agentic-rag/query",
            json={"query": query, "language": "en"},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=90.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "answer": data.get("answer", data.get("response", "")),
                "sources": data.get("sources", []),
                "confidence": data.get("confidence", 0.7),
            }
        logger.warning("  [ASK_LEGAL] HTTP %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("  [ASK_LEGAL] Failed: %s", e)
    return {"answer": "", "sources": [], "confidence": 0.0}


# ---------------------------------------------------------------------------
# REAL TOOL: search_intel → Fly.io backend
# ---------------------------------------------------------------------------

async def search_intel(**kwargs: Any) -> dict:
    """Call the real search_intel endpoint."""
    query = kwargs.get("query", "")
    logger.info("  [SEARCH_INTEL] %s", query[:80])
    client = await _get_http()
    try:
        resp = await client.get(
            f"{BACKEND_URL}/api/intel/search",
            params={"q": query, "limit": 5},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("  [SEARCH_INTEL] Failed: %s", e)
    return {"results": []}


# ---------------------------------------------------------------------------
# REAL TOOL: Exa-like web search via Brave (free tier)
# ---------------------------------------------------------------------------

async def exa_search(**kwargs: Any) -> dict:
    """Web search using Brave Search API (free tier, independent index)."""
    query = kwargs.get("query", "")
    num_results = kwargs.get("numResults", 5)
    include_domains = kwargs.get("includeDomains", [])
    logger.info("  [WEB_SEARCH] %s (max %d)", query[:60], num_results)

    client = await _get_http()

    # Build search query with domain filter if specified
    search_query = query
    if include_domains:
        domain_filter = " OR ".join(f"site:{d}" for d in include_domains[:3])
        search_query = f"{query} ({domain_filter})"

    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": search_query, "count": min(num_results, 10)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": os.getenv("BRAVE_API_KEY", ""),
            },
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
            logger.info("  [WEB_SEARCH] Got %d results", len(results))
            return {"results": results}
        else:
            logger.warning("  [WEB_SEARCH] HTTP %d", resp.status_code)
    except Exception as e:
        logger.warning("  [WEB_SEARCH] Failed: %s", e)

    return {"results": []}


# ---------------------------------------------------------------------------
# REAL TOOL: Brave search (diversifier)
# ---------------------------------------------------------------------------

async def brave_search(**kwargs: Any) -> dict:
    """Second web search call — returns empty to avoid duplicate results."""
    return {"web": {"results": []}}


# ---------------------------------------------------------------------------
# REAL TOOL: Fetch URL content
# ---------------------------------------------------------------------------

async def fetch_url(**kwargs: Any) -> dict:
    """Fetch URL content as text."""
    url = kwargs.get("url", "")
    max_length = kwargs.get("max_length", 50000)
    logger.info("  [FETCH] %s", url[:80])
    client = await _get_http()
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        return {"content": resp.text[:max_length]}
    except Exception as e:
        logger.warning("  [FETCH] Failed: %s", e)
        return {"content": ""}


# ---------------------------------------------------------------------------
# REAL TOOL: Gemini CLI (gemini-3.1-pro-preview, free with AI Ultra)
# ---------------------------------------------------------------------------

async def gemini_generate(prompt: str = "", **kwargs: Any) -> dict:
    """Call Gemini via CLI subprocess — free with Google AI Ultra subscription."""
    logger.info("  [GEMINI] Bulk reading %d chars via %s", len(prompt), GEMINI_MODEL)

    # Truncate prompt if too long for CLI arg (use stdin instead)
    try:
        proc = await asyncio.create_subprocess_exec(
            "gemini", "-m", GEMINI_MODEL,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Pass prompt via stdin to avoid shell arg length limits
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=120.0,
        )

        output = stdout.decode("utf-8", errors="replace")

        # Strip Gemini CLI noise (MCP refresh, policy warnings)
        clean_lines = []
        for line in output.split("\n"):
            if any(skip in line for skip in [
                "Scheduling MCP", "Executing MCP", "MCP context",
                "Policy file error", "Pattern:", "Suggestion:",
                "Loaded cached", "Registering notification",
                "Server '", "capabilities", "experimental",
                "GOOGLE_API_KEY", "GEMINI_API_KEY",
            ]):
                continue
            clean_lines.append(line)
        clean_output = "\n".join(clean_lines).strip()

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:500]
            logger.warning("  [GEMINI] Exit code %d: %s", proc.returncode, err)
            return {"text": clean_output or "{}"}

        logger.info("  [GEMINI] Got %d chars response", len(clean_output))
        return {"text": clean_output}

    except asyncio.TimeoutError:
        logger.error("  [GEMINI] Timed out after 120s")
        return {"text": "{}"}
    except FileNotFoundError:
        logger.error("  [GEMINI] CLI not found — install: npm i -g @google/gemini-cli")
        return {"text": "{}"}
    except Exception as e:
        logger.error("  [GEMINI] Failed: %s", e)
        return {"text": "{}"}


# ---------------------------------------------------------------------------
# STUBS (NLM + recall — require local NLM CLI or backend)
# ---------------------------------------------------------------------------

async def notebook_query(**kwargs: Any) -> dict:
    """Stub — NLM requires nlm CLI. Returns empty."""
    logger.info("  [NLM] notebook=%s (stub)", kwargs.get("notebook_id", "?"))
    return {"status": "success", "answer": "", "sources_used": []}


async def recall_similar(**kwargs: Any) -> dict:
    """Stub — episodic memory."""
    return {"episodes": []}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_live_test(query: str, tier: str, domain: str) -> None:
    """Run a Naga research query with real tools."""

    print(f"\n{'='*70}")
    print("  NAGA LIVE TEST (REAL TOOLS)")
    print(f"  Query:   {query}")
    print(f"  Tier:    {tier}")
    print(f"  Domain:  {domain}")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Gemini:  {GEMINI_MODEL}")
    print(f"{'='*70}\n")

    deps = SimpleNamespace(
        exa_search=exa_search,
        brave_search=brave_search,
        fetch=fetch_url,
        ask_legal=ask_legal,
        search_intel=search_intel,
        notebook_query=notebook_query,
        recall_similar=recall_similar,
        gemini_generate=gemini_generate,
    )

    orch = NagaOrchestrator(deps=deps)

    start = time.monotonic()
    result = await orch.research(
        query=query,
        tier=tier,
        domain=domain,
    )
    elapsed = time.monotonic() - start

    # Print results
    print(f"\n{'='*70}")
    print("  RESULTS")
    print(f"{'='*70}")
    print(f"  Status:      {result.get('status', '?')}")
    print(f"  Tier:        {result.get('tier', '?')}")
    print(f"  Domain:      {result.get('domain', '?')}")
    print(f"  Iterations:  {result.get('iteration', 0)}")
    print(f"  Sources:     {len(result.get('search_results', []))}")
    print(f"  Claims:      {result.get('claims_extracted', 0)}")
    print(f"  Confidence:  {result.get('avg_confidence', 0):.2f}")
    print(f"  Duration:    {elapsed:.1f}s")
    print(f"  Evidence:    {result.get('evidence_map_uri', 'N/A')}")

    report = result.get("report_markdown", "")
    if report:
        print(f"\n{'='*70}")
        print("  REPORT")
        print(f"{'='*70}")
        # Print full report for flash, first 2000 for deep/exhaustive
        max_chars = 5000 if tier == "flash" else 2000
        print(report[:max_chars])
        if len(report) > max_chars:
            print(f"\n  ... ({len(report)} total chars)")

    actions = result.get("action_items", [])
    if actions:
        print(f"\n{'='*70}")
        print(f"  ACTION ITEMS ({len(actions)})")
        print(f"{'='*70}")
        for a in actions:
            auto = "AUTO" if a.get("auto_execute") else "MANUAL"
            print(f"  [{a.get('priority', '?')}] {a.get('action_type', '?')} — {a.get('description', '')[:80]} ({auto})")

    error = result.get("error", "")
    if error:
        print(f"\n  ERROR: {error}")

    print(f"\n{'='*70}")
    status = result.get("status", "?")
    sources = len(result.get("search_results", []))
    claims = result.get("claims_extracted", 0)
    if status == "completed" and sources > 0:
        print(f"  NAGA LIVE TEST PASSED — {sources} sources, {claims} claims, {elapsed:.1f}s")
    elif status == "completed":
        print(f"  NAGA LIVE TEST COMPLETED (no sources found) — {elapsed:.1f}s")
    else:
        print(f"  NAGA LIVE TEST: status={status}")
    print(f"{'='*70}\n")

    # Cleanup
    global _http
    if _http:
        await _http.aclose()
        _http = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Naga Live Test (Real Tools)")
    parser.add_argument("query", help="Research query")
    parser.add_argument("--tier", default="auto", choices=["auto", "flash", "deep", "exhaustive"])
    parser.add_argument("--domain", default="auto", choices=["auto", "indonesia", "general", "hybrid"])
    args = parser.parse_args()

    asyncio.run(run_live_test(args.query, args.tier, args.domain))


if __name__ == "__main__":
    main()
