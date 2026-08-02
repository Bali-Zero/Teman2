"""
ZANTARA RAG - Ingestion Router
Book ingestion endpoints
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from backend.app.dependencies import get_current_user
from backend.app.models import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    BookIngestionRequest,
    BookIngestionResponse,
    TierLevel,
)
from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.ingest_paths import resolve_ingest_path, resolve_within_root
from backend.core.qdrant_db import QdrantClient
from backend.services.ingestion.ingestion_service import IngestionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


def _require_ingest_admin(user: dict[str, Any]) -> None:
    """Gate KB ingestion to admins. Raises 403 otherwise.

    Ingestion writes directly to the shared knowledge base (Qdrant), so an
    authenticated team member is not a sufficient principal (Case OS R3).
    """
    if not is_crm_admin(user):
        raise HTTPException(status_code=403, detail="Ingestion requires admin")


def save_upload_file_sync(path: Path, content: bytes) -> Any:
    """Helper for sync file writing"""
    with open(path, "wb") as f:
        f.write(content)


@router.post("/upload", response_model=BookIngestionResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    title: str | None = None,
    author: str | None = None,
    tier_override: TierLevel | None = None,
    current_user: dict = Depends(get_current_user),
) -> BookIngestionResponse:
    """
    Upload and ingest a single book.

    - **file**: PDF or EPUB file
    - **title**: Optional book title (auto-detected if not provided)
    - **author**: Optional author name
    - **tier_override**: Optional manual tier (S/A/B/C/D)
    """
    _require_ingest_admin(current_user)
    # Validate file type
    if not file.filename.endswith((".pdf", ".epub")):
        raise HTTPException(status_code=400, detail="Only PDF and EPUB files are supported")

    try:
        # Save uploaded file temporarily
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        # `file.filename` is caller-controlled and starlette does not sanitise it (it
        # decodes the Content-Disposition value and hands it over), so it can carry
        # directory components. Two ways this escapes, and the extension check above stops
        # neither because both still end in `.pdf`:
        #   `../../../tmp/x.pdf`  -> walks out of data/temp
        #   `/etc/cron.d/x.pdf`   -> pathlib REPLACES the whole path on an absolute operand
        # Containment is judged on the RESOLVED result, under this one server-chosen
        # directory — not against the ingest allow-list, which answers a different
        # question.
        try:
            temp_path = resolve_within_root(temp_dir, file.filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Non-blocking file reading
        content = await file.read()

        # Non-blocking file writing (offload to thread)
        await asyncio.to_thread(save_upload_file_sync, temp_path, content)

        logger.info("Uploaded file saved: %s", temp_path)

        # Ingest book
        service = IngestionService()
        result = await service.ingest_book(
            file_path=str(temp_path),
            title=title,
            author=author,
            tier_override=tier_override,
        )

        # Clean up temp file
        if temp_path.exists():
            os.remove(temp_path)

        return BookIngestionResponse(**result)

    except HTTPException:
        # Without this the 400 above is re-wrapped as a 500 by the handler below —
        # still fail-closed, but it would report a server fault for a client error.
        # `batch_ingest` in this file already does exactly this.
        raise
    except Exception as e:
        logger.error("Upload ingestion error: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e!s}") from e


@router.post("/file", response_model=BookIngestionResponse)
async def ingest_local_file(
    request: BookIngestionRequest,
    current_user: dict = Depends(get_current_user),
) -> BookIngestionResponse:
    """
    Ingest a book from local file path.

    - **file_path**: Path to PDF or EPUB file
    - **title**: Optional book title
    - **author**: Optional author name
    - **tier_override**: Optional manual tier classification
    """
    _require_ingest_admin(current_user)
    # Confine the caller-supplied path BEFORE it is touched or echoed. Everything below
    # uses the returned value, never `request.file_path`.
    try:
        file_path = resolve_ingest_path(request.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Validate file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        # Ingest
        service = IngestionService()
        result = await service.ingest_book(
            file_path=str(file_path),
            title=request.title,
            author=request.author,
            language=request.language,
            tier_override=request.tier_override,
        )

        return BookIngestionResponse(**result)

    except Exception as e:
        logger.error("File ingestion error: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e!s}") from e


@router.post("/batch", response_model=BatchIngestionResponse)
async def batch_ingest(
    request: BatchIngestionRequest,
    _background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> BatchIngestionResponse:
    """
    Process all books in a directory.

    - **directory_path**: Path to directory containing books
    - **file_patterns**: File patterns to match (default: ["*.pdf", "*.epub"])
    - **skip_existing**: Skip books already in database
    """
    _require_ingest_admin(current_user)
    try:
        start_time = time.time()

        try:
            directory = resolve_ingest_path(request.directory_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not directory.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Directory not found: {directory}",
            )

        # Get all matching files. `file_patterns` is caller-supplied too, and a glob
        # pattern escapes: `Path("data/raw_books").glob("../../*.pdf")` really does walk
        # up (measured). So every MATCH is re-confined — judging the resolved file, not
        # the shape of the pattern — and one escaping match fails the whole request
        # rather than being dropped silently.
        book_files = []
        for pattern in request.file_patterns:
            for candidate in directory.glob(pattern):
                try:
                    book_files.append(resolve_ingest_path(str(candidate)))
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File pattern matched outside the allowed roots: {exc}",
                    ) from exc

        if not book_files:
            raise HTTPException(
                status_code=400,
                detail=f"No books found in {directory}",
            )

        logger.info(f"Found {len(book_files)} books to ingest")

        # Process each book
        service = IngestionService()
        results = []
        successful = 0
        failed = 0

        for book_path in book_files:
            try:
                result = await service.ingest_book(str(book_path))
                results.append(BookIngestionResponse(**result))

                if result["success"]:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error("Error ingesting %s: %s", book_path, e)
                results.append(
                    BookIngestionResponse(
                        success=False,
                        book_title=book_path.stem,
                        book_author="Unknown",
                        tier="Unknown",
                        chunks_created=0,
                        message="Ingestion failed",
                        error=str(e),
                    ),
                )
                failed += 1

        execution_time = time.time() - start_time

        logger.info(
            f"Batch ingestion complete: {successful} successful, "
            f"{failed} failed in {execution_time:.2f}s",
        )

        return BatchIngestionResponse(
            total_books=len(book_files),
            successful=successful,
            failed=failed,
            results=results,
            execution_time_seconds=round(execution_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch ingestion error: %s", e)
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {e!s}") from e


@router.get("/stats")
async def get_ingestion_stats() -> dict[str, Any]:
    """
    Get current database statistics.

    Returns total documents, tier distribution, and collection info.
    """
    db = QdrantClient()
    try:
        stats = await db.get_stats()

        return {
            "status": "success",
            "collection": stats.get("collection_name", db.collection_name),
            "total_documents": stats.get("total_documents", 0),
            "tiers_distribution": stats.get("tiers_distribution", {}),
            "persist_directory": db.qdrant_url,
        }

    except Exception as e:
        logger.error("Stats error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e!s}") from e
    finally:
        await db.close()
