"""Curated Q&A harvester (SPEC v2 D3, F1b).

Reads normalized JSONL rows from apps/backend-rag/data/curated_qa/*.jsonl
(schema documented in that directory's README.md) and writes them to two
independent sinks:

- --faq: the FAQ cache (Redis via NotebookLMCacheService), UNSCOPED keys
  (no notebook_id) — this is what orchestrator_core.check_faq_cache() reads
  via faq_cache.get(query). Provenance is enforced by
  NotebookLMCacheService.set() itself (P7): every row's metadata is required
  to carry source_ref/source_date/domain/confidence_class/source_priority.
- --qdrant: the curated_qa Qdrant collection (create-if-missing, 1536-dim
  Cosine), embedding the QUESTION with the frozen text-embedding-3-small,
  flat payload (no nested "metadata" dict — data invariant).

Question-only seeds (answer: null — prewarm/golden question banks with no
vetted answer yet) are silently SKIPPED for BOTH sinks: an FAQ/curated_qa
entry with no answer is meaningless and would violate the provenance
contract. They are still counted in the stats for coverage analysis.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/curated_qa_harvest.py --faq --qdrant
    PYTHONPATH=. python scripts/curated_qa_harvest.py --faq --dry-run
    PYTHONPATH=. python scripts/curated_qa_harvest.py --purge-domain visa --faq --qdrant

Do NOT run against prod without Zero's review of the batch being loaded —
this writes into the same FAQ cache / curated_qa collection the live
orchestrator reads from.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("curated_qa_harvest")

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _SCRIPT_DIR.parent / "data" / "curated_qa"

_CURATED_QA_COLLECTION_NAME = "curated_qa"
_CURATED_QA_VECTOR_SIZE = 1536
_CURATED_QA_DISTANCE = "Cosine"

REQUIRED_ROW_KEYS: tuple[str, ...] = (
    "question",
    "answer",
    "domain",
    "lang",
    "source_ref",
    "source_date",
    "confidence_class",
    "law_refs",
    "source_priority",
)


@dataclass
class HarvestStats:
    """Per-class-labeled summary — see docstring: "skip nothing silently"."""

    total_rows: int = 0
    invalid_rows: int = 0
    malformed_lines: int = 0

    faq_written: int = 0
    faq_answerless_skipped: int = 0
    faq_collision_refused: int = 0
    faq_failed: int = 0

    qdrant_written: int = 0
    qdrant_answerless_skipped: int = 0
    qdrant_failed: int = 0

    purged_faq: int = 0
    purged_qdrant: int = 0

    confidence_class_counts: dict[str, int] = field(default_factory=dict)

    def summary_lines(self) -> list[str]:
        lines = [
            f"total_rows={self.total_rows} invalid_rows={self.invalid_rows} "
            f"malformed_lines={self.malformed_lines}",
        ]
        if self.faq_written or self.faq_answerless_skipped or self.faq_failed:
            lines.append(
                f"FAQ: written={self.faq_written} "
                f"answerless_skipped={self.faq_answerless_skipped} "
                f"collision_refused={self.faq_collision_refused} "
                f"failed={self.faq_failed}",
            )
        if self.qdrant_written or self.qdrant_answerless_skipped or self.qdrant_failed:
            lines.append(
                f"Qdrant: written={self.qdrant_written} "
                f"answerless_skipped={self.qdrant_answerless_skipped} "
                f"failed={self.qdrant_failed}",
            )
        if self.purged_faq or self.purged_qdrant:
            lines.append(f"Purge: faq={self.purged_faq} qdrant={self.purged_qdrant}")
        if self.confidence_class_counts:
            counts = ", ".join(
                f"{k}={v}" for k, v in sorted(self.confidence_class_counts.items())
            )
            lines.append(f"confidence_class counts: {counts}")
        return lines


# ── Load + validate ──────────────────────────────────────────────────────────


def load_jsonl_rows(paths: list[Path]) -> tuple[list[dict], int]:
    """Read one or more .jsonl files. Returns (rows, malformed_line_count).

    Blank lines are skipped silently (not counted as malformed). A line that
    fails to parse as JSON is logged and counted, but does not abort the load
    — one bad batch file should not block every other file.
    """
    rows: list[dict] = []
    malformed = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                malformed += 1
                logger.error("Malformed JSONL line %s:%d — %s", path, line_no, e)
    return rows, malformed


def validate_row(row: dict) -> str | None:
    """Return an error message if `row` is missing a required schema key,
    else None. `answer: null` (question-only seed) is valid — see module
    docstring."""
    missing = [k for k in REQUIRED_ROW_KEYS if k not in row]
    if missing:
        return f"missing keys: {missing}"
    return None


def _row_provenance_metadata(row: dict) -> dict[str, Any]:
    return {
        "source_ref": row["source_ref"],
        "source_date": row["source_date"],
        "domain": row["domain"],
        "confidence_class": row["confidence_class"],
        "source_priority": row["source_priority"],
    }


# ── FAQ sink ─────────────────────────────────────────────────────────────────


async def harvest_to_faq(
    rows: list[dict],
    cache: Any,
    *,
    dry_run: bool = False,
    stats: HarvestStats | None = None,
) -> HarvestStats:
    """Write `rows` to the FAQ cache with UNscoped keys (notebook_id="").

    Answer-less rows (question-only seeds) are skipped — an FAQ entry with no
    answer would violate NotebookLMCacheService.set()'s provenance contract
    and is meaningless to serve.
    """
    stats = stats or HarvestStats()
    for row in rows:
        if row.get("answer") is None:
            stats.faq_answerless_skipped += 1
            continue

        metadata = _row_provenance_metadata(row)
        if dry_run:
            stats.faq_written += 1
            continue

        try:
            ok = await cache.set(row["question"], row["answer"], metadata=metadata)
        except ValueError as e:
            # Provenance contract violation — should not happen given
            # validate_row(), but never crash the batch on one bad row.
            stats.faq_failed += 1
            logger.error("FAQ set() rejected row %r: %s", row.get("question"), e)
            continue

        if ok:
            stats.faq_written += 1
        else:
            # False = either infra failure or collision-policy refusal.
            # NotebookLMCacheService logs the specific reason itself.
            stats.faq_collision_refused += 1

    return stats


async def purge_domain_faq(cache: Any, domain: str, *, dry_run: bool = False) -> int:
    """Delete every FAQ cache entry whose metadata.domain == `domain`.

    FAQ cache keys are opaque content hashes (MD5 of the normalized
    question) — there is no key-pattern that encodes domain, so this scans
    every key under the cache prefix and filters by decoded metadata. Not a
    hot path; purge is an operator/cron action, not a request-path call.
    """
    if not cache.redis_client:
        return 0

    to_delete: list[str] = []
    async for key in cache.redis_client.scan_iter(match=f"{cache.cache_prefix}*"):
        raw = await cache.redis_client.get(key)
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if entry.get("metadata", {}).get("domain") == domain:
            to_delete.append(key)

    if not dry_run:
        for key in to_delete:
            await cache.redis_client.delete(key)

    return len(to_delete)


# ── Qdrant sink ──────────────────────────────────────────────────────────────


async def ensure_qdrant_collection(qdrant_client: Any) -> bool:
    """Create the curated_qa collection if it doesn't exist yet.

    Returns True if a new collection was created, False if it already existed.
    """
    stats = await qdrant_client.get_stats()
    if not stats.get("error"):
        return False

    await qdrant_client.create_collection(
        vector_size=_CURATED_QA_VECTOR_SIZE,
        distance=_CURATED_QA_DISTANCE,
    )
    return True


def _stable_point_id(question: str) -> str:
    import hashlib
    import uuid

    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
    # Deterministic UUID5 from the digest — same question always maps to the
    # same point id, so re-running the harvester upserts in place.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


async def harvest_to_qdrant(
    rows: list[dict],
    qdrant_client: Any,
    embedder: Any,
    *,
    dry_run: bool = False,
    batch_size: int = 100,
    stats: HarvestStats | None = None,
) -> HarvestStats:
    """Embed the QUESTION of each row and upsert a flat payload into the
    curated_qa collection.

    Answer-less rows are skipped: the collection exists to serve
    grounding-injection evidence (orchestrator_core._inject_curated_qa_grounding),
    and an entry with no answer can never be used there — indexing it would
    only burn embedding cost and collection space for zero benefit. (They
    remain visible for coverage analysis via the FAQ-sink stats / the JSONL
    source files themselves.)
    """
    stats = stats or HarvestStats()

    answerable = [r for r in rows if r.get("answer") is not None]
    stats.qdrant_answerless_skipped += len(rows) - len(answerable)

    if dry_run:
        stats.qdrant_written += len(answerable)
        return stats

    for i in range(0, len(answerable), batch_size):
        batch = answerable[i : i + batch_size]
        questions = [r["question"] for r in batch]
        try:
            embeddings = await embedder.generate_embeddings(questions)
        except Exception as e:
            stats.qdrant_failed += len(batch)
            logger.error("Embedding generation failed for batch starting at %d: %s", i, e)
            continue

        metadatas = [
            {
                "answer": r["answer"],
                "domain": r["domain"],
                "lang": r["lang"],
                "source_ref": r["source_ref"],
                "source_date": r["source_date"],
                "confidence_class": r["confidence_class"],
                "law_refs": r["law_refs"],
                "source_priority": r["source_priority"],
            }
            for r in batch
        ]
        ids = [_stable_point_id(q) for q in questions]

        result = await qdrant_client.upsert_documents(
            chunks=questions,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
            flatten_payload=True,
        )
        if result.get("success"):
            stats.qdrant_written += len(batch)
        else:
            stats.qdrant_failed += len(batch)
            logger.error("Qdrant upsert failed for batch starting at %d: %s", i, result)

    return stats


async def purge_domain_qdrant(qdrant_client: Any, domain: str, *, dry_run: bool = False) -> int:
    """Delete every curated_qa point whose flat `domain` field == `domain`."""
    matches = await qdrant_client.scroll(limit=10_000, metadata_filter={"domain": domain})
    ids = [m["id"] for m in matches]

    if not dry_run and ids:
        await qdrant_client.delete(ids=ids)

    return len(ids)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _resolve_input_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_file():
            paths.append(p)
        elif p.is_dir():
            paths.extend(sorted(p.glob("*.jsonl")))
        else:
            paths.extend(sorted(Path().glob(pattern)))
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harvest curated Q&A JSONL into the FAQ cache and/or curated_qa Qdrant collection.",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        default=[str(_DEFAULT_DATA_DIR)],
        help="One or more .jsonl files, directories, or glob patterns (default: data/curated_qa/)",
    )
    parser.add_argument("--faq", action="store_true", help="Write to the FAQ cache (Redis)")
    parser.add_argument("--qdrant", action="store_true", help="Write to the curated_qa Qdrant collection")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    parser.add_argument(
        "--purge-domain",
        default=None,
        help="Delete every entry for this domain from the selected sink(s) instead of loading",
    )
    return parser.parse_args(argv)


async def main_async(args: argparse.Namespace) -> HarvestStats:
    stats = HarvestStats()

    if args.purge_domain:
        if args.faq:
            from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

            cache = NotebookLMCacheService()
            await cache.initialize()
            stats.purged_faq = await purge_domain_faq(cache, args.purge_domain, dry_run=args.dry_run)
        if args.qdrant:
            from backend.core.qdrant_db import QdrantClient

            client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)
            stats.purged_qdrant = await purge_domain_qdrant(
                client,
                args.purge_domain,
                dry_run=args.dry_run,
            )
        return stats

    paths = _resolve_input_paths(args.input)
    rows, malformed = load_jsonl_rows(paths)
    stats.malformed_lines = malformed
    stats.total_rows = len(rows)

    valid_rows: list[dict] = []
    for row in rows:
        error = validate_row(row)
        if error:
            stats.invalid_rows += 1
            logger.error("Invalid row %r: %s", row.get("question", "<unknown>"), error)
            continue
        valid_rows.append(row)
        confidence_class = str(row.get("confidence_class"))
        stats.confidence_class_counts[confidence_class] = (
            stats.confidence_class_counts.get(confidence_class, 0) + 1
        )

    if args.faq:
        from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

        cache = NotebookLMCacheService()
        await cache.initialize()
        await harvest_to_faq(valid_rows, cache, dry_run=args.dry_run, stats=stats)

    if args.qdrant:
        from backend.core.embeddings import create_embeddings_generator
        from backend.core.qdrant_db import QdrantClient

        client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)
        if not args.dry_run:
            await ensure_qdrant_collection(client)
        embedder = create_embeddings_generator(provider="openai")
        await harvest_to_qdrant(valid_rows, client, embedder, dry_run=args.dry_run, stats=stats)

    return stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    stats = asyncio.run(main_async(args))
    logger.info("=== Curated QA Harvest Summary ===")
    for line in stats.summary_lines():
        logger.info("  %s", line)


if __name__ == "__main__":
    main()
