"""
Build a TWIN collection `kbli_2025_final_oss` (blue-green / shadow) — additive, NEVER touches
the live `kbli_2025_final_hybrid`. Ingests schema-v2 (OSS L0 + L1/L2/L3/L4) so we can bombard it
with verification queries BEFORE any alias swap to production.

Strategy (Zero's plan, 2026-06-19):
1. Create kbli_2025_final_oss with the SAME vector schema as the live one (dense 1536 + bm25 sparse).
2. Embed + upsert all 1559 codes (NO delete — the twin starts empty).
3. Verify, then bombard with queries. Live collection stays intact at all times.

Reuses build_embedding_text / build_payload / deterministic_uuid / embed_texts / BM25Vectorizer
from reindex_kbli_2025_final.py (the official, now-fixed+L4 script).

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/build_kbli_oss_twin.py [--limit N] [--dry-run]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.core.bm25_vectorizer import BM25Vectorizer
from backend.scripts.reindex_kbli_2025_final import (
    build_embedding_text,
    build_payload,
    deterministic_uuid,
    embed_texts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LIVE_COLLECTION = "kbli_2025_final_hybrid"
TWIN_COLLECTION = "kbli_2025_final_oss"
EMBEDDING_MODEL = "text-embedding-3-small"
UPSERT_BATCH_SIZE = 20

SOURCE_FILE = Path(__file__).resolve().parents[4] / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


async def get_live_schema(qurl: str, headers: dict) -> dict:
    """Read the live collection's vector + sparse-vector config to clone it exactly."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{qurl}/collections/{LIVE_COLLECTION}", headers=headers)
        r.raise_for_status()
        params = r.json()["result"]["config"]["params"]
        return {
            "vectors": params["vectors"],
            "sparse_vectors": params.get("sparse_vectors", {"bm25": {}}),
        }


async def create_twin(qurl: str, headers: dict, schema: dict) -> None:
    """Create the twin collection with the cloned schema (idempotent: recreate the TWIN only)."""
    async with httpx.AsyncClient(timeout=60) as http:
        # delete the twin if it exists (twin is disposable; live is never touched)
        await http.delete(f"{qurl}/collections/{TWIN_COLLECTION}", headers=headers)
        body = {"vectors": schema["vectors"], "sparse_vectors": schema["sparse_vectors"]}
        r = await http.put(f"{qurl}/collections/{TWIN_COLLECTION}", json=body, headers=headers)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"create twin failed: {r.status_code} {r.text[:300]}")
        logger.info(f"Created twin {TWIN_COLLECTION} with schema {json.dumps(schema)[:200]}")


async def upsert_twin(qurl: str, headers: dict, points: list[dict]) -> None:
    async with httpx.AsyncClient(timeout=120) as http:
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            r = await http.put(
                f"{qurl}/collections/{TWIN_COLLECTION}/points?wait=true",
                json={"points": batch},
                headers=headers,
            )
            if r.status_code != 200:
                logger.error(f"upsert batch {i} failed: {r.status_code} {r.text[:300]}")
                raise RuntimeError("upsert failed")
            logger.info(f"  upserted {i}-{i + len(batch)}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="limit codes (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    qurl = os.environ["QDRANT_URL"].rstrip("/")
    qkey = os.environ.get("QDRANT_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if qkey:
        headers["api-key"] = qkey

    if not SOURCE_FILE.exists():
        logger.error(f"source missing: {SOURCE_FILE}")
        sys.exit(1)

    source = json.load(open(SOURCE_FILE, encoding="utf-8"))
    entries = source["data"]
    # only 5-digit kelompok carry the per_skala + L4 detail that the RAG queries
    entries = [e for e in entries if len(str(e.get("kode_kbli_2025", ""))) == 5]
    if args.limit:
        entries = entries[: args.limit]
    logger.info(f"Source: {SOURCE_FILE}")
    logger.info(f"5-digit codes to index: {len(entries)}")

    indexed_at = datetime.now(timezone.utc).isoformat()
    all_points = []
    for e in entries:
        code = e["kode_kbli_2025"]
        text = build_embedding_text(e)
        payload = build_payload(e, text)
        payload["indexed_at"] = indexed_at
        payload["collection_origin"] = "oss_twin"
        all_points.append({"id": deterministic_uuid(code), "payload": payload, "_text": text})

    l4 = sum(1 for p in all_points if p["payload"]["has_bali_l4"])
    blocked = sum(1 for p in all_points if p["payload"]["bali_blocked"])
    logger.info(f"L4 coverage: {l4}/{len(all_points)} have Bali status, {blocked} blocked in Bali")

    if args.dry_run:
        logger.info("DRY RUN — no Qdrant writes. Sample:")
        for p in all_points[:2]:
            pl = p["payload"]
            logger.info(f"  {pl['kode']} {pl['judul'][:40]} | PMA={pl['pma_status']} | Bali={pl['bali_status']}")
        return

    # 1. clone schema + create twin (live untouched)
    schema = await get_live_schema(qurl, headers)
    await create_twin(qurl, headers, schema)

    # 2. embed (dense) + bm25 (sparse)
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    texts = [p["_text"] for p in all_points]
    logger.info(f"Embedding {len(texts)} texts ({EMBEDDING_MODEL})...")
    embeddings = await embed_texts(texts, client)
    logger.info(f"Got {len(embeddings)} dense vectors (dim={len(embeddings[0])})")

    bm25 = BM25Vectorizer()
    tok_lens = [len(bm25.tokenize(t)) for t in texts]
    bm25.update_avg_doc_length(sum(tok_lens) / len(tok_lens))
    sparse = [bm25.generate_sparse_vector(t) for t in texts]
    logger.info(f"Generated {len(sparse)} bm25 sparse vectors")

    # 3. upsert into twin
    qdrant_points = []
    for p, emb, sp in zip(all_points, embeddings, sparse, strict=False):
        qdrant_points.append(
            {"id": p["id"], "vector": {"dense": emb, "bm25": sp}, "payload": p["payload"]},
        )
    logger.info(f"Upserting {len(qdrant_points)} points into {TWIN_COLLECTION}...")
    await upsert_twin(qurl, headers, qdrant_points)

    # 4. verify twin count + that live is still intact
    async with httpx.AsyncClient(timeout=30) as http:
        rt = await http.get(f"{qurl}/collections/{TWIN_COLLECTION}", headers=headers)
        rl = await http.get(f"{qurl}/collections/{LIVE_COLLECTION}", headers=headers)
        tc = rt.json()["result"]["points_count"]
        lc = rl.json()["result"]["points_count"]
        logger.info(f"TWIN {TWIN_COLLECTION}: {tc} points")
        logger.info(f"LIVE {LIVE_COLLECTION}: {lc} points (must be UNCHANGED — 4624 baseline)")
    logger.info("Done. Live untouched. Twin ready for verification bombardment.")


if __name__ == "__main__":
    asyncio.run(main())
