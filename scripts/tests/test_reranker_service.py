"""
Test script for RerankerService with ZeroEntropy API
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"))

# Mock environment variables
os.environ["ENVIRONMENT"] = "development"
# IMPORTANT: ZERANK2_API_KEY must be set in environment or passed directly

from services.reranker_service import RerankerService

async def test_zeroentropy_reranker():
    print("\n🚀 Testing ZeroEntropy Reranker Integration...\n")
    
    api_key = os.getenv("ZERANK2_API_KEY")
    if not api_key:
        print("❌ SKIPPING: ZERANK2_API_KEY not found in environment")
        return

    try:
        # Initialize service with ZeroEntropy provider
        reranker = RerankerService(
            provider="zeroentropy",
            api_key=api_key,
            enable_cache=False # Disable cache for testing
        )
        
        query = "What is the capital of Indonesia?"
        documents = [
            {"text": "Jakarta is the capital of Indonesia.", "id": 1},
            {"text": "Bali is a province in Indonesia.", "id": 2},
            {"text": "Surabaya is a major city in East Java.", "id": 3},
            {"text": "Tokyo is the capital of Japan.", "id": 4}
        ]
        
        print(f"Query: {query}")
        print(f"Docs: {len(documents)}")
        
        # Execute Rerank
        results = await reranker.rerank(query, documents, top_k=2)
        
        print("\n✅ Results:")
        for doc, score in results:
            print(f"- [Score: {score:.4f}] {doc['text']}")
            
        # Verify correctness
        top_doc = results[0][0]
        if "Jakarta" in top_doc["text"]:
            print("\n✅ TEST PASSED: Jakarta identified as most relevant")
        else:
            print("\n❌ TEST FAILED: Unexpected top result")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_zeroentropy_reranker())
