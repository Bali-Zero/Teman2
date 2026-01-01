"""
Test Knowledge Graph Persistence & Export
"""
import sys
import os
import asyncio
import asyncpg
import json

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.services.autonomous_agents.knowledge_graph_builder import KnowledgeGraphBuilder, Entity, Relationship

async def test_persistence():
    print("🔌 Connecting to DB...")
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5433/nuzantara_dev")
    try:
        pool = await asyncpg.create_pool(db_url)
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return

    print("🏗️  Initializing Knowledge Graph Builder with Persistence...")
    kg = KnowledgeGraphBuilder(db_pool=pool)

    # 1. ADD DATA
    print("➕ Adding entities to DB...")
    e1 = Entity(
        entity_id="kbli_56101_persistent",
        entity_type="kbli_code",
        name="Restaurant KBLI (Persistent)",
        description="Persistent restaurant entity",
        properties={"risk": "high", "source": "test_script"}
    )
    await kg.add_entity(e1)

    e2 = Entity(
        entity_id="permit_nib_persistent",
        entity_type="permit",
        name="NIB (Persistent)",
        description="Persistent NIB",
        properties={"validity": "forever"}
    )
    await kg.add_entity(e2)

    r1 = Relationship(
        relationship_id="rel_persistent_1",
        source_entity_id="kbli_56101_persistent",
        target_entity_id="permit_nib_persistent",
        relationship_type="requires",
        properties={"mandatory": True}
    )
    await kg.add_relationship(r1)
    
    print("✅ Data persisted.")

    # 2. SIMULATE RESTART (New Instance)
    print("\n🔄 Simulating Server Restart (New Instance)...")
    kg_new = KnowledgeGraphBuilder(db_pool=pool)
    
    # 3. EXPORT FROM DB (Should fetch what we just saved)
    print("📦 Exporting from DB...")
    json_out = await kg_new.export_graph("json")
    data = json.loads(json_out)
    
    entities = data.get("entities", [])
    print(f"📊 Found {len(entities)} entities in DB export.")
    
    found = False
    for e in entities:
        if e["entity_id"] == "kbli_56101_persistent":
            found = True
            print(f"✅ Verified Entity: {e['name']}")
            print(f"   Properties: {e['properties']}")
            break
            
    if not found:
        print("❌ Failed to find persisted entity!")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_persistence())
