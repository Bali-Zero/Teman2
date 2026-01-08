"""
Legal Ingestion Service
Specialized ingestion pipeline for Indonesian legal documents
"""

import logging
import time
from pathlib import Path
from typing import Any

from core.embeddings import create_embeddings_generator
from core.legal import (
    HierarchicalIndexer,
    LegalChunker,
    LegalCleaner,
    LegalMetadataExtractor,
    LegalStructureParser,
)
from core.parsers import auto_detect_and_parse
from core.qdrant_db import QdrantClient
from utils.tier_classifier import TierClassifier

from app.metrics import metrics_collector
from app.models import TierLevel

from .ingestion_logger import IngestionStage, ingestion_logger

logger = logging.getLogger(__name__)


class LegalIngestionService:
    """
    Specialized ingestion service for Indonesian legal documents.
    Implements 4-stage pipeline: Clean → Extract Metadata → Parse Structure → Chunk
    """

    def __init__(self, collection_name: str = "legal_unified"):
        """
        Initialize legal ingestion service.

        Args:
            collection_name: Qdrant collection name for legal documents
        """
        self.cleaner = LegalCleaner()
        self.metadata_extractor = LegalMetadataExtractor()
        self.structure_parser = LegalStructureParser()
        self.chunker = LegalChunker()
        self.embedder = create_embeddings_generator()
        self.vector_db = QdrantClient(collection_name=collection_name)
        self.classifier = TierClassifier()

        # Initialize Hierarchical Indexer
        self.indexer = HierarchicalIndexer(
            structure_parser=self.structure_parser,
            qdrant_client=self.vector_db,
            embeddings=self.embedder,
            chunker=self.chunker,
        )

        logger.info(f"LegalIngestionService initialized (collection: {collection_name})")

    async def ingest_legal_document(
        self,
        file_path: str,
        title: str | None = None,
        tier_override: TierLevel | None = None,
        collection_name: str | None = None,
        skip_pricing: bool = False,
        category: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a legal document through the complete pipeline.

        Pipeline stages:
        1. Parse: Extract text from PDF/HTML
        2. Clean: Remove headers/footers/noise
        3. Extract Metadata: Type, number, year, topic
        4. Parse Structure: BAB, Pasal, Ayat hierarchy
        5. Chunk: Pasal-aware chunking with context injection
        6. Embed: Generate embeddings
        7. Store: Upsert to Qdrant

        Args:
            file_path: Path to legal document file
            title: Document title (auto-extracted if not provided)
            tier_override: Manual tier classification (optional)
            collection_name: Override collection name (optional)
            category: Document category (e.g., 'immigrazione', 'tasse')
            skip_pricing: Remove pricing information if True
            trace_id: Trace ID for correlation
            user_id: User ID who initiated ingestion

        Returns:
            Dictionary with ingestion results
        """
        start_time = time.time()
        document_id = None
        source = "file_upload"
        file_type = Path(file_path).suffix.lower()

        try:
            # Generate document ID and start logging
            document_id = f"legal_{int(start_time)}_{Path(file_path).stem}"
            document_id = ingestion_logger.start_ingestion(
                file_path=file_path,
                document_id=document_id,
                source=source,
                trace_id=trace_id,
                user_id=user_id,
            )

            logger.info(
                f"Starting legal document ingestion: {file_path} (Category: {category or 'None'})"
            )

            # Override collection if specified
            target_collection = collection_name or self.vector_db.collection_name
            if collection_name:
                self.vector_db = QdrantClient(collection_name=collection_name)
                # CRITICAL: Update indexer's client reference too!
                if self.indexer:
                    self.indexer.qdrant = self.vector_db

            # STAGE 1: Parse document
            parsing_start = time.time()
            raw_text = auto_detect_and_parse(file_path)
            parsing_duration = time.time() - parsing_start

            ingestion_logger.parsing_success(
                document_id=document_id,
                file_path=file_path,
                text_length=len(raw_text),
                duration_ms=parsing_duration * 1000,
                source=source,
                trace_id=trace_id,
            )

            metrics_collector.record_parsing_duration(
                file_type=file_type, source=source, duration_seconds=parsing_duration
            )

            logger.info(f"Extracted {len(raw_text)} characters from document")

            # STAGE 2: Clean (The Washer)
            cleaned_text = self.cleaner.clean(raw_text)

            # OPTIONAL: Skip Pricing (Golden Data Enforcement)
            if skip_pricing:
                logger.info("💰 skip_pricing=True: Removing pricing information from text...")
                # Split by newlines first
                lines = cleaned_text.splitlines()
                if len(lines) < 5 and len(cleaned_text) > 1000:
                    # If few lines but lots of text, it might be one huge block. Try splitting by periods.
                    logger.info(
                        "Text appears to be a single block. Splitting by sentences for pricing removal."
                    )
                    lines = cleaned_text.split(". ")
                    separator = ". "
                else:
                    separator = "\n"

                filtered_lines = [
                    line
                    for line in lines
                    if not any(x in line.upper() for x in ["IDR", "RP ", "RP.", "RUPIAH"])
                ]
                cleaned_text = separator.join(filtered_lines)
                logger.info(
                    f"Removed {len(lines) - len(filtered_lines)} segments containing pricing info"
                )

            logger.info(f"Cleaned text: {len(cleaned_text)} characters")

            # STAGE 3: Extract Metadata (The Librarian)
            metadata_start = time.time()
            metadata = self.metadata_extractor.extract(cleaned_text)
            metadata_duration = time.time() - metadata_start

            metrics_collector.record_metadata_extraction_duration(
                document_type="legal", source=source, duration_seconds=metadata_duration
            )

            ingestion_logger.metadata_extracted(
                document_id=document_id,
                metadata=metadata,
                source=source,
                trace_id=trace_id,
            )

            # HYBRID EXTRACTION: Fallback to Vertex AI if Pattern Extraction fails
            if not metadata or metadata.get("type") == "UNKNOWN":
                logger.info(
                    "Pattern extraction failed/incomplete. Attempting Vertex AI fallback..."
                )
                try:
                    from services.llm_clients.vertex_ai_service import VertexAIService

                    vertex_service = VertexAIService()
                    ai_metadata = await vertex_service.extract_metadata(cleaned_text)

                    if ai_metadata:
                        logger.info(
                            f"Vertex AI extraction successful: {ai_metadata.get('type_abbrev')} {ai_metadata.get('number')}"
                        )
                        # Merge AI metadata, preferring AI results for missing fields
                        if not metadata:
                            metadata = ai_metadata
                        else:
                            metadata.update({k: v for k, v in ai_metadata.items() if v})
                except Exception as e:
                    logger.warning(f"Vertex AI fallback failed: {e}")

            if not metadata or metadata.get("type_abbrev") == "UNKNOWN":
                logger.warning(
                    "Could not extract metadata (Pattern + AI failed), using category fallback"
                )

                # Use category as fallback for type_abbrev if possible
                fallback_type = "DOC"
                if category:
                    # e.g. "01_immigrazione" -> "IMMIGRAZIONE"
                    fallback_type = category.split("_")[-1].upper()

                if not metadata:
                    metadata = {
                        "type": "UNKNOWN",
                        "type_abbrev": fallback_type,
                        "number": "UNKNOWN",
                        "year": "UNKNOWN",
                        "topic": title or Path(file_path).stem,
                        "status": None,
                        "full_title": title or Path(file_path).stem,
                    }
                else:
                    metadata["type_abbrev"] = fallback_type
                    if metadata.get("topic") == "UNKNOWN":
                        metadata["topic"] = title or Path(file_path).stem

            # Use extracted title if not provided
            document_title = title or metadata.get("full_title", Path(file_path).stem)

            # STAGE 4: Parse Structure (The Architect)
            # structure = self.structure_parser.parse(cleaned_text)
            # logger.info(
            #     f"Parsed structure: {len(structure.get('batang_tubuh', []))} BAB, "
            #     f"{len(structure.get('pasal_list', []))} Pasal"
            # )

            # STAGE 5: Classify tier
            if tier_override:
                tier = tier_override
                logger.info(f"Using manual tier override: {tier.value}")
            else:
                # Use first 2000 chars for classification
                content_sample = cleaned_text[:2000]
                tier = self.classifier.classify_book_tier(
                    document_title, "Pemerintah Indonesia", content_sample
                )

            min_level = self.classifier.get_min_access_level(tier)

            # STAGE 6: Hierarchical Indexing (Parent-Child)
            # Generate a document ID
            doc_id = f"{metadata.get('type_abbrev', 'DOC')}_{metadata.get('number', '0')}_{metadata.get('year', '0')}".replace(
                " ", "_"
            ).replace("/", "_")

            # Prepare base metadata
            base_metadata = {
                "book_title": document_title,
                "book_author": "Pemerintah Indonesia",
                "category": category,
                "tier": tier.value,
                "min_level": min_level,
                "language": "id",  # Indonesian
                "file_path": file_path,
                "doc_type": "legal",
                # Legal-specific metadata
                "legal_type": metadata.get("type_abbrev"),
                "legal_number": metadata.get("number"),
                "legal_year": metadata.get("year"),
                "legal_topic": metadata.get("topic"),
                "legal_status": metadata.get("status"),
                # CRITICAL: Keep original keys for LegalChunker context injection
                "type_abbrev": metadata.get("type_abbrev"),
                "number": metadata.get("number"),
                "year": metadata.get("year"),
                "topic": metadata.get("topic"),
            }

            # Use HierarchicalIndexer
            indexing_start = time.time()
            indexing_result = await self.indexer.index_legal_document(
                document_text=cleaned_text, document_id=doc_id, metadata=base_metadata
            )
            indexing_duration = time.time() - indexing_start

            # Record chunking and embedding metrics
            metrics_collector.record_chunking_duration(
                file_type=file_type,
                chunk_strategy="legal_hierarchical",
                duration_seconds=indexing_duration,
            )

            total_duration = time.time() - start_time

            # Record success metrics
            metrics_collector.record_document_ingested(
                source=source,
                file_type=file_type,
                collection=target_collection,
                status="success",
                chunks_created=indexing_result["chunks_indexed"],
            )

            metrics_collector.record_document_processing_duration(
                source=source, collection=target_collection, duration_seconds=total_duration
            )

            logger.info(f"✅ Successfully ingested legal document: {document_title}")
            logger.info(f"   - Chunks: {indexing_result['chunks_indexed']}")
            logger.info(f"   - Parent Docs: {indexing_result['parent_documents']}")

            # Log completion
            ingestion_logger.ingestion_completed(
                document_id=document_id,
                file_path=file_path,
                chunks_created=indexing_result["chunks_indexed"],
                collection_name=target_collection,
                tier=tier.value,
                total_duration_ms=total_duration * 1000,
                source=source,
                trace_id=trace_id,
                user_id=user_id,
            )

            return {
                "success": True,
                "book_title": document_title,
                "book_author": "Pemerintah Indonesia",
                "tier": tier.value,
                "chunks_created": indexing_result["chunks_indexed"],
                "legal_metadata": metadata,
                "structure": {
                    "bab_count": indexing_result["total_bab"],
                    "pasal_count": indexing_result["total_pasal"],
                },
                "message": f"Successfully ingested {document_title}",
                "error": None,
                "document_id": document_id,
                "processing_time_seconds": total_duration,
            }

        except Exception as e:
            total_duration = time.time() - start_time
            error_type = type(e).__name__

            # Record error metrics
            metrics_collector.record_document_ingested(
                source=source,
                file_type=file_type,
                collection=collection_name or "unknown",
                status="error",
            )

            metrics_collector.record_parsing_error(
                file_type=file_type, error_type=error_type, source=source
            )

            # Log error with structured logging
            ingestion_logger.ingestion_failed(
                document_id=document_id or f"failed_{int(start_time)}",
                file_path=file_path,
                error=e,
                stage=IngestionStage.PARSING
                if "parse" in str(e).lower()
                else IngestionStage.COMPLETION,
                duration_ms=total_duration * 1000,
                source=source,
                trace_id=trace_id,
                user_id=user_id,
            )

            logger.error(f"❌ Error ingesting legal document {file_path}: {e}", exc_info=True)
            return {
                "success": False,
                "book_title": title or Path(file_path).stem,
                "book_author": "Pemerintah Indonesia",
                "tier": "Unknown",
                "chunks_created": 0,
                "message": "Failed to ingest legal document",
                "error": str(e),
                "document_id": document_id,
                "processing_time_seconds": total_duration,
            }

    def detect_legal_document(self, text: str) -> bool:
        """
        Detect if text appears to be an Indonesian legal document.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a legal document
        """
        return self.metadata_extractor.is_legal_document(text)
