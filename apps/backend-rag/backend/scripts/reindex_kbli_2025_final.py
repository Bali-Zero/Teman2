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

from dotenv import load_dotenv

from backend.core.collection_registry import resolve_collection_name

# Load apps/backend-rag/.env so QDRANT_URL / QDRANT_API_KEY / OPENAI_API_KEY are present
# even when this script is invoked directly (not via the FastAPI app). Path is derived
# from __file__ — backend/scripts/<this> → parents[2] == apps/backend-rag — so it works
# from any cwd. Without this the script silently fell back to localhost:6333 and aborted
# on a missing OPENAI_API_KEY (env had to be exported by hand). Existing env vars win
# (load_dotenv does not override), so CI / explicit exports still take precedence.
_BACKEND_RAG_ENV = Path(__file__).resolve().parents[2] / ".env"
if _BACKEND_RAG_ENV.exists():
    load_dotenv(_BACKEND_RAG_ENV)

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
    # CAP: some codes (e.g. 61108 telecom) carry 60+ per_skala entries whose verbatim
    # persyaratan/kewajiban blow the embedding text past the 8192-token limit of
    # text-embedding-3-small (observed 539k chars). The licensing detail is repetitive
    # across scale combinations; for SEMANTIC SEARCH the first N distinct entries carry
    # the signal. We cap to PER_SKALA_MAX entries and note the omission, so the embedding
    # stays under the model limit without losing the discriminating content.
    PER_SKALA_MAX = 12
    per_skala = entry.get("per_skala", [])
    if per_skala:
        parts.append("## Perizinan per Skala Usaha (PP 28/2025)")
        omitted = len(per_skala) - PER_SKALA_MAX
        for skala in per_skala[:PER_SKALA_MAX]:
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
        if omitted > 0:
            parts.append(
                f"(... {omitted} kombinasi skala/ruang-lingkup tambahan dengan pola "
                "perizinan serupa tidak ditampilkan di sini.)",
            )
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

    # L4 Bali sovereign-local status (moratorium 2026-05-13) — embed it so semantic
    # search surfaces the Bali block, not just the national PMA status.
    l4 = entry.get("l4_bali") or {}
    if l4.get("status"):
        parts.append("## Status PMA di Bali (L4 — moratorium provinsi)")
        if l4.get("blocked"):
            parts.append(
                "- DIBLOKIR untuk PMA di Bali: kegiatan risiko Rendah/Menengah-Rendah "
                "tidak dapat didaftarkan PT PMA di Provinsi Bali (moratorium 2026-05-13).",
            )
        parts.append(f"- Status Bali: {l4['status']}")
        if l4.get("reason"):
            parts.append(f"- Alasan: {l4['reason']}")
        parts.append(
            "- Catatan: status nasional (Perpres 10/2021) bisa TERBUKA 100% "
            "sementara di Bali diblokir — keduanya benar bersamaan.",
        )
        parts.append("")

    text = "\n".join(parts)
    # Final safety cap: text-embedding-3-small rejects inputs over 8192 tokens.
    # ~24000 chars is a conservative ceiling (mixed ID/EN ≈ 3 chars/token); the
    # PER_SKALA_MAX cap above keeps virtually every code well under this, but a
    # pathological uraian or ruang_lingkup must never abort the whole re-index.
    MAX_EMBED_CHARS = 20000
    if len(text) > MAX_EMBED_CHARS:
        text = text[:MAX_EMBED_CHARS].rsplit("\n", 1)[0] + "\n(... dipotong untuk batas panjang.)"
    return text


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

    # L4 Bali sovereign-local layer (flat fields — KBLI flat-payload golden rule).
    # National PMA openness (pma_status) != Bali registrability (bali_status).
    l4 = entry.get("l4_bali") or {}
    bali_status = l4.get("status", "")

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
        "version": "v8.1-final-l4-bali",
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
        # L4 Bali (flat) — sovereign-local status, moratorium 2026-05-13
        "bali_status": bali_status,
        "bali_blocked": bool(l4.get("blocked")),
        "bali_reason": l4.get("reason", ""),
        "has_bali_l4": bool(bali_status),
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


async def ensure_payload_indexes(qdrant_url: str, api_key: str | None):
    """Ensure the keyword payload indexes this script's filters depend on exist.

    delete_old_points() and verify_collection() filter/count on doc_type and
    metadata.doc_type; the kode_kbli index lets callers fetch a single code. Qdrant
    rejects a filtered count/delete on an UNINDEXED keyword field with
    'Index required but not found' — which silently aborted the delete step on a
    collection that had never been indexed. Creating an index is idempotent (a no-op
    if it already exists), so this is safe to run on every re-index.
    """
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    fields = ["doc_type", "metadata.doc_type", "kode_kbli"]
    async with httpx.AsyncClient(timeout=60) as http:
        for field in fields:
            resp = await http.put(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/index",
                params={"wait": "true"},
                json={"field_name": field, "field_schema": "keyword"},
                headers=headers,
            )
            if resp.status_code == 200:
                logger.info(f"  Payload index ready: {field}")
            else:
                # Already-exists or benign errors should not abort the re-index.
                logger.warning(f"  Index ensure for {field}: {resp.status_code} {resp.text[:120]}")


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

        # Count by doc_type.
        # Payloads are written FLAT (build_payload puts doc_type at top level, per the KBLI
        # flat-payload golden rule), but legacy points may still carry it nested under
        # `metadata.doc_type`. Match either, mirroring delete_old_points' dual-key filter —
        # otherwise this verify count returns 0 on a successful flat re-index (green-that-lies).
        for doc_type in ["kbli_bps", "kbli_gold"]:
            cr = await http.post(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points/count",
                json={
                    "filter": {
                        "should": [
                            {"key": "doc_type", "match": {"value": doc_type}},
                            {"key": "metadata.doc_type", "match": {"value": doc_type}},
                        ],
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
        "--dry-run",
        action="store_true",
        help="Parse and build but don't embed or upsert",
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="",
        help="Qdrant URL (default: from env or localhost)",
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
        payload["indexed_at"] = indexed_at  # flat payload (KBLI flat-payload golden rule)

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
            pl = p["payload"]  # flat payload
            logger.info(f"  Code: {pl['kode']}")
            logger.info(f"  Judul: {pl['judul'][:80]}")
            logger.info(f"  Sektor: {pl['sektor']}")
            logger.info(f"  PMA (national): {pl['pma_status']}")
            logger.info(f"  Bali (L4): {pl['bali_status']} (blocked={pl['bali_blocked']})")
            logger.info(f"  Scales: {pl['scales']}")
            logger.info(f"  Text preview: {p['_text_to_embed'][:300]}...")
            logger.info("")
        bali_blocked = sum(1 for p in all_points if p["payload"]["bali_blocked"])
        bali_l4 = sum(1 for p in all_points if p["payload"]["has_bali_l4"])
        logger.info(f"L4 coverage: {bali_l4}/{len(all_points)} have Bali status, {bali_blocked} blocked in Bali")
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

    # Step 3: Ensure payload indexes (delete/verify filters depend on them), then delete old points
    logger.info(f"\nStep 3: Ensuring payload indexes on {COLLECTION_NAME}...")
    await ensure_payload_indexes(qdrant_url, qdrant_api_key)
    if not args.skip_delete:
        logger.info(f"Step 3: Deleting old OSS_RBA_API points from {COLLECTION_NAME}...")
        await delete_old_points(qdrant_url, qdrant_api_key)
    else:
        logger.info("Step 3: Delete skipped (--skip-delete)")

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
