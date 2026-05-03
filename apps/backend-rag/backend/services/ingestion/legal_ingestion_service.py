"""
Legal Ingestion Service
Specialized ingestion pipeline for Indonesian legal documents
"""

import logging
import time
from pathlib import Path
from typing import Any

from backend.app.metrics import metrics_collector
from backend.app.models import TierLevel
from backend.core.bm25_vectorizer import BM25Vectorizer
from backend.core.collection_registry import resolve_collection_name
from backend.core.embeddings import create_embeddings_generator
from backend.core.legal import (
    HierarchicalIndexer,
    LegalChunker,
    LegalCleaner,
    LegalMetadataExtractor,
    LegalStructureParser,
)
from backend.core.parsers import DocumentParseError, auto_detect_and_parse
from backend.core.qdrant_db import QdrantClient
from backend.services.ingestion.ingestion_logger import IngestionStage, ingestion_logger
from backend.utils.tier_classifier import TierClassifier

logger = logging.getLogger(__name__)


class LegalIngestionService:
    """
    Specialized ingestion service for Indonesian legal documents.
    Implements 4-stage pipeline: Clean → Extract Metadata → Parse Structure → Chunk
    """

    def __init__(self, collection_name: str = "legal_unified") -> None:
        """
        Initialize legal ingestion service.

        Args:
            collection_name: Qdrant collection name for legal documents
        """
        self.cleaner = LegalCleaner()
        self.metadata_extractor = LegalMetadataExtractor()
        self.structure_parser = LegalStructureParser()
        self.chunker = LegalChunker()
        self.sparse_vectorizer = BM25Vectorizer()
        self.embedder = create_embeddings_generator()
        resolved_collection_name = resolve_collection_name(collection_name)
        self.vector_db = QdrantClient(collection_name=resolved_collection_name)
        self.classifier = TierClassifier()

        # Initialize Hierarchical Indexer
        self.indexer = HierarchicalIndexer(
            structure_parser=self.structure_parser,
            qdrant_client=self.vector_db,
            embeddings=self.embedder,
            chunker=self.chunker,
            sparse_vectorizer=self.sparse_vectorizer,
        )

        # Initialize KG Extractor (lazy init per evitare costi se non usato)
        self.kg_extractor = None
        self.kg_enabled = False  # TEMP DISABLED: KG extraction causes OOM on 2GB Fly machine

        logger.info(
            "LegalIngestionService initialized (collection: %s -> %s)",
            collection_name,
            resolved_collection_name,
        )

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
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a legal document through the complete pipeline.
        ...
        """
        start_time = time.time()
        source = "file_upload"
        file_type = Path(file_path).suffix.lower()

        try:
            # Generate document ID if not provided
            if not document_id:
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
            target_collection = resolve_collection_name(
                collection_name or self.vector_db.collection_name
            )
            if collection_name:
                self.vector_db = QdrantClient(collection_name=target_collection)
                # CRITICAL: Update indexer's client reference too!
                if self.indexer:
                    self.indexer.qdrant = self.vector_db

            # STAGE 1: Parse document
            parsing_start = time.time()
            ocr_used = False
            # Try normal extraction first, fallback to OCR if needed
            try:
                raw_text = auto_detect_and_parse(file_path, use_ocr=False)
            except DocumentParseError as e:
                if "No text extracted" in str(e):
                    # Try OCR for scanned PDFs (async version)
                    logger.info(
                        "[STAGE 1] No text found in PDF, attempting OCR extraction...",
                        extra={
                            "document_id": document_id,
                            "stage": "parsing",
                            "ocr_fallback": True,
                        },
                    )
                    import asyncio

                    from backend.core.parsers import extract_text_from_pdf_async

                    try:
                        # Check if we're in async context
                        asyncio.get_running_loop()
                        # We're in async context, use async version
                        raw_text = await extract_text_from_pdf_async(file_path, use_ocr=True)
                        ocr_used = True
                        logger.info(
                            f"[STAGE 1] OCR extraction successful: {len(raw_text)} characters",
                            extra={
                                "document_id": document_id,
                                "stage": "parsing",
                                "ocr_used": True,
                                "text_length": len(raw_text),
                            },
                        )
                    except RuntimeError:
                        # No running loop, use sync version
                        raw_text = auto_detect_and_parse(file_path, use_ocr=True)
                        ocr_used = True
                        logger.info(
                            f"[STAGE 1] OCR extraction successful (sync): {len(raw_text)} characters",
                            extra={
                                "document_id": document_id,
                                "stage": "parsing",
                                "ocr_used": True,
                                "text_length": len(raw_text),
                            },
                        )
                else:
                    raise
            parsing_duration = time.time() - parsing_start

            logger.info(
                f"[STAGE 1] Parsing completed: {len(raw_text)} chars in {parsing_duration:.2f}s",
                extra={
                    "document_id": document_id,
                    "stage": "parsing",
                    "duration_seconds": parsing_duration,
                    "text_length": len(raw_text),
                    "ocr_used": ocr_used,
                },
            )

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

            # Logging already done above with structured data

            # STAGE 1.5: Upload to Google Drive (Permanent)
            drive_file_id = None
            drive_web_link = None
            drive_folder_path = "BALI ZERO/PERATURAN"
            try:
                from backend.services.integrations.team_drive_service import TeamDriveService

                drive_service = TeamDriveService()

                # Trova/crea cartella
                folder_id = await self._ensure_drive_folder_exists(
                    drive_service=drive_service,
                    folder_path=drive_folder_path,
                )

                # Leggi file PDF
                with open(file_path, "rb") as f:
                    pdf_content = f.read()

                # Upload PDF
                drive_file = await drive_service.upload_file(
                    file_content=pdf_content,
                    filename=Path(file_path).name,
                    mime_type="application/pdf",
                    parent_folder_id=folder_id,
                )

                drive_file_id = drive_file["id"]
                drive_web_link = drive_file.get("webViewLink")

                logger.info(
                    f"[STAGE 1.5] Uploaded to Drive: {drive_file_id}",
                    extra={
                        "document_id": document_id,
                        "stage": "drive_upload",
                        "drive_file_id": drive_file_id,
                        "drive_web_link": drive_web_link,
                        "success": True,
                    },
                )

            except Exception as e:
                # Non bloccare ingestione se Drive fallisce
                logger.warning(
                    f"[STAGE 1.5] Google Drive upload failed (non-blocking): {e}",
                    extra={
                        "document_id": document_id,
                        "stage": "drive_upload",
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "non_blocking": True,
                    },
                )

            # STAGE 2: Clean (The Washer)
            cleaning_start = time.time()
            cleaned_text = self.cleaner.clean(raw_text)
            cleaning_duration = time.time() - cleaning_start

            # OPTIONAL: Skip Pricing (Golden Data Enforcement)
            pricing_removed = 0
            if skip_pricing:
                logger.info(
                    "[STAGE 2] Removing pricing information from text...",
                    extra={
                        "document_id": document_id,
                        "stage": "cleaning",
                        "skip_pricing": True,
                    },
                )
                # Split by newlines first
                lines = cleaned_text.splitlines()
                if len(lines) < 5 and len(cleaned_text) > 1000:
                    # If few lines but lots of text, it might be one huge block. Try splitting by periods.
                    logger.debug(
                        "[STAGE 2] Text appears to be a single block. Splitting by sentences.",
                        extra={"document_id": document_id, "stage": "cleaning"},
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
                pricing_removed = len(lines) - len(filtered_lines)
                cleaned_text = separator.join(filtered_lines)
                logger.info(
                    f"[STAGE 2] Removed {pricing_removed} segments containing pricing info",
                    extra={
                        "document_id": document_id,
                        "stage": "cleaning",
                        "pricing_segments_removed": pricing_removed,
                    },
                )

            logger.info(
                f"[STAGE 2] Cleaning completed: {len(cleaned_text)} chars in {cleaning_duration:.2f}s",
                extra={
                    "document_id": document_id,
                    "stage": "cleaning",
                    "duration_seconds": cleaning_duration,
                    "text_length": len(cleaned_text),
                    "pricing_removed": pricing_removed,
                },
            )

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

            # HYBRID EXTRACTION: Fallback to Google AI Studio if Pattern Extraction fails
            # NOTE: Changed from Vertex AI to Google AI Studio (2026-02-06)
            # Reason: Vertex AI costs were Rp 5.5M/month vs Google AI Studio ~Rp 800/month
            if not metadata or metadata.get("type") == "UNKNOWN":
                logger.info(
                    "[STAGE 3] Pattern extraction failed/incomplete. Attempting Google AI Studio fallback...",
                    extra={
                        "document_id": document_id,
                        "stage": "metadata_extraction",
                        "fallback_method": "google_ai_studio",
                    },
                )
                try:
                    import json as json_module
                    import os

                    from google import genai

                    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
                        "GOOGLE_IMAGEN_API_KEY"
                    )
                    if not api_key:
                        raise ValueError("GOOGLE_API_KEY not configured")

                    client = genai.Client(api_key=api_key)
                    prompt = f"""You are an expert Indonesian Legal Analyst.
Extract metadata from this legal document. Return ONLY a JSON object with these fields:
- type: Full document type (e.g., "Undang-Undang", "Peraturan Pemerintah")
- type_abbrev: Abbreviation (e.g., "UU", "PP", "PERMEN")
- number: Document number (e.g., "6", "28")
- year: Year (e.g., "2023", "2025")
- title: Document title
- issuer: Issuing body

Document text (first 3000 chars):
{cleaned_text[:3000]}

Return ONLY valid JSON, no markdown."""

                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    response_text = response.text.strip()
                    # Clean markdown if present
                    if response_text.startswith("```"):
                        response_text = response_text.split("```")[1]
                        if response_text.startswith("json"):
                            response_text = response_text[4:]
                    ai_metadata = json_module.loads(response_text)

                    if ai_metadata:
                        logger.info(
                            f"[STAGE 3] Google AI Studio extraction successful: {ai_metadata.get('type_abbrev')} {ai_metadata.get('number')}",
                            extra={
                                "document_id": document_id,
                                "stage": "metadata_extraction",
                                "metadata_type": ai_metadata.get("type_abbrev"),
                                "metadata_number": ai_metadata.get("number"),
                                "fallback_success": True,
                                "cost_effective": True,
                            },
                        )
                        # Merge AI metadata, preferring AI results for missing fields
                        if not metadata:
                            metadata = ai_metadata
                        else:
                            metadata.update({k: v for k, v in ai_metadata.items() if v})
                except Exception as e:
                    logger.warning(
                        f"[STAGE 3] Google AI Studio fallback failed: {e}",
                        extra={
                            "document_id": document_id,
                            "stage": "metadata_extraction",
                            "fallback_error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

            if not metadata or metadata.get("type_abbrev") == "UNKNOWN":
                logger.warning(
                    "[STAGE 3] Could not extract metadata (Pattern + AI failed), using category fallback",
                    extra={
                        "document_id": document_id,
                        "stage": "metadata_extraction",
                        "fallback_reason": "pattern_and_ai_failed",
                        "category": category,
                    },
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

            # Add Drive file info if available
            if drive_file_id:
                base_metadata["drive_file_id"] = drive_file_id
            if drive_web_link:
                base_metadata["drive_web_link"] = drive_web_link

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

            logger.info(
                f"[STAGE 6] Successfully ingested legal document: {document_title}",
                extra={
                    "document_id": document_id,
                    "stage": "completion",
                    "chunks_created": indexing_result["chunks_indexed"],
                    "parent_documents": indexing_result["parent_documents"],
                    "total_bab": indexing_result.get("total_bab", 0),
                    "total_pasal": indexing_result.get("total_pasal", 0),
                },
            )

            # STAGE 7: Knowledge Graph Extraction (Permanent)
            kg_extraction_result = {}
            if self.kg_enabled and indexing_result["chunks_indexed"] > 0:
                kg_start = time.time()
                try:
                    kg_extractor = await self._get_kg_extractor()

                    if kg_extractor is None:
                        logger.info(
                            "[STAGE 7] KG extractor not available - skipping KG extraction",
                            extra={
                                "document_id": document_id,
                                "stage": "kg_extraction",
                                "skipped": True,
                                "skip_reason": "extractor_not_available",
                            },
                        )
                        kg_extraction_result = {"skipped": "extractor_not_available"}
                    else:
                        # Extract KG from newly created chunks
                        # Usa collection_name corrente (potrebbe essere override)
                        logger.info(
                            "[STAGE 7] Starting KG extraction...",
                            extra={
                                "document_id": document_id,
                                "stage": "kg_extraction",
                                "collection_name": target_collection,
                            },
                        )
                        kg_result = await kg_extractor.extract_from_collection(
                            collection_name=target_collection,
                            document_id=doc_id,  # Filtra solo chunks di questo documento
                            limit=None,  # Processa tutti i chunks del documento
                            dry_run=False,
                        )

                        kg_duration = time.time() - kg_start

                        logger.info(
                            f"[STAGE 7] KG extraction completed: {kg_result.get('entities_extracted', 0)} entities, "
                            f"{kg_result.get('relationships_extracted', 0)} relationships",
                            extra={
                                "document_id": document_id,
                                "stage": "kg_extraction",
                                "entities_extracted": kg_result.get("entities_extracted", 0),
                                "relationships_extracted": kg_result.get(
                                    "relationships_extracted", 0
                                ),
                                "chunks_processed": kg_result.get("chunks_processed", 0),
                                "duration_seconds": kg_duration,
                                "success": True,
                            },
                        )

                        # Aggiungi KG stats al risultato
                        kg_extraction_result = {
                            "entities": kg_result.get("entities_extracted", 0),
                            "relationships": kg_result.get("relationships_extracted", 0),
                            "duration_seconds": kg_duration,
                        }

                except Exception as e:
                    # Non bloccare ingestione se KG fallisce - logga ma continua
                    error_msg = str(e)
                    kg_duration = time.time() - kg_start
                    logger.warning(
                        f"[STAGE 7] KG extraction failed (non-blocking): {error_msg}",
                        extra={
                            "document_id": document_id,
                            "stage": "kg_extraction",
                            "error": error_msg,
                            "error_type": type(e).__name__,
                            "duration_seconds": kg_duration,
                            "non_blocking": True,
                        },
                    )
                    kg_extraction_result = {"error": error_msg}
                    # Non rilanciare l'eccezione - l'ingestione deve continuare

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

            result = {
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

            # Add KG extraction results if available
            if kg_extraction_result:
                result["kg_extraction"] = kg_extraction_result

            # Semantic cache: wipe the legal domain so next reader sees fresh answers
            # within the next request, rather than waiting the 4h per-domain TTL.
            try:
                from backend.services.caching.semantic_cache import (
                    DOMAIN_LEGAL,
                    invalidate_by_domain,
                )

                await invalidate_by_domain(DOMAIN_LEGAL)
            except Exception as cache_exc:
                logger.debug(
                    "Semantic cache legal-domain invalidation skipped: %s",
                    cache_exc,
                )

            return result

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

    async def _ensure_drive_folder_exists(
        self,
        drive_service,
        folder_path: str,
    ) -> str:
        """
        Trova o crea cartella su Google Drive.

        Args:
            drive_service: TeamDriveService instance
            folder_path: Path relativo da root (es: "BALI ZERO/PERATURAN")

        Returns:
            Folder ID della cartella finale
        """
        from backend.app.core.config import settings

        # Split path in componenti
        parts = [p.strip() for p in folder_path.split("/") if p.strip()]

        # Inizia dalla root folder (da settings)
        current_parent_id = settings.google_drive_root_folder_id or "root"

        # Naviga/crea ogni livello
        for folder_name in parts:
            # Cerca cartella esistente usando list_files (più preciso per parent)
            try:
                parent_files_result = await drive_service.list_files(folder_id=current_parent_id)
                parent_files = parent_files_result.get("files", [])

                # Cerca cartella con nome esatto
                matching_folder = None
                for pf in parent_files:
                    if pf.get("name") == folder_name and pf.get("type") == "folder":
                        matching_folder = pf
                        break

                if matching_folder:
                    current_parent_id = matching_folder["id"]
                    logger.debug(f"Found existing Drive folder: {folder_name}")
                else:
                    # Crea cartella
                    folder = await drive_service.create_folder(
                        name=folder_name,
                        parent_folder_id=current_parent_id,
                    )
                    current_parent_id = folder["id"]
                    logger.info(f"Created Drive folder: {folder_name} ({current_parent_id})")
            except Exception as e:
                # Se list_files fallisce, prova a creare direttamente
                logger.warning(
                    f"Error listing files in {current_parent_id}: {e}. Attempting to create folder..."
                )
                try:
                    folder = await drive_service.create_folder(
                        name=folder_name,
                        parent_folder_id=current_parent_id,
                    )
                    current_parent_id = folder["id"]
                    logger.info(f"Created Drive folder: {folder_name} ({current_parent_id})")
                except Exception as create_error:
                    logger.error(f"Failed to create folder {folder_name}: {create_error}")
                    raise

        return current_parent_id

    async def _get_kg_extractor(self) -> None:
        """Lazy initialization of KG extractor."""
        if self.kg_extractor is None:
            import os
            import sys

            import asyncpg

            from backend.app.core.config import settings

            try:
                # Import KGIncrementalExtractor from scripts
                # File is at: apps/backend-rag/scripts/kg_incremental_extraction.py
                # Current file: apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py
                # Navigate: backend/services/ingestion -> backend/services -> backend -> apps/backend-rag
                backend_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                # backend_path is now apps/backend-rag/backend
                backend_rag_path = os.path.dirname(backend_path)  # apps/backend-rag
                scripts_path = os.path.join(backend_rag_path, "scripts")
                kg_extractor_path = os.path.join(scripts_path, "kg_incremental_extraction.py")

                if not os.path.exists(kg_extractor_path):
                    raise ImportError(
                        f"kg_incremental_extraction.py not found at {kg_extractor_path}"
                    )

                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)

                # Import with proper module path
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "kg_incremental_extraction", kg_extractor_path
                )
                kg_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(kg_module)
                KGIncrementalExtractor = kg_module.KGIncrementalExtractor

                # Initialize LLM client for KG extraction.
                gemini = None
                openai_client = None
                provider = "gemini"
                try:
                    from openai import AsyncOpenAI

                    openai_key = os.environ.get("OPENAI_API_KEY")
                    openai_base_url = os.environ.get("OPENAI_BASE_URL")
                    if openai_key:
                        client_kwargs = {"api_key": openai_key}
                        if openai_base_url:
                            client_kwargs["base_url"] = openai_base_url
                        openai_client = AsyncOpenAI(**client_kwargs)
                        provider = "openai"
                        logger.info("OpenAI client initialized for KG extraction")
                except Exception as e:
                    logger.warning(f"Could not initialize OpenAI for KG extraction: {e}")

                try:
                    if openai_client is None:
                        import tempfile

                        from google import genai

                        creds_json = settings.google_credentials_json
                        project_id = os.environ.get(
                            "GOOGLE_PROJECT_ID", "gen-lang-client-0498009027"
                        )
                        location = os.environ.get("GOOGLE_LOCATION", "us-central1")

                        if creds_json:
                            with tempfile.NamedTemporaryFile(
                                mode="w", suffix=".json", delete=False
                            ) as f:
                                f.write(creds_json)
                                creds_path = f.name
                            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

                        client = genai.Client(
                            vertexai=True, project=project_id, location=location
                        )
                        gemini = client
                        logger.info("Gemini client initialized for KG extraction")
                except Exception as e:
                    logger.warning(f"Could not initialize Gemini for KG extraction: {e}")

                # Create DB pool (with error handling)
                db_pool = None
                if settings.database_url:
                    try:
                        db_pool = await asyncpg.create_pool(
                            settings.database_url, min_size=1, max_size=5
                        )
                    except Exception as db_error:
                        logger.warning(
                            f"Could not create database pool for KG extraction: {db_error}"
                        )
                        # Return None to skip KG extraction
                        return None

                if not db_pool:
                    logger.warning("Database pool not available - skipping KG extraction")
                    return None

                # Initialize extractor
                self.kg_extractor = KGIncrementalExtractor(
                    db_pool=db_pool,
                    qdrant_url=settings.qdrant_url,
                    qdrant_api_key=settings.qdrant_api_key or "",
                    gemini_client=gemini,
                    openai_client=openai_client,
                    provider=provider,
                )
                logger.info("KG extractor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize KG extractor: {e}")
                return None

        return self.kg_extractor

    def detect_legal_document(self, text: str) -> bool:
        """
        Detect if text appears to be an Indonesian legal document.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a legal document
        """
        return self.metadata_extractor.is_legal_document(text)
