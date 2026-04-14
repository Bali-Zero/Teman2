"""asyncpg connection pool + ON CONFLICT upsert for GARUDA indexer."""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class PostgresWriter:
    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=os.environ["DATABASE_URL"],
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def upsert_index_record(
        self,
        file_id: str,
        name: str,
        path: str,
        parent_folder: str,
        category: str,
        mime_type: str,
        size_bytes: int,
        modified_at: datetime,
        drive_version: int,
        extracted_text: str,
        description: str,
        tags: list[str],
        content_hash: str,
        metadata: dict,
    ) -> None:
        """Insert or update garuda_index record.

        Only called after Qdrant upsert succeeds (atomic ordering per spec).
        """
        pool = await self.get_pool()
        await pool.execute(
            """
            INSERT INTO garuda_index (
                file_id, name, path, parent_folder, category, mime_type,
                size_bytes, modified_at, drive_version, extracted_text,
                description, tags, content_hash, metadata, indexed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14::jsonb, NOW())
            ON CONFLICT (file_id) DO UPDATE SET
                name = EXCLUDED.name,
                path = EXCLUDED.path,
                modified_at = EXCLUDED.modified_at,
                drive_version = EXCLUDED.drive_version,
                extracted_text = EXCLUDED.extracted_text,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                content_hash = EXCLUDED.content_hash,
                metadata = EXCLUDED.metadata,
                indexed_at = NOW()
            """,
            file_id,
            name,
            path,
            parent_folder,
            category,
            mime_type,
            size_bytes,
            modified_at,
            drive_version,
            extracted_text[:50000] if extracted_text else "",
            description[:2000] if description else "",
            json.dumps(tags),
            content_hash,
            json.dumps(metadata),
        )

    async def check_content_hash(
        self,
        content_hash: str,
        exclude_file_id: str,
    ) -> Optional[str]:
        """Returns existing file_id if same content hash found (dedup check)."""
        pool = await self.get_pool()
        row = await pool.fetchrow(
            "SELECT file_id FROM garuda_index WHERE content_hash = $1 AND file_id != $2 LIMIT 1",
            content_hash,
            exclude_file_id,
        )
        return row["file_id"] if row else None

    async def mark_archived(self, file_id: str) -> None:
        """Mark file as archived (tombstone)."""
        pool = await self.get_pool()
        await pool.execute(
            "UPDATE garuda_index SET archived = TRUE, modified_at = NOW() WHERE file_id = $1",
            file_id,
        )

    async def mark_quarantined(self, file_id: str, quarantine_reason: dict) -> None:
        """Mark file as quarantined by DLP."""
        pool = await self.get_pool()
        await pool.execute(
            "UPDATE garuda_index SET quarantined = TRUE, quarantine_reason = $2::jsonb WHERE file_id = $1",
            file_id,
            json.dumps(quarantine_reason),
        )

    async def get_drive_version(self, file_id: str) -> Optional[int]:
        """Get stored drive_version for a file (for change detection)."""
        pool = await self.get_pool()
        row = await pool.fetchrow(
            "SELECT drive_version FROM garuda_index WHERE file_id = $1",
            file_id,
        )
        return row["drive_version"] if row else None
