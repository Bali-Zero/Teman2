#!/usr/bin/env python3
"""
LOAD INTEL SOURCES TO QDRANT
=============================
Carica le 520+ fonti autoritarie da unified_sources.json in Qdrant
per retrieval durante operazioni di intelligence.

Collection: intel_authoritative_sources
Vector Model: text-embedding-3-small (1536 dim)
Total Sources: ~520 (deduplicated)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from loguru import logger
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI
from tqdm import tqdm
from datetime import datetime

# Configurazione
COLLECTION_NAME = "intel_authoritative_sources"
VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Percorso al file sorgenti
SOURCES_FILE = Path(__file__).parent.parent / "config" / "unified_sources.json"


async def create_collection(client: QdrantClient):
    """Crea la collezione se non esiste."""
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if exists:
        logger.info(f"⚠️ Collezione '{COLLECTION_NAME}' già esistente - cancello e ricreo")
        client.delete_collection(COLLECTION_NAME)
        exists = False
    
    logger.info(f"🛠️ Creazione collezione '{COLLECTION_NAME}'...")
    
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "default": models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            )
        },
        # Ottimizzazione per performance
        optimizers_config=models.OptimizersConfigDiff(
            default_segment_number=2,
            indexing_threshold=500,
        ),
        hnsw_config=models.HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10000,
        ),
    )
    
    # Indici payload
    logger.info("📑 Creazione indici payload...")
    
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="category_key",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="tier",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="authority",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="url",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    
    logger.success("✅ Collezione creata!")
    return True


async def generate_embedding(text: str, openai_client: AsyncOpenAI) -> list[float]:
    """Genera embedding OpenAI."""
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=VECTOR_SIZE
    )
    return response.data[0].embedding


async def load_sources():
    """Carica tutte le fonti in Qdrant."""
    logger.info("=" * 60)
    logger.info(f"📊 LOADING INTEL SOURCES TO QDRANT")
    logger.info(f"   Collection: {COLLECTION_NAME}")
    logger.info(f"   URL: {QDRANT_URL}")
    logger.info("=" * 60)
    
    # 1. Carica JSON
    if not SOURCES_FILE.exists():
        logger.error(f"❌ File non trovato: {SOURCES_FILE}")
        return
    
    with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_sources = data.get('total_sources', 0)
    logger.info(f"📚 Fonti da caricare: {total_sources}")
    logger.info(f"📂 Categorie: {data.get('total_categories', 0)}")
    print()
    
    # 2. Connessione Qdrant
    qdrant_client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=30,
        prefer_grpc=False,
    )
    
    # 3. Crea collezione
    await create_collection(qdrant_client)
    print()
    
    # 4. Connessione OpenAI
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # 5. Prepara dati per upload
    logger.info("🔄 Generazione embeddings...")
    points = []
    point_id = 0
    
    for category_key, category_data in tqdm(data['categories'].items(), desc="Categorie"):
        category_name = category_data.get('name', category_key)
        
        for source in tqdm(category_data.get('sources', []), desc=f"  {category_name}", leave=False):
            # Testo per embedding
            text_for_embedding = f"""
Source: {source.get('name', 'Unknown')}
Category: {category_name}
Description: {source.get('description', '')}
Authority: {source.get('authority', '')}
URL: {source.get('url', '')}
            """.strip()
            
            # Genera embedding
            try:
                embedding = await generate_embedding(text_for_embedding, openai_client)
            except Exception as e:
                logger.warning(f"⚠️ Errore embedding per {source.get('name')}: {e}")
                continue
            
            # Payload
            payload = {
                "name": source.get('name'),
                "url": source.get('url', ''),
                "tier": source.get('tier', 'T2'),
                "authority": source.get('authority', ''),
                "description": source.get('description', ''),
                "category_key": category_key,
                "category_name": category_name,
                "category_type": category_data.get('type', ''),
                "category_priority": category_data.get('priority', ''),
                "indexed_at": datetime.now().isoformat(),
            }
            
            point = models.PointStruct(
                id=point_id,
                vector={"default": embedding},
                payload=payload
            )
            
            points.append(point)
            point_id += 1
    
    # 6. Upload batch
    logger.info(f"⬆️ Upload {len(points)} punti a Qdrant...")
    
    BATCH_SIZE = 100
    for i in tqdm(range(0, len(points), BATCH_SIZE), desc="Upload batches"):
        batch = points[i:i+BATCH_SIZE]
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch,
            wait=True
        )
    
    logger.success("✅ Upload completato!")
    
    # 7. Verifica
    collection_info = qdrant_client.get_collection(COLLECTION_NAME)
    logger.info(f"📊 Punti nella collezione: {collection_info.points_count}")
    
    # 8. Test retrieval
    logger.info("🔍 Test retrieval...")
    test_query = "Immigration visa regulations Indonesia"
    test_embedding = await generate_embedding(test_query, openai_client)
    
    search_result = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=test_embedding,
        using="default",
        limit=5
    )
    
    logger.info(f"   Query: '{test_query}'")
    logger.info(f"   Top {len(search_result.points)} risultati:")
    for i, point in enumerate(search_result.points, 1):
        logger.info(f"      {i}. {point.payload['name']} (score: {point.score:.3f})")
    
    logger.success("🎉 Caricamento completato con successo!")


if __name__ == "__main__":
    asyncio.run(load_sources())
