#!/usr/bin/env python3
"""
Test KBLI foreign ownership queries against training_conversations_hybrid.
Verifies that the new training data is retrievable and relevant.
"""

import os
import sys
from pathlib import Path

import requests

script_dir = Path(__file__).parent
backend_rag_root = script_dir.parent
sys.path.insert(0, str(backend_rag_root / "backend"))

from dotenv import load_dotenv

load_dotenv(backend_rag_root / ".env")

COLLECTION_NAME = "training_conversations_hybrid"
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_embedding(text: str) -> list[float]:
    import openai

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    resp = client.embeddings.create(input=text, model="text-embedding-3-small")
    return resp.data[0].embedding


def get_bm25_sparse(text: str) -> dict:
    from core.bm25_vectorizer import BM25Vectorizer

    bm25 = BM25Vectorizer()
    return bm25.generate_sparse_vector(text)


def search_qdrant(query: str, top_k: int = 5) -> list[dict]:
    dense = get_embedding(query)
    sparse = get_bm25_sparse(query)

    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/query"
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}

    data = {
        "prefetch": [
            {"query": dense, "using": "dense", "limit": top_k * 2},
            {
                "query": {"indices": sparse["indices"], "values": sparse["values"]},
                "using": "bm25",
                "limit": top_k * 2,
            },
        ],
        "query": {"fusion": "rrf"},
        "limit": top_k,
        "with_payload": True,
    }

    resp = requests.post(url, headers=headers, json=data, timeout=30)
    if resp.status_code != 200:
        print(f"  ERROR: Qdrant returned {resp.status_code}: {resp.text[:200]}")
        return []

    results = resp.json().get("result", {}).get("points", [])
    return results


def test_query(query: str, expected_keywords: list[str]) -> bool:
    """Test a query and check if results contain expected keywords."""
    print(f"\n{'=' * 70}")
    print(f"QUERY: {query}")
    print(f"Expected keywords: {expected_keywords}")
    print(f"{'=' * 70}")

    results = search_qdrant(query, top_k=3)

    if not results:
        print("  NO RESULTS")
        return False

    found_keywords = set()
    has_kbli_ownership = False

    for i, r in enumerate(results):
        payload = r.get("payload", {})
        score = r.get("score", 0)
        source = payload.get("source", "unknown")
        text = payload.get("text", "")[:300]

        print(f"\n  Result {i + 1} (score={score:.4f}):")
        print(f"    Source: {source}")
        print(f"    Text: {text}...")

        # Check for expected keywords in full text
        full_text = payload.get("text", "").lower()
        for kw in expected_keywords:
            if kw.lower() in full_text:
                found_keywords.add(kw)

        # Check if result is from our new file
        if "business_033" in source or "kbli_foreign_ownership" in source:
            has_kbli_ownership = True

    match_pct = len(found_keywords) / len(expected_keywords) * 100 if expected_keywords else 0
    print(f"\n  Keywords found: {found_keywords} ({match_pct:.0f}%)")
    print(f"  From KBLI ownership file: {'YES' if has_kbli_ownership else 'NO'}")

    success = match_pct >= 50 and has_kbli_ownership
    print(f"  RESULT: {'PASS' if success else 'FAIL'}")
    return success


def main():
    print("=" * 70)
    print("KBLI FOREIGN OWNERSHIP - QUERY TEST SUITE")
    print("=" * 70)

    tests = [
        {
            "query": "KBLI ristorante proprietà straniera?",
            "keywords": ["56101", "100%", "TERBUKA", "restoran"],
        },
        {
            "query": "Posso aprire retail 100% straniero?",
            "keywords": ["47111", "retail", "TERBATAS", "UMKM"],
        },
        {
            "query": "KBLI consulting foreign ownership?",
            "keywords": ["70201", "100%", "consulting", "TERBUKA"],
        },
        {
            "query": "Can I open a restaurant with 100% foreign ownership in Bali?",
            "keywords": ["56101", "100%", "restaurant", "TERBUKA"],
        },
        {
            "query": "Which sectors are closed to foreign investors in Indonesia?",
            "keywords": ["TERTUTUP", "11010", "92000", "gambling"],
        },
        {
            "query": "KBLI code for villa rental foreign ownership percentage",
            "keywords": ["55192", "100%", "villa", "TERBUKA"],
        },
        {
            "query": "foreign ownership limit advertising agency Indonesia",
            "keywords": ["73100", "49%", "TERBATAS", "advertising"],
        },
        {
            "query": "IT software company foreign ownership Indonesia KBLI",
            "keywords": ["62011", "100%", "TERBUKA", "software"],
        },
    ]

    passed = 0
    for test in tests:
        if test_query(test["query"], test["keywords"]):
            passed += 1

    print(f"\n{'=' * 70}")
    print(f"FINAL RESULTS: {passed}/{len(tests)} tests passed ({passed / len(tests) * 100:.0f}%)")
    print(f"{'=' * 70}")

    if passed / len(tests) >= 0.75:
        print("SUCCESS: Query retrieval meets target (>= 75%)")
    else:
        print("NEEDS IMPROVEMENT: Some queries not retrieving relevant results")


if __name__ == "__main__":
    main()
