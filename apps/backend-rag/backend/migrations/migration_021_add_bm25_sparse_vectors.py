"""
Migration 021: Add BM25 Sparse Vectors for Hybrid Search

This migration adds BM25 sparse vectors to the knowledge_base collection
to enable hybrid search (dense + sparse) with Reciprocal Rank Fusion (RRF).

Strategy:
1. Create new collection with sparse vector support (knowledge_base_hybrid)
2. Copy all documents from old collection, generating sparse vectors
3. Rename collections (old -> _backup, new -> original name)

This approach minimizes downtime and provides rollback capability.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Migration configuration
SOURCE_COLLECTION = "knowledge_base"
TARGET_COLLECTION = "knowledge_base_hybrid"
BACKUP_COLLECTION = "knowledge_base_backup"
BATCH_SIZE = 100
VECTOR_SIZE = 1536


async def run_migration():
    """Execute the BM25 sparse vector migration."""
    from core.bm25_vectorizer import BM25Vectorizer
    from core.qdrant_db import QdrantClient

    logger.info("=" * 70)
    logger.info("MIGRATION 021: Add BM25 Sparse Vectors for Hybrid Search")
    logger.info("=" * 70)

    # Initialize clients
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    source_client = QdrantClient(
        qdrant_url=qdrant_url,
        collection_name=SOURCE_COLLECTION,
        api_key=qdrant_api_key,
    )

    target_client = QdrantClient(
        qdrant_url=qdrant_url,
        collection_name=TARGET_COLLECTION,
        api_key=qdrant_api_key,
    )

    bm25 = BM25Vectorizer()

    try:
        # Step 1: Get source collection stats
        logger.info(f"\n📊 Step 1: Checking source collection '{SOURCE_COLLECTION}'...")
        stats = await source_client.get_collection_stats()
        total_docs = stats.get("total_documents", 0)

        if total_docs == 0:
            logger.warning(f"Source collection is empty. Nothing to migrate.")
            return

        logger.info(f"Found {total_docs} documents to migrate")

        # Step 2: Create target collection with sparse vector support
        logger.info(f"\n🔧 Step 2: Creating target collection '{TARGET_COLLECTION}'...")
        created = await target_client.create_collection(
            vector_size=VECTOR_SIZE,
            distance="Cosine",
            enable_sparse=True,
        )

        if not created:
            logger.error("Failed to create target collection")
            return

        logger.info(f"✅ Created collection with sparse vector support")

        # Step 3: Migrate documents in batches
        logger.info(f"\n📦 Step 3: Migrating documents with BM25 sparse vectors...")
        start_time = time.time()
        total_migrated = 0
        offset = None

        while True:
            # Scroll through source collection
            http_client = await source_client._get_client()
            scroll_url = f"/collections/{SOURCE_COLLECTION}/points/scroll"
            scroll_payload = {
                "limit": BATCH_SIZE,
                "with_payload": True,
                "with_vectors": True,
            }
            if offset:
                scroll_payload["offset"] = offset

            response = await http_client.post(scroll_url, json=scroll_payload)
            response.raise_for_status()
            data = response.json().get("result", {})
            points = data.get("points", [])
            next_offset = data.get("next_page_offset")

            if not points:
                break

            # Process batch
            chunks = []
            embeddings = []
            sparse_vectors = []
            metadatas = []
            ids = []

            for point in points:
                point_id = str(point["id"])
                vector = point.get("vector", [])
                payload = point.get("payload", {})
                text = payload.get("text", "")
                metadata = payload.get("metadata", {})

                if not text or not vector:
                    continue

                # Generate BM25 sparse vector
                sparse_vec = bm25.generate_sparse_vector(text)

                chunks.append(text)
                embeddings.append(vector)
                sparse_vectors.append(sparse_vec)
                metadatas.append(metadata)
                ids.append(point_id)

            # Upsert to target collection
            if chunks:
                result = await target_client.upsert_documents_with_sparse(
                    chunks=chunks,
                    embeddings=embeddings,
                    sparse_vectors=sparse_vectors,
                    metadatas=metadatas,
                    ids=ids,
                    batch_size=BATCH_SIZE,
                )

                if result.get("success"):
                    total_migrated += len(chunks)
                    elapsed = time.time() - start_time
                    rate = total_migrated / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  Migrated {total_migrated}/{total_docs} documents "
                        f"({total_migrated/total_docs*100:.1f}%) - {rate:.1f} docs/sec"
                    )
                else:
                    logger.error(f"  Batch upsert failed: {result.get('error')}")

            if not next_offset:
                break
            offset = next_offset

        elapsed = time.time() - start_time
        logger.info(f"\n✅ Migration completed: {total_migrated} documents in {elapsed:.1f}s")

        # Step 4: Verify target collection
        logger.info(f"\n🔍 Step 4: Verifying target collection...")
        target_stats = await target_client.get_collection_stats()
        target_docs = target_stats.get("total_documents", 0)

        if target_docs == total_migrated:
            logger.info(f"✅ Target collection verified: {target_docs} documents")
        else:
            logger.warning(
                f"⚠️ Document count mismatch: expected {total_migrated}, got {target_docs}"
            )

        # Step 5: Instructions for swapping collections
        logger.info(f"\n📝 Step 5: Next Steps")
        logger.info("=" * 70)
        logger.info("To complete the migration, run the following commands:")
        logger.info("")
        logger.info("1. Verify hybrid search works on the new collection:")
        logger.info(f"   python -c \"import asyncio; from test_hybrid_search import test; asyncio.run(test())\"")
        logger.info("")
        logger.info("2. Swap collections (optional):")
        logger.info(f"   # Rename old collection to backup")
        logger.info(f"   curl -X POST '{qdrant_url}/collections/{SOURCE_COLLECTION}/aliases' \\")
        logger.info(f"        -H 'api-key: $QDRANT_API_KEY' -H 'Content-Type: application/json' \\")
        logger.info(f"        -d '{{\"actions\": [{{\"rename_collection\": {{\"old_name\": \"{SOURCE_COLLECTION}\", \"new_name\": \"{BACKUP_COLLECTION}\"}}}}]}}'")
        logger.info("")
        logger.info(f"   # Rename new collection to original name")
        logger.info(f"   curl -X POST '{qdrant_url}/collections/{TARGET_COLLECTION}/aliases' \\")
        logger.info(f"        -H 'api-key: $QDRANT_API_KEY' -H 'Content-Type: application/json' \\")
        logger.info(f"        -d '{{\"actions\": [{{\"rename_collection\": {{\"old_name\": \"{TARGET_COLLECTION}\", \"new_name\": \"{SOURCE_COLLECTION}\"}}}}]}}'")
        logger.info("")
        logger.info("3. Or use the new collection directly:")
        logger.info(f"   Set QDRANT_COLLECTION_NAME={TARGET_COLLECTION} in your environment")
        logger.info("=" * 70)

    finally:
        await source_client.close()
        await target_client.close()


async def test_hybrid_search():
    """Test hybrid search on the migrated collection."""
    from core.bm25_vectorizer import BM25Vectorizer
    from core.embeddings import create_embeddings_generator
    from core.qdrant_db import QdrantClient

    logger.info("\n🧪 Testing hybrid search...")

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    client = QdrantClient(
        qdrant_url=qdrant_url,
        collection_name=TARGET_COLLECTION,
        api_key=qdrant_api_key,
    )

    embedder = create_embeddings_generator()
    bm25 = BM25Vectorizer()

    try:
        test_queries = [
            "Apa persyaratan izin usaha restoran?",
            "KBLI untuk software house",
            "Definisi UMKM menurut PP 7 2021",
        ]

        for query in test_queries:
            logger.info(f"\n📝 Query: {query}")

            # Generate vectors
            dense_vec = embedder.generate_single_embedding(query)
            sparse_vec = bm25.generate_query_sparse_vector(query)

            # Hybrid search
            start = time.time()
            results = await client.hybrid_search(
                query_embedding=dense_vec,
                query_sparse=sparse_vec,
                limit=3,
            )
            elapsed = time.time() - start

            logger.info(f"   Time: {elapsed*1000:.0f}ms | Results: {results['total_found']}")
            for i, (doc_id, score) in enumerate(
                zip(results.get("ids", [])[:3], results.get("scores", [])[:3]), 1
            ):
                logger.info(f"   {i}. [{score:.3f}] {doc_id[:50]}")

    finally:
        await client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BM25 Sparse Vector Migration")
    parser.add_argument("--test", action="store_true", help="Test hybrid search only")
    args = parser.parse_args()

    if args.test:
        asyncio.run(test_hybrid_search())
    else:
        asyncio.run(run_migration())
