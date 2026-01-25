#!/usr/bin/env python3
"""
Direct Tool Execution Diagnostic
=================================

Tests the vector_search tool directly to diagnose collection routing issues.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag")

# Set minimal env vars
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuzantara_db")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "development")

async def test_vector_search():
    """Test vector_search tool directly."""
    print("🔍 Testing vector_search tool directly...")
    
    try:
        from backend.services.rag.agentic.tools import VectorSearchTool
        from backend.services.rag.retrieval_service import RetrievalService
        from backend.app.core.config import Settings
        
        # Initialize
        settings = Settings()
        retrieval = RetrievalService(settings)
        tool = VectorSearchTool(retrieval)
        
        # Test KBLI query
        print("\n[Test 1] KBLI Query")
        result = await tool.execute(
            query="codice KBLI per ristorante",
            collection="knowledge_base",
            top_k=5
        )
        print(f"Result: {result[:500]}...")
        
        # Test Immigration query
        print("\n[Test 2] Immigration Query")
        result2 = await tool.execute(
            query="KITAS Investor requirements",
            collection="knowledge_base",
            top_k=5
        )
        print(f"Result: {result2[:500]}...")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vector_search())
