"""
Verification Script for Agentic RAG with ZeroEntropy Reranker
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"))

# Mock environment variables
os.environ["ENVIRONMENT"] = "development"

from services.rag.agentic import AgenticRAGOrchestrator, VectorSearchTool
from services.reranker_service import RerankerService

# Mock Retriever
class MockRetriever:
    async def search_with_reranking(self, query, limit=5, **kwargs):
        # This method normally handles reranking internally, but here we simulate
        # standard search returning many results for external reranking
        return await self.search(query, limit=limit, **kwargs)

    async def search(self, query, limit=5, **kwargs):
        print(f"   🔍 Mock Retriever searching for: '{query}' (limit={limit})")
        # Return a list of mixed relevance documents
        docs = [
            {"text": "Bali is a popular tourist destination.", "metadata": {"title": "Bali Info", "score": 0.5}},
            {"text": "The capital of Indonesia is Jakarta.", "metadata": {"title": "Indonesia Capital", "score": 0.4}}, # Relevant
            {"text": "Surabaya is a large city in Java.", "metadata": {"title": "Java Cities", "score": 0.6}},
            {"text": "Tokyo is the capital of Japan.", "metadata": {"title": "Japan Info", "score": 0.3}},
            {"text": "Jakarta is the economic center of Indonesia.", "metadata": {"title": "Jakarta Economy", "score": 0.45}}, # Relevant
            {"text": "Rendang is a famous Indonesian dish.", "metadata": {"title": "Indonesian Food", "score": 0.55}},
        ]
        # Return up to limit
        return {"results": docs[:limit]}

async def run_test():
    print("🚀 Starting Agentic RAG + Reranker Verification...\n")
    
    api_key = os.getenv("ZERANK2_API_KEY")
    if not api_key:
        print("❌ SKIPPING: ZERANK2_API_KEY not found")
        return

    # 1. Initialize Reranker
    reranker = RerankerService(provider="zeroentropy", api_key=api_key)
    
    # 2. Initialize Retriever & Tool
    retriever = MockRetriever()
    
    # We create the tool manually to inject reranker
    vector_tool = VectorSearchTool(retriever, reranker=reranker)
    
    print("--- Testing VectorSearchTool with Reranker ---")
    query = "What is the capital of Indonesia?"
    
    # Request top_k=2, should trigger fetch_k=8 and reranking
    result_json = await vector_tool.execute(query, top_k=2)
    
    import json
    result = json.loads(result_json)
    
    print(f"\nQuery: {query}")
    print(f"Content length: {len(result['content'])}")
    print(f"Sources returned: {len(result['sources'])}")
    
    print("\nTop Results:")
    for i, source in enumerate(result['sources']):
        print(f"{i+1}. {source['title']} (Score: {source['score']:.4f})")
        
    # Validation
    top_title = result['sources'][0]['title']
    if "Jakarta" in top_title or "Indonesia Capital" in top_title:
        print("\n✅ TEST PASSED: Reranker correctly identified Jakarta/Capital info.")
    else:
        print(f"\n❌ TEST FAILED: Top result was {top_title}")

if __name__ == "__main__":
    asyncio.run(run_test())
