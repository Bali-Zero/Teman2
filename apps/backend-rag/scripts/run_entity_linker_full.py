"""Full entity linker runner for GraphRAG 2.0 completion.

Optimised over EntityLinker.link_collection:
- Pre-loads kg_nodes (name -> entity_id) into memory for O(1) exact match
- Batches mention INSERTs via executemany
- Tracks processed point_ids via UNIQUE index (idempotent)
- Resume-safe: skips point_ids already present for the collection
- Optional Telegram digest every PROGRESS_STEP points
- Bounded fuzzy-match fallback (Postgres trigram) only when exact miss

Usage:
    PYTHONPATH=. python scripts/run_entity_linker_full.py \
        --collection legal_unified_hybrid_hybrid --batch-size 256
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import asyncpg

# sys.path: apps/backend-rag/ is added so `backend.*` imports work when
# executed from scripts/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import re  # noqa: E402

def _require_env(name: str) -> str:
    import os as _os
    val = _os.environ.get(name)
    if not val:
        raise SystemExit(f"{name} env var is required (no hardcoded fallback for security)")
    return val



# Re-declared from backend/services/knowledge_graph/entity_linker.py to avoid
# importing the whole backend.services.* init chain (which boots Settings).
_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("undang_undang", re.compile(r"UU\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("peraturan_pemerintah", re.compile(r"PP\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("perpres", re.compile(r"Perpres\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("permen", re.compile(r"Permen\w*\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    # CONTEXT-style prefixes used in legal_unified payloads:
    # `PP - NO 6624 - TAHUN 2021`, `UU - NO 11 - TAHUN 2020`, etc.
    ("ctx_law", re.compile(
        r"\b(UU|PP|Perpres|Permen\w*)\s*-\s*NO\s+(\d+)\s*-\s*TAHUN\s+(\d{4})",
        re.IGNORECASE,
    )),
    ("kbli", re.compile(r"KBLI\s*(\d{4,5})", re.IGNORECASE)),
    ("visa", re.compile(r"\b(KITAS|KITAP|VITAS|KUNJUNGAN|B211A?|C312|VOA)\b", re.IGNORECASE)),
    ("izin", re.compile(r"\b(NIB|SIUP|TDP|NPWP|IMB|AMDAL|OSS|RPTKA|IMTA)\b", re.IGNORECASE)),
    ("company", re.compile(r"\b(PT\s*PMA|PT\s*PMDN|PT\s*Perorangan|CV)\b", re.IGNORECASE)),
    ("tax", re.compile(r"\b(PPh\s*\d{1,2}|PPN|PBB|BPHTB|SPT)\b", re.IGNORECASE)),
    ("gov", re.compile(r"\b(BKPM|DJP|Kemenkumham|Kemenaker|Imigrasi|BPN)\b", re.IGNORECASE)),
]


def extract_mentions(text: str) -> list[dict[str, str]]:
    mentions: list[dict[str, str]] = []
    seen: set[str] = set()
    for entity_type, pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            mention_text = match.group(0).strip()
            normalized = mention_text.upper().replace(".", "").replace(" ", "_")
            if normalized not in seen:
                seen.add(normalized)
                mentions.append({
                    "type": entity_type,
                    "text": mention_text,
                    "normalized": normalized,
                })
    return mentions

try:
    from qdrant_client import AsyncQdrantClient
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"qdrant-client not installed: {exc}") from exc


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entity_linker_full")


DB_URL_DEFAULT = _require_env("ENTITY_LINKER_DB_URL")
QDRANT_URL_DEFAULT = _require_env("QDRANT_URL")
QDRANT_API_KEY_DEFAULT = _require_env("QDRANT_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

PROGRESS_STEP = int(os.environ.get("ENTITY_LINKER_PROGRESS_STEP", "2000"))
TELEGRAM_STEP = int(os.environ.get("ENTITY_LINKER_TELEGRAM_STEP", "10000"))


async def _maybe_notify(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.debug("Telegram skipped (no token): %s", message)
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_notification": True,
                },
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram notify failed: %s", exc)


async def _load_name_index(pool: asyncpg.Pool) -> dict[str, tuple[str, str]]:
    """Map LOWER(name) -> (entity_id, entity_type). First-wins on collisions."""
    rows = await pool.fetch("SELECT entity_id, name, entity_type FROM kg_nodes")
    idx: dict[str, tuple[str, str]] = {}
    for row in rows:
        key = (row["name"] or "").strip().lower()
        if key and key not in idx:
            idx[key] = (row["entity_id"], row["entity_type"])
    logger.info("Loaded %d kg_nodes (unique-lower %d)", len(rows), len(idx))
    return idx


async def _load_processed_points(pool: asyncpg.Pool, collection: str) -> set[str]:
    """Return point_ids already linked for this collection (for resume)."""
    rows = await pool.fetch(
        "SELECT DISTINCT point_id FROM kg_entity_mentions WHERE collection_name = $1",
        collection,
    )
    return {r["point_id"] for r in rows}


async def _fuzzy_match(
    pool: asyncpg.Pool,
    mention_text: str,
    threshold: float = 0.85,
) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT entity_id, entity_type, similarity(name, $1) AS sim "
            "FROM kg_nodes WHERE similarity(name, $1) >= $2 "
            "ORDER BY sim DESC LIMIT 1",
            mention_text,
            threshold,
        )
        if row:
            return {
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "similarity": float(row["sim"]),
            }
        return None


def _pick_content(payload: dict[str, Any]) -> str:
    for field in ("content", "text", "chunk_text", "document"):
        val = payload.get(field)
        if val:
            return str(val)
    return ""


_UU_PP_NORM_RE = re.compile(r"^(UU|PP|PERPRES|PERMEN\w*)\s+(?:NO\.?\s+)?(\d+)\s+(?:TAHUN\s+)?(\d{4})$")
_UU_PP_CTX_RE = re.compile(r"^(UU|PP|PERPRES|PERMEN\w*)\s*-\s*NO\s+(\d+)\s*-\s*TAHUN\s+(\d{4})$")


def _match_variants(mention_text: str) -> list[str]:
    """Generate lookup key variants for kg_nodes.name index.

    Entities are stored inconsistently across 113K kg_nodes; this expands a
    single mention into the forms we have observed (e.g. `UU 13 2003` vs
    `UU 13/2003`, `UU NO. 11 TAHUN 2020`).
    """
    base = mention_text.strip()
    out = [base]
    low = base.lower()
    upper = base.upper()
    # Collapse whitespace runs
    collapsed = re.sub(r"\s+", " ", base)
    if collapsed != base:
        out.append(collapsed)

    m = _UU_PP_NORM_RE.match(upper) or _UU_PP_CTX_RE.match(upper)
    if m:
        law, num, year = m.group(1), m.group(2), m.group(3)
        out.extend(
            [
                f"{law} {num}/{year}",
                f"{law} No. {num} Tahun {year}",
                f"{law} NO. {num} TAHUN {year}",
                f"{law} No {num} Tahun {year}",
                f"{law} {num} {year}",
            ],
        )

    # KBLI always 4-5 digits
    km = re.match(r"KBLI\s*(\d{4,5})", upper)
    if km:
        code = km.group(1)
        out.append(f"KBLI {code}")

    # Deduplicate preserving order, lowercased for index lookup
    seen: set[str] = set()
    deduped: list[str] = []
    for variant in out:
        k = variant.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


async def process_collection(
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    collection: str,
    batch_size: int,
    limit: int | None,
    enable_fuzzy: bool,
) -> dict[str, Any]:
    start = time.time()

    name_index = await _load_name_index(pool)
    processed = await _load_processed_points(pool, collection)
    logger.info(
        "Resume state: %d point_ids already linked for %s",
        len(processed),
        collection,
    )
    await _maybe_notify(
        f"*Entity linker* start\n"
        f"collection: `{collection}`\n"
        f"resume: {len(processed)} points already linked"
    )

    points_processed = 0
    points_skipped = 0
    mentions_created = 0
    fuzzy_hits = 0
    exact_hits = 0
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

            content = _pick_content(point.payload or {})
            if not content:
                processed.add(point_id)
                points_skipped += 1
                continue

            mentions = extract_mentions(content)
            points_processed += 1
            processed.add(point_id)

            for mention in mentions:
                text = mention["text"]
                hit = None
                for key in _match_variants(text):
                    hit = name_index.get(key)
                    if hit is not None:
                        break

                if hit is not None:
                    entity_id, _ = hit
                    confidence = 1.0
                    match_type = "exact"
                    exact_hits += 1
                elif enable_fuzzy:
                    fmatch = await _fuzzy_match(pool, text)
                    if fmatch is None:
                        continue
                    entity_id = fmatch["entity_id"]
                    confidence = fmatch["similarity"]
                    match_type = "fuzzy"
                    fuzzy_hits += 1
                else:
                    continue

                mention_id = hashlib.md5(
                    f"{entity_id}:{collection}:{point_id}".encode(),
                ).hexdigest()
                insert_rows.append(
                    (
                        mention_id,
                        entity_id,
                        collection,
                        point_id,
                        text[:500],
                        confidence,
                        match_type,
                    ),
                )

        if insert_rows:
            async with pool.acquire() as conn:
                inserted = await conn.executemany(
                    "INSERT INTO kg_entity_mentions "
                    "(mention_id, entity_id, collection_name, point_id, "
                    "mention_text, confidence, match_type) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                    "ON CONFLICT (entity_id, collection_name, point_id) "
                    "DO NOTHING",
                    insert_rows,
                )
            mentions_created += len(insert_rows)
            logger.debug("Batch inserted %d mention rows (result=%s)", len(insert_rows), inserted)

        if points_processed and points_processed // PROGRESS_STEP != (points_processed - len(results)) // PROGRESS_STEP:
            logger.info(
                "progress: processed=%d skipped=%d mentions=%d exact=%d fuzzy=%d elapsed=%.1fs",
                points_processed,
                points_skipped,
                mentions_created,
                exact_hits,
                fuzzy_hits,
                time.time() - start,
            )

        if points_processed - last_telegram_at >= TELEGRAM_STEP:
            last_telegram_at = points_processed
            await _maybe_notify(
                f"*Entity linker* progress\n"
                f"processed: {points_processed}\n"
                f"skipped (resume): {points_skipped}\n"
                f"mentions: {mentions_created} (exact {exact_hits}, fuzzy {fuzzy_hits})\n"
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
        "mentions_created": mentions_created,
        "exact_hits": exact_hits,
        "fuzzy_hits": fuzzy_hits,
        "elapsed_s": round(elapsed, 1),
    }
    logger.info("DONE %s", stats)
    await _maybe_notify(
        f"*Entity linker* DONE `{collection}`\n"
        f"processed: {points_processed}\n"
        f"mentions: {mentions_created} (exact {exact_hits}, fuzzy {fuzzy_hits})\n"
        f"elapsed: {elapsed:.0f}s"
    )
    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description="Full entity linker runner")
    parser.add_argument(
        "--collection",
        default="legal_unified_hybrid_hybrid",
        help="Qdrant collection to scan",
    )
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on new points processed (None=all)",
    )
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Disable trigram fuzzy fallback (exact match only)",
    )
    parser.add_argument("--db-url", default=DB_URL_DEFAULT)
    parser.add_argument("--qdrant-url", default=QDRANT_URL_DEFAULT)
    parser.add_argument("--qdrant-api-key", default=QDRANT_API_KEY_DEFAULT)
    args = parser.parse_args()

    logger.info("Connecting to DB %s", args.db_url.split("@", 1)[-1])
    pool = await asyncpg.create_pool(args.db_url, min_size=1, max_size=4)
    qdrant = AsyncQdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key, timeout=60)
    try:
        stats = await process_collection(
            pool=pool,
            qdrant=qdrant,
            collection=args.collection,
            batch_size=args.batch_size,
            limit=args.limit,
            enable_fuzzy=not args.no_fuzzy,
        )
    finally:
        await qdrant.close()
        await pool.close()

    print("\nFINAL_STATS:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
