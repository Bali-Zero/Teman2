"""
Migration 031: Migrate Legacy Collections to Hybrid Format

This migration converts old-format collections (unnamed vectors) to hybrid format
(named dense vectors + BM25 sparse vectors) for improved search quality.

Collections to migrate:
- tax_genius (332 docs)
- bali_zero_pricing (65 docs)
- training_conversations (2898 docs)

Strategy:
1. Read all documents from old collection
2. Create new collection with hybrid schema
3. Generate BM25 sparse vectors for each document
4. Upsert with named vectors (dense + bm25)
5. Rename collections (old -> _legacy, new -> original)
"""

import asyncio
import logging
import os
import sys
import time

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
COLLECTIONS_TO_MIGRATE = [
    "tax_genius",
    "bali_zero_pricing",
    "training_conversations",
]
BATCH_SIZE = 200
VECTOR_SIZE = 1536


async def migrate_collection(
    collection_name: str,
    skip_if_hybrid: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Migrate a single collection to hybrid format.

    Args:
        collection_name: Name of the collection to migrate
        skip_if_hybrid: Skip if collection already has hybrid format
        dry_run: Only check, don't actually migrate

    Returns:
        Migration result dict
    """
    from core.bm25_vectorizer import BM25Vectorizer
    from core.qdrant_db import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    target_collection = f"{collection_name}_hybrid"
    legacy_collection = f"{collection_name}_legacy"

    logger.info(f"\n{'=' * 70}")
    logger.info(f"Migrating: {collection_name}")
    logger.info(f"{'=' * 70}")

    source_client = QdrantClient(
        qdrant_url=qdrant_url,
        collection_name=collection_name,
        api_key=qdrant_api_key,
    )

    result = {
        "collection": collection_name,
        "status": "pending",
        "documents_migrated": 0,
        "error": None,
    }

    try:
        # Step 1: Check source collection
        logger.info("Step 1: Checking source collection...")
        http_client = await source_client._get_client()

        # Get collection info
        info_response = await http_client.get(f"/collections/{collection_name}")
        if info_response.status_code != 200:
            result["status"] = "error"
            result["error"] = f"Collection not found: {collection_name}"
            return result

        info = info_response.json()["result"]
        vectors_config = info["config"]["params"].get("vectors", {})
        sparse_config = info["config"]["params"].get("sparse_vectors", {})
        total_docs = info["points_count"]

        # Check if already hybrid
        is_named = "dense" in vectors_config if isinstance(vectors_config, dict) else False
        has_sparse = bool(sparse_config)

        if is_named and has_sparse:
            logger.info("  Collection already has hybrid format, skipping")
            result["status"] = "skipped"
            result["documents_migrated"] = total_docs
            return result

        logger.info(f"  Found {total_docs} documents (named={is_named}, sparse={has_sparse})")

        if total_docs == 0:
            logger.warning("  Collection is empty, nothing to migrate")
            result["status"] = "skipped"
            return result

        if dry_run:
            logger.info(f"  [DRY RUN] Would migrate {total_docs} documents")
            result["status"] = "dry_run"
            result["documents_migrated"] = total_docs
            return result

        # Step 2: Create target collection with hybrid schema
        logger.info(f"Step 2: Creating hybrid collection '{target_collection}'...")

        target_client = QdrantClient(
            qdrant_url=qdrant_url,
            collection_name=target_collection,
            api_key=qdrant_api_key,
        )

        # Delete existing target if exists
        check_response = await http_client.get(f"/collections/{target_collection}")
        if check_response.status_code == 200:
            logger.info("  Deleting existing target collection...")
            await http_client.delete(f"/collections/{target_collection}")

        # Create with hybrid schema
        created = await target_client.create_collection(
            vector_size=VECTOR_SIZE,
            distance="Cosine",
            enable_sparse=True,
        )

        if not created:
            result["status"] = "error"
            result["error"] = "Failed to create target collection"
            return result

        logger.info("  Created hybrid collection")

        # Step 3: Migrate documents
        logger.info("Step 3: Migrating documents with BM25 sparse vectors...")

        bm25 = BM25Vectorizer()
        start_time = time.time()
        total_migrated = 0
        offset = None

        while True:
            # Scroll through source
            scroll_payload = {
                "limit": BATCH_SIZE,
                "with_payload": True,
                "with_vectors": True,
            }
            if offset:
                scroll_payload["offset"] = offset

            response = await http_client.post(
                f"/collections/{collection_name}/points/scroll", json=scroll_payload
            )
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

                # Handle different payload structures
                text = payload.get("text", "") or payload.get("content", "")
                metadata = payload.get("metadata", {})

                # If metadata is empty, use the whole payload minus text fields
                if not metadata:
                    metadata = {
                        k: v for k, v in payload.items() if k not in ["text", "content", "vector"]
                    }

                if not text or not vector:
                    continue

                # Generate BM25 sparse vector
                sparse_vec = bm25.generate_sparse_vector(text)

                chunks.append(text)
                embeddings.append(vector)
                sparse_vectors.append(sparse_vec)
                metadatas.append(metadata)
                ids.append(point_id)

            # Upsert to target
            if chunks:
                upsert_result = await target_client.upsert_documents_with_sparse(
                    chunks=chunks,
                    embeddings=embeddings,
                    sparse_vectors=sparse_vectors,
                    metadatas=metadatas,
                    ids=ids,
                    batch_size=BATCH_SIZE,
                )

                if upsert_result.get("success"):
                    total_migrated += len(chunks)
                    elapsed = time.time() - start_time
                    rate = total_migrated / elapsed if elapsed > 0 else 0
                    pct = total_migrated / total_docs * 100
                    logger.info(
                        f"  Migrated {total_migrated}/{total_docs} ({pct:.1f}%) - {rate:.1f} docs/sec"
                    )
                else:
                    logger.error(f"  Batch failed: {upsert_result.get('error')}")

            if not next_offset:
                break
            offset = next_offset

        elapsed = time.time() - start_time
        logger.info(f"  Migration completed: {total_migrated} docs in {elapsed:.1f}s")

        # Step 4: Verify
        logger.info("Step 4: Verifying migration...")
        target_info = await http_client.get(f"/collections/{target_collection}")
        target_count = target_info.json()["result"]["points_count"]

        if target_count >= total_migrated * 0.95:  # Allow 5% tolerance
            logger.info(f"  Verified: {target_count} documents in target")
        else:
            logger.warning(f"  Document mismatch: expected {total_migrated}, got {target_count}")

        # Step 5: Swap collections
        logger.info("Step 5: Swapping collections...")

        # Rename original to _legacy
        rename_payload = {
            "actions": [
                {"rename_collection": {"old_name": collection_name, "new_name": legacy_collection}}
            ]
        }
        rename_response = await http_client.post("/collections/aliases", json=rename_payload)

        if rename_response.status_code == 200:
            logger.info(f"  Renamed {collection_name} -> {legacy_collection}")
        else:
            logger.error(f"  Failed to rename original: {rename_response.text}")
            result["status"] = "partial"
            result["documents_migrated"] = total_migrated
            result["error"] = "Failed to rename original collection"
            return result

        # Rename hybrid to original name
        rename_payload = {
            "actions": [
                {"rename_collection": {"old_name": target_collection, "new_name": collection_name}}
            ]
        }
        rename_response = await http_client.post("/collections/aliases", json=rename_payload)

        if rename_response.status_code == 200:
            logger.info(f"  Renamed {target_collection} -> {collection_name}")
        else:
            logger.error(f"  Failed to rename hybrid: {rename_response.text}")
            result["status"] = "partial"
            result["documents_migrated"] = total_migrated
            result["error"] = "Failed to rename hybrid collection"
            return result

        result["status"] = "success"
        result["documents_migrated"] = total_migrated
        logger.info("  Migration complete!")

        await target_client.close()

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)
    finally:
        await source_client.close()

    return result


async def migrate_all(dry_run: bool = False):
    """Migrate all legacy collections."""
    logger.info("=" * 70)
    logger.info("MIGRATION 031: Convert Legacy Collections to Hybrid Format")
    logger.info("=" * 70)

    results = []

    for collection in COLLECTIONS_TO_MIGRATE:
        result = await migrate_collection(collection, dry_run=dry_run)
        results.append(result)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 70)

    for r in results:
        status_emoji = {
            "success": "",
            "skipped": "",
            "dry_run": "",
            "partial": "",
            "error": "",
        }.get(r["status"], "")

        logger.info(
            f"{status_emoji} {r['collection']}: {r['status']} ({r['documents_migrated']} docs)"
        )
        if r.get("error"):
            logger.info(f"   Error: {r['error']}")

    return results


async def verify_collections():
    """Verify all collections have hybrid format."""
    from core.qdrant_db import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    logger.info("\nVerifying collections...")

    client = QdrantClient(
        qdrant_url=qdrant_url,
        collection_name="test",
        api_key=qdrant_api_key,
    )

    try:
        http_client = await client._get_client()

        collections = COLLECTIONS_TO_MIGRATE + [
            "visa_oracle",
            "kbli_unified",
            "legal_unified_hybrid",
        ]

        for name in collections:
            response = await http_client.get(f"/collections/{name}")
            if response.status_code != 200:
                logger.info(f"  {name}: NOT FOUND")
                continue

            info = response.json()["result"]
            vectors = info["config"]["params"].get("vectors", {})
            sparse = info["config"]["params"].get("sparse_vectors", {})
            points = info["points_count"]

            is_named = "dense" in vectors if isinstance(vectors, dict) else False
            has_sparse = bool(sparse)

            if is_named and has_sparse:
                logger.info(f"  {name}: {points} docs (hybrid)")
            else:
                logger.info(f"  {name}: {points} docs (LEGACY - needs migration)")

    finally:
        await client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hybrid Collections Migration")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't migrate")
    parser.add_argument("--verify", action="store_true", help="Verify collection formats")
    parser.add_argument("--collection", type=str, help="Migrate specific collection only")
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_collections())
    elif args.collection:
        asyncio.run(migrate_collection(args.collection, dry_run=args.dry_run))
    else:
        asyncio.run(migrate_all(dry_run=args.dry_run))
