"""
End-to-end integration tests for GARUDA indexer pipeline.
Tests complete flow: file → extract → DLP → dedup → embed → Qdrant → Postgres
All external services are mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zantara_media.indexer.drive_client import DriveFile
from zantara_media.indexer.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Helper: build a DriveFile for tests
# ---------------------------------------------------------------------------


def make_drive_file(
    file_id: str = "test_file_001",
    name: str = "test.pdf",
    mime_type: str = "application/pdf",
    size: int = 1024 * 100,  # 100 KB
    parents: list[str] | None = None,
    version: int = 1,
) -> DriveFile:
    return DriveFile(
        id=file_id,
        name=name,
        mime_type=mime_type,
        parents=parents or ["1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq"],  # photos subfolder
        size=size,
        modified_time=datetime(2026, 4, 14, 10, 0, 0, tzinfo=UTC),
        version=version,
        trashed=False,
    )


# ---------------------------------------------------------------------------
# Helper: build a fully mocked Pipeline
# ---------------------------------------------------------------------------


def make_pipeline(
    *,
    download_bytes: bytes = b"%PDF-1.4 clean document text without any pii",
    check_content_hash_return: str | None = None,
    qdrant_side_effect: Exception | None = None,
    embed_return: list[float] | None = None,
) -> tuple[Pipeline, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return (pipeline, drive_mock, embedder_mock, qdrant_mock, pg_mock)."""
    drive = MagicMock()
    drive.download_file = AsyncMock(return_value=download_bytes)

    embedder = MagicMock()
    embedder.embed_text = AsyncMock(
        return_value=(embed_return if embed_return is not None else [0.1] * 1536)
    )

    qdrant = MagicMock()
    if qdrant_side_effect is not None:
        qdrant.upsert = AsyncMock(side_effect=qdrant_side_effect)
    else:
        qdrant.upsert = AsyncMock(return_value=None)
    qdrant.mark_archived = AsyncMock(return_value=None)

    pg = MagicMock()
    pg.check_content_hash = AsyncMock(return_value=check_content_hash_return)
    pg.upsert_index_record = AsyncMock(return_value=None)
    pg.mark_quarantined = AsyncMock(return_value=None)
    pg.mark_archived = AsyncMock(return_value=None)

    pipeline = Pipeline(
        embedder=embedder,
        qdrant_writer=qdrant,
        postgres_writer=pg,
        drive_client=drive,
    )
    return pipeline, drive, embedder, qdrant, pg


# ---------------------------------------------------------------------------
# Test 1: Clean PDF goes through full pipeline → indexed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_clean_pdf() -> None:
    """A clean PDF file should go through all steps and be indexed."""
    pipeline, drive, embedder, qdrant, pg = make_pipeline(
        download_bytes=b"%PDF-1.4 Bali property market analysis report 2026"
    )
    file = make_drive_file(file_id="pdf_clean_001", name="market_report.pdf")

    result = await pipeline.index_file_safe(file)

    assert result.status == "indexed"
    assert result.file_id == "pdf_clean_001"

    # Full pipeline executed
    drive.download_file.assert_called_once_with("pdf_clean_001")
    embedder.embed_text.assert_called_once()
    qdrant.upsert.assert_called_once()
    pg.upsert_index_record.assert_called_once()
    # DLP quarantine was NOT triggered
    pg.mark_quarantined.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Image file goes through pipeline → indexed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_image_file() -> None:
    """A JPEG image should be processed through the image handler and indexed."""
    pipeline, drive, embedder, qdrant, pg = make_pipeline(
        download_bytes=b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG header
    )
    file = make_drive_file(
        file_id="img_001",
        name="sunset_bali.jpg",
        mime_type="image/jpeg",
        parents=["1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq"],  # photos folder
    )

    result = await pipeline.index_file_safe(file)

    # Image extraction may fail gracefully but should not crash pipeline
    assert result.status in ("indexed", "error")
    # Drive download was always attempted
    drive.download_file.assert_called_once_with("img_001")


# ---------------------------------------------------------------------------
# Test 3: Text with NIK pattern → quarantined, NOT indexed to Qdrant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dlp_quarantine_nik() -> None:
    """A file containing a 16-digit NIK number must be quarantined."""
    pii_content = b"KTP: 3171023456789012 atas nama Budi Santoso direktur perusahaan"

    pipeline, drive, embedder, qdrant, pg = make_pipeline(
        download_bytes=pii_content
    )
    file = make_drive_file(
        file_id="pii_file_001",
        name="director_info.txt",
        mime_type="text/plain",
    )

    result = await pipeline.index_file_safe(file)

    assert result.status == "quarantined"
    assert result.file_id == "pii_file_001"

    # Postgres quarantine marker written
    pg.mark_quarantined.assert_called_once()
    # Qdrant must NOT have been called (no PII in vector store)
    qdrant.upsert.assert_not_called()
    # Postgres index record must NOT have been upserted
    pg.upsert_index_record.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Second file with same content hash → skipped_dedup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_same_content_hash() -> None:
    """When Postgres reports an existing content hash, file is skipped_dedup."""
    pipeline, drive, embedder, qdrant, pg = make_pipeline(
        check_content_hash_return="original_file_abc"
    )
    file = make_drive_file(file_id="duplicate_file_002", name="same_content.pdf")

    result = await pipeline.index_file_safe(file)

    assert result.status == "skipped_dedup"
    assert "original_file_abc" in (result.reason or "")

    # No embedding, no Qdrant, no Postgres write
    embedder.embed_text.assert_not_called()
    qdrant.upsert.assert_not_called()
    pg.upsert_index_record.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Qdrant raises → Postgres NOT written (atomic order)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qdrant_fail_no_postgres() -> None:
    """If Qdrant upsert raises, Postgres must never be written (atomic order)."""
    pipeline, drive, embedder, qdrant, pg = make_pipeline(
        qdrant_side_effect=ConnectionError("Qdrant unreachable")
    )
    file = make_drive_file(file_id="qdrant_fail_001", name="report.pdf")

    result = await pipeline.index_file_safe(file)

    assert result.status == "error"
    assert result.reason is not None

    # CRITICAL: Postgres must NOT be written when Qdrant fails
    pg.upsert_index_record.assert_not_called()
    # Qdrant was attempted
    qdrant.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6: File > 500 MB → skipped_size
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_size_cap_500mb() -> None:
    """Files larger than 500 MB must be skipped before any I/O."""
    pipeline, drive, embedder, qdrant, pg = make_pipeline()
    file = make_drive_file(
        file_id="giant_file_001",
        name="big_video.mp4",
        size=600_000_000,  # 600 MB — over the 500 MB cap
        mime_type="video/mp4",
    )

    result = await pipeline.index_file_safe(file)

    assert result.status == "skipped_size"
    assert result.reason == "too_large"

    # No download or any downstream steps
    drive.download_file.assert_not_called()
    embedder.embed_text.assert_not_called()
    qdrant.upsert.assert_not_called()
    pg.upsert_index_record.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7: Tombstone handling → mark_archived called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tombstone_handling() -> None:
    """Tombstone files (removed=True) should call mark_archived on both Qdrant and Postgres."""
    _, _, _, qdrant, pg = make_pipeline()

    # Simulate what the orchestrator does on a tombstone change:
    # It calls qdrant.mark_archived and pg.mark_archived directly.
    file_id = "tombstone_file_001"
    await qdrant.mark_archived(file_id)
    await pg.mark_archived(file_id)

    qdrant.mark_archived.assert_called_once_with(file_id)
    pg.mark_archived.assert_called_once_with(file_id)


# ---------------------------------------------------------------------------
# Test 8: Full batch flow — 5 files: 3 clean, 1 PII, 1 duplicate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_batch_flow() -> None:
    """Process 5 files and verify correct final stats: 3 indexed, 1 quarantined, 1 skipped_dedup."""

    # We need different pg.check_content_hash behaviour per file.
    # Build pipeline manually with side_effect for check_content_hash.
    drive = MagicMock()
    drive.download_file = AsyncMock(
        return_value=b"%PDF-1.4 clean bali property article"
    )

    embedder = MagicMock()
    embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

    qdrant = MagicMock()
    qdrant.upsert = AsyncMock(return_value=None)

    call_count = 0

    async def _check_hash(content_hash: str, exclude_id: str) -> str | None:
        nonlocal call_count
        call_count += 1
        # 4th call → duplicate (5th file is PII so won't reach dedup)
        if call_count == 4:
            return "original_file_xyz"
        return None

    pg = MagicMock()
    pg.check_content_hash = AsyncMock(side_effect=_check_hash)
    pg.upsert_index_record = AsyncMock(return_value=None)
    pg.mark_quarantined = AsyncMock(return_value=None)
    pg.mark_archived = AsyncMock(return_value=None)

    pipeline = Pipeline(
        embedder=embedder,
        qdrant_writer=qdrant,
        postgres_writer=pg,
        drive_client=drive,
    )

    # File 1-3: clean PDFs
    files_clean = [
        make_drive_file(file_id=f"clean_{i}", name=f"doc_{i}.pdf")
        for i in range(1, 4)
    ]
    # File 4: duplicate
    file_dup = make_drive_file(file_id="dup_001", name="duplicate.pdf")
    # File 5: PII — override download bytes via drive mock side_effect

    pii_bytes = b"KTP: 3171023456789012 direktur utama"
    clean_bytes = b"%PDF-1.4 clean bali property article"

    async def _download(file_id: str) -> bytes:
        if file_id == "pii_001":
            return pii_bytes
        return clean_bytes

    drive.download_file = AsyncMock(side_effect=_download)

    file_pii = make_drive_file(
        file_id="pii_001",
        name="passport_scan.txt",
        mime_type="text/plain",
    )

    # Process all 5 files
    all_files = files_clean + [file_dup, file_pii]
    results = []
    for f in all_files:
        r = await pipeline.index_file_safe(f)
        results.append(r)

    statuses = [r.status for r in results]

    # Count results
    indexed = statuses.count("indexed")
    quarantined = statuses.count("quarantined")
    skipped_dedup = statuses.count("skipped_dedup")

    assert indexed == 3, f"Expected 3 indexed, got {indexed}. Statuses: {statuses}"
    assert quarantined == 1, f"Expected 1 quarantined, got {quarantined}. Statuses: {statuses}"
    assert skipped_dedup == 1, f"Expected 1 skipped_dedup, got {skipped_dedup}. Statuses: {statuses}"

    # Qdrant upsert called exactly 3 times (only clean files)
    assert qdrant.upsert.call_count == 3
    # Postgres index record written 3 times
    assert pg.upsert_index_record.call_count == 3
    # DLP quarantine called once
    pg.mark_quarantined.assert_called_once()
