"""CRM→Qdrant per-client document indexer.

Closes the chain: CRM client created → Drive folder mirrored → docs uploaded
→ OCR extracted (already in `documents.ocr_extracted_data`) → THIS module
embeds the extracted text and upserts it into the per-client-filtered
`client_documents` Qdrant collection, so the RAG can reason over a single
client's documents.

Substrate is internal Qdrant (Law-2 governed, our infra), NOT NotebookLM:
the council (2026-06-18) killed NLM-per-client on hard caps + consumer-account
PII boundary. NotebookLM stays for curated non-PII domain notebooks only.

Two dependency-injected units (conn / qdrant / embedder passed in) so they are
unit-testable without live Postgres/Qdrant/OpenAI:

- enqueue_index_job: idempotent insert into document_index_jobs.
- index_pending_job: read OCR text → chunk → embed → upsert → mark indexed.

PII isolation invariant: every Qdrant point payload carries `client_id`, so
retrieval filters by `client_id` and a query for client A can never surface
client B's chunks.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

CLIENT_DOCS_COLLECTION = "client_documents"
_MAX_CHUNK_CHARS = 1500


async def enqueue_index_job(
    conn: Any,
    document_id: int,
    client_id: int,
    file_id: str,
    content_hash: str,
) -> None:
    """Idempotently enqueue a document for indexing.

    ON CONFLICT (document_id, content_hash) DO NOTHING — re-running the OCR
    hook for the same content is a no-op; a changed content_hash is a new job.
    """
    await conn.execute(
        """
        INSERT INTO document_index_jobs
            (document_id, client_id, file_id, content_hash, status)
        VALUES ($1, $2, $3, $4, 'pending')
        ON CONFLICT (document_id, content_hash) DO NOTHING
        """,
        document_id,
        client_id,
        file_id,
        content_hash,
    )


def _chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _extract_ocr_text(ocr_extracted_data: Any) -> str:
    """Pull plain text out of the documents.ocr_extracted_data JSONB blob."""
    if not ocr_extracted_data:
        return ""
    if isinstance(ocr_extracted_data, dict):
        return str(ocr_extracted_data.get("text") or "").strip()
    return str(ocr_extracted_data).strip()


async def index_pending_job(
    conn: Any,
    qdrant: Any,
    embedder: Any,
    job: dict[str, Any],
) -> None:
    """Index one pending job: OCR text → embeddings → Qdrant → indexed_active."""
    job_id = job["id"]
    document_id = job["document_id"]
    client_id = job["client_id"]
    file_id = job["file_id"]
    content_hash = job["content_hash"]

    row = await conn.fetchrow(
        "SELECT ocr_extracted_data FROM documents WHERE id = $1",
        document_id,
    )
    text = _extract_ocr_text(row["ocr_extracted_data"] if row else None)
    chunks = _chunk_text(text)

    if not chunks:
        await conn.execute(
            "UPDATE document_index_jobs SET status = 'failed', "
            "error = 'empty_ocr_text', attempts = attempts + 1 WHERE id = $1",
            job_id,
        )
        logger.warning("client_doc_indexer: empty OCR text for document %s", document_id)
        return

    embeddings = await embedder.generate_embeddings(chunks)

    ids = [
        hashlib.sha256(f"{file_id}:{content_hash}:{i}".encode()).hexdigest()
        for i in range(len(chunks))
    ]
    metadatas = [
        {
            "client_id": client_id,
            "document_id": document_id,
            "file_id": file_id,
            "content_hash": content_hash,
            "chunk_index": i,
            "state": "indexed_active",
        }
        for i in range(len(chunks))
    ]

    await qdrant.upsert_documents(
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
        flatten_payload=True,
    )

    await conn.execute(
        "UPDATE document_index_jobs SET status = 'indexed_active', "
        "indexed_at = NOW(), attempts = attempts + 1 WHERE id = $1",
        job_id,
    )
    logger.info(
        "client_doc_indexer: indexed document %s for client %s (%d chunks)",
        document_id,
        client_id,
        len(chunks),
    )


async def search_client_documents(
    qdrant: Any,
    embedder: Any,
    client_id: int,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve a single client's document chunks for a natural-language query.

    PII isolation invariant: the Qdrant filter ALWAYS carries `client_id` and
    `state='indexed_active'`, so a query scoped to client A can never surface
    client B's chunks. This filter is the sole boundary — never relax it.
    """
    query = (query or "").strip()
    if not query:
        return []

    query_embedding = await embedder.generate_single_embedding(query)
    response = await qdrant.search(
        query_embedding=query_embedding,
        filter={"client_id": client_id, "state": "indexed_active"},
        limit=limit,
    )
    if isinstance(response, dict):
        return response.get("results", [])
    return response or []
