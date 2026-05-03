#!/usr/bin/env python3
"""
KG extraction for 2026 laws — direct approach.
Bypasses dedup check (new collection, no duplicates possible).
Uses OpenAI gpt-4o-mini for entity/relationship extraction.
Saves directly to PostgreSQL kg_nodes + kg_edges.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL="postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable" \
    PYTHONPATH=. python scripts/kg_extract_2026_laws.py
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import asyncpg
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kg_2026")

QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_KEY = os.environ.get("QDRANT_API_KEY")
if not QDRANT_URL or not QDRANT_KEY:
    raise ValueError("Missing QDRANT_URL and/or QDRANT_API_KEY in environment")
COLLECTION = "legal_unified_2026"

EXTRACTION_PROMPT = """You are an Indonesian legal document analyst. Extract structured entities and relationships from this legal text.

Return ONLY a JSON object with this structure:
{{
  "entities": [
    {{"id": "unique_snake_case", "type": "undang_undang|permen|pp|pergub|pasal|kbli|izin_usaha|dokumen|biaya|lembaga|proses|persyaratan|sanksi", "name": "Human readable name", "description": "Brief description"}}
  ],
  "relationships": [
    {{"source": "entity_id", "target": "entity_id", "type": "REQUIRES|AMENDS|REFERENCES|PART_OF|HAS_FEE|HAS_DURATION|APPLIES_TO|PENALTY_FOR|ISSUED_BY|REGULATES"}}
  ]
}}

Text:
{text}

Return ONLY valid JSON."""


async def get_all_chunks() -> list[dict]:
    """Scroll all chunks from Qdrant."""
    chunks = []
    offset = None
    while True:
        payload = {"limit": 100, "with_payload": True}
        if offset:
            payload["offset"] = offset
        r = httpx.post(
            f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
            headers={"api-key": QDRANT_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        data = r.json()
        points = data.get("result", {}).get("points", [])
        next_offset = data.get("result", {}).get("next_page_offset")
        chunks.extend(points)
        if not next_offset:
            break
        offset = next_offset
    return chunks


async def extract_kg(openai: AsyncOpenAI, text: str) -> dict:
    """Extract entities and relationships using OpenAI."""
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:6000])}],
            temperature=0.1,
            max_tokens=2000,
        )
        content = response.choices[0].message.content.strip()
        # Clean JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Extraction error: {e}")
        return {"entities": [], "relationships": []}


async def save_to_db(
    db_pool: asyncpg.Pool,
    entities: list[dict],
    relationships: list[dict],
    chunk_id: str,
    collection_name: str,
):
    """Save extracted entities and relationships to PostgreSQL."""
    now = datetime.now(timezone.utc)
    entity_id_map = {}

    for entity in entities:
        eid = entity.get("id", "")
        if not eid:
            continue
        # Create deterministic UUID-like hash
        entity_hash = hashlib.md5(f"{collection_name}:{eid}".encode()).hexdigest()
        entity_id_map[eid] = entity_hash

        try:
            await db_pool.execute(
                """
                INSERT INTO kg_nodes (entity_id, entity_type, name, description,
                    confidence, source_collection, source_chunk_ids, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (entity_id) DO UPDATE SET
                    description = COALESCE(NULLIF(EXCLUDED.description, ''), kg_nodes.description),
                    source_chunk_ids = array_cat(kg_nodes.source_chunk_ids, EXCLUDED.source_chunk_ids),
                    updated_at = $9
                """,
                entity_hash,
                entity.get("type", "unknown"),
                entity.get("name", eid),
                entity.get("description", ""),
                0.9,  # Default confidence
                collection_name,
                [chunk_id],
                now,
                now,
            )
        except Exception as e:
            if "duplicate" not in str(e).lower():
                logger.warning(f"Entity save error: {e}")

    for rel in relationships:
        src = entity_id_map.get(rel.get("source"))
        tgt = entity_id_map.get(rel.get("target"))
        if not src or not tgt:
            continue
        rel_hash = hashlib.md5(f"{src}:{rel.get('type')}:{tgt}".encode()).hexdigest()

        try:
            await db_pool.execute(
                """
                INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id,
                    relationship_type, confidence, source_collection, source_chunk_ids, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (relationship_id) DO NOTHING
                """,
                rel_hash,
                src,
                tgt,
                rel.get("type", "RELATED"),
                0.9,
                collection_name,
                [chunk_id],
                now,
            )
        except Exception as e:
            if "duplicate" not in str(e).lower():
                logger.warning(f"Edge save error: {e}")


async def main():
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable",
    )

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def get_conn():
        """Get a fresh single connection (not pool — avoids Fly.io pool kill)."""
        ssl_ctx = "disable" if "sslmode=disable" in db_url else None
        kw = {}
        if ssl_ctx:
            kw["ssl"] = ssl_ctx
        return await asyncpg.connect(db_url, **kw)

    # Baseline
    conn = await get_conn()
    n0 = await conn.fetchval("SELECT count(*) FROM kg_nodes")
    e0 = await conn.fetchval("SELECT count(*) FROM kg_edges")
    await conn.close()
    logger.info(f"Baseline KG: {n0} nodes, {e0} edges")

    # Get all chunks from Qdrant
    logger.info(f"Fetching chunks from {COLLECTION}...")
    chunks = await get_all_chunks()
    logger.info(f"Total chunks: {len(chunks)}")

    valid = [(c["id"], c["payload"].get("text", "")) for c in chunks if c.get("payload", {}).get("text")]
    valid = [(cid, txt) for cid, txt in valid if len(txt) > 80]
    logger.info(f"Chunks with text > 80 chars: {len(valid)}")

    total_entities = 0
    total_rels = 0
    start = time.time()
    MICRO_BATCH = 3  # Small batch to avoid DB timeout

    for i in range(0, len(valid), MICRO_BATCH):
        batch = valid[i : i + MICRO_BATCH]

        # 1. Extract KG with OpenAI (parallel)
        tasks = [extract_kg(openai_client, txt) for _, txt in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Save to DB with fresh connection per micro-batch
        conn = None
        try:
            conn = await get_conn()
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                entities = result.get("entities", [])
                rels = result.get("relationships", [])
                if entities or rels:
                    chunk_id = str(batch[j][0])
                    now = datetime.now(timezone.utc)
                    # Save entities
                    for entity in entities:
                        eid = entity.get("id", "")
                        if not eid:
                            continue
                        entity_hash = hashlib.md5(f"{COLLECTION}:{eid}".encode()).hexdigest()
                        try:
                            await conn.execute(
                                "INSERT INTO kg_nodes (entity_id, entity_type, name, description, confidence, source_collection, source_chunk_ids, created_at, updated_at) "
                                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) "
                                "ON CONFLICT (entity_id) DO UPDATE SET description=COALESCE(NULLIF(EXCLUDED.description,''),kg_nodes.description), "
                                "source_chunk_ids=array_cat(kg_nodes.source_chunk_ids,EXCLUDED.source_chunk_ids), updated_at=$9",
                                entity_hash, entity.get("type","unknown"), entity.get("name",eid),
                                entity.get("description",""), 0.9, COLLECTION, [chunk_id], now, now,
                            )
                            total_entities += 1
                        except Exception:
                            pass
                    # Save relationships
                    for rel in rels:
                        src_hash = hashlib.md5(f"{COLLECTION}:{rel.get('source','')}".encode()).hexdigest()
                        tgt_hash = hashlib.md5(f"{COLLECTION}:{rel.get('target','')}".encode()).hexdigest()
                        rel_hash = hashlib.md5(f"{src_hash}:{rel.get('type')}:{tgt_hash}".encode()).hexdigest()
                        try:
                            await conn.execute(
                                "INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, "
                                "relationship_type, confidence, source_collection, source_chunk_ids, created_at) "
                                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (relationship_id) DO NOTHING",
                                rel_hash, src_hash, tgt_hash, rel.get("type","RELATED"),
                                0.9, COLLECTION, [chunk_id], now,
                            )
                            total_rels += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"DB error at batch {i}: {e}")
        finally:
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass

        # Progress log every 30 chunks
        processed = min(i + MICRO_BATCH, len(valid))
        if processed % 30 == 0 or processed == len(valid):
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (len(valid) - processed) / rate if rate > 0 else 0
            logger.info(
                f"Progress: {processed}/{len(valid)} ({processed*100//len(valid)}%) | "
                f"+{total_entities} entities, +{total_rels} rels | "
                f"{rate:.1f} c/s, ETA {eta/60:.1f}m"
            )

        # Small delay between batches to be gentle on DB
        await asyncio.sleep(0.5)

    # Final counts
    try:
        conn = await get_conn()
        n1 = await conn.fetchval("SELECT count(*) FROM kg_nodes")
        e1 = await conn.fetchval("SELECT count(*) FROM kg_edges")
        await conn.close()
    except Exception:
        n1, e1 = "?", "?"

    logger.info("=" * 60)
    logger.info("KG EXTRACTION COMPLETE")
    logger.info(f"Nodes: {n0} -> {n1} (+{total_entities} extracted)")
    logger.info(f"Edges: {e0} -> {e1} (+{total_rels} extracted)")
    logger.info(f"Time: {(time.time()-start)/60:.1f} minutes")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
