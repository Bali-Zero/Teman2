#!/usr/bin/env python3
"""Migrate Mata-Garuda skill/reflection/insight rows from SQLite → Qdrant local.

R10 forensic-informed (2026-05-04): skill/reflection/insight rows are LIVE
in apps/mata-garuda/data/knowledge.db (304 total as of 2026-05-06).
This script mirrors them to a local Qdrant collection on the Pro container
for semantic search, while leaving the SQLite write path untouched — Round
4 P1 retire was based on a wrong premise (the rows are NOT vaporware).

OSINT Law 2 compliant: target is the local Pro Qdrant container at
http://127.0.0.1:6333 (no cloud, no Fly).

Usage:
    PYTHONPATH=. python -m backend.scripts.migrate_skills_to_qdrant_local --bootstrap-only
    PYTHONPATH=. python -m backend.scripts.migrate_skills_to_qdrant_local --dry-run
    PYTHONPATH=. python -m backend.scripts.migrate_skills_to_qdrant_local --apply
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

logger = logging.getLogger("migrate_skills_to_qdrant_local")

# --- Constants (FROZEN per CLAUDE.md §6) ----------------------------------

COLLECTION_NAME = "bali_zero_skills_local"
VECTOR_SIZE = 1536  # text-embedding-3-small — FROZEN, never change
DISTANCE = "Cosine"
EMBED_MODEL = "text-embedding-3-small"
DEFAULT_QDRANT_URL = os.environ.get("QDRANT_LOCAL_URL", "http://127.0.0.1:6333")
DEFAULT_SQLITE_PATH = Path(
    os.environ.get(
        "MATA_GARUDA_KB_PATH",
        str(Path.home() / "Desktop/nuzantara/apps/mata-garuda/data/knowledge.db"),
    ),
)
TARGET_TYPES: tuple[str, ...] = ("skill", "reflection", "insight")
EMBED_BATCH_SIZE = 50
UPSERT_BATCH_SIZE = 50

# Fixed namespace for deterministic UUIDv5 point ids — never rotate, would
# cause re-upsert with new ids and orphan the prior vectors.
_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # OID ns


@dataclass(frozen=True)
class KnowledgeRow:
    """Subset of `knowledge` table columns relevant to the mirror.

    SQLite schema (apps/mata-garuda/data/knowledge.db):
        id, agent, type, content, source, confidence, created_at,
        accessed_count, last_accessed
    """

    row_id: int
    agent: str
    type: str
    content: str
    source: str | None
    confidence: float
    created_at: str
    accessed_count: int


# --- SQLite reader --------------------------------------------------------


def load_rows(db_path: Path, limit: int | None = None) -> list[KnowledgeRow]:
    """Read skill/reflection/insight rows from the local SQLite KB.

    The `knowledge` table accumulates harvested items, scored items, and
    other internal rows; we filter to the three types that represent
    Mata-Garuda's distilled cognition layer.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Mata-Garuda KB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" for _ in TARGET_TYPES)
        sql = (
            f"SELECT id, agent, type, content, source, confidence, "
            f"created_at, COALESCE(accessed_count, 0) "
            f"FROM knowledge WHERE type IN ({placeholders}) "
            f"ORDER BY id ASC"
        )
        params: list[object] = list(TARGET_TYPES)
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        cursor = conn.execute(sql, params)
        return [
            KnowledgeRow(
                row_id=int(r[0]),
                agent=str(r[1]),
                type=str(r[2]),
                content=str(r[3]),
                source=r[4],
                confidence=float(r[5] or 0.0),
                created_at=str(r[6]),
                accessed_count=int(r[7]),
            )
            for r in cursor.fetchall()
        ]
    finally:
        conn.close()


# --- ID + payload mapping -------------------------------------------------


def skill_id_for(row: KnowledgeRow) -> str:
    """Deterministic stable ID — `<type>_<sqlite_row_id>`. Same row → same id."""
    return f"{row.type}_{row.row_id}"


def point_uuid_for(row: KnowledgeRow) -> str:
    """Deterministic UUIDv5 from skill_id, used as Qdrant point id.

    Qdrant requires unsigned-int or UUID for point_id — strings aren't valid.
    UUIDv5 with a fixed namespace gives idempotent re-runs without
    collisions across the three types.
    """
    return str(uuid.uuid5(_POINT_NAMESPACE, skill_id_for(row)))


def payload_for(row: KnowledgeRow) -> dict[str, object]:
    """Build a flat Qdrant payload from a knowledge row (Golden Rule 11).

    Mapping (deviates from R4 spec because SQLite columns differ):
        skill_id     ← f"{type}_{id}"
        type         ← row.type (untouched)
        content      ← row.content
        source_cell  ← row.agent
        source       ← row.source or ""
        confidence   ← row.confidence (float)
        scope        ← row.type   (no separate scope column exists)
        valid_from   ← row.created_at  (no valid_from column exists)
        uses_count   ← row.accessed_count
        embedding_dim_check ← VECTOR_SIZE  (paranoia counter for dim drift)
    """
    return {
        "skill_id": skill_id_for(row),
        "type": row.type,
        "content": row.content,
        "source_cell": row.agent,
        "source": row.source or "",
        "confidence": float(row.confidence),
        "scope": row.type,
        "valid_from": row.created_at,
        "uses_count": int(row.accessed_count),
        "embedding_dim_check": VECTOR_SIZE,
    }


# --- Qdrant HTTP helpers --------------------------------------------------


def _validate_existing_collection_shape(body: dict) -> None:
    """Per Codex review 2026-05-06 P2: refuse to use a collection whose vector
    config has drifted (e.g. someone created `bali_zero_skills_local` with a
    different dim or distance). Catch the mismatch BEFORE burning embeddings.
    """
    try:
        params = body["result"]["config"]["params"]
        vectors = params["vectors"]
        size = int(vectors["size"])
        distance = str(vectors["distance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"unexpected Qdrant response shape — cannot validate "
            f"collection {COLLECTION_NAME}: {exc}",
        ) from exc
    if size != VECTOR_SIZE:
        raise RuntimeError(
            f"collection {COLLECTION_NAME} has dim={size}, expected "
            f"{VECTOR_SIZE} (text-embedding-3-small FROZEN). Drop the "
            f"collection and re-bootstrap.",
        )
    if distance != DISTANCE:
        raise RuntimeError(
            f"collection {COLLECTION_NAME} has distance={distance!r}, "
            f"expected {DISTANCE!r}. Drop the collection and re-bootstrap.",
        )


async def bootstrap_collection(url: str) -> bool:
    """Create the collection if missing. Return True if created, False if exists.

    TOCTOU note (Gemini review 2026-05-06): there is a small race between
    the GET 404 check and the PUT, so a concurrent caller could land in
    the same window. Qdrant returns HTTP 4xx with a "already exists" body
    in that case; treat any post-PUT 4xx that says "already exists" as a
    successful-but-not-by-us bootstrap (return False) rather than crashing.

    Shape validation (Codex review 2026-05-06): when the collection
    already exists, validate its vector size + distance match the FROZEN
    config before burning embedding calls.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{url}/collections/{COLLECTION_NAME}")
    if resp.status_code == 200:
        _validate_existing_collection_shape(resp.json())
        logger.info("collection %s already exists at %s (shape OK)",
                    COLLECTION_NAME, url)
        return False
    if resp.status_code != 404:
        raise RuntimeError(
            f"unexpected status {resp.status_code} from "
            f"GET /collections/{COLLECTION_NAME}: {resp.text[:200]}",
        )
    body = {"vectors": {"size": VECTOR_SIZE, "distance": DISTANCE}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        put_resp = await client.put(
            f"{url}/collections/{COLLECTION_NAME}", json=body,
        )
    if put_resp.status_code == 200:
        logger.info("created collection %s (dim=%d)", COLLECTION_NAME, VECTOR_SIZE)
        return True
    # TOCTOU defense: a sibling caller may have created the collection in
    # the GET-then-PUT window. Qdrant returns 4xx with "already exists" text.
    if (
        400 <= put_resp.status_code < 500
        and "already exists" in put_resp.text.lower()
    ):
        logger.info(
            "collection %s created by sibling between GET and PUT — "
            "treating as success", COLLECTION_NAME,
        )
        return False
    raise RuntimeError(
        f"create collection failed: {put_resp.status_code} "
        f"{put_resp.text[:200]}",
    )


async def count_points(url: str) -> int:
    """Return current point count in the collection (0 if not yet created)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{url}/collections/{COLLECTION_NAME}/points/count",
            json={"exact": True},
        )
    if resp.status_code == 404:
        return 0
    resp.raise_for_status()
    return int(resp.json()["result"]["count"])


async def upsert_points(
    url: str,
    points: list[dict[str, object]],
) -> None:
    """PUT /collections/{name}/points with `points: [...]` (idempotent upsert)."""
    if not points:
        return
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.put(
            f"{url}/collections/{COLLECTION_NAME}/points",
            json={"points": points},
            params={"wait": "true"},
        )
    if resp.status_code >= 300:
        raise RuntimeError(
            f"upsert failed: {resp.status_code} {resp.text[:300]}",
        )


# --- Embedder -------------------------------------------------------------


class OpenAIEmbedder:
    """Async OpenAI embedder using text-embedding-3-small (FROZEN).

    Lazy-imports openai inside `embed()` so dry-run paths don't pull the
    SDK if it's not actually called. The embed-dim guard is mandatory:
    any drift means downstream Qdrant collections become read-incompatible.
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY required (set in ~/.nuzantara-secrets.env)",
            )
        self._key = key
        self._model = EMBED_MODEL

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        from openai import AsyncOpenAI  # local import — keeps dry-run cheap

        client = AsyncOpenAI(api_key=self._key)
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            chunk = texts[i : i + EMBED_BATCH_SIZE]
            resp = await client.embeddings.create(
                model=self._model, input=chunk,
            )
            vecs = [item.embedding for item in resp.data]
            for v in vecs:
                if len(v) != VECTOR_SIZE:
                    raise RuntimeError(
                        f"embedding dim {len(v)} != {VECTOR_SIZE} (FROZEN)",
                    )
            all_vecs.extend(vecs)
        return all_vecs


# --- Orchestration --------------------------------------------------------


async def _run(args: argparse.Namespace) -> int:
    qdrant_url = args.qdrant_url
    rows = load_rows(args.sqlite_path, limit=args.limit)
    logger.info(
        "loaded %d rows (skill=%d reflection=%d insight=%d) from %s",
        len(rows),
        sum(1 for r in rows if r.type == "skill"),
        sum(1 for r in rows if r.type == "reflection"),
        sum(1 for r in rows if r.type == "insight"),
        args.sqlite_path,
    )

    if args.bootstrap_only:
        created = await bootstrap_collection(qdrant_url)
        logger.info("bootstrap-only: collection_created=%s", created)
        return 0

    if args.dry_run:
        logger.info(
            "dry-run: would embed %d texts and upsert %d points to %s",
            len(rows), len(rows), qdrant_url,
        )
        existing = await count_points(qdrant_url)
        logger.info("current points in %s: %d", COLLECTION_NAME, existing)
        return 0

    # --apply path
    await bootstrap_collection(qdrant_url)
    embedder = OpenAIEmbedder()

    total_batches = (len(rows) + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
    for batch_index, batch_start in enumerate(
        range(0, len(rows), UPSERT_BATCH_SIZE), start=1,
    ):
        batch = rows[batch_start : batch_start + UPSERT_BATCH_SIZE]
        texts = [r.content for r in batch]
        vecs = await embedder.embed(texts)
        points = [
            {
                "id": point_uuid_for(row),
                "vector": vec,
                "payload": payload_for(row),
            }
            for row, vec in zip(batch, vecs, strict=True)
        ]
        await upsert_points(qdrant_url, points)
        logger.info(
            "upserted batch %d/%d (%d points)",
            batch_index, total_batches, len(points),
        )

    final_count = await count_points(qdrant_url)
    logger.info("done: %s now has %d points", COLLECTION_NAME, final_count)
    return 0


# --- CLI entry point ------------------------------------------------------


def main() -> int:
    """CLI entry point. Returns shell exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap-only", action="store_true",
        help="Create collection if missing, then exit.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read + log counts; do NOT call OpenAI nor mutate Qdrant.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Read + embed + upsert (idempotent via UUIDv5 point ids).",
    )
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument(
        "--sqlite-path", default=str(DEFAULT_SQLITE_PATH), type=Path,
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit rows for smoke runs.",
    )
    args = parser.parse_args()

    if not (args.bootstrap_only or args.dry_run or args.apply):
        parser.error("one of --bootstrap-only / --dry-run / --apply is required")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
