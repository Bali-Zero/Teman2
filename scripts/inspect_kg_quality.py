#!/usr/bin/env python3
"""
Ispettore Qualità Knowledge Graph
Campiona entità e relazioni per verifica manuale
"""
import asyncio
import asyncpg
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Env setup
script_dir = Path(__file__).parent
backend_rag_dir = script_dir.parent / "apps" / "backend-rag"
sys.path.insert(0, str(backend_rag_dir))
load_dotenv(backend_rag_dir / ".env")

async def inspect_quality():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL mancante")
        return

    print(f"🔌 Connessione a {db_url}...")
    conn = await asyncpg.connect(db_url)
    
    try:
        print("\n" + "="*60)
        print("🔍 SAMPLE: KBLI ARRICCHITI")
        print("="*60)
        
        kbli_rows = await conn.fetch("""
            SELECT name, properties, updated_at
            FROM kg_nodes 
            WHERE entity_type = 'kbli' 
            AND properties ? 'ruang_lingkup'
            ORDER BY updated_at DESC 
            LIMIT 3
        """)
        
        for row in kbli_rows:
            print(f"\n📌 {row['name']}")
            print(f"   Updated: {row['updated_at']}")
            print(json.dumps(row['properties'], indent=2, ensure_ascii=False))
            
        print("\n" + "="*60)
        print("🔍 SAMPLE: BIAYA ARRICCHITI")
        print("="*60)
        
        biaya_rows = await conn.fetch("""
            SELECT name, properties, updated_at
            FROM kg_nodes 
            WHERE entity_type = 'biaya' 
            AND properties ? 'jenis'
            ORDER BY updated_at DESC 
            LIMIT 3
        """)
        
        for row in biaya_rows:
            print(f"\n💰 {row['name']}")
            print(json.dumps(row['properties'], indent=2, ensure_ascii=False))

        print("\n" + "="*60)
        print("🔍 SAMPLE: RELAZIONI PREDETTE (REQUIRES)")
        print("="*60)
        
        edges_req = await conn.fetch("""
            SELECT 
                s.name as source, 
                t.name as target, 
                e.properties, 
                e.confidence
            FROM kg_edges e
            JOIN kg_nodes s ON e.source_entity_id = s.entity_id
            JOIN kg_nodes t ON e.target_entity_id = t.entity_id
            WHERE e.relationship_type = 'REQUIRES'
            AND e.properties::text LIKE '%Inferred%'
            LIMIT 3
        """)
        
        for row in edges_req:
            print(f"\n🔗 {row['source']} --[REQUIRES]--> {row['target']}")
            print(f"   Conf: {row['confidence']}")
            print(f"   Evidence: {row['properties']}")

        print("\n" + "="*60)
        print("🔍 SAMPLE: RELAZIONI PREDETTE (HAS_FEE)")
        print("="*60)
        
        edges_fee = await conn.fetch("""
            SELECT 
                s.name as source, 
                t.name as target, 
                e.properties, 
                e.confidence
            FROM kg_edges e
            JOIN kg_nodes s ON e.source_entity_id = s.entity_id
            JOIN kg_nodes t ON e.target_entity_id = t.entity_id
            WHERE e.relationship_type = 'HAS_FEE'
            AND e.properties::text LIKE '%Inferred%'
            LIMIT 3
        """)
        
        for row in edges_fee:
            print(f"\n🔗 {row['source']} --[HAS_FEE]--> {row['target']}")
            print(f"   Conf: {row['confidence']}")
            print(f"   Evidence: {row['properties']}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_quality())
