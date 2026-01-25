#!/usr/bin/env python3
"""
Production Qdrant Diagnostics
==============================

Check collections on production Qdrant instance.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag")

async def diagnose_production_qdrant():
    """Diagnose production Qdrant collections."""
    print("🔍 Production Qdrant Diagnostics\n" + "="*60)
    
    try:
        from qdrant_client import QdrantClient
        
        # Production Qdrant URL (from fly.toml)
        QDRANT_URL = "https://nuzantara-qdrant.fly.dev"
        
        # We need the API key - let's try without first
        print(f"📍 Qdrant URL: {QDRANT_URL}")
        print("🔑 Attempting connection (may require API key)...\n")
        
        try:
            # Try without API key first
            client = QdrantClient(url=QDRANT_URL)
            collections_response = client.get_collections()
            collections = collections_response.collections
            
            print(f"✅ Connected to Production Qdrant")
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
                try:
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
                except Exception as e:
                    print(f"⚠️  {col.name}: Error getting details - {e}")
            
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
            
        except Exception as e:
            if "Unauthorized" in str(e) or "401" in str(e):
                print("❌ Authentication required - Qdrant API key needed")
                print("   Run: fly secrets list -a nuzantara-rag | grep QDRANT_API_KEY")
            else:
                raise
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_production_qdrant())
