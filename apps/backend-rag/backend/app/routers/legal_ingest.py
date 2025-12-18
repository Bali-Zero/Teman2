"""
Legal Document Ingestion Router
API endpoints for Indonesian legal document ingestion pipeline
"""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.models import TierLevel
from services.legal_ingestion_service import LegalIngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legal", tags=["legal-ingestion"])

# Initialize service (singleton pattern)
_legal_service: LegalIngestionService | None = None


def get_legal_service() -> LegalIngestionService:
    """Get or create LegalIngestionService instance"""
    global _legal_service
    if _legal_service is None:
        _legal_service = LegalIngestionService()
    return _legal_service


class LegalIngestRequest(BaseModel):
    """Request model for legal document ingestion"""

    file_path: str = Field(..., description="Path to legal document file")
    title: str | None = Field(None, description="Document title (auto-extracted if not provided)")
    tier: str | None = Field(None, description="Tier override (S, A, B, C, D)")
    collection_name: str | None = Field(
        None, description="Override collection name (default: legal_unified)"
    )


class LegalIngestResponse(BaseModel):
    """Response model for legal document ingestion"""

    success: bool
    book_title: str
    chunks_created: int
    legal_metadata: dict[str, Any] | None = None
    structure: dict[str, Any] | None = None
    message: str
    error: str | None = None


@router.post("/ingest", response_model=LegalIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_legal_document(request: LegalIngestRequest) -> LegalIngestResponse:
    """
    Ingest a single legal document through the specialized pipeline.

    Pipeline stages:
    1. Clean: Remove headers/footers/noise
    2. Extract Metadata: Type, number, year, topic
    3. Parse Structure: BAB, Pasal, Ayat hierarchy
    4. Chunk: Pasal-aware chunking with context injection
    5. Embed & Store: Generate embeddings and store in Qdrant

    Args:
        request: Legal ingestion request with file path and options

    Returns:
        Ingestion result with metadata and statistics
    """
    try:
        # Validate file exists
        if not Path(request.file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        # Parse tier override if provided
        tier_override = None
        if request.tier:
            try:
                tier_override = TierLevel(request.tier.upper())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid tier: {request.tier}. Must be one of: S, A, B, C, D",
                )

        # Get service and ingest
        service = get_legal_service()
        result = await service.ingest_legal_document(
            file_path=request.file_path,
            title=request.title,
            tier_override=tier_override,
            collection_name=request.collection_name,
        )

        return LegalIngestResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in legal ingestion endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest legal document: {str(e)}",
        )


@router.post("/upload", response_model=LegalIngestResponse, status_code=status.HTTP_200_OK)
async def upload_legal_document(
    file: UploadFile = File(...),
    title: str | None = None,
    tier: str | None = None,
    collection_name: str | None = None,
) -> LegalIngestResponse:
    """
    Upload and ingest a legal document via multipart/form-data.

    This endpoint accepts file uploads from remote clients (unlike /ingest which
    requires files to exist on the server).

    Pipeline stages:
    1. Save uploaded file temporarily
    2. Clean: Remove headers/footers/noise
    3. Extract Metadata: Type, number, year, topic
    4. Parse Structure: BAB, Pasal, Ayat hierarchy
    5. Chunk: Pasal-aware chunking with context injection
    6. Embed & Store: Generate embeddings and store in Qdrant + PostgreSQL
    7. Clean up temp file

    Args:
        file: PDF file to ingest
        title: Optional document title (auto-extracted if not provided)
        tier: Optional tier override (S, A, B, C, D)
        collection_name: Optional collection name override

    Returns:
        Ingestion result with metadata and statistics
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    temp_path = None
    try:
        # Save uploaded file temporarily
        temp_dir = Path("/tmp/legal_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_path = temp_dir / file.filename
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"Uploaded legal document saved: {temp_path} ({len(content)} bytes)")

        # Parse tier override if provided
        tier_override = None
        if tier:
            try:
                tier_override = TierLevel(tier.upper())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid tier: {tier}. Must be one of: S, A, B, C, D",
                )

        # Get service and ingest
        service = get_legal_service()
        result = await service.ingest_legal_document(
            file_path=str(temp_path),
            title=title,
            tier_override=tier_override,
            collection_name=collection_name,
        )

        logger.info(f"Successfully ingested: {result.get('book_title', file.filename)}")
        return LegalIngestResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading legal document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest legal document: {str(e)}",
        )
    finally:
        # Clean up temp file
        if temp_path and temp_path.exists():
            try:
                os.remove(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


@router.post("/ingest-batch", status_code=status.HTTP_200_OK)
async def ingest_legal_documents_batch(
    file_paths: list[str],
    collection_name: str | None = None,
) -> dict[str, Any]:
    """
    Ingest multiple legal documents in batch.

    Args:
        file_paths: List of file paths to ingest
        collection_name: Override collection name (optional)

    Returns:
        Batch ingestion results
    """
    service = get_legal_service()
    results = []

    for file_path in file_paths:
        try:
            result = await service.ingest_legal_document(
                file_path=file_path, collection_name=collection_name
            )
            results.append({"file_path": file_path, **result})
        except Exception as e:
            logger.error(f"Error ingesting {file_path}: {e}")
            results.append(
                {
                    "file_path": file_path,
                    "success": False,
                    "error": str(e),
                }
            )

    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "results": results,
    }


@router.get("/collections/stats", status_code=status.HTTP_200_OK)
async def get_collection_stats(collection_name: str = "legal_unified") -> dict[str, Any]:
    """
    Get statistics for legal document collection.

    Args:
        collection_name: Collection name to query

    Returns:
        Collection statistics
    """
    try:
        get_legal_service()
        # Access vector_db to get collection info
        # Note: This requires adding a method to QdrantClient for collection stats
        # For now, return basic info
        return {
            "collection_name": collection_name,
            "message": "Collection stats endpoint - implementation pending",
        }
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection stats: {str(e)}",
        )


class RegisterParentDocRequest(BaseModel):
    """Request to register a parent document"""
    id: str = Field(..., description="Unique ID for the parent document")
    document_id: str = Field(..., description="Document ID (e.g. 'training_visa_e33g')")
    doc_type: str = Field(default="training_conversation", description="Document type")
    title: str = Field(..., description="Document title")
    full_text: str = Field(..., description="Full text content (truncated if > 50KB)")
    char_count: int = Field(..., description="Character count of original text")
    chunk_count: int = Field(default=0, description="Number of chunks created from this doc")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


@router.post("/parent-documents", status_code=status.HTTP_201_CREATED)
async def register_parent_document(request: RegisterParentDocRequest) -> dict[str, Any]:
    """
    Register a parent document in PostgreSQL.
    Used by ingestion scripts to track source documents for chunks.

    Args:
        request: Parent document registration request

    Returns:
        Registration result
    """
    import json
    import asyncpg
    from app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        await conn.execute(
            """
            INSERT INTO parent_documents (
                id, document_id, type, title, full_text,
                char_count, pasal_count, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                full_text = EXCLUDED.full_text,
                char_count = EXCLUDED.char_count,
                pasal_count = EXCLUDED.pasal_count,
                metadata = EXCLUDED.metadata,
                created_at = NOW()
            """,
            request.id,
            request.document_id,
            request.doc_type,
            request.title,
            request.full_text[:50000],  # Limit to 50KB
            request.char_count,
            request.chunk_count,  # Using pasal_count column for chunk_count
            json.dumps(request.metadata),
        )

        await conn.close()

        logger.info(f"Registered parent document: {request.id}")
        return {
            "success": True,
            "id": request.id,
            "document_id": request.document_id,
            "message": "Parent document registered successfully",
        }

    except Exception as e:
        logger.error(f"Failed to register parent document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register parent document: {str(e)}",
        )


@router.get("/parent-documents/{document_id}", status_code=status.HTTP_200_OK)
async def get_parent_documents(document_id: str) -> dict[str, Any]:
    """
    Get parent documents (BAB/chapters) from PostgreSQL for a legal document.
    PUBLIC endpoint - no auth required.

    Args:
        document_id: Document ID (e.g. "PP_31_2013")

    Returns:
        List of BAB with metadata
    """
    import asyncpg
    from app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        rows = await conn.fetch(
            """
            SELECT id, document_id, type, title,
                   char_count, pasal_count, created_at
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
            """,
            document_id
        )

        await conn.close()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "document_id": row["document_id"],
                "type": row["type"],
                "title": row["title"],
                "char_count": row["char_count"],
                "pasal_count": row["pasal_count"],
                "created_at": str(row["created_at"]),
            })

        return {
            "success": True,
            "document_id": document_id,
            "total_bab": len(results),
            "bab_list": results,
        }

    except Exception as e:
        logger.error(f"Failed to query parent_documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query parent documents: {str(e)}",
        )


@router.get("/parent-documents/{document_id}/{bab_id}/text", status_code=status.HTTP_200_OK)
async def get_bab_full_text(document_id: str, bab_id: str) -> dict[str, Any]:
    """
    Get full text of a specific BAB from PostgreSQL.
    PUBLIC endpoint - no auth required.

    Args:
        document_id: Document ID
        bab_id: BAB ID (e.g. "PP_31_2013_BAB_III")

    Returns:
        Full text of the BAB
    """
    import asyncpg
    from app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        row = await conn.fetchrow(
            """
            SELECT id, title, full_text,
                   char_count, pasal_count
            FROM parent_documents
            WHERE document_id = $1 AND id = $2
            """,
            document_id, bab_id
        )

        await conn.close()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BAB not found: {bab_id}",
            )

        return {
            "success": True,
            "id": row["id"],
            "title": row["title"],
            "char_count": row["char_count"],
            "pasal_count": row["pasal_count"],
            "full_text": row["full_text"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query BAB text: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query BAB text: {str(e)}",
        )
