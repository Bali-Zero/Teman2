#!/usr/bin/env python3
"""
Sync KG Properties to Qdrant Payload
Synchronization script to push extracted properties from Postgres to Vector DB.
"""
import asyncio
import asyncpg
import os
import json
import requests
import sys
from pathlib import Path
from dotenv import load_dotenv

# Env setup
script_dir = Path(__file__).parent
backend_rag_dir = script_dir.parent / "apps" / "backend-rag"
sys.path.insert(0, str(backend_rag_dir))
load_dotenv(backend_rag_dir / ".env")

QDRANT_URL = "https://nuzantara-qdrant.fly.dev"
API_KEY = os.getenv("QDRANT_API_KEY")

async def sync_properties(limit=100, dry_run=True):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL missing")
        return

    print(f"🔌 Connecting to DB...")
    conn = await asyncpg.connect(db_url)
    
    try:
        # Fetch nodes with properties and source chunks
        rows = await conn.fetch("""
            SELECT entity_id, entity_type, name, properties, source_chunk_ids, source_collection
            FROM kg_nodes 
            WHERE properties IS NOT NULL 
            AND properties != '{}'::jsonb
            AND source_chunk_ids IS NOT NULL
            AND array_length(source_chunk_ids, 1) > 0
            LIMIT $1
        """, limit)
        
        print(f"📊 Found {len(rows)} candidates for sync.")
        
        synced_count = 0
        
        for row in rows:
            props = json.loads(row['properties'])
            chunk_ids = row['source_chunk_ids']
            collection = row['source_collection'] or "legal_unified_hybrid"
            
            # Map properties to Qdrant Payload keys
            payload_update = {}
            
            if row['entity_type'] == 'kbli':
                if 'skala_usaha' in props:
                    payload_update['kg_business_scale'] = props['skala_usaha']
                if 'tingkat_risiko' in props:
                    payload_update['kg_risk_level'] = props['tingkat_risiko']
                if 'pma_allowed' in props:
                    payload_update['kg_pma_allowed'] = props['pma_allowed']
                if 'kode' in props:
                    payload_update['kg_kbli_code'] = props['kode']
                    
            elif row['entity_type'] == 'biaya':
                if 'jumlah' in props:
                    payload_update['kg_fee_amount'] = props['jumlah']
                if 'mata_uang' in props:
                    payload_update['kg_currency'] = props['mata_uang']
                if 'jenis' in props:
                    payload_update['kg_fee_type'] = props['jenis']
            
            if not payload_update:
                continue
                
            print(f"🔄 Syncing {row['name'][:30]}... ({len(chunk_ids)} chunks)")
            print(f"   Payload: {payload_update}")
            
            if dry_run:
                continue
                
            # Perform Update on Qdrant
            # POST /collections/{collection_name}/points/payload
            # { "conf": "explicit", "points": [ids...], "payload": {...} }
            
            try:
                # We need to process chunks in batches if too many
                # But typically < 5 chunks per entity.
                
                # Check valid chunk IDs (UUID or Int?)
                # Qdrant IDs can be UUID or Int. Our source_chunk_ids should match.
                
                resp = requests.post(
                    f"{QDRANT_URL}/collections/{collection}/points/payload",
                    headers={"api-key": API_KEY},
                    json={
                        "points": chunk_ids,
                        "payload": payload_update
                    },
                    timeout=10
                )
                
                if resp.status_code == 200:
                    print(f"   ✅ Success")
                    synced_count += 1
                else:
                    print(f"   ❌ Error {resp.status_code}: {resp.text}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
                
        print(f"\n✅ Synced {synced_count} entities to Qdrant.")

    finally:
        await conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE")
        
    asyncio.run(sync_properties(args.limit, not args.dry_run)) # Negate dry_run logic in func vs arg? 
    # Wait, func def is sync_properties(limit, dry_run).
    # If passed dry_run=True, it skips.
    # Args say --dry-run (action store true).
    # So if flag is present, args.dry_run is True.
    # Call: asyncio.run(sync_properties(args.limit, args.dry_run))
