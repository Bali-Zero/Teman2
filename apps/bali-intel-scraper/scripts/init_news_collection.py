#!/usr/bin/env python3
"""
INIT NEWS COLLECTION (Hybrid: Dense + Sparse)
=============================================
Inizializza la collezione Qdrant per la cronologia delle news.
Configurata per RAG ibrido (vettori densi + keyword search BM25).

Collection: balizero_news_history
Vector Model: text-embedding-3-small (1536 dim)
Sparse Model: BM25
"""

import asyncio
import os
import sys
from pathlib import Path
from loguru import logger
from qdrant_client import QdrantClient, models

# Configurazione
COLLECTION_NAME = "balizero_news_history"
VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

async def init_collection():
    logger.info("=" * 60)
    logger.info(f"🆕 INITIALIZING COLLECTION: {COLLECTION_NAME}")
    logger.info(f"   URL: {QDRANT_URL}")
    logger.info("=" * 60)

    try:
        # 1. Connessione a Qdrant
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # 2. Check esistenza
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if exists:
            logger.warning(f"⚠️ La collezione '{COLLECTION_NAME}' esiste già.")
            # Chiedi conferma per ricreare solo se lanciato interattivamente, 
            # altrimenti esci
            logger.info("Mantengo la collezione esistente.")
            return

        # 3. Creazione Collezione Ibrida (Dense + Sparse)
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
            # Ottimizzazione per performance
            optimizers_config=models.OptimizersConfigDiff(
                default_segment_number=2,
                indexing_threshold=1000,
            ),
            # HNSW config standard
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100,
                full_scan_threshold=10000,
            ),
        )
        logger.success("✅ Collezione creata con successo!")

        # 4. Creazione Indici Payload (per filtri veloci)
        logger.info("📑 Creazione indici payload...")
        
        # Indice per data (essenziale per filtrare news recenti)
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="published_at",
            field_schema=models.PayloadSchemaType.DATETIME,
        )
        
        # Indice per URL (deduplicazione esatta)
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="source_url",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        
        # Indice per categoria
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="category",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        
        # Indice per tier (T1/T2)
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="tier",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        logger.success("✅ Indici creati!")
        logger.info("\n🎉 SETUP COMPLETATO: La collezione è pronta per l'ingestion.")

    except Exception as e:
        logger.error(f"❌ Errore durante l'inizializzazione: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_collection())
