"""
ZANTARA RAG - Ingestion Service
Book processing pipeline: parse → chunk → embed → store
Auto-routes legal documents to LegalIngestionService
"""

import logging
from pathlib import Path
from typing import Any

from core.chunker import TextChunker
from core.embeddings import create_embeddings_generator
from core.parsers import auto_detect_and_parse, get_document_info
from core.qdrant_db import QdrantClient
from utils.tier_classifier import TierClassifier

from app.models import TierLevel

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Complete book ingestion pipeline.
    Handles the full flow from raw document to searchable embeddings.
    """

    def __init__(self):
        """Initialize ingestion service with all components"""
        self.chunker = TextChunker()
        self.embedder = create_embeddings_generator()
        self.vector_db = QdrantClient()
        self.classifier = TierClassifier()

        logger.info("IngestionService initialized")

    async def ingest_book(
        self,
        file_path: str,
        title: str | None = None,
        author: str | None = None,
        language: str = "en",
        tier_override: TierLevel | None = None,
        status_vigensi: str | None = None,
        wilayah: str | None = None,
        doc_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a single book through the complete pipeline.
        Auto-routes legal documents to LegalIngestionService.

        Args:
            file_path: Path to book file (PDF or EPUB)
            title: Book title (auto-detected if not provided)
            author: Book author (auto-detected if not provided)
            language: Book language code
            tier_override: Manual tier classification (optional)
            status_vigensi: Legal validity status (e.g., "berlaku", "dicabut") - extracted from doc_info if not provided
            wilayah: Region/territory (e.g., "Indonesia", "Bali") - extracted from doc_info if not provided
            doc_type: Document type override ("legal" to force legal pipeline)

        Returns:
            Dictionary with ingestion results
        """
        try:
            logger.info(f"Starting ingestion for: {file_path}")

            # AUTO-ROUTING: Check if this is a legal document
            if doc_type == "legal" or self._is_legal_document(file_path):
                logger.info("📜 Legal document detected - routing to LegalIngestionService")
                from services.legal_ingestion_service import LegalIngestionService

                legal_service = LegalIngestionService()
                return await legal_service.ingest_legal_document(
                    file_path=file_path,
                    title=title,
                    tier_override=tier_override,
                )

            # Step 1: Extract document info
            doc_info = get_document_info(file_path)
            book_title = title or doc_info.get("title", Path(file_path).stem)
            book_author = author or doc_info.get("author", "Unknown")

            # Extract legal metadata if available
            extracted_status_vigensi = (
                status_vigensi or doc_info.get("status_vigensi") or doc_info.get("status")
            )
            extracted_wilayah = wilayah or doc_info.get("wilayah") or doc_info.get("region")

            logger.info(f"Book: {book_title} by {book_author}")
            if extracted_status_vigensi:
                logger.info(f"Legal status: {extracted_status_vigensi}")
            if extracted_wilayah:
                logger.info(f"Region: {extracted_wilayah}")

            # Step 2: Parse document
            text = auto_detect_and_parse(file_path)
            logger.info(f"Extracted {len(text)} characters")

            # Step 3: Classify tier
            if tier_override:
                tier = tier_override
                logger.info(f"Using manual tier override: {tier.value}")
            else:
                # Use first 2000 chars as content sample for classification
                content_sample = text[:2000]
                tier = self.classifier.classify_book_tier(book_title, book_author, content_sample)

            min_level = self.classifier.get_min_access_level(tier)

            # Step 4: Chunk text
            base_metadata = {
                "book_title": book_title,
                "book_author": book_author,
                "tier": tier.value,
                "min_level": min_level,
                "language": language,
                "file_path": file_path,
            }

            # Add legal metadata if available
            if extracted_status_vigensi:
                base_metadata["status_vigensi"] = extracted_status_vigensi
            if extracted_wilayah:
                base_metadata["wilayah"] = extracted_wilayah

            chunks = self.chunker.semantic_chunk(text, metadata=base_metadata)
            logger.info(f"Created {len(chunks)} chunks")

            # Step 5: Generate embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.embedder.generate_embeddings(chunk_texts)
            logger.info(f"Generated {len(embeddings)} embeddings")

            # Step 6: Prepare metadata for each chunk
            metadatas = []
            for chunk in chunks:
                meta = {
                    "book_title": book_title,
                    "book_author": book_author,
                    "tier": tier.value,
                    "min_level": min_level,
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "language": language,
                    "file_path": file_path,
                }
                # Add legal metadata if available
                if extracted_status_vigensi:
                    meta["status_vigensi"] = extracted_status_vigensi
                if extracted_wilayah:
                    meta["wilayah"] = extracted_wilayah
                metadatas.append(meta)

            # Step 7: Store in vector database
            self.vector_db.upsert_documents(
                chunks=chunk_texts, embeddings=embeddings, metadatas=metadatas
            )

            logger.info(f"✅ Successfully ingested: {book_title}")

            return {
                "success": True,
                "book_title": book_title,
                "book_author": book_author,
                "tier": tier.value,
                "chunks_created": len(chunks),
                "message": f"Successfully ingested {book_title}",
                "error": None,
            }

        except Exception as e:
            logger.error(f"❌ Error ingesting {file_path}: {e}")
            return {
                "success": False,
                "book_title": title or Path(file_path).stem,
                "book_author": author or "Unknown",
                "tier": "Unknown",
                "chunks_created": 0,
                "message": "Failed to ingest book",
                "error": str(e),
            }

    def _is_legal_document(self, file_path: str) -> bool:
        """
        Detect if file is an Indonesian legal document.

        Args:
            file_path: Path to document file

        Returns:
            True if document appears to be legal
        """
        try:
            # Quick check: parse first 5000 chars
            text = auto_detect_and_parse(file_path)
            sample = text[:5000] if len(text) > 5000 else text

            # Use LegalMetadataExtractor to detect
            from core.legal import LegalMetadataExtractor

            extractor = LegalMetadataExtractor()
            return extractor.is_legal_document(sample)

        except Exception as e:
            logger.warning(f"Error detecting legal document: {e}")
            return False
