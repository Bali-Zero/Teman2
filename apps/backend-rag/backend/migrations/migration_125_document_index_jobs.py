"""Migration 125: document_index_jobs queue table.

Part of the CRM→Qdrant per-client document indexing pipeline. A job row is
enqueued when a document's OCR completes (crm_enhanced OCR-completed hook); an
indexer worker consumes pending jobs, reads the already-extracted OCR text
from `documents.ocr_extracted_data`, embeds the chunks, and upserts them into
the `client_documents` Qdrant collection with a flat `client_id` payload.

Idempotency is enforced at the DB level: UNIQUE(document_id, content_hash)
guarantees the same document content can never be enqueued twice. A changed
content_hash for the same document is a legitimate new job (re-index).

State machine (status column):
    pending      -> claimed by worker
    indexing     -> worker upserting to Qdrant
    indexed_active -> live, returned by retrieval
    soft_deleted -> document/client soft-deleted; hidden from retrieval but
                    NEVER physically dropped (evidence retention).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_index_jobs (
            id            BIGSERIAL PRIMARY KEY,
            document_id   BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            client_id     BIGINT NOT NULL,
            file_id       TEXT NOT NULL,
            content_hash  VARCHAR(64) NOT NULL,
            status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'indexing', 'indexed_active',
                                            'stale_reindex', 'soft_deleted', 'failed')),
            attempts      INT NOT NULL DEFAULT 0,
            error         TEXT DEFAULT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            indexed_at    TIMESTAMPTZ DEFAULT NULL,
            UNIQUE (document_id, content_hash)
        );
        """
    )

    # Worker claims pending/stale jobs cheaply.
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_index_jobs_claimable
        ON document_index_jobs (status, created_at)
        WHERE status IN ('pending', 'stale_reindex');
        """
    )

    # Retrieval/lifecycle lookups by client.
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_index_jobs_client
        ON document_index_jobs (client_id, status);
        """
    )

    logger.info("Migration 125 applied: document_index_jobs queue table + indexes")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_document_index_jobs_client;")
    await conn.execute("DROP INDEX IF EXISTS idx_document_index_jobs_claimable;")
    await conn.execute("DROP TABLE IF EXISTS document_index_jobs;")
    logger.info("Migration 125 rolled back: document_index_jobs dropped")
