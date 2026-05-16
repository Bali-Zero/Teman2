#!/usr/bin/env python3
"""
STREAMING INTEL SOURCES UPLOAD
================================
Versione streaming per evitare timeout: genera embedding + upload immediato.
Batch size ridotto a 10, timeout aumentato a 120s.
"""

import asyncio
import json
import os
from pathlib import Path
from loguru import logger
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI
from datetime import datetime
import time

# Configurazione
COLLECTION_NAME = "intel_authoritative_sources"
VECTOR_SIZE = 1536
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SOURCES_FILE = Path(__file__).parent.parent / "config" / "unified_sources.json"

# Parametri aggressivi per stabilità
BATCH_SIZE = 10  # Ridotto da 100
TIMEOUT = 120    # Aumentato da 30
MAX_RETRIES = 3


async def create_collection(client: QdrantClient):
    """Crea collezione."""
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if exists:
        logger.warning(f"⚠️ Cancello collezione esistente")
        client.delete_collection(COLLECTION_NAME)

    logger.info(f"🛠️ Creazione collezione...")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "default": models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            )
        },
        optimizers_config=models.OptimizersConfigDiff(
            default_segment_number=2,
            indexing_threshold=500,
        ),
        hnsw_config=models.HnswConfigDiff(
            m=16,
            ef_construct=100,
        ),
    )

    # Indici
    client.create_payload_index(COLLECTION_NAME, "category_key", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "tier", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "url", models.PayloadSchemaType.KEYWORD)

    logger.success("✅ Collezione creata!")


async def generate_embedding(text: str, openai_client: AsyncOpenAI) -> list[float]:
    """Genera embedding."""
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=VECTOR_SIZE
    )
    return response.data[0].embedding


async def upload_batch_with_retry(client: QdrantClient, points: list, attempt: int = 1):
    """Upload batch con retry."""
    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )
        return True
    except Exception as e:
        if attempt < MAX_RETRIES:
            logger.warning(f"⚠️ Retry {attempt}/{MAX_RETRIES} dopo errore: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            return await upload_batch_with_retry(client, points, attempt + 1)
        else:
            logger.error(f"❌ Fallito dopo {MAX_RETRIES} tentativi: {e}")
            return False


async def load_sources_streaming():
    """Carica fonti in modalità streaming."""
    logger.info("=" * 60)
    logger.info(f"📊 STREAMING UPLOAD TO QDRANT")
    logger.info(f"   Batch size: {BATCH_SIZE}")
    logger.info(f"   Timeout: {TIMEOUT}s")
    logger.info("=" * 60)

    # Carica JSON
    with open(SOURCES_FILE, encoding='utf-8') as f:
        data = json.load(f)

    total_sources = data.get('total_sources', 0)
    logger.info(f"📚 Fonti: {total_sources}")
    logger.info(f"📂 Categorie: {data.get('total_categories', 0)}")
    print()

    # Client Qdrant con timeout aumentato
    qdrant_client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=TIMEOUT,
        prefer_grpc=False,
    )

    # Crea collezione
    await create_collection(qdrant_client)
    print()

    # Client OpenAI
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Streaming upload
    logger.info("🔄 Inizio upload streaming...")

    point_id = 0
    batch = []
    uploaded = 0
    failed = 0
    start_time = time.time()

    for category_key, category_data in data['categories'].items():
        category_name = category_data.get('name', category_key)
        sources = category_data.get('sources', [])

        logger.info(f"📁 {category_name}: {len(sources)} fonti")

        for source in sources:
            # Genera embedding
            try:
                text_for_embedding = f"""
Source: {source.get('name', 'Unknown')}
Category: {category_name}
Description: {source.get('description', '')}
Authority: {source.get('authority', '')}
URL: {source.get('url', '')}
                """.strip()

                embedding = await generate_embedding(text_for_embedding, openai_client)

                # Payload
                payload = {
                    "name": source.get('name'),
                    "url": source.get('url', ''),
                    "tier": source.get('tier', 'T2'),
                    "authority": source.get('authority', ''),
                    "description": source.get('description', ''),
                    "category_key": category_key,
                    "category_name": category_name,
                    "indexed_at": datetime.now().isoformat(),
                }

                # Aggiungi al batch
                point = models.PointStruct(
                    id=point_id,
                    vector={"default": embedding},
                    payload=payload
                )
                batch.append(point)
                point_id += 1

                # Upload batch quando raggiunge dimensione target
                if len(batch) >= BATCH_SIZE:
                    success = await upload_batch_with_retry(qdrant_client, batch)
                    if success:
                        uploaded += len(batch)
                        elapsed = time.time() - start_time
                        rate = uploaded / elapsed if elapsed > 0 else 0
                        logger.info(f"   ✓ {uploaded}/{total_sources} ({rate:.1f}/s)")
                    else:
                        failed += len(batch)
                        logger.error(f"   ✗ Batch fallito ({failed} totali)")

                    batch = []

            except Exception as e:
                logger.warning(f"⚠️ Errore per {source.get('name')}: {e}")
                failed += 1
                continue

    # Upload batch rimanente
    if batch:
        success = await upload_batch_with_retry(qdrant_client, batch)
        if success:
            uploaded += len(batch)
        else:
            failed += len(batch)

    # Report finale
    elapsed = time.time() - start_time
    logger.success("=" * 60)
    logger.success(f"✅ UPLOAD COMPLETATO!")
    logger.success(f"   Caricati: {uploaded}/{total_sources}")
    logger.success(f"   Falliti: {failed}")
    logger.success(f"   Tempo: {elapsed:.1f}s ({uploaded/elapsed:.1f}/s)")
    logger.success("=" * 60)

    # Verifica
    info = qdrant_client.get_collection(COLLECTION_NAME)
    logger.info(f"📊 Punti in collezione: {info.points_count}")

    # Test retrieval
    if info.points_count > 0:
        logger.info("🔍 Test query...")
        test_embedding = await generate_embedding("Immigration visa Indonesia", openai_client)

        result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=test_embedding,
            using="default",
            limit=3
        )

        for i, point in enumerate(result.points, 1):
            logger.info(f"   {i}. {point.payload['name']} ({point.score:.3f})")

    logger.success("🎉 COMPLETATO CON SUCCESSO!")


if __name__ == "__main__":
    asyncio.run(load_sources_streaming())
