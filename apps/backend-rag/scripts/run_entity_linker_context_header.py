"""Context-Header Entity Linker — GraphRAG 2.0 coverage boost.

Strategy: for points with [CONTEXT: PP - NO X - TAHUN Y] or [CONTEXT: UU - NO X - TAHUN Y]
in their text, extract the law reference directly from the context header and link it
to the corresponding kg_node. This avoids NER and fuzzy match for the ~43% of unprocessed
points that have explicit law references in the CONTEXT prefix.

Usage:
    ENTITY_LINKER_DB_URL=... QDRANT_URL=... QDRANT_API_KEY=... \\
    PYTHONPATH=. python scripts/run_entity_linker_context_header.py \\
        --collection legal_unified_hybrid_hybrid --batch-size 128
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import re
import sys
import time
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
logger = logging.getLogger("entity_linker_ctx")


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

PROGRESS_STEP = int(os.environ.get("ENTITY_LINKER_PROGRESS_STEP", "2000"))
TELEGRAM_STEP = int(os.environ.get("ENTITY_LINKER_TELEGRAM_STEP", "10000"))

# Extract law reference from CONTEXT header
# Matches: [CONTEXT: PP - NO 6624 - TAHUN 2021 ...] or [CONTEXT: UU - NO 6 - TAHUN 2023 ...]
_CTX_HEADER_RE = re.compile(
    r"\[CONTEXT:\s*(UU|PP|Perpres|Permen\w*)\s*-\s*NO\s+(\d+)\s*-\s*TAHUN\s+(\d{4})",
    re.IGNORECASE,
)
# Also extract from metadata book_title field
_BOOK_UU_PP_RE = re.compile(
    r"(UU|PP|Perpres|Permen\w*)\s*(?:No\.?\s*|NO\s+)?(\d+)\s*(?:Tahun\s*|TAHUN\s*|/\s*)(\d{4})",
    re.IGNORECASE,
)


def _ctx_header_mention(text: str) -> dict[str, str] | None:
    """Extract law reference from CONTEXT header if present and not UNKNOWN."""
    m = _CTX_HEADER_RE.search(text)
    if not m:
        return None
    law, num, year = m.group(1).upper(), m.group(2), m.group(3)
    # UNKNOWN nums/years skip
    if num.upper() == "UNKNOWN" or year.upper() == "UNKNOWN":
        return None
    mention_text = f"{law} - NO {num} - TAHUN {year}"
    return {"type": "ctx_law", "text": mention_text, "law": law, "num": num, "year": year}


def _book_title_mention(book_title: str) -> dict[str, str] | None:
    """Extract law reference from book_title metadata field."""
    if not book_title:
        return None
    m = _BOOK_UU_PP_RE.search(book_title)
    if not m:
        return None
    law, num, year = m.group(1).upper(), m.group(2), m.group(3)
    if num.upper() == "UNKNOWN" or year.upper() == "UNKNOWN":
        return None
    mention_text = f"{law} - NO {num} - TAHUN {year}"
    return {"type": "book_title_law", "text": mention_text, "law": law, "num": num, "year": year}


def _lookup_variants(law: str, num: str, year: str) -> list[str]:
    """Generate name_index lookup keys for a law reference."""
    variants = [
        f"{law} {num}/{year}",
        f"{law} No. {num} Tahun {year}",
        f"{law} NO. {num} TAHUN {year}",
        f"{law} No {num} Tahun {year}",
        f"{law} {num} Tahun {year}",
        f"{law} {num} {year}",
        f"{law} Nomor {num} Tahun {year}",
        f"{law} NOMOR {num} TAHUN {year}",
    ]
    return [v.lower() for v in variants]


async def _maybe_notify(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_notification": True},
            )
    except Exception as exc:
        logger.warning("Telegram notify failed: %s", exc)


async def _load_name_index(pool: asyncpg.Pool) -> dict[str, tuple[str, str]]:
    rows = await pool.fetch(
        "SELECT entity_id, name, entity_type FROM kg_nodes WHERE entity_type IN "
        "('undang_undang','peraturan_pemerintah','perpres','permen','regulation','perda')"
    )
    idx: dict[str, tuple[str, str]] = {}
    for row in rows:
        key = (row["name"] or "").strip().lower()
        if key and key not in idx:
            idx[key] = (row["entity_id"], row["entity_type"])
    logger.info("Loaded %d law-type kg_nodes into name index", len(idx))
    return idx


async def _load_processed_points(pool: asyncpg.Pool, collection: str) -> set[str]:
    rows = await pool.fetch(
        "SELECT DISTINCT point_id FROM kg_entity_mentions WHERE collection_name = $1",
        collection,
    )
    return {r["point_id"] for r in rows}


async def process_collection(
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    collection: str,
    batch_size: int,
    limit: int | None,
) -> dict[str, Any]:
    start = time.time()

    name_index = await _load_name_index(pool)
    processed = await _load_processed_points(pool, collection)
    logger.info("Resume: %d points already linked for %s", len(processed), collection)

    await _maybe_notify(
        f"*CTX Header Linker* start\n"
        f"collection: `{collection}`\n"
        f"resume: {len(processed)} already linked\n"
        f"name index: {len(name_index)} law nodes"
    )

    points_processed = 0
    points_skipped = 0
    points_ctx_found = 0
    mentions_created = 0
    ctx_hits = 0
    ctx_misses = 0
    last_telegram_at = 0
    offset: Any = None

    while True:
        try:
            results, next_offset = await qdrant.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.error("Qdrant scroll failed at offset=%s: %s", offset, exc)
            raise

        if not results:
            break

        insert_rows: list[tuple[str, str, str, str, str, float, str]] = []

        for point in results:
            point_id = str(point.id)
            if point_id in processed:
                points_skipped += 1
                continue

            processed.add(point_id)
            points_processed += 1

            payload = point.payload or {}
            text = payload.get("text") or payload.get("content") or ""
            metadata = payload.get("metadata") or {}
            book_title = metadata.get("book_title", "") if isinstance(metadata, dict) else ""

            # Try context header first, then book_title
            mention = _ctx_header_mention(text) or _book_title_mention(book_title)
            if not mention:
                continue

            points_ctx_found += 1
            law, num, year = mention["law"], mention["num"], mention["year"]

            hit = None
            for key in _lookup_variants(law, num, year):
                if key in name_index:
                    hit = name_index[key]
                    break

            if hit is None:
                ctx_misses += 1
                continue

            ctx_hits += 1
            entity_id, _ = hit
            mention_id = hashlib.md5(
                f"{entity_id}:{collection}:{point_id}".encode()
            ).hexdigest()
            insert_rows.append((
                mention_id, entity_id, collection, point_id,
                mention["text"][:500], 0.95, mention["type"],
            ))

        if insert_rows:
            async with pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO kg_entity_mentions "
                    "(mention_id, entity_id, collection_name, point_id, "
                    "mention_text, confidence, match_type) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                    "ON CONFLICT (entity_id, collection_name, point_id) DO NOTHING",
                    insert_rows,
                )
            mentions_created += len(insert_rows)

        total_done = points_processed + points_skipped
        if total_done and total_done % PROGRESS_STEP < batch_size:
            logger.info(
                "progress: processed=%d skip=%d ctx_found=%d hits=%d misses=%d mentions=%d elapsed=%.1fs",
                points_processed, points_skipped, points_ctx_found,
                ctx_hits, ctx_misses, mentions_created, time.time() - start,
            )

        if points_processed - last_telegram_at >= TELEGRAM_STEP:
            last_telegram_at = points_processed
            await _maybe_notify(
                f"*CTX Header Linker* progress\n"
                f"processed: {points_processed} | skip: {points_skipped}\n"
                f"ctx_found: {points_ctx_found} | hits: {ctx_hits} | misses: {ctx_misses}\n"
                f"mentions: {mentions_created}\n"
                f"elapsed: {time.time() - start:.0f}s"
            )

        if limit is not None and points_processed >= limit:
            logger.info("Hit limit=%d, stopping", limit)
            break

        offset = next_offset
        if offset is None:
            break

    elapsed = time.time() - start
    stats = {
        "collection": collection,
        "points_processed": points_processed,
        "points_skipped": points_skipped,
        "points_ctx_found": points_ctx_found,
        "ctx_hits": ctx_hits,
        "ctx_misses": ctx_misses,
        "mentions_created": mentions_created,
        "hit_rate_pct": round(ctx_hits / max(1, points_ctx_found) * 100, 1),
        "coverage_boost": round(mentions_created / 81251 * 100, 2),
        "elapsed_s": round(elapsed, 1),
    }
    logger.info("DONE %s", stats)
    await _maybe_notify(
        f"*CTX Header Linker* DONE `{collection}`\n"
        f"processed: {points_processed} | ctx_found: {points_ctx_found}\n"
        f"hits: {ctx_hits} ({stats['hit_rate_pct']}%) | misses: {ctx_misses}\n"
        f"mentions created: {mentions_created}\n"
        f"coverage boost: +{stats['coverage_boost']}%\n"
        f"elapsed: {elapsed:.0f}s"
    )
    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description="Context-header entity linker")
    parser.add_argument("--collection", default="legal_unified_hybrid_hybrid")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--db-url", default=DB_URL_DEFAULT)
    parser.add_argument("--qdrant-url", default=QDRANT_URL_DEFAULT)
    parser.add_argument("--qdrant-api-key", default=QDRANT_API_KEY_DEFAULT)
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.db_url, min_size=1, max_size=4)
    qdrant = AsyncQdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key, timeout=60)
    try:
        stats = await process_collection(
            pool=pool, qdrant=qdrant, collection=args.collection,
            batch_size=args.batch_size, limit=args.limit,
        )
    finally:
        await qdrant.close()
        await pool.close()

    print("\nFINAL_STATS:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
