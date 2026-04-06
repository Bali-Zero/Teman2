"""
Migration 084: Create nlm_verification_log table

Stores discrepancies detected by the NLM async verification service
(nlm_verifier.py) for human review and model improvement.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL=<url> PYTHONPATH=. python backend/migrations/migration_084_nlm_verification_log.py

    # Dry run (shows DDL without executing):
    DATABASE_URL=<url> PYTHONPATH=. python backend/migrations/migration_084_nlm_verification_log.py --dry-run

    # Downgrade (drop table):
    DATABASE_URL=<url> PYTHONPATH=. python backend/migrations/migration_084_nlm_verification_log.py --downgrade
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIGRATION_ID: int = 84
MIGRATION_NAME: str = "nlm_verification_log"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS nlm_verification_log (
    id              SERIAL          PRIMARY KEY,
    query           TEXT            NOT NULL,
    zantara_answer  TEXT,
    nlm_answer      TEXT,
    domain          VARCHAR(50),
    evidence_score  FLOAT,
    discrepancy     TEXT,
    reviewed        BOOLEAN         DEFAULT FALSE,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
)
"""

_CREATE_IDX_DOMAIN = (
    "CREATE INDEX IF NOT EXISTS idx_nlm_verify_domain "
    "ON nlm_verification_log (domain)"
)

_CREATE_IDX_CREATED = (
    "CREATE INDEX IF NOT EXISTS idx_nlm_verify_created "
    "ON nlm_verification_log (created_at)"
)

_DROP_TABLE = "DROP TABLE IF EXISTS nlm_verification_log"


async def upgrade(pool: asyncpg.Pool) -> None:
    """Create nlm_verification_log table and indexes."""
    await pool.execute(_CREATE_TABLE)
    logger.info("Table nlm_verification_log created (or already exists)")

    await pool.execute(_CREATE_IDX_DOMAIN)
    logger.info("Index idx_nlm_verify_domain created")

    await pool.execute(_CREATE_IDX_CREATED)
    logger.info("Index idx_nlm_verify_created created")


async def downgrade(pool: asyncpg.Pool) -> None:
    """Drop nlm_verification_log table."""
    await pool.execute(_DROP_TABLE)
    logger.info("Table nlm_verification_log dropped")


async def _run(database_url: str, *, do_downgrade: bool, dry_run: bool) -> None:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
    try:
        if dry_run:
            if do_downgrade:
                logger.info("[DRY RUN] Would execute: %s", _DROP_TABLE)
            else:
                logger.info("[DRY RUN] Would execute:\n%s", _CREATE_TABLE)
                logger.info("[DRY RUN] Would execute: %s", _CREATE_IDX_DOMAIN)
                logger.info("[DRY RUN] Would execute: %s", _CREATE_IDX_CREATED)
            return

        if do_downgrade:
            await downgrade(pool)
        else:
            await upgrade(pool)

        logger.info("Migration %d (%s) complete.", MIGRATION_ID, MIGRATION_NAME)
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Migration {MIGRATION_ID}: {MIGRATION_NAME}"
    )
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Drop the table instead of creating it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print DDL statements without executing",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL env var is required")
        sys.exit(1)

    asyncio.run(_run(database_url, do_downgrade=args.downgrade, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
