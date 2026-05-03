#!/usr/bin/env python3
"""
Latency Breakdown Test Suite
============================
Measures individual component latencies to identify bottlenecks in the Zantara RAG system.

Tests:
1. Raw Gemini Flash API latency (no tools)
2. Individual tool execution times (vector_search, knowledge_graph, pricing)
3. Full ReAct loop timing per step
4. End-to-end query timing with different query types

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/test_latency_breakdown.py

Author: Claude Code
Date: 2026-01-27
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from statistics import mean, stdev

logging.basicConfig(level=logging.WARNING)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Suppress warnings
import warnings  # noqa: E402

warnings.filterwarnings("ignore")


@dataclass
class TimingResult:
    """Stores timing results for a test."""

    name: str
    duration_ms: float
    success: bool
    details: str = ""


class LatencyTester:
    """Tests individual component latencies."""

    def __init__(self):
        self.results: list[TimingResult] = []
        self._llm_gateway = None
        self._search_service = None
        self._tools = {}

    async def initialize(self):
        """Initialize services (lazy loading)."""
        print("\n🔧 Initializing services...")
        start = time.time()

        try:
            # Import and initialize LLM Gateway
            from backend.services.rag.agentic.llm_gateway import TIER_FLASH, LLMGateway

            self._llm_gateway = LLMGateway()
            self._tier_flash = TIER_FLASH
            print(f"   ✅ LLMGateway initialized ({(time.time() - start) * 1000:.0f}ms)")
        except Exception as e:
            print(f"   ❌ LLMGateway failed: {e}")
            return False

        try:
            # Import and initialize Search Service
            from backend.services.search.search_service import SearchService

            self._search_service = SearchService()
            print(f"   ✅ SearchService initialized ({(time.time() - start) * 1000:.0f}ms)")
        except Exception as e:
            print(f"   ⚠️ SearchService failed (non-critical): {e}")

        try:
            # Import Tools
            from backend.services.rag.agentic.tools import (
                PricingTool,
                VectorSearchTool,
            )

            if self._search_service:
                self._tools["vector_search"] = VectorSearchTool(self._search_service)
            self._tools["pricing"] = PricingTool()
            # KG tool needs db_pool, skip for now
            print(f"   ✅ Tools initialized ({(time.time() - start) * 1000:.0f}ms)")
        except Exception as e:
            print(f"   ⚠️ Tools failed (non-critical): {e}")

        print(f"   📊 Total init time: {(time.time() - start) * 1000:.0f}ms")
        return True

    # ==================== TEST 1: Raw Gemini API Latency ====================

    async def test_gemini_flash_raw(self, iterations: int = 3) -> list[TimingResult]:
        """Test raw Gemini Flash API latency without tools."""
        print("\n" + "=" * 70)
        print("TEST 1: Raw Gemini 3 Flash API Latency (no function calling)")
        print("=" * 70)

        results = []
        test_prompts = [
            "What is 2+2? Answer in one word.",
            "Say hello in Indonesian.",
            "What color is the sky? One word.",
        ]

        for i, prompt in enumerate(test_prompts[:iterations]):
            try:
                # Create a simple chat without function calling
                chat = self._llm_gateway.create_chat_with_history(
                    history_to_use=[],
                    model_tier=self._tier_flash,
                )

                start = time.time()
                response, model_name, _, usage = await self._llm_gateway.send_message(
                    chat=chat,
                    message=prompt,
                    system_prompt="Answer briefly in one sentence.",
                    tier=self._tier_flash,
                    enable_function_calling=False,  # No tools!
                )
                duration_ms = (time.time() - start) * 1000

                result = TimingResult(
                    name=f"gemini_flash_raw_{i + 1}",
                    duration_ms=duration_ms,
                    success=True,
                    details=f"Model: {model_name}, Tokens: {usage.total_tokens if usage else 'N/A'}",
                )
                results.append(result)
                print(f"   [{i + 1}] {duration_ms:.0f}ms - {model_name}")

            except Exception as e:
                results.append(
                    TimingResult(
                        name=f"gemini_flash_raw_{i + 1}",
                        duration_ms=0,
                        success=False,
                        details=str(e),
                    )
                )
                print(f"   [{i + 1}] ❌ FAILED: {e}")

        if results:
            successful = [r.duration_ms for r in results if r.success]
            if successful:
                avg = mean(successful)
                print(f"\n   📊 Average: {avg:.0f}ms (n={len(successful)})")

        self.results.extend(results)
        return results

    # ==================== TEST 2: Gemini with Function Calling ====================

    async def test_gemini_flash_with_tools(self, iterations: int = 3) -> list[TimingResult]:
        """Test Gemini Flash API latency WITH function calling enabled."""
        print("\n" + "=" * 70)
        print("TEST 2: Gemini 3 Flash API Latency (WITH function calling)")
        print("=" * 70)

        results = []
        test_prompts = [
            "What is the price for PT PMA setup?",  # Should trigger pricing tool
            "What are KITAS requirements?",  # Should trigger search
            "Who is the CEO of Bali Zero?",  # Should trigger team tool
        ]

        for i, prompt in enumerate(test_prompts[:iterations]):
            try:
                chat = self._llm_gateway.create_chat_with_history(
                    history_to_use=[],
                    model_tier=self._tier_flash,
                )

                start = time.time()
                response, model_name, response_obj, usage = await self._llm_gateway.send_message(
                    chat=chat,
                    message=prompt,
                    system_prompt="You are a helpful assistant. Use tools when needed.",
                    tier=self._tier_flash,
                    enable_function_calling=True,  # With tools!
                )
                duration_ms = (time.time() - start) * 1000

                # Check if function call was requested
                has_function_call = False
                if hasattr(response_obj, "candidates") and response_obj.candidates:
                    for candidate in response_obj.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, "function_call"):
                                    has_function_call = True
                                    break

                result = TimingResult(
                    name=f"gemini_flash_tools_{i + 1}",
                    duration_ms=duration_ms,
                    success=True,
                    details=f"Model: {model_name}, FuncCall: {has_function_call}",
                )
                results.append(result)
                print(
                    f"   [{i + 1}] {duration_ms:.0f}ms - {model_name} (FuncCall: {has_function_call})"
                )

            except Exception as e:
                results.append(
                    TimingResult(
                        name=f"gemini_flash_tools_{i + 1}",
                        duration_ms=0,
                        success=False,
                        details=str(e),
                    )
                )
                print(f"   [{i + 1}] ❌ FAILED: {e}")

        if results:
            successful = [r.duration_ms for r in results if r.success]
            if successful:
                avg = mean(successful)
                print(f"\n   📊 Average: {avg:.0f}ms (n={len(successful)})")

        self.results.extend(results)
        return results

    # ==================== TEST 3: Tool Execution Times ====================

    async def test_vector_search_tool(self, iterations: int = 3) -> list[TimingResult]:
        """Test VectorSearchTool execution time."""
        print("\n" + "=" * 70)
        print("TEST 3a: VectorSearchTool Execution Time (Qdrant)")
        print("=" * 70)

        if "vector_search" not in self._tools:
            print("   ⚠️ VectorSearchTool not available")
            return []

        results = []
        test_queries = [
            "PT PMA requirements",
            "KITAS visa process",
            "Tax rates Indonesia",
        ]

        tool = self._tools["vector_search"]

        for i, query in enumerate(test_queries[:iterations]):
            try:
                start = time.time()
                result = await tool.execute(query=query, top_k=5)
                duration_ms = (time.time() - start) * 1000

                # Parse result
                result_data = json.loads(result) if isinstance(result, str) else result
                num_sources = len(result_data.get("sources", []))

                timing = TimingResult(
                    name=f"vector_search_{i + 1}",
                    duration_ms=duration_ms,
                    success=True,
                    details=f"Sources: {num_sources}",
                )
                results.append(timing)
                print(f"   [{i + 1}] {duration_ms:.0f}ms - {num_sources} sources found")

            except Exception as e:
                results.append(
                    TimingResult(
                        name=f"vector_search_{i + 1}", duration_ms=0, success=False, details=str(e)
                    )
                )
                print(f"   [{i + 1}] ❌ FAILED: {e}")

        if results:
            successful = [r.duration_ms for r in results if r.success]
            if successful:
                avg = mean(successful)
                print(f"\n   📊 Average: {avg:.0f}ms (n={len(successful)})")

        self.results.extend(results)
        return results

    async def test_pricing_tool(self, iterations: int = 3) -> list[TimingResult]:
        """Test PricingTool execution time."""
        print("\n" + "=" * 70)
        print("TEST 3b: PricingTool Execution Time (Local JSON)")
        print("=" * 70)

        if "pricing" not in self._tools:
            print("   ⚠️ PricingTool not available")
            return []

        results = []
        test_queries = [
            {"service_type": "pt_pma"},
            {"service_type": "kitas"},
            {"service_type": "visa"},
        ]

        tool = self._tools["pricing"]

        for i, query in enumerate(test_queries[:iterations]):
            try:
                start = time.time()
                await tool.execute(**query)
                duration_ms = (time.time() - start) * 1000

                timing = TimingResult(
                    name=f"pricing_tool_{i + 1}",
                    duration_ms=duration_ms,
                    success=True,
                    details=f"Service: {query['service_type']}",
                )
                results.append(timing)
                print(f"   [{i + 1}] {duration_ms:.0f}ms - {query['service_type']}")

            except Exception as e:
                results.append(
                    TimingResult(
                        name=f"pricing_tool_{i + 1}", duration_ms=0, success=False, details=str(e)
                    )
                )
                print(f"   [{i + 1}] ❌ FAILED: {e}")

        if results:
            successful = [r.duration_ms for r in results if r.success]
            if successful:
                avg = mean(successful)
                print(f"\n   📊 Average: {avg:.0f}ms (n={len(successful)})")

        self.results.extend(results)
        return results

    # ==================== TEST 4: Full E2E Query via HTTP ====================

    async def test_e2e_query_http(self, iterations: int = 3) -> list[TimingResult]:
        """Test end-to-end query via HTTP API."""
        print("\n" + "=" * 70)
        print("TEST 4: End-to-End Query via HTTP (Production API)")
        print("=" * 70)

        import httpx

        results = []
        test_queries = [
            "Quanto costa aprire una PT PMA a Bali?",  # The original slow query
            "What is KITAS?",  # Simple knowledge query
            "Ciao!",  # Greeting (should be fast-path)
        ]

        # Try production first, then local
        base_urls = [
            "https://nuzantara-rag.fly.dev",  # Production
            "http://localhost:8000",  # Local
        ]

        working_url = None
        for url in base_urls:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url}/health")
                    if resp.status_code == 200:
                        working_url = url
                        print(f"   🌐 Using API: {url}")
                        break
            except Exception:
                continue

        if not working_url:
            print("   ❌ No API available (production or local)")
            return []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, query in enumerate(test_queries[:iterations]):
                try:
                    start = time.time()

                    # Use the agentic query endpoint (sync version for timing)
                    resp = await client.post(
                        f"{working_url}/api/agentic/query",
                        json={
                            "query": query,
                            "user_id": "latency_test",
                            "conversation_history": [],
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    duration_ms = (time.time() - start) * 1000

                    if resp.status_code == 200:
                        timing = TimingResult(
                            name=f"e2e_query_{i + 1}",
                            duration_ms=duration_ms,
                            success=True,
                            details=f"Query: {query[:30]}...",
                        )
                        print(f"   [{i + 1}] {duration_ms:.0f}ms - '{query[:30]}...'")
                    else:
                        timing = TimingResult(
                            name=f"e2e_query_{i + 1}",
                            duration_ms=duration_ms,
                            success=False,
                            details=f"HTTP {resp.status_code}",
                        )
                        print(f"   [{i + 1}] ❌ HTTP {resp.status_code} ({duration_ms:.0f}ms)")

                    results.append(timing)

                except Exception as e:
                    results.append(
                        TimingResult(
                            name=f"e2e_query_{i + 1}", duration_ms=0, success=False, details=str(e)
                        )
                    )
                    print(f"   [{i + 1}] ❌ FAILED: {e}")

        if results:
            successful = [r.duration_ms for r in results if r.success]
            if successful:
                avg = mean(successful)
                print(f"\n   📊 Average: {avg:.0f}ms (n={len(successful)})")

        self.results.extend(results)
        return results

    # ==================== SUMMARY ====================

    def print_summary(self):
        """Print summary of all test results."""
        print("\n" + "=" * 70)
        print("📊 LATENCY BREAKDOWN SUMMARY")
        print("=" * 70)

        # Group by test type
        groups = {}
        for r in self.results:
            prefix = r.name.rsplit("_", 1)[0]
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(r)

        for group_name, group_results in groups.items():
            successful = [r for r in group_results if r.success]
            if successful:
                times = [r.duration_ms for r in successful]
                avg = mean(times)
                min_t = min(times)
                max_t = max(times)
                std = stdev(times) if len(times) > 1 else 0

                print(f"\n{group_name}:")
                print(f"   Average: {avg:.0f}ms")
                print(f"   Min/Max: {min_t:.0f}ms / {max_t:.0f}ms")
                if std > 0:
                    print(f"   StdDev:  {std:.0f}ms")
                print(f"   Success: {len(successful)}/{len(group_results)}")

        # Total breakdown estimate
        print("\n" + "-" * 70)
        print("ESTIMATED TOTAL LATENCY BREAKDOWN (3-step ReAct):")
        print("-" * 70)

        gemini_raw = [
            r.duration_ms for r in self.results if "gemini_flash_raw" in r.name and r.success
        ]
        gemini_tools = [
            r.duration_ms for r in self.results if "gemini_flash_tools" in r.name and r.success
        ]
        vector = [r.duration_ms for r in self.results if "vector_search" in r.name and r.success]
        e2e = [r.duration_ms for r in self.results if "e2e_query" in r.name and r.success]

        gemini_avg = mean(gemini_raw) if gemini_raw else 0
        gemini_tools_avg = mean(gemini_tools) if gemini_tools else 0
        vector_avg = mean(vector) if vector else 0
        e2e_avg = mean(e2e) if e2e else 0

        function_calling_overhead = (
            gemini_tools_avg - gemini_avg if gemini_tools_avg and gemini_avg else 0
        )

        print(f"\n   Raw Gemini Flash (no tools):     {gemini_avg:.0f}ms")
        print(f"   + Function Calling overhead:     +{function_calling_overhead:.0f}ms")
        print(f"   = Gemini w/ Function Calling:    {gemini_tools_avg:.0f}ms")
        print(f"\n   Vector Search (Qdrant):          {vector_avg:.0f}ms")

        estimated_step = gemini_tools_avg + vector_avg
        estimated_3_steps = estimated_step * 3

        print(f"\n   Estimated per ReAct Step:        {estimated_step:.0f}ms")
        print(f"   Estimated 3 Steps (sequential):  {estimated_3_steps:.0f}ms")

        if e2e_avg:
            print(f"\n   Actual E2E Measured:             {e2e_avg:.0f}ms")
            overhead = e2e_avg - estimated_3_steps
            print(f"   Unexplained overhead:            {overhead:.0f}ms")


async def main():
    """Run all latency tests."""
    print("\n" + "=" * 70)
    print("🚀 ZANTARA LATENCY BREAKDOWN TEST SUITE")
    print("=" * 70)
    print("Testing individual components to identify bottlenecks...")

    tester = LatencyTester()

    # Initialize
    if not await tester.initialize():
        print("\n❌ Failed to initialize. Exiting.")
        return

    # Run tests
    await tester.test_gemini_flash_raw(iterations=3)
    await tester.test_gemini_flash_with_tools(iterations=3)
    await tester.test_vector_search_tool(iterations=3)
    await tester.test_pricing_tool(iterations=3)
    await tester.test_e2e_query_http(iterations=3)

    # Summary
    tester.print_summary()

    print("\n✅ Test suite complete!")


if __name__ == "__main__":
    asyncio.run(main())
