#!/usr/bin/env python3
"""
RAG Canary — Embedding drift detection + golden query regression test.

Pure Python stdlib + curl calls. No external dependencies.
Runs monthly (embedding drift) or weekly (golden queries).

Usage:
    python3 scripts/rag_canary.py                     # Full run (drift + golden)
    python3 scripts/rag_canary.py --drift-only         # Embedding drift only
    python3 scripts/rag_canary.py --golden-only        # Golden queries only
    python3 scripts/rag_canary.py --save-baseline      # Save current embeddings as baseline
    python3 scripts/rag_canary.py --verbose             # Debug output
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_DIR = PROJECT_ROOT / "scripts" / ".rag_canary"
BASELINE_FILE = BASELINE_DIR / "embedding_baseline.json"
RESULTS_FILE = BASELINE_DIR / "last_run.json"

# --- Qdrant config (read from .env) ---
BACKEND_ENV = PROJECT_ROOT / "apps" / "backend-rag" / ".env"

# --- Reference texts for embedding drift detection ---
# These are domain-specific texts that should produce stable embeddings.
# If the embedding model changes, cosine distance will spike.
REFERENCE_TEXTS = [
    "PT PMA is a foreign-owned limited liability company in Indonesia",
    "KITAS is a temporary stay permit for foreigners working in Indonesia",
    "KITAP is a permanent stay permit granted after consecutive KITAS",
    "NPWP is the Indonesian tax identification number required for all companies",
    "Akte Pendirian is the deed of establishment for an Indonesian company",
    "OSS is the Online Single Submission system for business licensing",
    "NIB is the business identification number issued through OSS",
    "RPTKA is the expatriate manpower utilization plan required before hiring foreigners",
    "IMTA is the foreign worker employment permit issued by Kemenaker",
    "PPh 21 is the income tax on employee salaries in Indonesia",
    "PPN is the value added tax at 11% for most goods and services",
    "Hak Pakai is the right to use land in Indonesia available to foreigners",
    "HGB is the right to build on land for Indonesian legal entities",
    "Bali Zero provides visa and company setup services in Bali Indonesia",
    "Investor KITAS requires a minimum investment of USD 1.5 billion in Indonesia",
    "The KBLI 2025 classification system categorizes all business activities",
    "Peraturan Pemerintah number 28 year 2025 governs business licensing",
    "A CV or Commanditaire Vennootschap is a limited partnership in Indonesia",
    "Notaris in Indonesia handles company formation and deed authentication",
    "The Ministry of Manpower Kemenaker oversees foreign worker permits",
]

# --- Golden queries with expected top-3 collection matches ---
# Each query should return relevant results from specific collections.
GOLDEN_QUERIES = [
    {
        "query": "What documents are needed for KITAS work permit?",
        "expected_collections": ["visa_oracle", "legal_unified_hybrid_hybrid"],
        "min_score": 0.35,
    },
    {
        "query": "How much does a PT PMA cost?",
        "expected_collections": ["bali_zero_pricing_hybrid", "legal_unified_hybrid_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "KBLI code for restaurant business",
        "expected_collections": ["kbli_2025_final_hybrid"],
        "min_score": 0.40,
    },
    {
        "query": "What is the process to extend a KITAP?",
        "expected_collections": ["visa_oracle", "legal_unified_hybrid_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "PPh 21 tax rate for employees in Indonesia",
        "expected_collections": ["tax_genius_hybrid", "legal_unified_hybrid_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "Investor visa requirements and minimum capital",
        "expected_collections": ["visa_oracle"],
        "min_score": 0.30,
    },
    {
        "query": "How to open a company in Bali",
        "expected_collections": ["legal_unified_hybrid_hybrid", "training_conversations_hybrid"],
        "min_score": 0.25,
    },
    {
        "query": "RPTKA requirements for hiring foreign workers",
        "expected_collections": ["visa_oracle", "legal_unified_hybrid_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "Property ownership rights for foreigners in Bali",
        "expected_collections": ["legal_unified_hybrid_hybrid"],
        "min_score": 0.25,
    },
    {
        "query": "OSS online single submission business licensing",
        "expected_collections": ["legal_unified_hybrid_hybrid", "kbli_2025_final_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "Bali Zero team members and services",
        "expected_collections": ["training_conversations_hybrid"],
        "min_score": 0.20,
    },
    {
        "query": "PPN VAT tax obligations for PT companies",
        "expected_collections": ["tax_genius_hybrid", "legal_unified_hybrid_hybrid"],
        "min_score": 0.25,
    },
    {
        "query": "Peraturan Pemerintah 28 2025 business classification",
        "expected_collections": ["legal_unified_hybrid_hybrid", "kbli_2025_final_hybrid"],
        "min_score": 0.30,
    },
    {
        "query": "Social visa B211A requirements",
        "expected_collections": ["visa_oracle"],
        "min_score": 0.30,
    },
    {
        "query": "Company annual report and compliance requirements",
        "expected_collections": ["legal_unified_hybrid_hybrid"],
        "min_score": 0.20,
    },
]

VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[canary] {msg}", file=sys.stderr)


def _load_env() -> dict[str, str]:
    """Load Qdrant credentials from .env file."""
    env = {}
    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _openai_embed(texts: list[str], api_key: str) -> list[list[float]]:
    """Call OpenAI embeddings API."""
    payload = json.dumps({
        "model": "text-embedding-3-small",
        "input": texts,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    # Sort by index to ensure order
    sorted_data = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in sorted_data]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance (1 - cosine_similarity)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


def _qdrant_search(query_vector: list[float], collection: str, qdrant_url: str, api_key: str, limit: int = 5) -> list[dict]:
    """Search Qdrant collection. Uses named vector 'dense' for hybrid collections."""
    payload = json.dumps({
        "vector": {
            "name": "dense",
            "vector": query_vector,
        },
        "limit": limit,
        "with_payload": True,
    }).encode()

    req = urllib.request.Request(
        f"{qdrant_url}/collections/{collection}/points/search",
        data=payload,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("result", [])
    except Exception as e:
        log(f"Qdrant search failed for {collection}: {e}")
        return []


# --- Embedding Drift Detection ---

def run_drift_check(api_key: str) -> dict:
    """Re-embed reference texts and compare to baseline."""
    log("Running embedding drift check...")

    # Generate current embeddings
    log(f"Embedding {len(REFERENCE_TEXTS)} reference texts...")
    start = time.time()
    current_embeddings = _openai_embed(REFERENCE_TEXTS, api_key)
    embed_time = time.time() - start
    log(f"Embeddings generated in {embed_time:.1f}s")

    dims = len(current_embeddings[0]) if current_embeddings else 0

    result = {
        "timestamp": datetime.now(WITA).isoformat(),
        "model": "text-embedding-3-small",
        "dimensions": dims,
        "num_texts": len(REFERENCE_TEXTS),
        "embed_time_s": round(embed_time, 2),
    }

    # Check dimensions
    if dims != 1536:
        result["status"] = "CRITICAL"
        result["message"] = f"Wrong dimensions: {dims} (expected 1536)"
        return result

    # Compare to baseline if it exists
    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())
        baseline_embeddings = baseline["embeddings"]

        distances = []
        for i, (curr, base) in enumerate(zip(current_embeddings, baseline_embeddings)):
            d = _cosine_distance(curr, base)
            distances.append(d)
            if d > 0.005:
                log(f"  Text {i}: distance={d:.6f} (HIGH)")

        avg_dist = sum(distances) / len(distances) if distances else 0
        max_dist = max(distances) if distances else 0

        result["avg_cosine_distance"] = round(avg_dist, 8)
        result["max_cosine_distance"] = round(max_dist, 8)
        result["baseline_date"] = baseline.get("timestamp", "unknown")

        if avg_dist < 0.001:
            result["status"] = "STABLE"
            result["message"] = f"Avg distance {avg_dist:.6f} — model unchanged"
        elif avg_dist < 0.005:
            result["status"] = "MONITOR"
            result["message"] = f"Avg distance {avg_dist:.6f} — minor drift detected"
        elif avg_dist < 0.01:
            result["status"] = "WARNING"
            result["message"] = f"Avg distance {avg_dist:.6f} — significant drift!"
        else:
            result["status"] = "CRITICAL"
            result["message"] = f"Avg distance {avg_dist:.6f} — model likely changed! Re-index needed."
    else:
        result["status"] = "NO_BASELINE"
        result["message"] = "No baseline found. Run with --save-baseline first."

    return result


def save_baseline(api_key: str) -> None:
    """Save current embeddings as drift baseline."""
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Generating baseline from {len(REFERENCE_TEXTS)} texts...")
    embeddings = _openai_embed(REFERENCE_TEXTS, api_key)

    baseline = {
        "timestamp": datetime.now(WITA).isoformat(),
        "model": "text-embedding-3-small",
        "dimensions": len(embeddings[0]) if embeddings else 0,
        "num_texts": len(REFERENCE_TEXTS),
        "texts": REFERENCE_TEXTS,
        "embeddings": embeddings,
    }

    BASELINE_FILE.write_text(json.dumps(baseline))
    print(f"Baseline saved: {BASELINE_FILE} ({len(embeddings)} embeddings, {len(embeddings[0])} dims)")


# --- Golden Query Regression ---

def run_golden_queries(api_key: str, qdrant_url: str, qdrant_key: str) -> dict:
    """Run golden queries and check retrieval quality."""
    log("Running golden query regression test...")

    # Get all collections
    req = urllib.request.Request(
        f"{qdrant_url}/collections",
        headers={"api-key": qdrant_key},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        collections_data = json.loads(resp.read())
    available_collections = [c["name"] for c in collections_data["result"]["collections"]]

    results = []
    total_pass = 0
    total_fail = 0
    scores = []

    for gq in GOLDEN_QUERIES:
        query = gq["query"]
        expected = gq["expected_collections"]
        min_score = gq["min_score"]

        log(f"Query: {query[:60]}...")

        # Embed the query
        query_embedding = _openai_embed([query], api_key)[0]

        # Search across expected collections
        best_score = 0.0
        found_in = []

        for collection in expected:
            if collection not in available_collections:
                log(f"  Collection {collection} not found, skipping")
                continue

            hits = _qdrant_search(query_embedding, collection, qdrant_url, qdrant_key, limit=3)
            if hits:
                top_score = hits[0].get("score", 0)
                if top_score > best_score:
                    best_score = top_score
                if top_score > 0.2:
                    found_in.append(collection)
                log(f"  {collection}: top_score={top_score:.4f} ({len(hits)} hits)")

        passed = best_score >= min_score and len(found_in) > 0
        if passed:
            total_pass += 1
        else:
            total_fail += 1

        scores.append(best_score)

        results.append({
            "query": query,
            "expected_collections": expected,
            "found_in": found_in,
            "best_score": round(best_score, 4),
            "min_score": min_score,
            "passed": passed,
        })

    avg_score = sum(scores) / len(scores) if scores else 0
    pass_rate = total_pass / len(GOLDEN_QUERIES) * 100 if GOLDEN_QUERIES else 0

    return {
        "timestamp": datetime.now(WITA).isoformat(),
        "total_queries": len(GOLDEN_QUERIES),
        "passed": total_pass,
        "failed": total_fail,
        "pass_rate_pct": round(pass_rate, 1),
        "avg_best_score": round(avg_score, 4),
        "status": "OK" if pass_rate >= 80 else "WARNING" if pass_rate >= 60 else "CRITICAL",
        "results": results,
    }


# --- Main ---

def main() -> None:
    global VERBOSE

    parser = argparse.ArgumentParser(description="RAG Canary — embedding drift + golden query tests")
    parser.add_argument("--drift-only", action="store_true")
    parser.add_argument("--golden-only", action="store_true")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    VERBOSE = args.verbose

    # Load credentials
    env = _load_env()
    openai_key = env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    qdrant_url = env.get("QDRANT_URL") or os.environ.get("QDRANT_URL")
    qdrant_key = env.get("QDRANT_API_KEY") or os.environ.get("QDRANT_API_KEY")

    if not openai_key:
        print("ERROR: OPENAI_API_KEY not found in .env or environment")
        sys.exit(1)

    if args.save_baseline:
        save_baseline(openai_key)
        return

    report = {
        "timestamp": datetime.now(WITA).isoformat(),
        "machine": f"{os.environ.get('USER', 'unknown')}@{os.uname().nodename}",
    }

    # Run drift check
    if not args.golden_only:
        drift = run_drift_check(openai_key)
        report["embedding_drift"] = drift

    # Run golden queries
    if not args.drift_only:
        if not qdrant_url or not qdrant_key:
            print("ERROR: QDRANT_URL/QDRANT_API_KEY not found")
            sys.exit(1)
        golden = run_golden_queries(openai_key, qdrant_url, qdrant_key)
        report["golden_queries"] = golden

    # Save results
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2))

    # Print summary
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
