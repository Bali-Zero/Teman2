#!/usr/bin/env python3
"""
Comprehensive RAG Test Suite - 40 Questions
Tests different collections and query types directly via API
"""

import asyncio
import json
import os
import sys

# Add backend to path correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.rag.agentic.tools import VectorSearchTool
from services.search.search_service import SearchService

# Test questions organized by category
TEST_QUESTIONS = {
    "PRICING": [
        "Quanto costa aprire una PT PMA a Bali?",
        "What is the price for KITAS application?",
        "Berapa biaya visa investor?",
        "How much does company setup cost?",
        "Costo del visto E33G?",
    ],
    "VISA": [
        "What are the requirements for E33G visa?",
        "Come ottenere il KITAS investor?",
        "Apa syarat visa C1 Tourism?",
        "How long does KITAP processing take?",
        "Requisiti per il visto C312?",
    ],
    "KBLI": [
        "What KBLI code for restaurant business?",
        "Codice KBLI per e-commerce?",
        "KBLI untuk usaha konstruksi?",
        "Can foreigners own 100% in IT services?",
        "Is tourism sector open for PMA?",
    ],
    "TAX": [
        "What is the corporate tax rate in Indonesia?",
        "Aliquota IVA in Indonesia?",
        "Pajak penghasilan untuk WNA?",
        "Tax benefits for investment in Bali?",
        "How to get NPWP for foreigners?",
    ],
    "LEGAL": [
        "Steps to register PT PMA?",
        "What is OSS RBA?",
        "Minimum capital for foreign company?",
        "How to get NIB?",
        "Peraturan terbaru tentang investasi asing?",
    ],
    "TEAM": [
        "Who is the founder of Bali Zero?",
        "Chi sono i membri del team?",
        "What services does Bali Zero offer?",
        "Contact information for Bali Zero?",
        "Where is Bali Zero located?",
    ],
    "CULTURAL": [
        "Business etiquette in Indonesia?",
        "How to greet Indonesian partners?",
        "Ramadan considerations for business?",
        "Indonesian negotiation style?",
        "Cultural tips for expats in Bali?",
    ],
    "COMPLEX": [
        "I'm Italian, want to open a restaurant in Bali. What do I need?",
        "Compare KITAS vs KITAP for long-term stay",
        "Full process to start tech company in Indonesia",
        "Tax implications for digital nomads in Bali",
        "Best visa for remote worker earning abroad?",
    ],
}


async def test_vector_search_tool():
    """Test the VectorSearchTool directly"""
    print("\n" + "=" * 80)
    print("TESTING VECTORSEARCHTOOL DIRECTLY")
    print("=" * 80)

    # Initialize
    search_service = SearchService()
    tool = VectorSearchTool(search_service)

    results = []

    for category, questions in TEST_QUESTIONS.items():
        print(f"\n### {category} ###")
        for q in questions:
            try:
                result = await tool.execute(query=q, top_k=3)
                result_data = json.loads(result)

                sources = result_data.get("sources", [])
                collections = set(s.get("collection", "unknown") for s in sources)
                scores = [s.get("score", 0) for s in sources]
                max_score = max(scores) if scores else 0

                status = "PASS" if sources and max_score > 0.5 else "FAIL"

                print(f"  [{status}] {q[:50]}...")
                print(
                    f"       Collections: {collections}, MaxScore: {max_score:.2f}, Sources: {len(sources)}"
                )

                results.append(
                    {
                        "category": category,
                        "question": q,
                        "status": status,
                        "collections": list(collections),
                        "max_score": max_score,
                        "num_sources": len(sources),
                    }
                )

            except Exception as e:
                print(f"  [ERROR] {q[:50]}... → {str(e)[:50]}")
                results.append(
                    {
                        "category": category,
                        "question": q,
                        "status": "ERROR",
                        "error": str(e),
                    }
                )

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"Total: {total} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")
    print(f"Success Rate: {passed / total * 100:.1f}%")

    # Category breakdown
    print("\nBy Category:")
    for cat in TEST_QUESTIONS:
        cat_results = [r for r in results if r["category"] == cat]
        cat_pass = sum(1 for r in cat_results if r["status"] == "PASS")
        print(f"  {cat}: {cat_pass}/{len(cat_results)}")

    # Failed questions
    if failed > 0:
        print("\nFailed Questions:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - [{r['category']}] {r['question'][:60]}...")

    return results


if __name__ == "__main__":
    asyncio.run(test_vector_search_tool())
