"""
ZANTARA RAG - Ingestion Router
Book ingestion endpoints
"""

import logging
import os
import time
from pathlib import Path

from core.qdrant_db import QdrantClient
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from services.ingestion_service import IngestionService

from ..models import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    BookIngestionRequest,
    BookIngestionResponse,
    TierLevel,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/upload", response_model=BookIngestionResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    title: str | None = None,
    author: str | None = None,
    tier_override: TierLevel | None = None,
):
    """
    Upload and ingest a single book.

    - **file**: PDF or EPUB file
    - **title**: Optional book title (auto-detected if not provided)
    - **author**: Optional author name
    - **tier_override**: Optional manual tier (S/A/B/C/D)
    """
    # Validate file type
    if not file.filename.endswith((".pdf", ".epub")):
        raise HTTPException(status_code=400, detail="Only PDF and EPUB files are supported")

    try:
        # Save uploaded file temporarily
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_path = temp_dir / file.filename
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"Uploaded file saved: {temp_path}")

        # Ingest book
        service = IngestionService()
        result = await service.ingest_book(
            file_path=str(temp_path), title=title, author=author, tier_override=tier_override
        )

        # Clean up temp file
        if temp_path.exists():
            os.remove(temp_path)

        return BookIngestionResponse(**result)

    except Exception as e:
        logger.error(f"Upload ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}") from e


@router.post("/file", response_model=BookIngestionResponse)
async def ingest_local_file(request: BookIngestionRequest):
    """
    Ingest a book from local file path.

    - **file_path**: Path to PDF or EPUB file
    - **title**: Optional book title
    - **author**: Optional author name
    - **tier_override**: Optional manual tier classification
    """
    # Validate file exists
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    try:
        # Ingest
        service = IngestionService()
        result = await service.ingest_book(
            file_path=request.file_path,
            title=request.title,
            author=request.author,
            language=request.language,
            tier_override=request.tier_override,
        )

        return BookIngestionResponse(**result)

    except Exception as e:
        logger.error(f"File ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}") from e


@router.post("/batch", response_model=BatchIngestionResponse)
async def batch_ingest(request: BatchIngestionRequest, _background_tasks: BackgroundTasks):
    """
    Process all books in a directory.

    - **directory_path**: Path to directory containing books
    - **file_patterns**: File patterns to match (default: ["*.pdf", "*.epub"])
    - **skip_existing**: Skip books already in database
    """
    try:
        start_time = time.time()

        directory = Path(request.directory_path)
        if not directory.exists():
            raise HTTPException(
                status_code=404, detail=f"Directory not found: {request.directory_path}"
            )

        # Get all matching files
        book_files = []
        for pattern in request.file_patterns:
            book_files.extend(directory.glob(pattern))

        if not book_files:
            raise HTTPException(
                status_code=400, detail=f"No books found in {request.directory_path}"
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
                logger.error(f"Error ingesting {book_path}: {e}")
                results.append(
                    BookIngestionResponse(
                        success=False,
                        book_title=book_path.stem,
                        book_author="Unknown",
                        tier="Unknown",
                        chunks_created=0,
                        message="Ingestion failed",
                        error=str(e),
                    )
                )
                failed += 1

        execution_time = time.time() - start_time

        logger.info(
            f"Batch ingestion complete: {successful} successful, "
            f"{failed} failed in {execution_time:.2f}s"
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
        logger.error(f"Batch ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {str(e)}") from e


@router.get("/stats")
async def get_ingestion_stats():
    """
    Get current database statistics.

    Returns total documents, tier distribution, and collection info.
    """
    try:
        db = QdrantClient()
        stats = db.get_collection_stats()

        return {
            "status": "success",
            "collection": stats["collection_name"],
            "total_documents": stats["total_documents"],
            "tiers_distribution": stats.get("tiers_distribution", {}),
            "persist_directory": stats["persist_directory"],
        }

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}") from e
