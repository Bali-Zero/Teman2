#!/usr/bin/env python3
"""
Local Qdrant Diagnostics
=========================

Test Qdrant connectivity using backend services directly.
Runs locally against Docker Compose Qdrant instance.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag")

# Set env vars
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuzantara_db")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "development")

async def diagnose_qdrant():
    """Diagnose Qdrant collections and connectivity."""
    print("🔍 Qdrant Diagnostics\n" + "="*60)
    
    try:
        from qdrant_client import QdrantClient
        from backend.app.core.config import Settings
        
        settings = Settings()
        print(f"📍 Qdrant URL: {settings.qdrant_url}")
        
        # Connect to Qdrant
        client = QdrantClient(url=settings.qdrant_url)
        
        # List collections
        collections_response = client.get_collections()
        collections = collections_response.collections
        
        print(f"\n✅ Connected to Qdrant")
        print(f"📚 Found {len(collections)} collections:\n")
        
        # Tool-defined collections
        TOOL_COLLECTIONS = [
            "visa_oracle",
            "legal_unified_hybrid",
            "kbli_unified",
            "tax_genius_hybrid",
            "bali_zero_pricing",
            "training_conversations_hybrid",
        ]
        
        actual_collections = {}
        for col in collections:
            info = client.get_collection(col.name)
            actual_collections[col.name] = {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
            
            # Check if in tool definitions
            in_tool = "✅" if col.name in TOOL_COLLECTIONS else "⚠️ "
            print(f"{in_tool} {col.name}")
            print(f"   Points: {info.points_count:,}")
            print(f"   Vectors: {info.vectors_count:,}")
            print(f"   Status: {info.status}")
            print()
        
        # Check for missing collections
        print("\n🔍 Collection Mapping Analysis:")
        print("-" * 60)
        
        for tool_col in TOOL_COLLECTIONS:
            if tool_col in actual_collections:
                print(f"✅ {tool_col}: EXISTS ({actual_collections[tool_col]['points_count']:,} points)")
            else:
                print(f"❌ {tool_col}: MISSING (tool expects this collection)")
        
        # Check for extra collections
        extra = set(actual_collections.keys()) - set(TOOL_COLLECTIONS)
        if extra:
            print(f"\n⚠️  Extra collections not in tool definitions:")
            for col in extra:
                print(f"   - {col} ({actual_collections[col]['points_count']:,} points)")
        
        # Test search on KBLI collection
        print("\n\n🧪 Testing Vector Search on KBLI Collection:")
        print("-" * 60)
        
        if "kbli_unified" in actual_collections:
            from backend.services.rag.retrieval_service import RetrievalService
            
            retrieval = RetrievalService(settings)
            
            # Test search
            result = await retrieval.search(
                query="codice KBLI ristorante",
                user_level=1,
                limit=3,
                collection_override="kbli_unified"
            )
            
            results = result.get("results", [])
            print(f"Query: 'codice KBLI ristorante'")
            print(f"Results: {len(results)} documents")
            
            if results:
                print("\nTop Result:")
                top = results[0]
                text = top.get("text", "") if isinstance(top, dict) else getattr(top, "text", "")
                print(f"  Score: {top.get('score', 0) if isinstance(top, dict) else 0:.3f}")
                print(f"  Text: {text[:200]}...")
            else:
                print("❌ NO RESULTS FOUND - This explains the audit failure!")
        else:
            print("❌ kbli_unified collection not found!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_qdrant())
