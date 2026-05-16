"""Tests for content hash dedup logic in the GARUDA pipeline."""

from __future__ import annotations

from datetime import datetime, timezone, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from zantara_media.indexer.drive_client import DriveFile
from zantara_media.indexer.pipeline import Pipeline, compute_content_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(
    file_id: str = "file_abc",
    name: str = "test.pdf",
    mime_type: str = "application/pdf",
    size: int = 1024,
    parents: list[str] | None = None,
    version: int = 1,
) -> DriveFile:
    return DriveFile(
        id=file_id,
        name=name,
        mime_type=mime_type,
        parents=parents or ["1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1"],
        size=size,
        modified_time=datetime(2024, 1, 1, tzinfo=UTC),
        version=version,
        trashed=False,
    )


def _make_pipeline(
    *,
    check_content_hash_return: str | None = None,
) -> tuple[Pipeline, MagicMock, MagicMock, MagicMock]:
    """Return (pipeline, embedder_mock, qdrant_mock, pg_mock)."""
    embedder = MagicMock()
    embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

    qdrant = MagicMock()
    qdrant.upsert = AsyncMock(return_value=None)

    pg = MagicMock()
    pg.check_content_hash = AsyncMock(return_value=check_content_hash_return)
    pg.upsert_index_record = AsyncMock(return_value=None)
    pg.mark_quarantined = AsyncMock(return_value=None)
    pg.mark_archived = AsyncMock(return_value=None)

    drive = MagicMock()
    drive.download_file = AsyncMock(return_value=b"%PDF-1.4 hello world content")

    pipeline = Pipeline(
        embedder=embedder,
        qdrant_writer=qdrant,
        postgres_writer=pg,
        drive_client=drive,
    )
    return pipeline, embedder, qdrant, pg


# ---------------------------------------------------------------------------
# Unit tests for compute_content_hash
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    def test_same_file_id_same_text_gives_same_hash(self) -> None:
        """Hash is deterministic: same inputs → same output."""
        h1 = compute_content_hash("file_abc", "hello world")
        h2 = compute_content_hash("file_abc", "hello world")
        assert h1 == h2

    def test_different_file_id_same_text_gives_different_hash(self) -> None:
        """file_id is part of hash so two files with same text → different hashes."""
        h1 = compute_content_hash("file_001", "same text prefix here")
        h2 = compute_content_hash("file_002", "same text prefix here")
        assert h1 != h2

    def test_same_file_id_different_text_gives_different_hash(self) -> None:
        h1 = compute_content_hash("file_abc", "text version A")
        h2 = compute_content_hash("file_abc", "text version B")
        assert h1 != h2

    def test_empty_text_is_handled(self) -> None:
        h = compute_content_hash("file_abc", "")
        assert isinstance(h, str) and len(h) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# Integration tests for Pipeline.index_file_safe — dedup path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_skips_when_duplicate_found() -> None:
    """When pg.check_content_hash returns an existing file_id, result is skipped_dedup."""
    pipeline, embedder, qdrant, pg = _make_pipeline(
        check_content_hash_return="existing_file_xyz"
    )
    file = _make_file()

    result = await pipeline.index_file_safe(file)

    assert result.status == "skipped_dedup"
    assert "existing_file_xyz" in (result.reason or "")
    # Neither embedder nor Qdrant should be called when we deduplicate
    embedder.embed_text.assert_not_called()
    qdrant.upsert.assert_not_called()
    pg.upsert_index_record.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_proceeds_when_no_duplicate() -> None:
    """When pg.check_content_hash returns None, file is fully indexed."""
    pipeline, embedder, qdrant, pg = _make_pipeline(
        check_content_hash_return=None
    )
    file = _make_file()

    result = await pipeline.index_file_safe(file)

    assert result.status == "indexed"
    embedder.embed_text.assert_called_once()
    qdrant.upsert.assert_called_once()
    pg.upsert_index_record.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_skips_oversized_file() -> None:
    """Files over SIZE_CAP_BYTES (500 MB) are skipped before any IO."""
    pipeline, embedder, qdrant, pg = _make_pipeline()
    file = _make_file(size=600_000_000)

    result = await pipeline.index_file_safe(file)

    assert result.status == "skipped_size"
    # No download, no extraction, no DB calls
    pipeline.drive.download_file.assert_not_called()
    qdrant.upsert.assert_not_called()
    pg.upsert_index_record.assert_not_called()
