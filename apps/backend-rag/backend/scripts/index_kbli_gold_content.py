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
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core.collection_registry import resolve_collection_name
from backend.scripts._kbli_repo_root import resolve_repo_root
from backend.services.kbli_editorial_certification import (
    load_editorial_registry,
    matches_editorial_certification,
    with_neutral_kbli_chat_opener,
)
from backend.services.kbli_pma_disclosure import disclose_pma

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
COLLECTION_NAME = resolve_collection_name("kbli_2025_final")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 20
BATCH_SIZE = 20

# Repo root: robust resolver that works in both the dev checkout and the Fly
# container (where parents[4] raises IndexError — the layout is shallower).
# Honours KBLI_REPO_ROOT env override; otherwise walks up looking for the gold
# content marker file.
_REPO_ROOT = resolve_repo_root(
    ["apps/kbli-navigator/lib/kbli-gold-content.ts"],
    script_file=__file__,
)

GOLD_CONTENT_FILE = _REPO_ROOT / "apps" / "kbli-navigator" / "lib" / "kbli-gold-content.ts"

KBLI_DATA_FILE = _REPO_ROOT / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"

# 5-digit KBLI codes (e.g. "56101")
_CODE_RE = re.compile(r"^\d{5}$")
_CERTIFICATION_CONTENT_KEY = "_certification_content"

_NODE_LITERAL_TO_JSON = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(0, "utf8");
const value = vm.runInNewContext(`(${source})`, Object.create(null), { timeout: 5000 });
if (value === null || typeof value !== "object" || Array.isArray(value)) {
  throw new Error("KBLI gold literal did not evaluate to an object");
}
process.stdout.write(JSON.stringify(value));
"""


def parse_only_codes(raw: str | None) -> list[str] | None:
    """Parse the --only flag value into a list of validated 5-digit codes.

    Returns ``None`` when *raw* is falsy (flag not given).  Raises
    ``argparse.ArgumentTypeError`` on any malformed token so argparse surfaces
    a clean error — the caller never sees junk.
    """
    if not raw:
        return None
    codes: list[str] = []
    for token in raw.split(","):
        code = token.strip()
        if not _CODE_RE.match(code):
            raise argparse.ArgumentTypeError(
                f"invalid KBLI code {code!r} in --only — expected 5-digit numeric",
            )
        codes.append(code)
    if not codes:
        raise argparse.ArgumentTypeError("--only received no codes")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def filter_to_codes(
    entries: dict[str, dict],
    only_codes: list[str] | None,
) -> dict[str, dict]:
    """Filter *entries* to *only_codes*, erroring on any absent code.

    A silent skip would report success over nothing (esiste≠armato), so we exit
    nonzero naming every missing code instead.
    """
    if only_codes is None:
        return entries
    missing = [c for c in only_codes if c not in entries]
    if missing:
        logger.error(
            "--only requested code(s) absent from parsed gold: %s",
            ", ".join(missing),
        )
        sys.exit(1)
    return {c: entries[c] for c in only_codes}


def _extract_gold_object_literal(source: str) -> str:
    """Extract the exact top-level object while ignoring braces in prose."""
    marker = re.search(r"\bconst\s+KBLI_GOLD_CONTENT\b[^=]*=\s*\{", source)
    if marker is None:
        raise ValueError("KBLI_GOLD_CONTENT object declaration not found")
    start = source.find("{", marker.start())
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    pos = start
    while pos < len(source):
        char = source[pos]
        nxt = source[pos + 1] if pos + 1 < len(source) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                pos += 1
        elif quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and nxt == "/":
            line_comment = True
            pos += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            pos += 1
        elif char in ('"', "'", "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
        pos += 1
    raise ValueError("unterminated KBLI_GOLD_CONTENT object literal")


def _evaluate_gold_literal(literal: str) -> dict[str, dict]:
    """Use the image's pinned Node runtime to preserve exact JS string semantics."""
    if "${" in literal:
        raise ValueError("dynamic template interpolation is forbidden in certified gold content")
    node = os.environ.get("KBLI_NODE_BINARY") or shutil.which("node")
    if not node:
        raise RuntimeError("node is required to parse certified KBLI gold content")
    try:
        completed = subprocess.run(
            [node, "-e", _NODE_LITERAL_TO_JSON],
            input=literal,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("timed out parsing KBLI gold content") from exc
    if completed.returncode != 0:
        raise ValueError(f"Node could not parse KBLI gold content: {completed.stderr[:500]}")
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise ValueError("parsed KBLI gold content is not an object")
    return parsed


def parse_gold_content_ts(filepath: Path) -> dict[str, dict]:
    """Parse exact TS literals and retain an unmodified object for hash gating."""
    raw_entries = _evaluate_gold_literal(
        _extract_gold_object_literal(filepath.read_text(encoding="utf-8"))
    )
    entries: dict[str, dict] = {}
    for code, content in raw_entries.items():
        if not _CODE_RE.fullmatch(code) or not isinstance(content, dict):
            raise ValueError(f"invalid KBLI gold entry {code!r}")
        entry = dict(content)
        entry[_CERTIFICATION_CONTENT_KEY] = content
        tka = content.get("tkaInfo")
        if isinstance(tka, dict):
            insight = tka.get("insight")
            if isinstance(insight, str) and insight.strip():
                entry["tka_insight"] = insight.strip()
            positions = []
            raw_positions = tka.get("relevantPositions")
            if isinstance(raw_positions, list):
                for position in raw_positions:
                    if not isinstance(position, dict):
                        continue
                    title_en = position.get("titleEn")
                    title_id = position.get("titleId")
                    if isinstance(title_en, str) and isinstance(title_id, str):
                        positions.append({"en": title_en, "id": title_id})
            if positions:
                entry["tka_positions"] = positions
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
            "kode_kbli_2025": kode,
            "judul": code.get("judul", ""),
            "uraian": code.get("uraian", ""),
            "pma_status": code.get("pma_status", ""),
            "pma_max_asing": code.get("pma_max_asing"),
            "pma_verification_status": code.get("pma_verification_status", "declared_gap"),
            "pma_official_basis": code.get("pma_official_basis", ""),
            "pma_source_vintage": code.get("pma_source_vintage", ""),
            "pma_kondisi": code.get("pma_kondisi"),
            "pma_prioritas": code.get("pma_prioritas", False),
            "pma_nota": code.get("pma_nota"),
            "pma_source": code.get("pma_source"),
            "pma_cap_special": code.get("pma_cap_special", False),
            "pma_cap_verified": code.get("pma_cap_verified", False),
            "pma_route_to": code.get("pma_route_to"),
            "sektor_id": code.get("sektor_id", ""),
        }
    return lookup


def certification_content(gold: dict) -> dict:
    """Return the exact JS object, excluding parser-only derived fields."""
    content = gold.get(_CERTIFICATION_CONTENT_KEY)
    if isinstance(content, dict):
        return content
    return {
        key: value
        for key, value in gold.items()
        if key not in {_CERTIFICATION_CONTENT_KEY, "tka_insight", "tka_positions"}
    }


def disclosed_standalone_gold(
    code: str,
    gold: dict,
    base: dict,
    registry: dict | None = None,
) -> dict | None:
    """Return a reviewed gold block only while both exact hashes still match."""
    content = certification_content(gold)
    if not matches_editorial_certification("standaloneGold", code, base, content, registry):
        return None
    return with_neutral_kbli_chat_opener(code, gold)


def build_embedding_text(
    code: str,
    gold: dict,
    base: dict,
    registry: dict | None = None,
) -> str:
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

    certified_gold = disclosed_standalone_gold(code, gold, base, registry)
    if certified_gold is None:
        official_description = base.get("uraian", "")
        if official_description:
            parts.extend(["## Deskripsi (BPS)", official_description, ""])
        parts.extend(
            [
                "## Status PMA: NOT_VERIFIED",
                "- Gold editorial withheld: the exact content and PMA fingerprint are not in the reviewed registry.",
            ]
        )
        return "\n".join(parts)

    gold = certified_gold

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


def build_payload(
    code: str,
    gold: dict,
    base: dict,
    embedding_text: str,
    registry: dict | None = None,
) -> dict:
    """Build Qdrant payload matching existing kbli_2025_final schema."""
    official_description = base.get("uraian", "")
    certified_gold = disclosed_standalone_gold(code, gold, base, registry)
    editorial_disclosed = certified_gold is not None
    public_gold = certified_gold or {}
    pma = disclose_pma(base)
    return {
        "text": embedding_text,
        "content": embedding_text,
        "kode": code,
        "kode_kbli": code,
        "kode_kbli_2025": code,
        "judul": base.get("judul", ""),
        "official_description": official_description,
        "description": official_description,
        "prefix_2": code[:2],
        "prefix_3": code[:3],
        "digit_count": len(code),
        "sources": (
            ["GOLD_EDITORIAL", "BPS_7_2025", "PP_28_2025"]
            if editorial_disclosed
            else ["BPS_7_2025", "PP_28_2025"]
        ),
        "doc_type": "kbli_gold",
        "version": "GOLD_2026",
        "sektor": base.get("sektor_id", ""),
        "section": base.get("sektor_id", ""),
        "pma_status": pma["pma_status"],
        "pma_max_asing": pma["pma_max_asing"],
        "pma_verification_status": pma["pma_verification_status"],
        "pma_official_basis": pma["pma_official_basis"],
        "pma_source_vintage": pma["pma_source_vintage"],
        "pma_cap_special": pma["pma_cap_special"],
        "pma_cap_verified": pma["pma_cap_verified"],
        "has_gold_content": editorial_disclosed,
        "editorial_disclosed": editorial_disclosed,
        "gold_fields": [
            key
            for key in public_gold
            if key not in {_CERTIFICATION_CONTENT_KEY, "tka_insight", "tka_positions"}
        ],
        "has_tka_info": bool(public_gold.get("tka_positions")),
        "tka_position_count": len(public_gold.get("tka_positions", [])),
        "indexed_at": "",  # filled at upsert time
    }


def deterministic_uuid(code: str) -> str:
    """Generate deterministic UUID from code for idempotent upserts."""
    key = f"kbli_gold_editorial::{code}"
    return str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))


def build_point(
    code: str,
    gold: dict,
    base: dict,
    indexed_at: str,
    registry: dict | None = None,
) -> dict | None:
    """Build one Qdrant point (id + flat payload + text-to-embed) for a gold code.

    Extracted from the main() loop so it can be exercised directly by tests —
    never a recreated copy of the production logic (Codex review on #3817).
    """
    certified_gold = disclosed_standalone_gold(code, gold, base, registry)
    if certified_gold is None:
        return None
    embedding_text = build_embedding_text(code, gold, base, registry)
    payload = build_payload(code, gold, base, embedding_text, registry)
    payload["indexed_at"] = indexed_at  # flat payload (KBLI flat-payload golden rule)
    return {
        "id": deterministic_uuid(code),
        "payload": payload,
        "_text_to_embed": embedding_text,
    }


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
                raise RuntimeError("Failed to upsert certified KBLI gold points")
            else:
                logger.info(f"  Upserted batch {i}-{i + len(batch)} ({len(batch)} points)")


async def delete_existing_gold_points(
    point_ids: list[str],
    qdrant_url: str,
    api_key: str | None,
    *,
    sweep_owned: bool = False,
) -> None:
    """Retract this indexer's owned points before any replacement work.

    A full reconciliation first sweeps ``doc_type=kbli_gold`` so points removed
    from the current TypeScript source are still retracted.  Deterministic IDs
    are also deleted for the current (or ``--only`` selected) raw entries,
    covering legacy points that predate the ownership tag.  Both selectors are
    intentionally narrow and any failed delete aborts before embedding/upsert.
    """
    if not point_ids and not sweep_owned:
        return

    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    selectors: list[tuple[str, dict]] = []
    if sweep_owned:
        selectors.append(
            (
                "owned gold payloads",
                {
                    "filter": {
                        "must": [
                            {"key": "doc_type", "match": {"value": "kbli_gold"}},
                        ]
                    }
                },
            )
        )
    if point_ids:
        selectors.append(("deterministic gold IDs", {"points": point_ids}))

    async with httpx.AsyncClient(timeout=120) as http:
        for label, selector in selectors:
            response = await http.post(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points/delete",
                params={"wait": "true"},
                json=selector,
                headers=headers,
            )
            if response.status_code != 200:
                logger.error(
                    "Qdrant gold delete failed for %s: %s %s",
                    label,
                    response.status_code,
                    response.text[:300],
                )
                raise RuntimeError("Failed to delete legacy KBLI gold points")
            logger.info("  Retracted %s", label)


def field_coverage(all_points: list[dict]) -> dict[str, int]:
    """Count how many points carry each gold field (flat payload — the
    KBLI flat-payload golden rule; ``gold_fields`` lives directly on
    ``point["payload"]``, never under a nested sub-dict)."""
    fields_count: dict[str, int] = {}
    for p in all_points:
        for f in p["payload"].get("gold_fields", []):
            fields_count[f] = fields_count.get(f, 0) + 1
    return fields_count


def tka_total(all_points: list[dict]) -> int:
    """Count points flagged ``has_tka_info`` (flat payload)."""
    return sum(1 for p in all_points if p["payload"]["has_tka_info"])


def sample_lines(point: dict) -> list[str]:
    """Human-readable preview lines for one point (dry-run sample display).

    Returns plain strings — the caller is responsible for logging them.
    """
    payload = point["payload"]
    return [
        f"  Code: {payload['kode']}",
        f"  Judul: {payload['judul'][:80]}",
        f"  Text preview: {point['_text_to_embed'][:300]}...",
    ]


async def main():
    parser = argparse.ArgumentParser(description="Index KBLI gold content into kbli_2025_final")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qdrant-url", type=str, default="")
    parser.add_argument(
        "--only",
        type=parse_only_codes,
        default=None,
        metavar="CODE[,CODE...]",
        help="Comma-separated 5-digit KBLI codes — index ONLY these codes "
        "(errors out if any requested code is absent from the parsed gold).",
    )
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
    raw_gold_entries = parse_gold_content_ts(GOLD_CONTENT_FILE)
    total_parsed = len(raw_gold_entries)
    logger.info(f"Parsed {total_parsed} gold entries")

    # Selection is validated against the RAW source, not the certified subset.
    # An existing but now-uncertified --only code is a valid delete-only
    # reconciliation, while a code absent from the source remains an error.
    selected_raw_entries = filter_to_codes(raw_gold_entries, args.only)
    retraction_ids = [deterministic_uuid(code) for code in sorted(selected_raw_entries)]
    if args.only:
        logger.info(
            "%d of %d raw gold entries selected via --only",
            len(selected_raw_entries),
            total_parsed,
        )

    # Retraction is the first external publication action.  Missing OpenAI
    # credentials, certification drift, or an embedding failure after this
    # point can leave silence but can never leave stale uncertified prose live.
    if not args.dry_run:
        logger.info("Retracting owned/selected gold points before certification and embedding...")
        await delete_existing_gold_points(
            retraction_ids,
            qdrant_url,
            qdrant_api_key,
            sweep_owned=args.only is None,
        )

    # Load base KBLI data for enrichment
    base_data = {}
    if KBLI_DATA_FILE.exists():
        base_data = load_kbli_base_data(KBLI_DATA_FILE)
        logger.info(f"Loaded {len(base_data)} base KBLI codes for enrichment")

    registry = load_editorial_registry()

    # Publication is an allowlist over exact content + exact public PMA state,
    # not an allowlist over code names. Unsafe legacy entries are never turned
    # into points at all.
    certified_entries = {
        code: gold
        for code, gold in selected_raw_entries.items()
        if disclosed_standalone_gold(code, gold, base_data.get(code, {}), registry) is not None
    }
    logger.info(
        "Certified %d/%d parsed gold entries for publication",
        len(certified_entries),
        len(selected_raw_entries),
    )

    gold_entries = certified_entries

    # Build points
    indexed_at = datetime.now(timezone.utc).isoformat()
    all_points = []

    for code, gold in sorted(gold_entries.items()):
        base = base_data.get(code, {"judul": "", "sektor_id": ""})
        point = build_point(code, gold, base, indexed_at, registry)
        if point is None:  # defensive against registry/data drift during the run
            logger.error("certification changed while building KBLI %s", code)
            sys.exit(1)
        all_points.append(point)

    logger.info(f"Built {len(all_points)} points to index")

    # Stats
    fields_count = field_coverage(all_points)
    logger.info("Gold field coverage:")
    for f, n in sorted(fields_count.items(), key=lambda x: -x[1]):
        percentage = 100 * n // len(all_points) if all_points else 0
        logger.info(f"  {f}: {n}/{len(all_points)} ({percentage}%)")

    tka_count = tka_total(all_points)
    logger.info(f"Codes with TKA info: {tka_count}/{len(all_points)}")

    if args.dry_run:
        logger.info("DRY RUN — sample points:")
        for p in all_points[:2]:
            for line in sample_lines(p):
                logger.info(line)
            logger.info("")
        logger.info(f"Would upsert {len(all_points)} gold points to {COLLECTION_NAME}")
        logger.info(
            "Would retract %d selected deterministic IDs%s before publication",
            len(retraction_ids),
            " plus all doc_type=kbli_gold points" if args.only is None else "",
        )
        return

    if not all_points:
        logger.info("Delete-only reconciliation complete; no certified gold points to publish.")
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
    for point, emb in zip(all_points, embeddings, strict=True):
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
