#!/usr/bin/env python3
"""
NB-RAG v2 Validation Benchmark Script
=======================================
Re-runs benchmark queries from the NB-RAG v2 design spec to validate
improvements against baseline scores measured on 2026-04-06.

Usage:
    PYTHONPATH=. python scripts/validate_nb_rag_v2.py
    PYTHONPATH=. python scripts/validate_nb_rag_v2.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import openai
from dotenv import load_dotenv

# Load .env from backend-rag root (override system env)
_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.misc.golden_answer_service import GoldenAnswerService

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark definitions
# ---------------------------------------------------------------------------

BENCHMARK_QUERIES: list[dict[str, Any]] = [
    {
        "query": "B211A visa requirements documents needed",
        "collection": "visa_oracle",
        "baseline_score": 0.575,
        "baseline_result": "WRONG — returned C7 instead of B211A-related visa",
        "target": "golden answer match OR score > 0.65 with correct visa code",
        "target_score": 0.65,
        "target_content": "B211A",
    },
    {
        "query": "restaurant food service KBLI code foreigner PMA",
        "collection": "kbli_2025_final_hybrid",
        "baseline_score": 0.533,
        "baseline_result": "WRONG — returned 56303 cafe instead of 56101 restaurant at #1",
        "target": "56101 in top 1, score > 0.55",
        "target_score": 0.55,
        "target_content": "56101",
    },
    {
        "query": "golden visa Indonesia requirements",
        "collection": "immigration_circulars",
        "baseline_score": 0.442,
        "baseline_result": "WRONG — no golden visa docs, only TKA circular",
        "target": "golden visa doc in results, score > 0.55",
        "target_score": 0.55,
        "target_content": "golden visa",
    },
    {
        "query": "corporate income tax rate PT PMA Indonesia",
        "collection": "tax_genius_hybrid",
        "baseline_score": 0.637,
        "baseline_result": "OK but from training conversations not normative",
        "target": "score > 0.60 maintained",
        "target_score": 0.60,
        "target_content": None,
    },
    {
        "query": "golden visa vs second home visa retired European",
        "collection": "training_conversations_hybrid",
        "baseline_score": 0.588,
        "baseline_result": "OK — found comparison conversation",
        "target": "score > 0.55 maintained",
        "target_score": 0.55,
        "target_content": None,
    },
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    query: str
    collection: str
    baseline_score: float
    baseline_result: str
    target: str
    target_score: float
    target_content: str | None
    # Populated at runtime
    current_score: float = 0.0
    top_result_payload: dict[str, Any] | None = None
    top_results: list[dict[str, Any]] | None = None
    golden_match: str = "NO MATCH"
    golden_match_type: str | None = None
    status: str = "UNKNOWN"  # IMPROVED / MAINTAINED / REGRESSED
    target_met: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------


def _qdrant_headers(api_key: str) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


async def embed_query(query: str, api_key: str) -> list[float]:
    """Generate embedding using text-embedding-3-small (FROZEN model)."""
    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    return response.data[0].embedding


async def search_qdrant(
    qdrant_url: str,
    qdrant_api_key: str,
    collection: str,
    vector: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Search Qdrant collection using named 'dense' vector.

    Returns list of hits with score and payload.
    """
    headers = _qdrant_headers(qdrant_api_key)
    payload = {
        "vector": {
            "name": "dense",
            "vector": vector,
        },
        "limit": top_k,
        "with_payload": True,
        "with_vector": False,
    }

    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/search"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    hits: list[dict[str, Any]] = data.get("result", [])
    return hits


# ---------------------------------------------------------------------------
# Target evaluation helpers
# ---------------------------------------------------------------------------


def _payload_text(payload: dict[str, Any]) -> str:
    """Flatten payload fields (including nested metadata) into a single searchable string."""
    parts: list[str] = []
    for field in ["kode_kbli", "judul", "content", "title", "visa_code", "visa_type",
                  "document_type", "kode", "name", "text", "answer"]:
        val = payload.get(field)
        if isinstance(val, str):
            parts.append(val)
    # Also search inside LangChain-style metadata dict
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for field in ["kode_kbli", "kode", "judul", "title", "visa_code", "source"]:
            val = meta.get(field)
            if isinstance(val, str):
                parts.append(val)
    return " ".join(parts).lower()


def _check_target_content(
    hits: list[dict[str, Any]],
    target_content: str | None,
    top_n: int = 1,
) -> bool:
    """Check if target_content appears in top_n results."""
    if target_content is None:
        return True  # No content target, pass automatically
    needle = target_content.lower()
    for hit in hits[:top_n]:
        payload = hit.get("payload", {})
        if needle in _payload_text(payload):
            return True
    return False


def _evaluate_status(result: BenchmarkResult) -> None:
    """Set result.status and result.target_met based on current vs baseline."""
    score = result.current_score
    target_score = result.target_score
    baseline = result.baseline_score

    # Target met = score threshold + content check (top-3 window for content)
    content_ok = _check_target_content(
        result.top_results or [], result.target_content, top_n=3
    )
    golden_ok = result.golden_match != "NO MATCH"

    # For score-based targets
    score_ok = score >= target_score

    # Special case: golden answer match is also acceptable for B211A
    if golden_ok:
        result.target_met = True
    elif score_ok and content_ok:
        result.target_met = True
    else:
        result.target_met = False

    # Delta classification
    delta = score - baseline
    if delta > 0.01:
        result.status = "IMPROVED"
    elif delta < -0.01:
        result.status = "REGRESSED"
    else:
        result.status = "MAINTAINED"


def _delta_label(current: float, baseline: float) -> str:
    delta = current - baseline
    sign = "+" if delta >= 0 else ""
    suffix = " IMPROVED" if delta > 0.01 else (" REGRESSED" if delta < -0.01 else " (same)")
    return f"{sign}{delta:.3f}{suffix}"


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------


async def run_benchmark(verbose: bool = False) -> list[BenchmarkResult]:
    qdrant_url = os.environ.get("QDRANT_URL", "")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    database_url = os.environ.get("DATABASE_URL", "")

    if not qdrant_url:
        print("ERROR: QDRANT_URL not set in environment.")
        sys.exit(1)
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in environment.")
        sys.exit(1)

    # Initialise GoldenAnswerService
    golden_svc: GoldenAnswerService | None = None
    if database_url:
        try:
            golden_svc = GoldenAnswerService(database_url)
            await golden_svc.connect()
        except Exception as exc:
            print(f"  [WARN] GoldenAnswerService unavailable: {exc}")
            golden_svc = None
    else:
        print("  [WARN] DATABASE_URL not set — golden answer lookup disabled.")

    results: list[BenchmarkResult] = []

    for bq in BENCHMARK_QUERIES:
        result = BenchmarkResult(
            query=bq["query"],
            collection=bq["collection"],
            baseline_score=bq["baseline_score"],
            baseline_result=bq["baseline_result"],
            target=bq["target"],
            target_score=bq["target_score"],
            target_content=bq.get("target_content"),
        )

        print(f"\n--- {result.query} ---")

        try:
            # 1. Golden answer lookup
            if golden_svc is not None:
                try:
                    ga_result = await golden_svc.lookup_golden_answer(result.query)
                    if ga_result:
                        match_type = ga_result.get("match_type", "unknown")
                        result.golden_match = f"MATCH ({match_type})"
                        result.golden_match_type = match_type
                    else:
                        result.golden_match = "NO MATCH"
                except Exception as exc:
                    result.golden_match = f"ERROR: {exc}"

            # 2. Embed query
            vector = await embed_query(result.query, openai_api_key)

            # 3. Search Qdrant
            hits = await search_qdrant(
                qdrant_url, qdrant_api_key, result.collection, vector, top_k=5
            )

            if not hits:
                result.error = "No results returned from Qdrant"
                result.status = "REGRESSED"
                results.append(result)
                _print_result(result, verbose)
                continue

            result.top_results = hits
            result.current_score = hits[0]["score"]
            result.top_result_payload = hits[0].get("payload", {})

            # 4. Evaluate
            _evaluate_status(result)

        except httpx.HTTPStatusError as exc:
            result.error = f"HTTP {exc.response.status_code}: {exc.response.text[:120]}"
            result.status = "REGRESSED"
        except Exception as exc:
            result.error = str(exc)
            result.status = "REGRESSED"

        results.append(result)
        _print_result(result, verbose)

    # Cleanup
    if golden_svc is not None:
        await golden_svc.close()

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _extract_top_label(payload: dict[str, Any] | None) -> str:
    """Extract a readable label from the top result's payload."""
    if not payload:
        return "(no payload)"
    # Try known flat fields first
    for field in ["kode_kbli", "visa_code", "visa_type", "kode", "title", "judul", "content"]:
        val = payload.get(field)
        if val:
            return str(val)[:60]
    # Try metadata nested dict (LangChain-style)
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for field in ["kode_kbli", "visa_code", "kode", "title", "judul", "source"]:
            val = meta.get(field)
            if val:
                return str(val)[:60]
    # Fall back to first 60 chars of text field
    text_val = payload.get("text")
    if text_val:
        return str(text_val)[:60]
    return "(unknown)"


def _print_result(result: BenchmarkResult, verbose: bool) -> None:
    print(f"  Collection: {result.collection}")
    print(f"  Golden Answer: {result.golden_match}")
    print(f"  Baseline: {result.baseline_score:.3f} ({result.baseline_result})")

    if result.error:
        print(f"  Current:  ERROR — {result.error}")
        print(f"  Target:   {result.target}")
        return

    top_label = _extract_top_label(result.top_result_payload)
    print(f"  Current:  {result.current_score:.3f} (top result: {top_label})")
    print(f"  Delta:    {_delta_label(result.current_score, result.baseline_score)}")
    print(f"  Target:   {result.target}")
    target_label = "MET" if result.target_met else "NOT MET"
    print(f"  Target status: {target_label}")

    if verbose and result.top_results:
        print(f"  Top {min(3, len(result.top_results))} results:")
        for i, hit in enumerate(result.top_results[:3], 1):
            payload = hit.get("payload", {})
            label = _extract_top_label(payload)
            print(f"    [{i}] score={hit['score']:.3f}  {label}")


def _print_summary(results: list[BenchmarkResult]) -> None:
    sep = "=" * 70
    print(f"\n{sep}")
    print("SUMMARY")
    print(sep)

    improved = sum(1 for r in results if r.status == "IMPROVED")
    maintained = sum(1 for r in results if r.status == "MAINTAINED")
    regressed = sum(1 for r in results if r.status == "REGRESSED")
    targets_met = sum(1 for r in results if r.target_met)
    total = len(results)

    print(f"  Improved:   {improved}/{total}")
    print(f"  Maintained: {maintained}/{total}")
    print(f"  Regressed:  {regressed}/{total}")
    print(f"  Targets met: {targets_met}/{total}")
    print(sep)

    # Per-query summary table
    print(f"\n  {'Query':<45} {'Baseline':>8} {'Current':>8} {'Delta':>8} {'Status':<12} {'Target'}")
    print(f"  {'-'*45} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*8}")
    for r in results:
        delta = r.current_score - r.baseline_score
        sign = "+" if delta >= 0 else ""
        q = r.query[:44]
        target_ok = "MET" if r.target_met else "MISS"
        print(
            f"  {q:<45} {r.baseline_score:>8.3f} {r.current_score:>8.3f} "
            f"{sign}{delta:>7.3f} {r.status:<12} {target_ok}"
        )
    print()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="NB-RAG v2 Validation Benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show top 3 results with metadata for each query",
    )
    args = parser.parse_args()

    sep = "=" * 70
    print(sep)
    print("NB-RAG v2 VALIDATION BENCHMARK")
    print(sep)
    print(f"Qdrant URL: {os.environ.get('QDRANT_URL', '(not set)')}")
    print(f"Queries:    {len(BENCHMARK_QUERIES)}")
    print(f"Verbose:    {args.verbose}")
    print(sep)

    results = await run_benchmark(verbose=args.verbose)
    _print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
