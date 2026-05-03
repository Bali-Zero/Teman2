#!/usr/bin/env python3
"""
garuda-bootstrap — One-time setup: create Qdrant collection + payload indexes
Usage: garuda-bootstrap [--force-recreate]
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path


def load_env() -> None:
    """Load environment variables from apps/backend-rag/.env if not already set."""
    candidates = [
        Path(__file__).parents[2] / ".env",
        Path(__file__).parents[3] / "backend-rag" / ".env",
        Path.home() / "Desktop" / "nuzantara" / "apps" / "backend-rag" / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = value.strip()
            break


async def async_main(force_recreate: bool) -> int:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        VectorParams,
        Distance,
        HnswConfigDiff,
        OptimizersConfigDiff,
        PayloadSchemaType,
    )

    logger = logging.getLogger("garuda-bootstrap")

    client = AsyncQdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=30.0,
    )

    COLLECTION = "garuda_assets"

    try:
        collections = await client.get_collections()
        existing = [c.name for c in collections.collections]

        if COLLECTION in existing:
            if force_recreate:
                logger.warning("Force-recreating collection %s", COLLECTION)
                await client.delete_collection(COLLECTION)
            else:
                logger.info(
                    "Collection %s already exists — skipping (use --force-recreate to reset)",
                    COLLECTION,
                )
                await client.close()
                return 0

        # Create collection per spec
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=100,
                full_scan_threshold=30000,
            ),
            optimizers_config=OptimizersConfigDiff(
                default_segment_number=0,
                indexing_threshold=30000,
            ),
        )
        logger.info("Created collection %s (1536-dim cosine)", COLLECTION)

        # Payload indexes per spec
        payload_indexes = [
            ("category", PayloadSchemaType.KEYWORD),
            ("mime", PayloadSchemaType.KEYWORD),
            ("parent_folder", PayloadSchemaType.KEYWORD),
            ("archived", PayloadSchemaType.BOOL),
            ("quarantined", PayloadSchemaType.BOOL),
            ("modified_at", PayloadSchemaType.DATETIME),
        ]

        for field_name, schema_type in payload_indexes:
            await client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info("Created payload index: %s (%s)", field_name, schema_type)

        logger.info("Bootstrap complete — garuda_assets collection ready")
        return 0

    finally:
        await client.close()


def main() -> None:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap GARUDA Qdrant collection")
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Delete and recreate collection if it exists",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(async_main(args.force_recreate)))


if __name__ == "__main__":
    main()
