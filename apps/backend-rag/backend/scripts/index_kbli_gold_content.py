"""
Index KBLI 2025 Gold-Tier editorial content into kbli_2025_final Qdrant collection.

Reads gold content from apps/kbli-navigator/lib/kbli-gold-content.ts,
parses the TypeScript object, and upserts editorial chunks alongside
existing BPS + PP28/2025 + Ingub 6/2026 data.

Each gold code produces 1 point with a rich embedding text combining:
  - whatItMeans: plain-language explanation
  - whatYouNeed: licensing requirements by scale
  - whatChanged: 2020 -> 2025 transition details
  - baliContext: Bali-specific intelligence
  - youllAlsoNeed: related codes
  - tkaInfo: foreign worker position data

The point ID is deterministic (code-based) so re-runs are idempotent.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/index_kbli_gold_content.py [--dry-run]
"""

import argparse
import hashlib
import json
import logging
import os
import re
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
BATCH_SIZE = 20

GOLD_CONTENT_FILE = (
    Path(__file__).resolve().parents[4] / "apps" / "kbli-navigator" / "lib" / "kbli-gold-content.ts"
)

KBLI_DATA_FILE = (
    Path(__file__).resolve().parents[4] / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
)


def parse_gold_content_ts(filepath: Path) -> dict[str, dict]:
    """
    Parse the TypeScript gold content file into a Python dict.

    The file exports a Record<string, KBLIGoldContent> where each entry has:
    whatItMeans, whatYouNeed, whatChanged, baliContext, youllAlsoNeed,
    zantaraOpener, tkaInfo.
    """
    raw = filepath.read_text(encoding="utf-8")

    # Extract the object body between the first { and last }
    # The file has: export const KBLI_GOLD_CONTENT: Record<...> = { ... };
    start = raw.index("= {") + 2
    # Find the matching closing brace (last }; in file)
    end = raw.rindex("};")
    obj_str = raw[start : end + 1]

    # Convert TypeScript object to valid JSON-ish:
    # 1. Code keys: "56101": { ... } — already valid
    # 2. String values with template literals (`...`) — convert to regular strings
    # 3. Property names without quotes — add quotes
    # 4. Trailing commas — remove

    # Actually, this is complex TS. Let's use a regex-based extraction instead.
    entries = {}
    # Match each top-level code entry: "XXXXX": { ... }
    # We find code keys and extract their content sections
    code_pattern = re.compile(r'"(\d{5})"\s*:\s*\{', re.MULTILINE)

    positions = [(m.group(1), m.start(), m.end()) for m in code_pattern.finditer(obj_str)]

    for _i, (code, _, brace_start) in enumerate(positions):
        # Find the matching closing brace for this entry
        # Count braces from brace_start-1 (the opening {)
        depth = 1
        pos = brace_start
        while depth > 0 and pos < len(obj_str):
            ch = obj_str[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            pos += 1
        entry_str = obj_str[brace_start - 1 : pos]

        # Extract field values using regex
        entry = {}
        for field in [
            "whatItMeans",
            "whatYouNeed",
            "whatChanged",
            "baliContext",
            "youllAlsoNeed",
            "zantaraOpener",
        ]:
            # Match: fieldName: "...", or fieldName: `...`,
            # Handle multi-line strings with template literals
            pattern = (
                rf'{field}\s*:\s*(?:"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`|\'((?:[^\'\\]|\\.)*)\')'
            )
            m = re.search(pattern, entry_str, re.DOTALL)
            if m:
                val = m.group(1) or m.group(2) or m.group(3) or ""
                # Unescape
                val = val.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")
                entry[field] = val.strip()

        # Extract tkaInfo.insight if present
        tka_insight_match = re.search(
            r'insight\s*:\s*(?:"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)',
            entry_str,
            re.DOTALL,
        )
        if tka_insight_match:
            entry["tka_insight"] = (
                (tka_insight_match.group(1) or tka_insight_match.group(2) or "")
                .replace("\\n", "\n")
                .strip()
            )

        # Extract TKA positions
        tka_positions = []
        for pm in re.finditer(
            r'titleEn\s*:\s*"([^"]*)".*?titleId\s*:\s*"([^"]*)"', entry_str, re.DOTALL,
        ):
            tka_positions.append({"en": pm.group(1), "id": pm.group(2)})
        if tka_positions:
            entry["tka_positions"] = tka_positions

        if entry:
            entries[code] = entry

    return entries


def load_kbli_base_data(filepath: Path) -> dict[str, dict]:
    """Load base KBLI data (judul, sektor, PMA) for context enrichment."""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    lookup = {}
    for code in data.get("data", []):
        kode = code.get("kode_kbli_2025", "")
        lookup[kode] = {
            "judul": code.get("judul", ""),
            "uraian": code.get("uraian", ""),
            "pma_status": code.get("pma_status", ""),
            "pma_max_asing": code.get("pma_max_asing", ""),
            "sektor_id": code.get("sektor_id", ""),
        }
    return lookup


def build_embedding_text(code: str, gold: dict, base: dict) -> str:
    """
    Build rich embedding text for a gold KBLI code.

    Matches the [CONTEXT: ...] prefix pattern used by existing kbli_2025_final points.
    """
    judul = base.get("judul", "")
    base.get("sektor_id", "")

    parts = [
        f"[CONTEXT: KBLI 2025 - Gold Editorial - Kode {code} - {judul}]",
        "",
        f"# KBLI {code}: {judul}",
        "",
    ]

    if gold.get("zantaraOpener"):
        parts.append("## Quick Answer")
        parts.append(gold["zantaraOpener"])
        parts.append("")

    if gold.get("whatItMeans"):
        parts.append("## What It Means")
        parts.append(gold["whatItMeans"])
        parts.append("")

    if gold.get("whatYouNeed"):
        parts.append("## What You Need (Licensing)")
        parts.append(gold["whatYouNeed"])
        parts.append("")

    if gold.get("whatChanged"):
        parts.append("## What Changed (KBLI 2020 to 2025)")
        parts.append(gold["whatChanged"])
        parts.append("")

    if gold.get("baliContext"):
        parts.append("## Bali Context")
        parts.append(gold["baliContext"])
        parts.append("")

    if gold.get("youllAlsoNeed"):
        parts.append("## Related Codes You'll Also Need")
        parts.append(gold["youllAlsoNeed"])
        parts.append("")

    if gold.get("tka_positions"):
        parts.append("## Foreign Worker (TKA) Positions")
        for pos in gold["tka_positions"]:
            parts.append(f"- {pos['en']} ({pos['id']})")
        parts.append("")

    if gold.get("tka_insight"):
        parts.append(gold["tka_insight"])
        parts.append("")

    return "\n".join(parts)


def build_payload(code: str, gold: dict, base: dict, embedding_text: str) -> dict:
    """Build Qdrant payload matching existing kbli_2025_final schema."""
    description = gold.get("whatItMeans") or base.get("uraian", "")
    return {
        "text": embedding_text,
        "content": embedding_text,
        "kode": code,
        "kode_kbli": code,
        "kode_kbli_2025": code,
        "judul": base.get("judul", ""),
        "description": description,
        "prefix_2": code[:2],
        "prefix_3": code[:3],
        "digit_count": len(code),
        "sources": ["GOLD_EDITORIAL", "BPS_7_2025", "PP_28_2025"],
        "doc_type": "kbli_gold",
        "version": "GOLD_2026",
        "sektor": base.get("sektor_id", ""),
        "section": base.get("sektor_id", ""),
        "pma_status": base.get("pma_status", ""),
        "pma_max_asing": base.get("pma_max_asing", ""),
        "has_gold_content": True,
        "gold_fields": [k for k in gold if k not in ("tka_positions",)],
        "has_tka_info": bool(gold.get("tka_positions")),
        "tka_position_count": len(gold.get("tka_positions", [])),
        "indexed_at": "",  # filled at upsert time
    }


def deterministic_uuid(code: str) -> str:
    """Generate deterministic UUID from code for idempotent upserts."""
    key = f"kbli_gold_editorial::{code}"
    return str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))


async def embed_texts(texts: list[str], client) -> list[list[float]]:
    """Embed texts using OpenAI."""
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([d.embedding for d in response.data])
    return all_embeddings


async def upsert_to_qdrant(points: list[dict], qdrant_url: str, api_key: str | None):
    """Upsert points to Qdrant."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=120) as http:
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            resp = await http.put(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points",
                json={"points": batch},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error(f"Qdrant upsert failed: {resp.status_code} {resp.text[:300]}")
            else:
                logger.info(f"  Upserted batch {i}-{i + len(batch)} ({len(batch)} points)")


async def main():
    parser = argparse.ArgumentParser(description="Index KBLI gold content into kbli_2025_final")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qdrant-url", type=str, default="")
    args = parser.parse_args()

    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")

    logger.info(f"Gold content file: {GOLD_CONTENT_FILE}")
    logger.info(f"KBLI data file: {KBLI_DATA_FILE}")
    logger.info(f"Qdrant: {qdrant_url} -> {COLLECTION_NAME}")

    if not GOLD_CONTENT_FILE.exists():
        logger.error(f"Gold content file not found: {GOLD_CONTENT_FILE}")
        sys.exit(1)

    # Parse gold content
    logger.info("Parsing gold content from TypeScript...")
    gold_entries = parse_gold_content_ts(GOLD_CONTENT_FILE)
    logger.info(f"Parsed {len(gold_entries)} gold entries")

    # Load base KBLI data for enrichment
    base_data = {}
    if KBLI_DATA_FILE.exists():
        base_data = load_kbli_base_data(KBLI_DATA_FILE)
        logger.info(f"Loaded {len(base_data)} base KBLI codes for enrichment")

    # Build points
    indexed_at = datetime.now(timezone.utc).isoformat()
    all_points = []

    for code, gold in sorted(gold_entries.items()):
        base = base_data.get(code, {"judul": "", "sektor_id": ""})
        embedding_text = build_embedding_text(code, gold, base)
        payload = build_payload(code, gold, base, embedding_text)
        payload["metadata"]["indexed_at"] = indexed_at

        all_points.append(
            {
                "id": deterministic_uuid(code),
                "payload": payload,
                "_text_to_embed": embedding_text,
            },
        )

    logger.info(f"Built {len(all_points)} points to index")

    # Stats
    fields_count = {}
    for p in all_points:
        for f in p["payload"]["metadata"].get("gold_fields", []):
            fields_count[f] = fields_count.get(f, 0) + 1
    logger.info("Gold field coverage:")
    for f, n in sorted(fields_count.items(), key=lambda x: -x[1]):
        logger.info(f"  {f}: {n}/{len(all_points)} ({100 * n // len(all_points)}%)")

    tka_count = sum(1 for p in all_points if p["payload"]["metadata"]["has_tka_info"])
    logger.info(f"Codes with TKA info: {tka_count}/{len(all_points)}")

    if args.dry_run:
        logger.info("DRY RUN — sample points:")
        for p in all_points[:2]:
            logger.info(f"  Code: {p['payload']['metadata']['kode']}")
            logger.info(f"  Judul: {p['payload']['metadata']['judul'][:80]}")
            logger.info(f"  Text preview: {p['_text_to_embed'][:300]}...")
            logger.info("")
        logger.info(f"Would upsert {len(all_points)} gold points to {COLLECTION_NAME}")
        return

    # Embed
    from openai import AsyncOpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    client = AsyncOpenAI(api_key=openai_key)
    texts = [p["_text_to_embed"] for p in all_points]
    logger.info(f"Embedding {len(texts)} gold chunks...")
    embeddings = await embed_texts(texts, client)
    logger.info(f"Got {len(embeddings)} embeddings")

    # Build Qdrant points (named vectors: "dense" for this hybrid collection)
    qdrant_points = []
    for point, emb in zip(all_points, embeddings, strict=False):
        qdrant_points.append(
            {
                "id": point["id"],
                "vector": {"dense": emb},
                "payload": point["payload"],
            },
        )

    logger.info(f"Upserting {len(qdrant_points)} points...")
    await upsert_to_qdrant(qdrant_points, qdrant_url, qdrant_api_key)
    logger.info(f"Done. {len(qdrant_points)} gold editorial points indexed into {COLLECTION_NAME}.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
