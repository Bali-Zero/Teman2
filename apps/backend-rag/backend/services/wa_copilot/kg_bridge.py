"""WA Copilot S1.6 — KG Bridge module.

Links `whatsapp_extractions` rows to `kg_nodes` entities, populating:
  - `whatsapp_entity_links` (extraction_id, entity_id, link_confidence, link_method)
  - `kg_entity_mentions` (collection_name='wa_messages', point_id=message_id, entity_id, mention_text, confidence, match_type)

Algorithm cascade per extraction:
  1. fact_type → kg_nodes.entity_type mapping (skip for fact_types without KG correspondence)
  2. Lookup candidate within mapped entity_types:
     - exact name match (LOWER(name)=LOWER(value)) → link_method='exact_alias' conf=0.95
     - fuzzy trgm similarity(name, value) >= 0.7 → link_method='fuzzy_alias' conf=similarity
     - else skip
  3. INSERT whatsapp_entity_links ON CONFLICT DO NOTHING
  4. INSERT kg_entity_mentions ON CONFLICT (entity_id, collection_name, point_id) DO UPDATE confidence if higher

CLI:
    python -m backend.services.wa_copilot.kg_bridge \\
        [--apply | --dry-run] \\
        [--batch-size 500] [--limit N] \\
        [--fact-types visa_type,kbli_code,dokumen] \\
        [--metrics-json /tmp/kg-bridge.json]

Reference:
  - S1.5 extraction_pipeline.py
  - whatsapp_entity_links schema: migration 200
  - kg_entity_mentions: UNIQUE (entity_id, collection_name, point_id)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping fact_type (whatsapp_extractions) -> entity_type (kg_nodes)
# ---------------------------------------------------------------------------
# kg_nodes.entity_type distribution (top 30, audit 2026-05-25):
#   dokumen 42245, kbli 13418, pasal 10162, izin_usaha 9462, biaya 9180,
#   undang_undang 3698, jangka_waktu 3653, peraturan_pemerintah 2843,
#   perizinan 2789, permen 1930, sanksi 1508, pt_pma 1421, perda 1323,
#   pt_pmdn 1269, perpres 673, proses 589, lembaga 575, vitas 413,
#   kitas 403, ...
# Note: 'visa_type' (extractions) maps to multiple kg entity_types
#       (vitas, kitas, permit_type, jangka_waktu) — we search all.
FACT_TYPE_TO_KG_ENTITY_TYPES: dict[str, tuple[str, ...]] = {
    "visa_type": ("vitas", "kitas", "permit_type", "jangka_waktu"),
    "kbli_code": ("kbli",),
    "kbli": ("kbli",),  # alias seen in extractions
    "dokumen": ("dokumen",),
    "document": ("dokumen",),
    "biaya": ("biaya", "ppn", "pph_21"),
    "jangka_waktu": ("jangka_waktu",),
    "izin_usaha": ("izin_usaha", "perizinan"),
    # Fact types without KG mapping — explicit skip list for observability
    # ("blocker", "team_commitment", "client_question", "intent")
}

# Confidence thresholds
EXACT_CONFIDENCE = 0.95
FUZZY_THRESHOLD = 0.70


@dataclass
class BridgeMetrics:
    """Aggregated counters for one bridge run."""

    extractions_total: int = 0
    extractions_processed: int = 0
    extractions_skipped_no_mapping: int = 0
    extractions_skipped_no_value: int = 0
    extractions_no_match: int = 0
    links_inserted: int = 0
    links_skipped_existing: int = 0
    mentions_inserted: int = 0
    mentions_updated: int = 0
    by_method: dict[str, int] = field(default_factory=dict)
    by_fact_type: dict[str, int] = field(default_factory=dict)
    sample_links: list[dict[str, Any]] = field(default_factory=list)
    wall_seconds: float = 0.0
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "extractions_total": self.extractions_total,
            "extractions_processed": self.extractions_processed,
            "extractions_skipped_no_mapping": self.extractions_skipped_no_mapping,
            "extractions_skipped_no_value": self.extractions_skipped_no_value,
            "extractions_no_match": self.extractions_no_match,
            "links_inserted": self.links_inserted,
            "links_skipped_existing": self.links_skipped_existing,
            "mentions_inserted": self.mentions_inserted,
            "mentions_updated": self.mentions_updated,
            "by_method": dict(self.by_method),
            "by_fact_type": dict(self.by_fact_type),
            "sample_links": list(self.sample_links),
            "wall_seconds": round(self.wall_seconds, 3),
            "dry_run": self.dry_run,
        }


def _extract_value(fact_value: Any) -> str | None:
    """Pull the canonical mention string from a fact_value JSON blob.

    fact_value examples (post-S1.5):
      {"value": "D12"}
      {"value": "850000 IDR"}
      {"for": "transfer", "value": "taxes"}
      {"value": "curriculum_vitae"}
    """
    if fact_value is None:
        return None
    if isinstance(fact_value, str):
        # asyncpg may return raw JSON string if no codec set; parse defensively
        try:
            fact_value = json.loads(fact_value)
        except (json.JSONDecodeError, TypeError):
            return fact_value.strip() or None
    if isinstance(fact_value, dict):
        v = fact_value.get("value")
        if isinstance(v, str):
            cleaned = v.strip()
            return cleaned or None
        if v is not None:
            return str(v)
    return None


def _normalize_for_match(value: str) -> str:
    """Normalize a value for matching: strip, collapse whitespace, lowercase.

    Also strips trailing snake_case underscores → space-form for fuzzy match,
    e.g. 'curriculum_vitae' -> 'curriculum vitae'.
    """
    v = value.strip().lower()
    # Replace underscores with spaces (qwen3.5 emits snake_case for documents)
    v = v.replace("_", " ")
    # Collapse multiple spaces
    v = " ".join(v.split())
    return v


def _make_mention_id(entity_id: str, collection_name: str, point_id: str) -> str:
    """Deterministic mention_id for kg_entity_mentions (PK is TEXT, no default)."""
    raw = f"{collection_name}|{point_id}|{entity_id}"
    return f"wa-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]}"


async def _lookup_entity(
    conn: asyncpg.Connection,
    value: str,
    entity_types: tuple[str, ...],
) -> dict[str, Any] | None:
    """Return best match (entity_id, name, entity_type, method, confidence)
    or None if no candidate within entity_types meets thresholds.

    Cascade:
      1. exact LOWER(name)=LOWER(:v) → method='exact_alias' conf=0.95
      2. similarity(name, :v) >= 0.7 ordered DESC LIMIT 1 → method='fuzzy_alias' conf=sim
    """
    needle = value.strip().lower()
    if not needle:
        return None

    # Exact match (case-insensitive)
    exact = await conn.fetchrow(
        """
        SELECT entity_id, name, entity_type
        FROM kg_nodes
        WHERE entity_type = ANY($1::text[])
          AND LOWER(name) = $2
        LIMIT 1
        """,
        list(entity_types),
        needle,
    )
    if exact:
        return {
            "entity_id": exact["entity_id"],
            "name": exact["name"],
            "entity_type": exact["entity_type"],
            "method": "exact_alias",
            "confidence": EXACT_CONFIDENCE,
        }

    # Fuzzy via pg_trgm
    norm = _normalize_for_match(value)
    fuzzy = await conn.fetchrow(
        """
        SELECT entity_id, name, entity_type,
               similarity(LOWER(name), $2) AS sim
        FROM kg_nodes
        WHERE entity_type = ANY($1::text[])
          AND LOWER(name) % $2
        ORDER BY sim DESC
        LIMIT 1
        """,
        list(entity_types),
        norm,
    )
    if fuzzy and fuzzy["sim"] is not None and fuzzy["sim"] >= FUZZY_THRESHOLD:
        return {
            "entity_id": fuzzy["entity_id"],
            "name": fuzzy["name"],
            "entity_type": fuzzy["entity_type"],
            "method": "fuzzy_alias",
            "confidence": round(float(fuzzy["sim"]), 4),
        }

    return None


async def _process_extraction(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    *,
    apply: bool,
    metrics: BridgeMetrics,
) -> None:
    """Process one extraction row: lookup KG entity, insert link + mention."""
    fact_type: str = row["fact_type"]
    fact_value = row["fact_value"]
    mention_text: str = row["mention_text"] or ""
    extraction_id: int = row["extraction_id"]
    message_id: int = row["message_id"]

    metrics.by_fact_type[fact_type] = metrics.by_fact_type.get(fact_type, 0)

    entity_types = FACT_TYPE_TO_KG_ENTITY_TYPES.get(fact_type)
    if not entity_types:
        metrics.extractions_skipped_no_mapping += 1
        return

    value = _extract_value(fact_value)
    if not value:
        metrics.extractions_skipped_no_value += 1
        return

    match = await _lookup_entity(conn, value, entity_types)
    if not match:
        metrics.extractions_no_match += 1
        return

    metrics.extractions_processed += 1
    metrics.by_fact_type[fact_type] += 1
    metrics.by_method[match["method"]] = metrics.by_method.get(match["method"], 0) + 1

    sample_payload = {
        "extraction_id": extraction_id,
        "fact_type": fact_type,
        "value": value,
        "matched_entity_id": match["entity_id"],
        "matched_name": match["name"],
        "matched_entity_type": match["entity_type"],
        "method": match["method"],
        "confidence": match["confidence"],
    }
    if len(metrics.sample_links) < 12:
        metrics.sample_links.append(sample_payload)

    if not apply:
        return

    # 1) whatsapp_entity_links
    link_result = await conn.execute(
        """
        INSERT INTO whatsapp_entity_links
            (extraction_id, entity_id, link_confidence, link_method)
        VALUES ($1, $2, $3::numeric, $4)
        ON CONFLICT (extraction_id, entity_id) DO NOTHING
        """,
        extraction_id,
        match["entity_id"],
        match["confidence"],
        match["method"],
    )
    # asyncpg.execute returns 'INSERT 0 N' where N is row count
    if link_result.endswith(" 1"):
        metrics.links_inserted += 1
    else:
        metrics.links_skipped_existing += 1

    # 2) kg_entity_mentions (collection_name='wa_messages', point_id=message_id)
    mention_id = _make_mention_id("wa_messages", str(message_id), match["entity_id"])
    mention_text_value = mention_text or value
    # UPSERT: insert; on conflict, update confidence only if new is higher
    mention_result = await conn.fetchrow(
        """
        INSERT INTO kg_entity_mentions
            (mention_id, entity_id, collection_name, point_id,
             mention_text, confidence, match_type)
        VALUES ($1, $2, 'wa_messages', $3, $4, $5, $6)
        ON CONFLICT (entity_id, collection_name, point_id) DO UPDATE
            SET confidence = GREATEST(
                kg_entity_mentions.confidence, EXCLUDED.confidence
            ),
                mention_text = CASE
                    WHEN EXCLUDED.confidence > kg_entity_mentions.confidence
                    THEN EXCLUDED.mention_text
                    ELSE kg_entity_mentions.mention_text
                END
        RETURNING (xmax = 0) AS inserted
        """,
        mention_id,
        match["entity_id"],
        str(message_id),
        mention_text_value,
        match["confidence"],
        match["method"],
    )
    if mention_result and mention_result["inserted"]:
        metrics.mentions_inserted += 1
    else:
        metrics.mentions_updated += 1


async def run_bridge(
    dsn: str,
    *,
    apply: bool,
    batch_size: int,
    limit: int | None,
    fact_type_filter: list[str] | None,
) -> BridgeMetrics:
    """Drive the full bridge pipeline."""
    metrics = BridgeMetrics(dry_run=not apply)
    t0 = time.monotonic()

    # PgBouncer-safe pool: 5 connections, statement_cache_size=0
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=5,
        statement_cache_size=0,
        max_inactive_connection_lifetime=60.0,
    )

    try:
        # Count total candidate extractions
        async with pool.acquire() as conn:
            where_clauses = ["fact_type = ANY($1::text[])"]
            mappable_types = list(FACT_TYPE_TO_KG_ENTITY_TYPES.keys())
            if fact_type_filter:
                mappable_types = [t for t in mappable_types if t in fact_type_filter]
                if not mappable_types:
                    logger.warning(
                        "fact_type filter %s yields zero mappable types",
                        fact_type_filter,
                    )
                    metrics.wall_seconds = time.monotonic() - t0
                    return metrics

            count_query = (
                "SELECT COUNT(*) FROM whatsapp_extractions WHERE "
                + " AND ".join(where_clauses)
            )
            total = await conn.fetchval(count_query, mappable_types)
            metrics.extractions_total = int(total or 0)
            logger.info(
                "kg_bridge candidates=%d (apply=%s batch=%d limit=%s)",
                metrics.extractions_total,
                apply,
                batch_size,
                limit,
            )

        # Iterate in batches via OFFSET pagination on extraction_id
        offset = 0
        remaining = limit if limit is not None else None
        while True:
            current_batch = batch_size
            if remaining is not None:
                if remaining <= 0:
                    break
                current_batch = min(batch_size, remaining)

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT extraction_id, message_id, fact_type, fact_value,
                           mention_text
                    FROM whatsapp_extractions
                    WHERE fact_type = ANY($1::text[])
                    ORDER BY extraction_id
                    LIMIT $2 OFFSET $3
                    """,
                    mappable_types,
                    current_batch,
                    offset,
                )

            if not rows:
                break

            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row in rows:
                        await _process_extraction(
                            conn, row, apply=apply, metrics=metrics
                        )

            offset += len(rows)
            if remaining is not None:
                remaining -= len(rows)

            logger.info(
                "kg_bridge progress offset=%d links_inserted=%d "
                "mentions_inserted=%d no_match=%d",
                offset,
                metrics.links_inserted,
                metrics.mentions_inserted,
                metrics.extractions_no_match,
            )

    finally:
        await pool.close()

    metrics.wall_seconds = time.monotonic() - t0
    return metrics


def _build_dsn() -> str:
    """Resolve DATABASE_URL from env (set by caller)."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL not set — source apps/backend-rag/.env first"
        )
    return dsn


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="backend.services.wa_copilot.kg_bridge",
        description="Link whatsapp_extractions to kg_nodes via "
        "exact + pg_trgm fuzzy alias",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write to DB")
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute matches without DB writes (default)",
    )
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--fact-types",
        type=str,
        default=None,
        help="Comma-separated list of fact_type to process",
    )
    p.add_argument("--metrics-json", type=str, default=None)
    p.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stderr,
    )

    apply = bool(args.apply)
    if not apply and not args.dry_run:
        logger.info("Neither --apply nor --dry-run given; defaulting to --dry-run")

    fact_types = (
        [s.strip() for s in args.fact_types.split(",") if s.strip()]
        if args.fact_types
        else None
    )

    dsn = _build_dsn()
    metrics = asyncio.run(
        run_bridge(
            dsn,
            apply=apply,
            batch_size=args.batch_size,
            limit=args.limit,
            fact_type_filter=fact_types,
        )
    )

    payload = metrics.as_dict()
    # Emit metrics JSON to stdout for downstream piping (jq, cron telemetry).
    # Golden Rule #8 carve-out: this is a CLI entrypoint, not library code —
    # stdout is the result channel, logger.* goes to stderr.
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    sys.stdout.flush()

    if args.metrics_json:
        try:
            with open(args.metrics_json, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            logger.info("metrics written to %s", args.metrics_json)
        except OSError as exc:
            logger.error("failed to write metrics-json %s: %s", args.metrics_json, exc)
            return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
