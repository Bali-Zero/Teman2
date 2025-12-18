import sys
import os
import asyncio
import logging
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent / "apps/backend-rag"
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Mock environment variables for local test
os.environ["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
os.environ["LOG_LEVEL"] = "INFO"

from backend.services.legal_ingestion_service import LegalIngestionService

# PDF to test
TEST_PDF = "apps/kb/data/04_aziende/UU_6_2023_Cipta_Kerja_20251122_163034_739044.pdf"

async def test_legal_ingestion():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(TEST_PDF):
        logger.error(f"Test PDF not found: {TEST_PDF}")
        return

    logger.info(f"🚀 Starting Ingestion Test for: {TEST_PDF}")
    
    # We use a temporary collection to avoid polluting production-like data
    # or we use 'legal_unified' if we want to see it in action.
    collection = "test_legal_ingestion"
    
    service = LegalIngestionService(collection_name=collection)
    
    try:
        result = await service.ingest_legal_document(
            file_path=TEST_PDF,
            title="UU 6 2011 Keimigrasian (TEST)",
            collection_name=collection
        )
        
        if result["success"]:
            logger.info("✅ INGESTION SUCCESSFUL!")
            logger.info(f"📊 Summary:")
            logger.info(f"   - Chunks created: {result['chunks_created']}")
            logger.info(f"   - BAB count: {result['structure']['bab_count']}")
            logger.info(f"   - Pasal count: {result['structure']['pasal_count']}")
            logger.info(f"   - Tier: {result['tier']}")
            
            # Now let's verify PostgreSQL content
            doc_id = result['legal_metadata'].get('type_abbrev', 'DOC') + "_" + \
                     result['legal_metadata'].get('number', '0') + "_" + \
                     result['legal_metadata'].get('year', '0')
            doc_id = doc_id.replace(" ", "_").replace("/", "_")
            
            logger.info(f"🔍 Verifying parent_documents in DB for doc_id: {doc_id}")
            
            import asyncpg
            conn = await asyncpg.connect(os.environ["DATABASE_URL"])
            rows = await conn.fetch("SELECT id, title, pasal_count FROM parent_documents WHERE document_id = $1", doc_id)
            
            logger.info(f"Found {len(rows)} parent documents (BAB) in PostgreSQL:")
            for row in rows:
                logger.info(f"   - {row['id']}: {row['title']} ({row['pasal_count']} pasals)")
            
            await conn.close()
            
        else:
            logger.error(f"❌ INGESTION FAILED: {result['error']}")
            
    except Exception as e:
        logger.error(f"💥 ERROR during test: {e}", exc_info=True)
    finally:
        await service.indexer.close()

if __name__ == "__main__":
    asyncio.run(test_legal_ingestion())
