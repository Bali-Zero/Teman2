"""
Golden Answers Refresh Script

Reads canonical questions from YAML, queries NLM notebooks for grounded answers,
and populates the golden_answers + query_clusters PostgreSQL tables.

Usage:
    cd apps/backend-rag && PYTHONPATH=. python scripts/golden_answers_refresh.py [--dry-run] [--domain visa]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import yaml
from dotenv import load_dotenv

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv(override=True)

# ── sys.path: add monorepo root so we can import apps.evaluator ──────────────
# Script lives at: apps/backend-rag/scripts/golden_answers_refresh.py
# Monorepo root is 3 levels up from the script.
_SCRIPT_DIR = Path(__file__).resolve().parent
_MONOREPO_ROOT = _SCRIPT_DIR.parent.parent.parent
if str(_MONOREPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_MONOREPO_ROOT))

# ── Deferred import of NLM bridge (needs monorepo root in path) ──────────────
try:
    from apps.evaluator.nlm_deep_research.nlm_bridge import (
        check_nlm_available,
        nlm_query,
    )
    NLM_AVAILABLE = True
except ImportError as _e:
    NLM_AVAILABLE = False
    _NLM_IMPORT_ERROR = str(_e)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
YAML_PATH = _SCRIPT_DIR / "golden_answers_questions.yaml"
RATE_LIMIT_SLEEP = 2  # seconds between NLM calls
NLM_TIMEOUT = 120  # seconds per query


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_cluster_id(question: str) -> str:
    """Deterministic cluster_id from question text (sha256[:16])."""
    return hashlib.sha256(question.strip().encode("utf-8")).hexdigest()[:16]


def make_query_hash(query_text: str) -> str:
    """MD5 of lowercased query text — matches GoldenAnswerService lookup."""
    return hashlib.md5(query_text.lower().strip().encode("utf-8")).hexdigest()


def load_questions(domain_filter: str | None = None) -> list[dict[str, Any]]:
    """Load canonical questions from YAML, optionally filtered by domain."""
    with open(YAML_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    questions: list[dict[str, Any]] = data.get("questions", [])

    if domain_filter:
        questions = [q for q in questions if q.get("domain") == domain_filter]

    return questions


def format_sources(sources_used: list[Any]) -> str:
    """Serialize sources to JSON string for DB storage."""
    return json.dumps(sources_used if sources_used else [])


def extract_confidence(nlm_result: dict[str, Any]) -> float:
    """
    Derive a confidence score from NLM result.

    NLM does not return a native confidence value, so we use heuristics:
    - sources_used count: more sources = higher confidence
    - answer length: longer = more grounded
    Capped at [0.50, 0.95].
    """
    sources_count = len(nlm_result.get("sources_used", []))
    answer_len = len(nlm_result.get("answer", ""))

    source_score = min(sources_count / 5.0, 1.0) * 0.4   # max 0.40
    length_score = min(answer_len / 500.0, 1.0) * 0.30   # max 0.30
    base = 0.50

    return round(min(base + source_score + length_score, 0.95), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

async def get_db_pool(database_url: str) -> asyncpg.Pool:
    """Create and return an asyncpg connection pool."""
    return await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=5,
        command_timeout=30,
    )


async def upsert_golden_answer(
    conn: asyncpg.Connection,
    cluster_id: str,
    canonical_question: str,
    answer: str,
    sources: str,
    confidence: float,
) -> None:
    """Upsert a row into golden_answers. Does NOT reset usage_count on conflict."""
    await conn.execute(
        """
        INSERT INTO golden_answers
            (cluster_id, canonical_question, answer, sources, confidence, usage_count, created_at, last_used_at)
        VALUES
            ($1, $2, $3, $4, $5, 0, $6, NULL)
        ON CONFLICT (cluster_id) DO UPDATE SET
            canonical_question = EXCLUDED.canonical_question,
            answer             = EXCLUDED.answer,
            sources            = EXCLUDED.sources,
            confidence         = EXCLUDED.confidence
        """,
        cluster_id,
        canonical_question,
        answer,
        sources,
        confidence,
        datetime.now(timezone.utc),
    )


async def upsert_query_cluster(
    conn: asyncpg.Connection,
    query_hash: str,
    cluster_id: str,
    query_text: str,
) -> None:
    """Upsert a row into query_clusters (idempotent)."""
    await conn.execute(
        """
        INSERT INTO query_clusters (query_hash, cluster_id, query_text)
        VALUES ($1, $2, $3)
        ON CONFLICT (query_hash) DO UPDATE SET
            cluster_id = EXCLUDED.cluster_id,
            query_text = EXCLUDED.query_text
        """,
        query_hash,
        cluster_id,
        query_text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Core logic
# ─────────────────────────────────────────────────────────────────────────────

async def process_question(
    question_entry: dict[str, Any],
    pool: asyncpg.Pool | None,
    dry_run: bool,
    index: int,
    total: int,
) -> str:
    """
    Process a single question entry.

    Returns:
        "success" | "failed" | "skipped"
    """
    question: str = question_entry["question"]
    nb_id: str = question_entry["nb_id"]
    aliases: list[str] = question_entry.get("aliases", [])
    domain: str = question_entry.get("domain", "unknown")
    cluster_id = make_cluster_id(question)

    prefix = f"[{index}/{total}] [{domain.upper()}]"

    if dry_run:
        logger.info(
            "[DRY RUN] %s cluster_id=%s | q=%s | aliases=%d",
            prefix,
            cluster_id,
            question[:80],
            len(aliases),
        )
        return "skipped"

    # ── Call NLM (synchronous → wrap for async) ───────────────────────────
    logger.info("%s Querying NLM notebook %s...", prefix, nb_id)
    try:
        result: dict[str, Any] = await asyncio.to_thread(
            nlm_query, nb_id, question, None, NLM_TIMEOUT
        )
    except Exception as exc:
        logger.error("%s NLM call raised exception: %s", prefix, exc)
        return "failed"

    if result.get("status") != "success" or not result.get("answer"):
        logger.warning(
            "%s NLM returned status=%s error=%s",
            prefix,
            result.get("status"),
            result.get("error", ""),
        )
        return "failed"

    answer: str = result["answer"]
    sources_str = format_sources(result.get("sources_used", []))
    confidence = extract_confidence(result)

    logger.info(
        "%s  answer=%d chars, sources=%d, confidence=%.2f",
        prefix,
        len(answer),
        len(result.get("sources_used", [])),
        confidence,
    )

    # ── Write to DB ────────────────────────────────────────────────────────
    assert pool is not None  # guaranteed when not dry_run
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Upsert golden answer
            await upsert_golden_answer(
                conn, cluster_id, question, answer, sources_str, confidence
            )

            # 2. Upsert canonical question → cluster mapping
            await upsert_query_cluster(
                conn, make_query_hash(question), cluster_id, question
            )

            # 3. Upsert each alias → same cluster
            for alias in aliases:
                await upsert_query_cluster(
                    conn, make_query_hash(alias), cluster_id, alias
                )

    logger.info(
        "%s  Saved cluster_id=%s + %d alias rows",
        prefix,
        cluster_id,
        len(aliases),
    )
    return "success"


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate golden_answers + query_clusters tables from YAML via NLM."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without calling NLM or writing to DB.",
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=["visa", "tax", "company", "property"],
        default=None,
        help="Filter questions by domain.",
    )
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    domain_filter: str | None = args.domain

    # ── Import guard ──────────────────────────────────────────────────────
    if not dry_run and not NLM_AVAILABLE:
        logger.error(
            "Could not import nlm_bridge: %s\n"
            "Make sure you are running from the monorepo root with PYTHONPATH=.\n"
            "Or add monorepo root to PYTHONPATH.",
            _NLM_IMPORT_ERROR,
        )
        sys.exit(1)

    # ── NLM availability check ────────────────────────────────────────────
    if not dry_run:
        logger.info("Checking NLM CLI availability...")
        if not check_nlm_available():
            logger.error(
                "nlm CLI not found or not responding. "
                "Install with: npm install -g notebooklm-mcp"
            )
            sys.exit(1)
        logger.info("NLM CLI available.")

    # ── Load questions ────────────────────────────────────────────────────
    questions = load_questions(domain_filter=domain_filter)
    total = len(questions)

    if total == 0:
        logger.warning("No questions found (domain_filter=%s).", domain_filter)
        return

    logger.info(
        "Loaded %d questions%s from %s",
        total,
        f" (domain={domain_filter})" if domain_filter else "",
        YAML_PATH,
    )

    # ── DB pool (skip in dry-run) ─────────────────────────────────────────
    pool: asyncpg.Pool | None = None
    if not dry_run:
        import os

        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL env var not set.")
            sys.exit(1)

        logger.info("Connecting to PostgreSQL...")
        pool = await get_db_pool(database_url)
        logger.info("PostgreSQL connected.")

    # ── Process each question ─────────────────────────────────────────────
    stats: dict[str, int] = {"success": 0, "failed": 0, "skipped": 0}

    for idx, entry in enumerate(questions, start=1):
        status = await process_question(
            question_entry=entry,
            pool=pool,
            dry_run=dry_run,
            index=idx,
            total=total,
        )
        stats[status] = stats.get(status, 0) + 1

        # Rate limit between NLM calls (only when actually calling)
        if not dry_run and idx < total:
            await asyncio.sleep(RATE_LIMIT_SLEEP)

    # ── Close pool ────────────────────────────────────────────────────────
    if pool:
        await pool.close()
        logger.info("PostgreSQL connection closed.")

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("GOLDEN ANSWERS REFRESH — COMPLETE")
    logger.info("  Total    : %d", total)
    logger.info("  Success  : %d", stats.get("success", 0))
    logger.info("  Failed   : %d", stats.get("failed", 0))
    logger.info("  Skipped  : %d", stats.get("skipped", 0))
    logger.info("  Dry-run  : %s", dry_run)
    logger.info("=" * 60)

    if stats.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
