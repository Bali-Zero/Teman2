#!/usr/bin/env python3
"""Migrate Mata-Garuda skills/reflections/insights from SQLite → Qdrant Cloud.

R5 AIL #1 (2026-05-17): re-indexes `bali_zero_skills_local` (Pro Docker,
local-only) to `bali_zero_skills_hybrid` on Qdrant Cloud so the surface
is reachable from Fly.io production.

Collection name change:
  bali_zero_skills_local  → bali_zero_skills_hybrid  (Qdrant Cloud)

Source: apps/mata-garuda/data/knowledge.db (613 rows: skill/reflection/insight)

Usage:
    cd apps/backend-rag
    PYTHONPATH=. python -m backend.scripts.migrate_skills_to_qdrant_cloud --dry-run
    PYTHONPATH=. python -m backend.scripts.migrate_skills_to_qdrant_cloud --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger("migrate_skills_cloud")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_NAME = "bali_zero_skills_hybrid"
VECTOR_SIZE = 1536  # text-embedding-3-small — FROZEN
DISTANCE = "Cosine"
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 50
UPSERT_BATCH_SIZE = 50

QDRANT_URL = os.environ.get(
    "QDRANT_URL",
    "https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_SQLITE_PATH = Path(
    os.environ.get(
        "MATA_GARUDA_KB_PATH",
        str(Path.home() / "Desktop/nuzantara/apps/mata-garuda/data/knowledge.db"),
    ),
)

TARGET_TYPES: tuple[str, ...] = ("skill", "reflection", "insight")

# Deterministic UUID namespace — same as migrate_skills_to_qdrant_local.py
_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KnowledgeRow:
    row_id: int
    agent: str
    type: str
    content: str
    source: str | None
    confidence: float
    created_at: str


def _row_point_id(row_id: int) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"skills:{row_id}"))


# ---------------------------------------------------------------------------
# SQLite reader
# ---------------------------------------------------------------------------

def load_rows(sqlite_path: Path) -> list[KnowledgeRow]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite not found: {sqlite_path}")
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.execute(
            "SELECT id, agent, type, content, source, confidence, created_at "
            "FROM knowledge WHERE type IN ('skill','reflection','insight') "
            "ORDER BY id"
        )
        return [
            KnowledgeRow(
                row_id=r[0], agent=r[1], type=r[2], content=r[3],
                source=r[4], confidence=float(r[5] or 0.5), created_at=r[6] or "",
            )
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Embedding (OpenAI REST — no SDK, no paid Anthropic key)
# ---------------------------------------------------------------------------

async def embed_batch(texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
    resp = await client.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={"model": EMBED_MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]


# ---------------------------------------------------------------------------
# Qdrant Cloud helpers
# ---------------------------------------------------------------------------

def _qdrant_headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        h["api-key"] = QDRANT_API_KEY
    return h


async def collection_exists(client: httpx.AsyncClient) -> bool:
    r = await client.get(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        headers=_qdrant_headers(),
        timeout=10,
    )
    return r.status_code == 200


async def create_collection(client: httpx.AsyncClient) -> None:
    payload = {
        "vectors": {
            "size": VECTOR_SIZE,
            "distance": DISTANCE,
            "on_disk": False,
        },
        "sparse_vectors": {
            "text-sparse": {"index": {"on_disk": False}}
        },
    }
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        headers=_qdrant_headers(),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    logger.info("Collection %s created", COLLECTION_NAME)


async def upsert_points(
    client: httpx.AsyncClient,
    rows: list[KnowledgeRow],
    vectors: list[list[float]],
) -> None:
    points = [
        {
            "id": _row_point_id(row.row_id),
            "vector": vec,
            "payload": {
                "row_id": row.row_id,
                "agent": row.agent,
                "type": row.type,
                "content": row.content,
                "source": row.source or "",
                "confidence": row.confidence,
                "created_at": row.created_at,
            },
        }
        for row, vec in zip(rows, vectors, strict=True)
    ]
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        headers=_qdrant_headers(),
        json={"points": points},
        timeout=60,
    )
    r.raise_for_status()


async def get_point_count(client: httpx.AsyncClient) -> int:
    r = await client.get(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        headers=_qdrant_headers(),
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()["result"].get("points_count", 0)
    return 0


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

async def run_migration(dry_run: bool, sqlite_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)
    if not QDRANT_API_KEY:
        logger.error("QDRANT_API_KEY not set")
        sys.exit(1)

    logger.info("Loading rows from %s", sqlite_path)
    rows = load_rows(sqlite_path)
    logger.info("Loaded %d rows (skill=%d, reflection=%d, insight=%d)",
        len(rows),
        sum(1 for r in rows if r.type == "skill"),
        sum(1 for r in rows if r.type == "reflection"),
        sum(1 for r in rows if r.type == "insight"),
    )

    if dry_run:
        logger.info("[DRY RUN] Would upsert %d points to %s/%s", len(rows), QDRANT_URL[:40], COLLECTION_NAME)
        return

    async with httpx.AsyncClient() as client:
        exists = await collection_exists(client)
        if not exists:
            logger.info("Creating collection %s on Qdrant Cloud ...", COLLECTION_NAME)
            await create_collection(client)
        else:
            existing_count = await get_point_count(client)
            logger.info("Collection already exists with %d points — upserting (idempotent)", existing_count)

        # Embed in batches
        all_vectors: list[list[float]] = []
        for i in range(0, len(rows), EMBED_BATCH_SIZE):
            batch = rows[i:i + EMBED_BATCH_SIZE]
            texts = [r.content for r in batch]
            logger.info("Embedding batch %d/%d (%d texts) ...",
                i // EMBED_BATCH_SIZE + 1,
                (len(rows) - 1) // EMBED_BATCH_SIZE + 1,
                len(texts),
            )
            vecs = await embed_batch(texts, client)
            all_vectors.extend(vecs)

        # Upsert in batches
        for i in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch_rows = rows[i:i + UPSERT_BATCH_SIZE]
            batch_vecs = all_vectors[i:i + UPSERT_BATCH_SIZE]
            logger.info("Upserting batch %d/%d (%d points) ...",
                i // UPSERT_BATCH_SIZE + 1,
                (len(rows) - 1) // UPSERT_BATCH_SIZE + 1,
                len(batch_rows),
            )
            await upsert_points(client, batch_rows, batch_vecs)

        final_count = await get_point_count(client)
        logger.info("Done. Collection %s now has %d points (expected %d)",
            COLLECTION_NAME, final_count, len(rows))

        if final_count < len(rows):
            logger.error("Point count mismatch! Expected %d, got %d", len(rows), final_count)
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate skills to Qdrant Cloud")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--apply", action="store_true", help="Execute migration")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)

    asyncio.run(run_migration(
        dry_run=args.dry_run,
        sqlite_path=Path(args.sqlite_path),
    ))


if __name__ == "__main__":
    main()
