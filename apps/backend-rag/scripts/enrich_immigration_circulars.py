#!/usr/bin/env python3
"""
Enrich immigration_circulars collection from legal_unified_hybrid_hybrid.

Uses server-side payload filtering to avoid scanning all 81K points (no vectors
transferred in the first pass). Then fetches matched points with vectors in small
batches and upserts into immigration_circulars with a flat payload.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/enrich_immigration_circulars.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_PATH = Path(__file__).resolve().parents[1]  # apps/backend-rag/
PROJECT_ROOT = BACKEND_PATH.parents[1]              # nuzantara/
sys.path.insert(0, str(BACKEND_PATH))

from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Qdrant setup ──────────────────────────────────────────────────────────────
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchText, PointStruct

SOURCE_COLLECTION = "legal_unified_hybrid_hybrid"
TARGET_COLLECTION = "immigration_circulars"
DENSE_DIMS = 1536  # FROZEN — text-embedding-3-small
SCROLL_BATCH = 200   # points per scroll page (no vectors → lightweight)
FETCH_BATCH = 100    # points per retrieve batch (with vectors)
UPSERT_BATCH = 50    # points per upsert call

# ── Immigration keywords ──────────────────────────────────────────────────────
# MatchText performs full-text (case-insensitive substring) matching.
# Each keyword generates one `should` condition — any single match qualifies.
IMMIGRATION_KEYWORDS: list[str] = [
    "visa",
    "imigrasi",
    "keimigrasian",
    "izin tinggal",
    "golden visa",
    "second home",
    "digital nomad",
    "TKA",
    "tenaga kerja asing",
    "RPTKA",
    "IMTA",
    "orang asing",
    "Permenkumham",
]

# For the 2-keyword-hit requirement we track per-point how many DISTINCT keywords
# appear in the text (case-insensitive, simple substring check).
KEYWORD_LOWER: list[str] = [kw.lower() for kw in IMMIGRATION_KEYWORDS]

MIN_KEYWORD_HITS = 2  # require at least 2 distinct keyword hits to reduce noise


def _make_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL")
    key = os.getenv("QDRANT_API_KEY")
    if not url:
        raise RuntimeError("QDRANT_URL is not set in environment")
    return QdrantClient(url=url, api_key=key, timeout=60, check_compatibility=False)


def _build_scroll_filter() -> Filter:
    """Build a `should` filter: at least ONE immigration keyword must appear in `text`."""
    return Filter(
        should=[
            FieldCondition(key="text", match=MatchText(text=kw))
            for kw in IMMIGRATION_KEYWORDS
        ]
    )


def _count_keyword_hits(text: str) -> int:
    """Return number of distinct immigration keywords found in text (case-insensitive)."""
    lowered = text.lower()
    return sum(1 for kw in KEYWORD_LOWER if kw in lowered)


def _text_hash(text: str) -> str:
    """Stable dedup key: MD5 of the first 200 chars."""
    return hashlib.md5(text[:200].encode("utf-8")).hexdigest()


def _build_flat_payload(src_payload: dict[str, Any], keyword_hits: int) -> dict[str, Any]:
    """
    Convert nested legal_unified payload to the flat immigration_circulars schema.

    Source shape:
      {
        "text": "...",
        "metadata": {
          "book_title": "...",
          "legal_topic": "...",
          "legal_type": "...",
          "legal_number": "...",
          "legal_year": "...",
          "doc_type": "...",
          "bab_title": "...",
          "chunk_index": ...,
          "document_id": "...",
          ...
        }
      }

    Target shape (flat — matches existing immigration_circulars points):
      {
        "text": "...",
        "source": "legal_unified_hybrid_hybrid",
        "document_type": "...",
        "regulation_number": "...",
        "title": "...",
        "issuing_authority": "...",
        "ministry": "...",
        "effective_date": null,
        "keywords": [...],
        "ingested_at": "...",
        "chunk_type": "...",
        "chunk_index": ...,
        "topic": "...",
        "keyword_matches": ...,
      }
    """
    meta: dict[str, Any] = src_payload.get("metadata", {}) if isinstance(src_payload.get("metadata"), dict) else {}
    text: str = src_payload.get("text", "")

    legal_type = meta.get("legal_type") or meta.get("doc_type") or "Regulation"
    legal_number = meta.get("legal_number") or meta.get("number") or ""
    legal_year = meta.get("legal_year") or meta.get("year") or ""
    reg_number = f"{legal_type} {legal_number}/{legal_year}".strip(" /")

    topic = (
        meta.get("legal_topic")
        or meta.get("topic")
        or meta.get("bab_title")
        or meta.get("book_title")
        or ""
    )

    # Derive matched keywords for transparency
    lowered = text.lower()
    matched_kws = [kw for kw in IMMIGRATION_KEYWORDS if kw.lower() in lowered]

    return {
        "text": text,
        "source": SOURCE_COLLECTION,
        "document_type": legal_type,
        "regulation_number": reg_number,
        "title": meta.get("book_title") or meta.get("book_author") or reg_number,
        "issuing_authority": meta.get("book_author") or "",
        "ministry": _extract_ministry(meta),
        "effective_date": None,
        "keywords": matched_kws,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "chunk_type": meta.get("hierarchy_path") or "chunk",
        "chunk_index": meta.get("chunk_index") or 0,
        "topic": topic,
        "keyword_matches": keyword_hits,
        "source_document_id": meta.get("document_id") or "",
        "source_chunk_id": meta.get("chunk_id") or "",
    }


def _extract_ministry(meta: dict[str, Any]) -> str:
    """Heuristic: extract ministry from legal_type."""
    legal_type = (meta.get("legal_type") or "").lower()
    book_title = (meta.get("book_title") or "").lower()
    if "kumham" in book_title or "permenkumham" in legal_type:
        return "Kemenkumham"
    if "naker" in book_title or "permenaker" in legal_type:
        return "Kemnaker"
    if "bkpm" in book_title or "bkpm" in legal_type:
        return "BKPM"
    if "perpres" in legal_type:
        return "Presiden RI"
    if "pp" == legal_type:
        return "Pemerintah RI"
    return ""


def enrich(dry_run: bool = False, limit: int | None = None) -> None:
    client = _make_client()

    # ── Connectivity check ────────────────────────────────────────────────────
    try:
        src_info = client.get_collection(SOURCE_COLLECTION)
        tgt_info = client.get_collection(TARGET_COLLECTION)
    except Exception as exc:
        logger.error("Cannot reach Qdrant collections: %s", exc)
        sys.exit(1)

    logger.info("Source '%s': %d points", SOURCE_COLLECTION, src_info.points_count)
    logger.info("Target '%s': %d points (before)", TARGET_COLLECTION, tgt_info.points_count)

    scroll_filter = _build_scroll_filter()

    # ── Pass 1: scroll WITHOUT vectors, collect matching IDs ─────────────────
    logger.info("Pass 1: scrolling '%s' with immigration filter (no vectors)...", SOURCE_COLLECTION)

    matched_ids: list[str | int] = []
    # text_hash → True  (dedup within source)
    seen_source_hashes: set[str] = set()

    offset: Any = None
    scanned = 0

    while True:
        points, next_offset = client.scroll(
            collection_name=SOURCE_COLLECTION,
            scroll_filter=scroll_filter,
            limit=SCROLL_BATCH,
            offset=offset,
            with_vectors=False,
            with_payload=True,
        )
        if not points:
            break

        for p in points:
            scanned += 1
            text = (p.payload or {}).get("text", "")
            hits = _count_keyword_hits(text)
            if hits < MIN_KEYWORD_HITS:
                continue  # not immigration-specific enough

            h = _text_hash(text)
            if h in seen_source_hashes:
                continue  # dedup within source pass
            seen_source_hashes.add(h)

            matched_ids.append(p.id)
            if limit and len(matched_ids) >= limit:
                break

        logger.info("  Scrolled %d points, %d matched so far", scanned, len(matched_ids))

        if next_offset is None or (limit and len(matched_ids) >= limit):
            break
        offset = next_offset

    logger.info(
        "Pass 1 complete: scanned=%d filter_passed=? deduped_matched=%d",
        scanned,
        len(matched_ids),
    )

    if not matched_ids:
        logger.warning("No immigration-relevant points found — check keywords or MIN_KEYWORD_HITS.")
        return

    # ── Load existing target hashes to avoid duplicate upserts ───────────────
    logger.info("Loading existing '%s' content hashes for dedup...", TARGET_COLLECTION)
    existing_hashes: set[str] = set()
    ex_offset: Any = None
    while True:
        ex_pts, ex_next = client.scroll(
            collection_name=TARGET_COLLECTION,
            limit=200,
            offset=ex_offset,
            with_payload=True,
            with_vectors=False,
        )
        if not ex_pts:
            break
        for ep in ex_pts:
            et = (ep.payload or {}).get("text", "")
            existing_hashes.add(_text_hash(et))
        if ex_next is None:
            break
        ex_offset = ex_next
    logger.info("  %d existing points loaded", len(existing_hashes))

    # ── Pass 2: fetch matched IDs with vectors in batches ────────────────────
    logger.info("Pass 2: fetching %d matched points WITH vectors (batch=%d)...", len(matched_ids), FETCH_BATCH)

    upsert_points: list[PointStruct] = []
    new_inserted = 0
    skipped_dedup = 0

    for batch_start in range(0, len(matched_ids), FETCH_BATCH):
        batch_ids = matched_ids[batch_start : batch_start + FETCH_BATCH]

        fetched = client.retrieve(
            collection_name=SOURCE_COLLECTION,
            ids=batch_ids,
            with_vectors=True,
            with_payload=True,
        )

        for p in fetched:
            text = (p.payload or {}).get("text", "")
            h = _text_hash(text)

            if h in existing_hashes:
                skipped_dedup += 1
                continue
            existing_hashes.add(h)  # mark so we don't insert it twice

            # Extract dense vector
            raw_vec = p.vector
            if isinstance(raw_vec, dict):
                dense_vec = raw_vec.get("dense")
            else:
                dense_vec = raw_vec  # plain list (shouldn't happen for this collection)

            if dense_vec is None or len(dense_vec) != DENSE_DIMS:
                logger.warning("Point %s has no usable dense vector — skipping", p.id)
                continue

            hits = _count_keyword_hits(text)
            flat_payload = _build_flat_payload(p.payload or {}, hits)

            upsert_points.append(
                PointStruct(
                    id=str(uuid.uuid4()),  # always new UUIDs in target
                    vector={"dense": dense_vec},
                    payload=flat_payload,
                )
            )

        # Flush upsert buffer
        while len(upsert_points) >= UPSERT_BATCH:
            batch = upsert_points[:UPSERT_BATCH]
            upsert_points = upsert_points[UPSERT_BATCH:]

            if not dry_run:
                client.upsert(collection_name=TARGET_COLLECTION, points=batch)
            new_inserted += len(batch)
            logger.info(
                "  Upserted %d points (total inserted=%d, skipped_dedup=%d)%s",
                len(batch),
                new_inserted,
                skipped_dedup,
                " [DRY RUN]" if dry_run else "",
            )

        logger.info(
            "  Fetched batch %d-%d (%d in buffer, %d inserted, %d skipped)",
            batch_start + 1,
            batch_start + len(batch_ids),
            len(upsert_points),
            new_inserted,
            skipped_dedup,
        )

    # Flush remaining
    if upsert_points:
        if not dry_run:
            client.upsert(collection_name=TARGET_COLLECTION, points=upsert_points)
        new_inserted += len(upsert_points)
        logger.info(
            "  Final flush: %d points%s",
            len(upsert_points),
            " [DRY RUN]" if dry_run else "",
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("ENRICHMENT COMPLETE%s", " [DRY RUN]" if dry_run else "")
    logger.info("  Source scanned      : %d", scanned)
    logger.info("  Keyword-matched     : %d (>= %d hits, deduped within source)", len(matched_ids), MIN_KEYWORD_HITS)
    logger.info("  Skipped (dedup)     : %d", skipped_dedup)
    logger.info("  Inserted            : %d", new_inserted)
    logger.info("=" * 60)

    if not dry_run:
        final_info = client.get_collection(TARGET_COLLECTION)
        logger.info("Target '%s' final count: %d points", TARGET_COLLECTION, final_info.points_count)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich immigration_circulars from legal_unified_hybrid_hybrid"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and match but do NOT write to target collection",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after collecting N matched IDs (useful for testing)",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode — no writes to '%s'", TARGET_COLLECTION)

    enrich(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
