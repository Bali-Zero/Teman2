"""
ORACLE INGEST API Router
Endpoint per caricare massivamente documenti legali su Qdrant

POST /api/oracle/ingest - Bulk upload di chunks con embeddings
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))


from app.dependencies import get_search_service
from services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oracle", tags=["Oracle INGEST"])


# ========================================
# Request/Response Models
# ========================================


class DocumentChunk(BaseModel):
    """Single document chunk to ingest"""

    content: str = Field(..., description="Document content (text)", min_length=10)
    metadata: dict[str, Any] = Field(
        ..., description="Metadata (law_id, pasal, category, type, etc.)"
    )


class IngestRequest(BaseModel):
    """Bulk ingest request"""

    collection: str = Field("legal_intelligence", description="Target collection name")
    documents: list[DocumentChunk] = Field(
        ...,
        description="List of document chunks to ingest",
        min_items=1,
        max_items=1000,  # Limit per richiesta
    )
    batch_size: int = Field(100, ge=10, le=500, description="Batch size for ingestion")


class IngestResponse(BaseModel):
    """Ingest response"""

    success: bool
    collection: str
    documents_ingested: int
    execution_time_ms: float
    message: str
    error: str | None = None


# ========================================
# INGEST ENDPOINT
# ========================================


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    request: IngestRequest, service: SearchService = Depends(get_search_service)
):
    """
    Bulk ingest documents into Qdrant collection

    **Usage:**
    ```python
    import requests

    chunks = [
        {
            "content": "### PP-28-2025 - Pasal 1\\n\\nContent here...",
            "metadata": {
                "law_id": "PP-28-2025",
                "pasal": "1",
                "category": "business_licensing",
                "type": "legal_regulation"
            }
        }
    ]

    response = requests.post(
        "https://nuzantara-rag.fly.dev/api/oracle/ingest",
        json={"collection": "legal_intelligence", "documents": chunks}
    )
    ```

    **Rate Limits:**
    - Max 1000 documents per request
    - Batch processing for large uploads
    """

    start_time = time.time()

    try:
        # Validate collection exists
        if request.collection not in service.collections:
            # Auto-create collection if legal_intelligence
            if request.collection == "legal_intelligence":
                logger.info(f"Auto-creating collection: {request.collection}")
                from core.qdrant_db import QdrantClient

                vector_db = QdrantClient(collection_name=request.collection)
                service.collections[request.collection] = vector_db
            else:
                return IngestResponse(
                    success=False,
                    collection=request.collection,
                    documents_ingested=0,
                    execution_time_ms=0,
                    message="Collection not found",
                    error=f"Collection '{request.collection}' not found. Available: {list(service.collections.keys())}",
                )

        vector_db = service.collections[request.collection]

        # Generate embeddings for all documents
        from core.embeddings import create_embeddings_generator

        embedder = create_embeddings_generator()
        contents = [doc.content for doc in request.documents]

        logger.info(f"Generating embeddings for {len(contents)} documents...")
        embeddings = embedder.generate_batch_embeddings(contents)

        # Prepare data for Qdrant
        documents = []
        metadatas = []
        ids = []

        for idx, (doc, _embedding) in enumerate(zip(request.documents, embeddings, strict=True)):
            # Generate unique ID
            law_id = doc.metadata.get("law_id", "UNKNOWN")
            pasal = doc.metadata.get("pasal", str(idx))
            doc_id = f"{law_id}_pasal_{pasal}_{idx}"

            documents.append(doc.content)
            metadatas.append(doc.metadata)
            ids.append(doc_id)

        # Batch ingest
        logger.info(f"Ingesting {len(documents)} documents into {request.collection}...")

        # Qdrant upsert method (async)
        await vector_db.upsert_documents(
            chunks=documents, embeddings=embeddings, metadatas=metadatas, ids=ids
        )

        execution_time = (time.time() - start_time) * 1000

        logger.info(
            f"✅ Successfully ingested {len(documents)} documents in {execution_time:.2f}ms"
        )

        return IngestResponse(
            success=True,
            collection=request.collection,
            documents_ingested=len(documents),
            execution_time_ms=execution_time,
            message=f"Successfully ingested {len(documents)} documents",
        )

    except Exception as e:
        logger.error(f"Ingest error: {e}", exc_info=True)
        execution_time = (time.time() - start_time) * 1000

        return IngestResponse(
            success=False,
            collection=request.collection,
            documents_ingested=0,
            execution_time_ms=execution_time,
            message="Ingest failed",
            error=str(e),
        )


@router.get("/collections")
async def list_collections(service: SearchService = Depends(get_search_service)):
    """
    List all available collections

    **Returns:**
    - List of collection names
    - Document counts for each collection
    """

    try:
        collections_info = {}

        for name, vector_db in service.collections.items():
            try:
                stats = vector_db.get_collection_stats()
                count = stats.get("total_documents", 0)
                collections_info[name] = {"name": name, "document_count": count}
            except Exception as e:
                logger.error(f"Error getting count for {name}: {e}")
                collections_info[name] = {"name": name, "document_count": 0, "error": str(e)}

        return {
            "success": True,
            "collections": list(collections_info.keys()),
            "details": collections_info,
        }

    except Exception as e:
        logger.error(f"List collections error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
