#!/usr/bin/env python3
"""
INIT NEWS COLLECTION usando httpx direttamente (workaround per problema qdrant-client)
"""
import os
import json
import httpx
from loguru import logger

COLLECTION_NAME = "balizero_news_history"
VECTOR_SIZE = 1536
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

def init_collection():
    logger.info("=" * 60)
    logger.info(f"🆕 INITIALIZING COLLECTION: {COLLECTION_NAME}")
    logger.info(f"   URL: {QDRANT_URL}")
    logger.info("=" * 60)

    headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}
    
    with httpx.Client(timeout=30.0, headers=headers) as client:
        # 1. Check esistenza
        try:
            logger.info("Checking existing collections...")
            response = client.get(f"{QDRANT_URL}/collections")
            response.raise_for_status()
            collections_data = response.json()
            collections = collections_data.get("result", {}).get("collections", [])
            exists = any(c["name"] == COLLECTION_NAME for c in collections)
            
            if exists:
                logger.warning(f"⚠️ La collezione '{COLLECTION_NAME}' esiste già.")
                logger.info("Mantengo la collezione esistente.")
                return
            
            # 2. Creazione Collezione Ibrida
            logger.info("🛠️ Creazione collezione ibrida...")
            
            collection_config = {
                "vectors": {
                    "default": {
                        "size": VECTOR_SIZE,
                        "distance": "Cosine"
                    }
                },
                "sparse_vectors": {
                    "bm25": {
                        "modifier": "idf"
                    }
                },
                "optimizers_config": {
                    "default_segment_number": 2,
                    "indexing_threshold": 1000
                },
                "hnsw_config": {
                    "m": 16,
                    "ef_construct": 100,
                    "full_scan_threshold": 10000
                }
            }
            
            response = client.put(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
                json=collection_config
            )
            response.raise_for_status()
            logger.success("✅ Collezione creata con successo!")
            
            # 3. Creazione Indici Payload
            logger.info("📑 Creazione indici payload...")
            
            indices = [
                ("published_at", "datetime"),
                ("source_url", "keyword"),
                ("category", "keyword"),
                ("tier", "keyword")
            ]
            
            for field_name, field_type in indices:
                try:
                    payload_schema = {"type": field_type}
                    response = client.put(
                        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/index",
                        json={"field_name": field_name, "field_schema": payload_schema}
                    )
                    response.raise_for_status()
                    logger.info(f"   ✅ Indice '{field_name}' creato")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400:
                        logger.warning(f"   ⚠️ Indice '{field_name}' già esistente o errore: {e.response.text[:100]}")
                    else:
                        raise
            
            logger.success("✅ Indici creati!")
            logger.info("\n🎉 SETUP COMPLETATO: La collezione è pronta per l'ingestion.")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Errore HTTP: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"❌ Errore durante l'inizializzazione: {e}")
            raise

if __name__ == "__main__":
    init_collection()
