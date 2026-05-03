"""
Re-index kbli_2025_final from KBLI_2025_FINAL_CLEAN.json (v8.0-final-complete).

Replaces old OSS_RBA_API data with definitive BPS 7/2025 + PP28/2025 data.
Preserves existing gold editorial points (doc_type=kbli_gold).

Data flow:
1. Load 1,563 codes from KBLI_2025_FINAL_CLEAN.json
2. Build rich embedding text per code (uraian + per_skala + PMA + intel_2026)
3. Generate dense embeddings (text-embedding-3-small, 1536 dims)
4. Generate BM25 sparse vectors (hash-based, vocab_size=30000)
5. Delete old OSS_RBA_API points (preserve gold editorial)
6. Upsert with named vectors {"dense": [...], "bm25": {...}}

Deterministic UUIDs ensure idempotent re-runs.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/reindex_kbli_2025_final.py --dry-run
    PYTHONPATH=. python backend/scripts/reindex_kbli_2025_final.py --qdrant-url http://localhost:16335
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core.collection_registry import resolve_collection_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
COLLECTION_NAME = resolve_collection_name("kbli_2025_final")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 20
UPSERT_BATCH_SIZE = 20
DELETE_BATCH_SIZE = 100

SOURCE_FILE = (
    Path(__file__).resolve().parents[4] / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
)


def deterministic_uuid(code: str) -> str:
    """Generate deterministic UUID from KBLI code for idempotent upserts."""
    key = f"kbli_2025_bps::{code}"
    return str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))


def build_embedding_text(entry: dict) -> str:
    """
    Build rich embedding text for a KBLI code.

    Combines BPS uraian, PP28 licensing detail, PMA status, and intel_2026
    into a single searchable text block with [CONTEXT:] prefix.
    """
    code = entry["kode_kbli_2025"]
    judul = entry.get("judul", "")
    uraian = entry.get("uraian", "")
    sektor = entry.get("sektor_id", "")
    pma_status = entry.get("pma_status", "")

    parts = [
        f"[CONTEXT: KBLI 2025 - BPS 7/2025 + PP28/2025 - Kode {code} - {judul}]",
        "",
        f"# KBLI {code}: {judul}",
        "",
    ]

    # BPS description (uraian)
    if uraian:
        parts.append("## Deskripsi (BPS)")
        parts.append(uraian)
        parts.append("")

    # Sektor
    if sektor:
        parts.append(f"**Sektor:** {sektor}")
        parts.append("")

    # PMA status
    if pma_status:
        pma_section = [f"## Status PMA: {pma_status}"]
        if entry.get("pma_max_asing"):
            pma_section.append(f"- Kepemilikan asing maksimal: {entry['pma_max_asing']}")
        if entry.get("pma_kondisi"):
            pma_section.append(f"- Kondisi: {entry['pma_kondisi']}")
        if entry.get("pma_prioritas"):
            pma_section.append(f"- Prioritas: {entry['pma_prioritas']}")
        if entry.get("pma_nota"):
            pma_section.append(f"- Nota: {entry['pma_nota']}")
        parts.extend(pma_section)
        parts.append("")

    # PP28/2025 licensing (per_skala)
    per_skala = entry.get("per_skala", [])
    if per_skala:
        parts.append("## Perizinan per Skala Usaha (PP 28/2025)")
        for skala in per_skala:
            skala_names = ", ".join(skala.get("skala_usaha", []))
            risiko = skala.get("kategori_risiko", "")
            perizinan = skala.get("perizinan", "")
            jangka = skala.get("jangka_waktu", "")

            parts.append(f"### Skala: {skala_names}")
            parts.append(f"- Kategori risiko: {risiko}")
            parts.append(f"- Perizinan: {perizinan}")
            if jangka:
                parts.append(f"- Jangka waktu: {jangka}")

            persyaratan = skala.get("persyaratan", [])
            if persyaratan:
                parts.append("- Persyaratan:")
                for req in persyaratan:
                    parts.append(f"  - {req}")

            kewajiban = skala.get("kewajiban", [])
            if kewajiban:
                parts.append("- Kewajiban:")
                for kew in kewajiban:
                    parts.append(f"  - {kew}")

            kewenangan = skala.get("kewenangan", "")
            if kewenangan:
                parts.append(f"- Kewenangan: {kewenangan}")

            fiktif = skala.get("fiktif_positif", False)
            if fiktif:
                parts.append("- Fiktif positif: Ya (otomatis jika tidak ditolak)")

            parts.append("")

    # Intel 2026 (Bali-specific intelligence)
    intel = entry.get("intel_2026")
    if intel:
        parts.append("## Intelligence 2026")
        if isinstance(intel, dict):
            for k, v in intel.items():
                if v:
                    parts.append(f"- {k}: {v}")
        elif isinstance(intel, str):
            parts.append(intel)
        parts.append("")

    return "\n".join(parts)


def build_payload(entry: dict, embedding_text: str) -> dict:
    """Build Qdrant payload matching the kbli_2025_final schema."""
    code = entry["kode_kbli_2025"]
    per_skala = entry.get("per_skala", [])

    # Extract scale names and risk levels
    scales = []
    risk_levels = set()
    for skala in per_skala:
        scales.extend(skala.get("skala_usaha", []))
        if skala.get("kategori_risiko"):
            risk_levels.add(skala["kategori_risiko"])

    description = entry.get("uraian", "")
    risk_category = next(iter(risk_levels), "")

    return {
        "text": embedding_text,
        "content": embedding_text,
        "kode": code,
        "kode_kbli": code,
        "kode_kbli_2025": code,
        "judul": entry.get("judul", ""),
        "description": description,
        "prefix_2": code[:2],
        "prefix_3": code[:3],
        "digit_count": len(code),
        "sources": ["BPS_7_2025", "PP_28_2025"],
        "doc_type": "kbli_bps",
        "version": "v8.0-final-complete",
        "sektor": entry.get("sektor_id", ""),
        "section": entry.get("sektor_id", ""),
        "pma_status": entry.get("pma_status", ""),
        "pma_max_asing": entry.get("pma_max_asing", ""),
        "has_per_skala": bool(per_skala),
        "scales": scales,
        "risk_levels": list(risk_levels),
        "kategori_risiko": risk_category,
        "has_intel_2026": bool(entry.get("intel_2026")),
        "has_gold_content": False,
        "status_mapping": entry.get("status_mapping", ""),
        "indexed_at": "",  # filled at upsert time
    }


async def embed_texts(texts: list[str], client) -> list[list[float]]:
    """Embed texts using OpenAI text-embedding-3-small."""
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([d.embedding for d in response.data])
        logger.info(f"  Embedded batch {i}-{i + len(batch)} ({len(batch)} texts)")
    return all_embeddings


async def delete_old_points(qdrant_url: str, api_key: str | None):
    """Delete old OSS_RBA_API points, preserving gold editorial points."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=120) as http:
        # Count old points first
        count_resp = await http.post(
            f"{qdrant_url}/collections/{COLLECTION_NAME}/points/count",
            json={
                "filter": {
                    "should": [
                        {"key": "doc_type", "match": {"value": "kbli_bps"}},
                        {"key": "metadata.doc_type", "match": {"value": "kbli_bps"}},
                    ],
                },
                "exact": True,
            },
            headers=headers,
        )
        if count_resp.status_code == 200:
            old_count = count_resp.json()["result"]["count"]
            logger.info(f"  Found {old_count} old (non-gold) points to delete")
        else:
            logger.warning(f"  Count failed: {count_resp.status_code}")
            old_count = 0

        if old_count == 0:
            logger.info("  No old points to delete")
            return

        # Delete by filter (all non-gold points)
        del_resp = await http.post(
            f"{qdrant_url}/collections/{COLLECTION_NAME}/points/delete",
            json={
                "filter": {
                    "should": [
                        {"key": "doc_type", "match": {"value": "kbli_bps"}},
                        {"key": "metadata.doc_type", "match": {"value": "kbli_bps"}},
                    ],
                },
            },
            headers=headers,
        )
        if del_resp.status_code == 200:
            logger.info(f"  Deleted {old_count} old points")
        else:
            logger.error(f"  Delete failed: {del_resp.status_code} {del_resp.text[:300]}")
            raise RuntimeError("Failed to delete old points")


async def upsert_to_qdrant(points: list[dict], qdrant_url: str, api_key: str | None):
    """Upsert points to Qdrant in batches."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=120) as http:
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            resp = await http.put(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points",
                json={"points": batch},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error(f"  Upsert batch {i} failed: {resp.status_code} {resp.text[:300]}")
            else:
                logger.info(f"  Upserted batch {i}-{i + len(batch)} ({len(batch)} points)")


async def verify_collection(qdrant_url: str, api_key: str | None):
    """Verify final collection state."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{qdrant_url}/collections/{COLLECTION_NAME}", headers=headers)
        if r.status_code == 200:
            info = r.json()["result"]
            total = info["points_count"]
            indexed = info["indexed_vectors_count"]
            logger.info(f"  Collection: {total} points, {indexed} indexed vectors")

        # Count by doc_type
        for doc_type in ["kbli_bps", "kbli_gold"]:
            cr = await http.post(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points/count",
                json={
                    "filter": {
                        "must": [{"key": "metadata.doc_type", "match": {"value": doc_type}}],
                    },
                    "exact": True,
                },
                headers=headers,
            )
            if cr.status_code == 200:
                count = cr.json()["result"]["count"]
                logger.info(f"  doc_type={doc_type}: {count} points")


async def main():
    parser = argparse.ArgumentParser(
        description="Re-index kbli_2025_final from KBLI_2025_FINAL_CLEAN.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and build but don't embed or upsert",
    )
    parser.add_argument(
        "--qdrant-url", type=str, default="", help="Qdrant URL (default: from env or localhost)",
    )
    parser.add_argument("--skip-delete", action="store_true", help="Skip deleting old points")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of codes (0=all)")
    args = parser.parse_args()

    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")

    # Try to get Qdrant key from environment or use known production key
    if not qdrant_api_key and "16335" in qdrant_url:
        # Fly proxy — try getting key from Qdrant app
        logger.warning("No QDRANT_API_KEY set. For fly proxy, set it or pass via env.")

    logger.info(f"Source: {SOURCE_FILE}")
    logger.info(f"Qdrant: {qdrant_url} -> {COLLECTION_NAME}")
    logger.info(f"Dry run: {args.dry_run}")

    if not SOURCE_FILE.exists():
        logger.error(f"Source file not found: {SOURCE_FILE}")
        sys.exit(1)

    # Load source data
    logger.info("Loading KBLI_2025_FINAL_CLEAN.json...")
    with open(SOURCE_FILE, encoding="utf-8") as f:
        source = json.load(f)

    version = source["metadata"]["version"]
    entries = source["data"]
    logger.info(f"Version: {version}")
    logger.info(f"Total codes: {len(entries)}")

    if args.limit > 0:
        entries = entries[: args.limit]
        logger.info(f"Limited to {args.limit} codes")

    # Build points
    logger.info("Building embedding texts and payloads...")
    indexed_at = datetime.now(timezone.utc).isoformat()
    all_points = []

    for entry in entries:
        code = entry["kode_kbli_2025"]
        embedding_text = build_embedding_text(entry)
        payload = build_payload(entry, embedding_text)
        payload["metadata"]["indexed_at"] = indexed_at

        all_points.append(
            {
                "id": deterministic_uuid(code),
                "payload": payload,
                "_text_to_embed": embedding_text,
            },
        )

    logger.info(f"Built {len(all_points)} points")

    # Statistics
    has_uraian = sum(1 for e in entries if e.get("uraian"))
    has_per_skala = sum(1 for e in entries if e.get("per_skala"))
    has_pma = sum(1 for e in entries if e.get("pma_status"))
    has_intel = sum(1 for e in entries if e.get("intel_2026"))
    logger.info("Data coverage:")
    logger.info(f"  uraian (BPS description): {has_uraian}/{len(entries)}")
    logger.info(f"  per_skala (PP28 licensing): {has_per_skala}/{len(entries)}")
    logger.info(f"  pma_status: {has_pma}/{len(entries)}")
    logger.info(f"  intel_2026: {has_intel}/{len(entries)}")

    # Text length stats
    text_lengths = [len(p["_text_to_embed"]) for p in all_points]
    avg_len = sum(text_lengths) / len(text_lengths)
    logger.info(
        f"  Avg text length: {avg_len:.0f} chars (min={min(text_lengths)}, max={max(text_lengths)})",
    )

    if args.dry_run:
        logger.info("\nDRY RUN - sample points:")
        for p in all_points[:2]:
            logger.info(f"  Code: {p['payload']['metadata']['kode']}")
            logger.info(f"  Judul: {p['payload']['metadata']['judul'][:80]}")
            logger.info(f"  Sektor: {p['payload']['metadata']['sektor']}")
            logger.info(f"  PMA: {p['payload']['metadata']['pma_status']}")
            logger.info(f"  Scales: {p['payload']['metadata']['scales']}")
            logger.info(f"  Text preview: {p['_text_to_embed'][:300]}...")
            logger.info("")
        logger.info(f"Would delete old OSS_RBA_API points and upsert {len(all_points)} new points")
        return

    # --- Real execution ---

    # Step 1: Generate dense embeddings
    from openai import AsyncOpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    client = AsyncOpenAI(api_key=openai_key)
    texts = [p["_text_to_embed"] for p in all_points]
    logger.info(f"\nStep 1: Embedding {len(texts)} texts with {EMBEDDING_MODEL}...")
    embeddings = await embed_texts(texts, client)
    logger.info(f"Got {len(embeddings)} embeddings (dims={len(embeddings[0])})")

    # Step 2: Generate BM25 sparse vectors
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.core.bm25_vectorizer import BM25Vectorizer

    bm25 = BM25Vectorizer()

    # Update avg doc length based on actual corpus
    token_lengths = [len(bm25.tokenize(t)) for t in texts]
    avg_tokens = sum(token_lengths) / len(token_lengths)
    bm25.update_avg_doc_length(avg_tokens)

    logger.info(f"\nStep 2: Generating BM25 sparse vectors (avg {avg_tokens:.0f} tokens/doc)...")
    sparse_vectors = [bm25.generate_sparse_vector(t) for t in texts]
    logger.info(f"Generated {len(sparse_vectors)} sparse vectors")

    # Step 3: Delete old points
    if not args.skip_delete:
        logger.info(f"\nStep 3: Deleting old OSS_RBA_API points from {COLLECTION_NAME}...")
        await delete_old_points(qdrant_url, qdrant_api_key)
    else:
        logger.info("\nStep 3: Skipped (--skip-delete)")

    # Step 4: Build final Qdrant points and upsert
    logger.info(f"\nStep 4: Upserting {len(all_points)} points...")
    qdrant_points = []
    for point, emb, sparse in zip(all_points, embeddings, sparse_vectors, strict=False):
        qdrant_points.append(
            {
                "id": point["id"],
                "vector": {
                    "dense": emb,
                    "bm25": sparse,
                },
                "payload": point["payload"],
            },
        )

    await upsert_to_qdrant(qdrant_points, qdrant_url, qdrant_api_key)

    # Step 5: Verify
    logger.info(f"\nStep 5: Verifying {COLLECTION_NAME}...")
    await verify_collection(qdrant_url, qdrant_api_key)

    logger.info(f"\nDone. {len(qdrant_points)} BPS codes re-indexed into {COLLECTION_NAME}.")
    logger.info("Gold editorial points preserved. Old OSS_RBA_API data replaced.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
