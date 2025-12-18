import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "apps/backend-rag"
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Config
os.environ["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
os.environ["LOG_LEVEL"] = "INFO"

from backend.services.legal_ingestion_service import LegalIngestionService

# Load Catalog
CATALOG_FILE = "master_ingestion_catalog.json"

async def run_single_ingestion():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("IngestionTank")
    
    with open(CATALOG_FILE, 'r') as f:
        catalog = json.load(f)
    
    # Find a file in '01_immigrazione' for a better test
    target_item = None
    for item in catalog['items']:
        if "01_immigrazione" in item['category']:
            target_item = item
            break
    
    if not target_item:
        target_item = catalog['items'][0]
        
    file_path = target_item['primary_path']
    filename = target_item['filename']
    category = target_item['category']
            
    logger.info(f"🚀 Processing SINGLE PDF: {filename}")
    logger.info(f"📂 Category: {category}")
    
    # Init Service
    service = LegalIngestionService(collection_name="legal_unified")
    
    try:
        # Ingest
        result = await service.ingest_legal_document(
            file_path=file_path,
            title=None,
            collection_name="legal_unified",
            category=category
        )
        
        if result["success"]:
            logger.info("✅ Ingestion Success!")
            doc_id_base = result['legal_metadata'].get('type_abbrev', 'DOC') + "_" + \
                          result['legal_metadata'].get('number', '0') + "_" + \
                          result['legal_metadata'].get('year', '0')
            doc_id = doc_id_base.replace(" ", "_").replace("/", "_")
            
            print("\n" + "="*60)
            print(f"📊 REPORT: {filename}")
            print("="*60)
            print(f"Document ID: {doc_id}")
            print(f"Chunks Created (Qdrant): {result['chunks_created']}")
            print(f"BAB Count (Postgres): {result['structure']['bab_count']}")
            print(f"Pasal Count: {result['structure']['pasal_count']}")
            print("-" * 60)
            
            # Verify Postgres
            import asyncpg
            conn = await asyncpg.connect(os.environ["DATABASE_URL"])
            rows = await conn.fetch("SELECT id, title, char_count FROM parent_documents WHERE document_id = $1", doc_id)
            
            print("🐘 POSTGRESQL (Parent Documents / BAB):")
            if rows:
                for row in rows:
                    print(f"  - [{row['id']}] {row['title']} ({row['char_count']} chars)")
            else:
                print("  (No BABs found in Postgres - maybe unstructured document?)")
            
            await conn.close()
            
            # Verify Qdrant (Simulated check via log, real check via API)
            print("\n🦅 QDRANT (Chunks):")
            print("  (Chunks upserted successfully. Use Qdrant dashboard to inspect vectors.)")
            print("="*60 + "\n")
            
        else:
            logger.error(f"❌ Failed: {result['error']}")

    except Exception as e:
        logger.error(f"Critical Error: {e}", exc_info=True)
    finally:
        await service.indexer.close()

if __name__ == "__main__":
    asyncio.run(run_single_ingestion())
