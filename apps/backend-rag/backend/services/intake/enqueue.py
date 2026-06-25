"""Unified document-intake enqueue core (FASE 1B).

ZERO CRM writes. Only writes to `document_instances` + `intake_queue`.
PII stays 100% local (Law 2 / UU-PDP) — never call cloud LLMs here, never
ship document bytes off-box. This module computes content hashes and performs
idempotent INSERTs only.

Contract (migration 212, FASE 1A):
- document_instances: immutable blob registry, UNIQUE(blob_hash, pipeline_version).
- intake_queue: work queue, UNIQUE(intake_key) where
  intake_key = sha256("{source}|{source_ref}|{blob_hash}|{pipeline_version}").
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

# Current pipeline version (X7). Bump only with a re-index plan.
PIPELINE_VERSION = "intake-v1"

# Valid sources (mirrors CHECK constraints in migration 212).
VALID_SOURCES = frozenset({"whatsapp", "drive", "zoho"})

# intake_key separator (X7) — hashlib stdlib, "|" separator.
_KEY_SEP = "|"

# Streaming chunk size for blob hashing (avoid loading huge files in RAM).
_HASH_CHUNK = 1 << 20  # 1 MiB


@dataclass(frozen=True)
class EnqueueResult:
    """Outcome of an enqueue() call."""

    instance_id: int
    queue_id: int
    was_new: bool  # True iff a NEW intake_queue row was created this call.


def compute_blob_hash(blob_path: str | Path) -> str:
    """sha256 hex digest of a file's bytes, streamed in 1 MiB chunks."""
    h = hashlib.sha256()
    with open(blob_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_intake_key(
    source: str,
    source_ref: str,
    blob_hash: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    """intake_key = sha256("{source}|{source_ref}|{blob_hash}|{pipeline_version}") (X7)."""
    raw = _KEY_SEP.join((source, source_ref, blob_hash, pipeline_version))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def enqueue(
    pool: asyncpg.Pool,
    *,
    source: str,
    source_ref: str,
    blob_path: str | Path,
    client_id_hint: int | None = None,
    text_hash: str | None = None,
    phash: str | None = None,
    mime_type: str | None = None,
    blob_hash: str | None = None,
    byte_size: int | None = None,
    received_by: str | None = None,
    sender_phone: str | None = None,
    source_path: str | None = None,
    source_context: dict[str, object] | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> EnqueueResult:
    """Idempotently register a blob and enqueue it for processing.

    Steps (single transaction):
      1. sha256 the blob (unless caller supplied blob_hash).
      2. INSERT into document_instances ON CONFLICT(blob_hash, pipeline_version)
         DO NOTHING; on conflict, SELECT the existing id (exact cross-source dedup).
      3. Compute intake_key; INSERT into intake_queue ON CONFLICT(intake_key)
         DO NOTHING; on conflict, SELECT the existing id.

    Returns (instance_id, queue_id, was_new). was_new is True only when a fresh
    intake_queue row was created by THIS call.

    Reuses the caller's persistent asyncpg pool (Golden Rule #10 — never create
    a pool/AsyncClient in a loop). NO CRM tables touched.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid source {source!r}; must be one of {sorted(VALID_SOURCES)}")
    if not source_ref:
        raise ValueError("source_ref must be non-empty")

    blob_path_str = str(blob_path)
    if blob_hash is None:
        blob_hash = compute_blob_hash(blob_path)
    if byte_size is None:
        try:
            byte_size = os.path.getsize(blob_path)
        except OSError:
            byte_size = None

    intake_key = compute_intake_key(source, source_ref, blob_hash, pipeline_version)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. document_instances — idempotent on (blob_hash, pipeline_version).
            instance_id = await conn.fetchval(
                """
                INSERT INTO document_instances
                    (blob_hash, normalized_text_hash, phash, pipeline_version,
                     blob_path, byte_size, mime_type, first_source, first_source_ref)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (blob_hash, pipeline_version) DO NOTHING
                RETURNING id
                """,
                blob_hash, text_hash, phash, pipeline_version,
                blob_path_str, byte_size, mime_type, source, source_ref,
            )
            if instance_id is None:
                instance_id = await conn.fetchval(
                    """
                    SELECT id FROM document_instances
                    WHERE blob_hash = $1 AND pipeline_version = $2
                    """,
                    blob_hash, pipeline_version,
                )
            if instance_id is None:
                raise RuntimeError(
                    f"document_instances upsert failed for blob_hash={blob_hash[:12]}…"
                )

            # 2. intake_queue — idempotent on intake_key.
            #    received_by (m218) records the team member who RECEIVED the
            #    document (live-WhatsApp path only; NULL for drive/zoho/export).
            #    sender_phone (m225) records WHO SENT it (raw transport value;
            #    routing normalizes + matches it against clients.phone_normalized).
            #    source_path (m227) records WHERE the blob came from relative to
            #    the watched Drive root (folder name = client-name signal; NULL
            #    for whatsapp/zoho).
            #    source_context (m232) records PII-safe transport context such as
            #    WA mirror direct/group scope. It is NOT stage output and survives
            #    worker reprocess resets.
            queue_id = await conn.fetchval(
                """
                INSERT INTO intake_queue
                    (instance_id, source, source_ref, blob_path, blob_hash,
                     text_hash, phash, client_id_hint, received_by, sender_phone,
                     source_path, source_context, pipeline_version, intake_key)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14)
                ON CONFLICT (intake_key) DO NOTHING
                RETURNING id
                """,
                instance_id, source, source_ref, blob_path_str, blob_hash,
                text_hash, phash, client_id_hint, received_by, sender_phone,
                source_path, json.dumps(source_context or {}, sort_keys=True),
                pipeline_version, intake_key,
            )
            was_new = queue_id is not None
            if queue_id is None:
                queue_id = await conn.fetchval(
                    "SELECT id FROM intake_queue WHERE intake_key = $1",
                    intake_key,
                )
            if queue_id is None:
                raise RuntimeError(f"intake_queue upsert failed for intake_key={intake_key[:12]}…")

    logger.info(
        "enqueue source=%s ref=%s blob=%s instance=%s queue=%s new=%s",
        source, source_ref, blob_hash[:12], instance_id, queue_id, was_new,
    )
    return EnqueueResult(instance_id=instance_id, queue_id=queue_id, was_new=was_new)
