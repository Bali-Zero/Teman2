#!/usr/bin/env python3
"""
Add alias metadata + text to visa_oracle Qdrant collection.
Re-embeds and re-generates BM25 sparse vectors for matched points.

For each point whose metadata.code is in VISA_ALIAS_MAP:
  1. Appends alias names to the text (so BM25 indexes them)
  2. Re-embeds the new text with text-embedding-3-small
  3. Re-generates BM25 sparse vector
  4. Upserts point with new dense vector, new sparse vector, and aliases payload field

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/add_visa_aliases.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

import os

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

import openai

from backend.core.bm25_vectorizer import BM25Vectorizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

COLLECTION_NAME = "visa_oracle"
BATCH_SIZE = 100
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536  # FROZEN — never change
ALIAS_SUFFIX_PREFIX = "\n\nAlternative names: "

VISA_ALIAS_MAP: dict[str, list[str]] = {
    "B1": ["B211A", "B211", "visit visa", "visa kunjungan", "wisata"],
    "C6": ["social visa", "visa sosial", "social budaya", "B211A social"],
    "C7": ["cultural visa", "visa budaya", "seni budaya", "B211A budaya"],
    "C2": ["business visa", "visa bisnis", "B211 business"],
    "C1": ["tourism visa", "visa wisata", "tourist visa", "VOA", "visa on arrival"],
    "C18": ["work trial visa", "visa uji coba kerja"],
    "E23": ["employee KITAS", "work permit", "KITAS kerja", "working KITAS"],
    "E25B": ["director KITAS", "KITAS direktur", "direksi KITAS"],
    "E28A": ["investor KITAS", "KITAS investor", "investor visa"],
    "E28B": ["investor company setup", "KITAS investor pendirian"],
    "E33": ["second home visa", "visa rumah kedua", "E33 second home"],
    "E33E": ["retirement visa", "visa pensiun", "retirement KITAS"],
    "E33F": ["retirement visa 55+", "visa lansia"],
    "E33G": ["digital nomad KITAS", "remote worker visa", "E33G digital nomad"],
    "E32A": ["spouse KITAS", "KITAS pasangan", "dependent visa"],
    "D12": ["multiple entry visa", "visa kunjungan beberapa kali", "VKMK"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_env(key: str) -> str:
    """Get required environment variable, raise if missing."""
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _embed_text(client: openai.OpenAI, text: str) -> list[float]:
    """Embed a single text using text-embedding-3-small."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def _embed_batch(client: openai.OpenAI, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using text-embedding-3-small."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    # Results are returned in the same order as inputs
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def _build_alias_text(original_text: str, aliases: list[str]) -> str:
    """Append alias names to the original text for BM25 indexing."""
    alias_str = ", ".join(aliases)
    return f"{original_text}{ALIAS_SUFFIX_PREFIX}{alias_str}"


def _is_already_enriched(payload: dict[str, Any]) -> bool:
    """Check if point already has aliases field (idempotency guard)."""
    return "aliases" in payload


def _extract_code(payload: dict[str, Any]) -> str | None:
    """Extract visa code from point payload (supports nested metadata.code or flat code)."""
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get("code")
    # Flat payload fallback
    return payload.get("code")


def _extract_text(payload: dict[str, Any]) -> str:
    """Extract text content from point payload."""
    return payload.get("text") or payload.get("content") or ""


# ── Main logic ───────────────────────────────────────────────────────────────

def scroll_all_points(
    qdrant: QdrantClient,
    collection_name: str,
) -> list[Any]:
    """Scroll all points from a Qdrant collection with payload and vectors."""
    all_points = []
    offset: Any = None
    page = 0

    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            limit=BATCH_SIZE,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        all_points.extend(points)
        page += 1
        logger.info("  Scrolled page %d: %d points (total so far: %d)", page, len(points), len(all_points))

        if not points or next_offset is None:
            break
        offset = next_offset

    return all_points


def process_and_upsert(
    qdrant: QdrantClient,
    openai_client: openai.OpenAI,
    bm25: BM25Vectorizer,
    all_points: list[Any],
    dry_run: bool,
) -> dict[str, int]:
    """
    Process matched points: re-embed, re-vectorize BM25, upsert.

    Returns stats dict with matched/updated/skipped/already_enriched counts.
    """
    stats = {
        "total": len(all_points),
        "matched": 0,
        "already_enriched": 0,
        "skipped_no_text": 0,
        "updated": 0,
    }

    # Collect points that need updating
    to_update: list[tuple[Any, list[str]]] = []  # (point, aliases)

    for point in all_points:
        payload = point.payload or {}
        code = _extract_code(payload)

        if code not in VISA_ALIAS_MAP:
            continue

        stats["matched"] += 1
        aliases = VISA_ALIAS_MAP[code]

        if _is_already_enriched(payload):
            stats["already_enriched"] += 1
            logger.debug("Point %s (code=%s) already has aliases — skipping", point.id, code)
            continue

        original_text = _extract_text(payload)
        if not original_text:
            stats["skipped_no_text"] += 1
            logger.warning("Point %s (code=%s) has no text — skipping", point.id, code)
            continue

        to_update.append((point, aliases))

    logger.info(
        "Stats: total=%d matched=%d already_enriched=%d skipped_no_text=%d to_update=%d",
        stats["total"],
        stats["matched"],
        stats["already_enriched"],
        stats["skipped_no_text"],
        len(to_update),
    )

    if dry_run:
        logger.info("[DRY RUN] Would update %d points:", len(to_update))
        for point, aliases in to_update:
            code = _extract_code(point.payload or {})
            logger.info(
                "  [DRY RUN] Point %s | code=%s | aliases: %s",
                point.id,
                code,
                ", ".join(aliases),
            )
        stats["updated"] = len(to_update)
        return stats

    if not to_update:
        logger.info("No points to update.")
        return stats

    # Process in batches for embedding efficiency
    for batch_start in range(0, len(to_update), BATCH_SIZE):
        batch = to_update[batch_start : batch_start + BATCH_SIZE]

        # Build enriched texts for the batch
        enriched_texts: list[str] = []
        for point, aliases in batch:
            original_text = _extract_text(point.payload or {})
            enriched_texts.append(_build_alias_text(original_text, aliases))

        # Re-embed all texts in the batch
        logger.info(
            "Embedding batch %d-%d (%d texts)...",
            batch_start + 1,
            batch_start + len(batch),
            len(enriched_texts),
        )
        dense_vectors = _embed_batch(openai_client, enriched_texts)

        # Build PointStruct list for upsert
        upsert_points: list[PointStruct] = []
        for i, (point, aliases) in enumerate(batch):
            enriched_text = enriched_texts[i]
            dense_vec = dense_vectors[i]

            # Re-generate BM25 sparse vector from enriched text
            sparse_dict = bm25.generate_sparse_vector(enriched_text)
            sparse_vec = SparseVector(
                indices=sparse_dict["indices"],
                values=sparse_dict["values"],
            )

            # Build updated payload (preserve all existing fields + add aliases)
            updated_payload = dict(point.payload or {})
            updated_payload["aliases"] = ", ".join(aliases)

            # Also update the text field with enriched version (so payload reflects what's indexed)
            updated_payload["text"] = enriched_text

            upsert_points.append(
                PointStruct(
                    id=point.id,
                    vector={"dense": dense_vec, "bm25": sparse_vec},
                    payload=updated_payload,
                )
            )

        # Upsert batch
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=upsert_points,
            wait=True,
        )
        stats["updated"] += len(upsert_points)
        logger.info(
            "Upserted batch of %d points (%d/%d total updated)",
            len(upsert_points),
            stats["updated"],
            len(to_update),
        )

        # Small delay between batches to avoid rate limiting on embedding API
        if batch_start + BATCH_SIZE < len(to_update):
            time.sleep(0.2)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add visa alias metadata + BM25 re-vectorization to visa_oracle collection."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without making any changes to Qdrant.",
    )
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    if dry_run:
        logger.info("=== DRY RUN MODE — no writes will be made ===")

    # Load credentials
    qdrant_url = _get_env("QDRANT_URL")
    qdrant_api_key = _get_env("QDRANT_API_KEY")
    openai_api_key = _get_env("OPENAI_API_KEY")

    logger.info("Connecting to Qdrant Cloud: %s", qdrant_url)
    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)

    logger.info("Initialising OpenAI client (model=%s)", EMBEDDING_MODEL)
    openai_client = openai.OpenAI(api_key=openai_api_key)

    logger.info("Initialising BM25Vectorizer")
    bm25 = BM25Vectorizer()

    # Verify collection exists
    collections = {c.name for c in qdrant.get_collections().collections}
    if COLLECTION_NAME not in collections:
        logger.error("Collection '%s' not found on Qdrant. Available: %s", COLLECTION_NAME, sorted(collections))
        sys.exit(1)

    info = qdrant.get_collection(COLLECTION_NAME)
    logger.info(
        "Collection '%s': %d points",
        COLLECTION_NAME,
        info.points_count,
    )

    # Scroll all points
    logger.info("Scrolling all points (with_vectors=True)...")
    all_points = scroll_all_points(qdrant, COLLECTION_NAME)
    logger.info("Total points retrieved: %d", len(all_points))

    # Process and upsert
    stats = process_and_upsert(qdrant, openai_client, bm25, all_points, dry_run)

    # Final summary
    logger.info("=== DONE ===")
    logger.info("  Total points scanned : %d", stats["total"])
    logger.info("  Matched alias codes  : %d", stats["matched"])
    logger.info("  Already enriched     : %d", stats["already_enriched"])
    logger.info("  Skipped (no text)    : %d", stats["skipped_no_text"])
    if dry_run:
        logger.info("  Would update         : %d [DRY RUN]", stats["updated"])
    else:
        logger.info("  Updated              : %d", stats["updated"])


if __name__ == "__main__":
    main()
