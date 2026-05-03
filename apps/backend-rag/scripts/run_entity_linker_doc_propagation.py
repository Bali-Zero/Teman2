"""Document-level entity propagation — GraphRAG 2.0 coverage boost.

Strategy: if other chunks of the same document (same document_id in Qdrant metadata)
are already linked to an entity, propagate that link to unlinked chunks of the
same document. No NER, no ML — pure structural inference.

Phase 1: Full Qdrant scan to build {document_id -> [point_ids]} map
Phase 2: For each document_id that has at least one linked point, find the
         dominant entity (most frequent among linked chunks) and link all
         unlinked chunks of that document to the same entity.

Usage:
    ENTITY_LINKER_DB_URL=... QDRANT_URL=... QDRANT_API_KEY=... \\
    PYTHONPATH=. python scripts/run_entity_linker_doc_propagation.py \\
        --collection legal_unified_hybrid_hybrid
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from qdrant_client import AsyncQdrantClient
except ImportError as exc:
    raise SystemExit(f"qdrant-client not installed: {exc}") from exc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entity_linker_doc_prop")


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"{name} env var is required")
    return val


DB_URL_DEFAULT = _require_env("ENTITY_LINKER_DB_URL")
QDRANT_URL_DEFAULT = _require_env("QDRANT_URL")
QDRANT_API_KEY_DEFAULT = _require_env("QDRANT_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


async def _maybe_notify(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
                      "parse_mode": "Markdown", "disable_notification": True},
            )
    except Exception as exc:
        logger.warning("Telegram notify failed: %s", exc)


async def _scan_qdrant(
    qdrant: AsyncQdrantClient,
    collection: str,
    batch_size: int,
) -> dict[str, list[str]]:
    """Scan full collection, return {document_id -> [point_ids]}."""
    doc_to_points: dict[str, list[str]] = defaultdict(list)
    offset: Any = None
    total = 0

    while True:
        results, next_offset = await qdrant.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not results:
            break

        for point in results:
            pid = str(point.id)
            meta = (point.payload or {}).get("metadata") or {}
            doc_id = meta.get("document_id") if isinstance(meta, dict) else None
            if doc_id and doc_id not in ("UNKNOWN", "", None):
                doc_to_points[doc_id].append(pid)

        total += len(results)
        if total % 10000 == 0:
            logger.info("Scanned %d points, %d doc_ids so far", total, len(doc_to_points))

        offset = next_offset
        if offset is None:
            break

    logger.info("Scan complete: %d total points, %d distinct document_ids", total, len(doc_to_points))
    return dict(doc_to_points)


async def _load_existing_links(
    pool: asyncpg.Pool,
    collection: str,
) -> dict[str, dict[str, int]]:
    """Return {point_id -> {entity_id -> count}} from existing mentions."""
    rows = await pool.fetch(
        "SELECT point_id, entity_id FROM kg_entity_mentions WHERE collection_name = $1",
        collection,
    )
    # point_id -> entity_id (first-wins — usually 1 entity per point for law chunks)
    point_to_entity: dict[str, str] = {}
    for row in rows:
        pid = row["point_id"]
        if pid not in point_to_entity:
            point_to_entity[pid] = row["entity_id"]
    return point_to_entity


async def propagate(
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    collection: str,
    batch_size: int,
    min_linked_chunks: int,
    dry_run: bool,
) -> dict[str, Any]:
    start = time.time()

    logger.info("Phase 1: scanning Qdrant for document_id groups...")
    doc_to_points = await _scan_qdrant(qdrant, collection, batch_size)

    logger.info("Phase 2: loading existing kg_entity_mentions...")
    point_to_entity = await _load_existing_links(pool, collection)
    already_linked = set(point_to_entity.keys())
    logger.info("Already linked: %d points", len(already_linked))

    # Phase 3: for each doc, find dominant entity among linked chunks
    docs_eligible = 0
    docs_skipped_no_links = 0
    docs_skipped_ambiguous = 0
    insert_rows: list[tuple[str, str, str, str, str, float, str]] = []

    for doc_id, point_ids in doc_to_points.items():
        linked_in_doc = [pid for pid in point_ids if pid in already_linked]
        if len(linked_in_doc) < min_linked_chunks:
            docs_skipped_no_links += 1
            continue

        # Count entity_id frequency among linked chunks
        entity_counts: dict[str, int] = defaultdict(int)
        for pid in linked_in_doc:
            entity_counts[point_to_entity[pid]] += 1

        # Dominant entity: must have >50% of linked chunks for this doc
        total_linked = len(linked_in_doc)
        dominant_entity = max(entity_counts, key=lambda e: entity_counts[e])
        dominant_count = entity_counts[dominant_entity]

        if dominant_count / total_linked < 0.5:
            docs_skipped_ambiguous += 1
            continue

        docs_eligible += 1
        unlinked_in_doc = [pid for pid in point_ids if pid not in already_linked]

        for pid in unlinked_in_doc:
            mention_id = hashlib.md5(
                f"{dominant_entity}:{collection}:{pid}:propagated".encode()
            ).hexdigest()
            insert_rows.append((
                mention_id, dominant_entity, collection, pid,
                f"[propagated from doc:{doc_id}]", 0.80, "doc_propagation",
            ))

    logger.info(
        "Docs eligible: %d | skipped (no links): %d | skipped (ambiguous): %d | rows to insert: %d",
        docs_eligible, docs_skipped_no_links, docs_skipped_ambiguous, len(insert_rows),
    )

    if dry_run:
        logger.info("DRY RUN — no inserts")
        return {
            "dry_run": True,
            "docs_eligible": docs_eligible,
            "rows_would_insert": len(insert_rows),
        }

    # Phase 4: batch insert
    CHUNK = 1000
    inserted_total = 0
    for i in range(0, len(insert_rows), CHUNK):
        batch = insert_rows[i:i + CHUNK]
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO kg_entity_mentions "
                "(mention_id, entity_id, collection_name, point_id, "
                "mention_text, confidence, match_type) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "ON CONFLICT (entity_id, collection_name, point_id) DO NOTHING",
                batch,
            )
        inserted_total += len(batch)
        if inserted_total % 5000 < CHUNK:
            logger.info("Inserted %d / %d rows", inserted_total, len(insert_rows))

    elapsed = time.time() - start
    new_coverage = (len(already_linked) + inserted_total) / 81251 * 100

    stats = {
        "collection": collection,
        "docs_eligible": docs_eligible,
        "docs_skipped_no_links": docs_skipped_no_links,
        "docs_skipped_ambiguous": docs_skipped_ambiguous,
        "mentions_created": inserted_total,
        "estimated_coverage_pct": round(new_coverage, 1),
        "elapsed_s": round(elapsed, 1),
    }
    logger.info("DONE %s", stats)
    await _maybe_notify(
        f"*Doc Propagation* DONE `{collection}`\n"
        f"eligible docs: {docs_eligible}\n"
        f"mentions created: {inserted_total}\n"
        f"estimated coverage: ~{new_coverage:.1f}%\n"
        f"elapsed: {elapsed:.0f}s"
    )
    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description="Document-level entity propagation")
    parser.add_argument("--collection", default="legal_unified_hybrid_hybrid")
    parser.add_argument("--batch-size", type=int, default=256,
                        help="Qdrant scroll batch size")
    parser.add_argument("--min-linked-chunks", type=int, default=1,
                        help="Min linked chunks in doc before propagating (default 1)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count eligible rows without inserting")
    parser.add_argument("--db-url", default=DB_URL_DEFAULT)
    parser.add_argument("--qdrant-url", default=QDRANT_URL_DEFAULT)
    parser.add_argument("--qdrant-api-key", default=QDRANT_API_KEY_DEFAULT)
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.db_url, min_size=1, max_size=4)
    qdrant = AsyncQdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key, timeout=60)
    try:
        stats = await propagate(
            pool=pool, qdrant=qdrant, collection=args.collection,
            batch_size=args.batch_size,
            min_linked_chunks=args.min_linked_chunks,
            dry_run=args.dry_run,
        )
    finally:
        await qdrant.close()
        await pool.close()

    print("\nFINAL_STATS:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
