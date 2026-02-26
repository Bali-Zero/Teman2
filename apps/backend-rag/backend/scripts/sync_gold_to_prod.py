import json
import asyncio
import asyncpg
import logging
import os
import sys

# Add backend to path so we can import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_gold")

async def sync():
    # Load Gold codes from the JSON we just copied into backend/data
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/KBLI_2025_FINAL_CLEAN.json"))
    
    with open(json_path, "r") as f:
        db = json.load(f)
    
    # Filter for Gold codes (those with intel_2026)
    gold_data = [item for item in db["data"] if "intel_2026" in item]
    logger.info(f"Found {len(gold_data)} gold codes to sync")

    # Connect to Production DB
    logger.info(f"Connecting to database...")
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        for item in gold_data:
            code = item["kode_kbli_2025"]
            judul = item["judul"]
            intel_dict = item["intel_2026"]
            intel_json = json.dumps(intel_dict)
            
            # Update Knowledge Graph Node
            await conn.execute(
                "UPDATE kg_nodes SET name = $1, properties = properties || $2::jsonb WHERE entity_id = $3",
                judul, intel_json, f"kbli:{code}"
            )
            
            # Update kbli_documents
            means = intel_dict.get('whatItMeans', '')
            context = intel_dict.get('baliContext', '')
            doc_content = f"KBLI {code}: {judul}\n\nWHAT IT MEANS:\n{means}\n\nBALI CONTEXT:\n{context}"
            
            await conn.execute(
                "UPDATE kbli_documents SET judul = $1, content = $2 WHERE kode_kbli = $3",
                judul, doc_content, code
            )
            
            logger.info(f"✅ Synced KBLI {code}")
            
        logger.info("🚀 Synchronization complete!")
            
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(sync())
