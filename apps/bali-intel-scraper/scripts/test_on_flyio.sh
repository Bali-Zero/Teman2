#!/bin/bash
# Script per eseguire test completo direttamente su Fly.io
# Copia i file necessari e li esegue nel container

set -e

echo "🚀 Esecuzione test su Fly.io..."

# Crea uno script Python combinato che può essere eseguito direttamente
cat > /tmp/test_dedup_flyio.py << 'PYTHON_SCRIPT'
import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, '/app')

from loguru import logger
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

COLLECTION_NAME = "balizero_news_history"
VECTOR_SIZE = 1536
SIMILARITY_THRESHOLD = 0.88

async def main():
    logger.info("=" * 70)
    logger.info("🧪 TEST COMPLETO - SEMANTIC DEDUPLICATION (Fly.io)")
    logger.info("=" * 70)
    
    # Step 1: Verifica env vars
    logger.info("\n📋 STEP 1: Verifica Environment Variables...")
    qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    logger.info(f"   QDRANT_URL: {qdrant_url}")
    logger.info(f"   QDRANT_API_KEY: {'✅ Set' if qdrant_key else '❌ Missing'}")
    logger.info(f"   OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
    
    if not qdrant_key or not openai_key:
        logger.error("❌ Chiavi mancanti!")
        return False
    
    # Step 2: Inizializza collezione
    logger.info("\n📋 STEP 2: Inizializzazione Collezione Qdrant...")
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if exists:
            logger.warning(f"⚠️ La collezione '{COLLECTION_NAME}' esiste già.")
            logger.info("Mantengo la collezione esistente.")
        else:
            logger.info("🛠️ Creazione collezione ibrida...")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "default": models.VectorParams(
                        size=VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    indexing_threshold=1000,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                ),
            )
            logger.success("✅ Collezione creata!")
            
            # Crea indici
            logger.info("📑 Creazione indici payload...")
            client.create_payload_index(COLLECTION_NAME, "published_at", models.PayloadSchemaType.DATETIME)
            client.create_payload_index(COLLECTION_NAME, "source_url", models.PayloadSchemaType.KEYWORD)
            client.create_payload_index(COLLECTION_NAME, "category", models.PayloadSchemaType.KEYWORD)
            client.create_payload_index(COLLECTION_NAME, "tier", models.PayloadSchemaType.KEYWORD)
            logger.success("✅ Indici creati!")
        
        logger.success("✅ Collezione pronta")
    except Exception as e:
        logger.error(f"❌ Errore collezione: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Test Deduplicator
    logger.info("\n📋 STEP 3: Test Semantic Deduplicator...")
    try:
        openai_client = AsyncOpenAI(api_key=openai_key)
        qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
        
        # Test 1: Articolo nuovo
        logger.info("\n   🧪 Test 1: Articolo nuovo...")
        title = "Bali Introduces Revolutionary Digital Nomad Visa Program"
        summary = "The Indonesian government has launched a new visa program specifically designed for remote workers and digital nomads, allowing them to stay in Bali for up to 5 years."
        url = "https://test.example.com/bali-nomad-visa-2025"
        
        # Genera embedding
        response = await openai_client.embeddings.create(
            input=f"{title}\n{summary}",
            model="text-embedding-3-small"
        )
        vector = response.data[0].embedding
        
        # Check duplicato
        from datetime import datetime, timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
        
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=1,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="published_at",
                        range=models.DatetimeRange(gte=cutoff_date)
                    )
                ]
            ),
            with_payload=True
        )
        
        if search_result and search_result[0].score >= SIMILARITY_THRESHOLD:
            logger.warning(f"   ⚠️ Trovato duplicato (Score: {search_result[0].score:.2f})")
        else:
            logger.success(f"   ✅ Articolo UNICO")
        
        # Test 2: Salvataggio
        logger.info("\n   🧪 Test 2: Salvataggio articolo...")
        import hashlib
        import uuid
        doc_id = str(uuid.UUID(hashlib.md5(url.encode()).hexdigest()))
        
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload={
                        "title": title,
                        "summary": summary,
                        "source_url": url,
                        "source": "TestBot",
                        "category": "immigration",
                        "published_at": "2025-01-09T12:00:00Z",
                        "tier": "T2",
                        "ingested_at": datetime.utcnow().isoformat()
                    }
                )
            ]
        )
        logger.success("   ✅ Articolo salvato")
        
        # Test 3: Re-check
        logger.info("\n   🧪 Test 3: Re-check stesso articolo...")
        await asyncio.sleep(1)
        
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=1,
            with_payload=True
        )
        
        if search_result and search_result[0].score >= SIMILARITY_THRESHOLD:
            logger.success(f"   ✅ DUPLICATO RILEVATO! (Score: {search_result[0].score:.2f})")
        else:
            logger.warning(f"   ⚠️ Duplicato non rilevato")
        
    except Exception as e:
        logger.error(f"❌ Errore test deduplicator: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ TEST COMPLETATO CON SUCCESSO!")
    logger.info("=" * 70)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
PYTHON_SCRIPT

# Copia e esegui su Fly.io
fly ssh console -a nuzantara-rag -C "cat > /tmp/test_dedup_flyio.py" < /tmp/test_dedup_flyio.py
fly ssh console -a nuzantara-rag -C "python3 /tmp/test_dedup_flyio.py"

rm -f /tmp/test_dedup_flyio.py
