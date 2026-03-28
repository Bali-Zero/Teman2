"""
Auto Ingestion Service - Phase 8

Automatically extracts structured data from scraped legal documents
using LLM and ingests into Qdrant knowledge graph.

Features:
- LLM-based content extraction
- Structured data parsing
- Qdrant ingestion with embeddings
- Batch processing
- Quality validation
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.services.monitoring import AlertLevel, get_alert_service

logger = logging.getLogger(__name__)


class IngestionStatus(str, Enum):
    """Status of ingestion process"""

    PENDING = "pending"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    EMBEDDING = "embedding"
    INGESTING = "ingesting"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"  # Failed quality check


class DocumentType(str, Enum):
    """Types of legal documents"""

    UNDANG_UNDANG = "undang_undang"  # Law
    PERATURAN_PEMERINTAH = "peraturan_pemerintah"  # Government Regulation
    PERATURAN_PRESIDEN = "peraturan_presiden"  # Presidential Regulation
    PERATURAN_MENTERI = "peraturan_menteri"  # Ministerial Regulation
    KEPUTUSAN = "keputusan"  # Decision
    SURAT_EDARAN = "surat_edaran"  # Circular Letter
    PERATURAN_DAERAH = "peraturan_daerah"  # Regional Regulation
    KBLI = "kbli"  # Business classification
    OTHER = "other"


@dataclass
class ExtractedDocument:
    """Structured document extracted by LLM"""

    document_id: str
    source_id: str
    title: str
    document_type: DocumentType
    document_number: str = ""  # e.g., "UU No. 13 Tahun 2003"
    publication_date: str = ""  # ISO format date
    effective_date: str = ""  # ISO format date
    issuing_authority: str = ""  # e.g., "Kemenkumham", "BPK"
    subject: str = ""  # Main subject/topic
    summary: str = ""  # Brief summary
    key_points: list[str] = field(default_factory=list)
    related_documents: list[str] = field(default_factory=list)
    full_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0  # LLM confidence

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "document_type": self.document_type.value,
            "document_number": self.document_number,
            "publication_date": self.publication_date,
            "effective_date": self.effective_date,
            "issuing_authority": self.issuing_authority,
            "subject": self.subject,
            "summary": self.summary,
            "key_points": self.key_points,
            "related_documents": self.related_documents,
            "full_text": self.full_text[:1000] + "..."
            if len(self.full_text) > 1000
            else self.full_text,
            "metadata": self.metadata,
            "confidence_score": self.confidence_score,
        }


@dataclass
class IngestionResult:
    """Result of ingestion process"""

    document_id: str
    status: IngestionStatus
    started_at: datetime
    completed_at: datetime | None = None
    extracted_document: ExtractedDocument | None = None
    qdrant_id: str | None = None  # ID in Qdrant
    error_message: str | None = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "document_id": self.document_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "extracted": self.extracted_document.to_dict() if self.extracted_document else None,
            "qdrant_id": self.qdrant_id,
            "error": self.error_message,
            "processing_time_ms": self.processing_time_ms,
        }


class AutoIngestionService:
    """
    Service for automatic ingestion of legal documents into Qdrant.

    Uses LLM to extract structured data from raw scraped content.
    """

    # LLM extraction prompt
    EXTRACTION_PROMPT = """You are a legal document extraction specialist. Analyze the following Indonesian legal document and extract structured information.

Document Title: {title}
Source: {source}
Content:
{content}

Extract the following information in JSON format:
{{
    "document_type": "One of: undang_undang, peraturan_pemerintah, peraturan_presiden, peraturan_menteri, keputusan, surat_edaran, peraturan_daerah, kbli, other",
    "document_number": "Full document number (e.g., 'UU No. 13 Tahun 2003' or 'PP No. 78 Tahun 2015')",
    "publication_date": "Publication date in YYYY-MM-DD format if found, else empty",
    "effective_date": "Effective date in YYYY-MM-DD format if found, else empty",
    "issuing_authority": "The government body that issued this (e.g., 'Kemenkumham', 'Kemenkeu', 'BPK')",
    "subject": "Main subject/topic of the document (max 100 chars)",
    "summary": "Brief summary of the document (2-3 sentences)",
    "key_points": ["List of 3-5 key points or provisions"],
    "related_documents": ["List of related document numbers referenced"],
    "confidence_score": "Number between 0.0 and 1.0 indicating extraction confidence"
}}

Return ONLY the JSON object, no other text."""

    def __init__(
        self,
        llm_client=None,
        qdrant_client=None,
        embedding_service=None,
        quality_service=None,
        db_pool=None,
    ) -> None:
        """
        Initialize auto ingestion service.

        Args:
            llm_client: LLM client for extraction
            qdrant_client: Qdrant client for storage
            embedding_service: Service for generating embeddings
            quality_service: QualityCheckService for validation
            db_pool: PostgreSQL connection pool
        """
        self.llm = llm_client
        self.qdrant = qdrant_client
        self.embedding = embedding_service
        self.quality = quality_service
        self.db_pool = db_pool
        self.alert_service = get_alert_service()

        self.ingestion_stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "rejected": 0,
            "total_chunks_ingested": 0,
            "last_run": None,
        }

        logger.info("✅ AutoIngestionService initialized")
        logger.info(f"   LLM: {'✅' if llm_client else '❌'}")
        logger.info(f"   Qdrant: {'✅' if qdrant_client else '❌'}")
        logger.info(f"   Embeddings: {'✅' if embedding_service else '❌'}")

    async def initialize_db(self) -> None:
        """Initialize database tables for ingestion tracking"""
        if not self.db_pool:
            logger.warning("No DB pool provided")
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS kg_ingestion_results (
                        document_id VARCHAR(32) PRIMARY KEY,
                        source_id VARCHAR(64) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        completed_at TIMESTAMP WITH TIME ZONE,
                        extracted_data JSONB,
                        qdrant_id VARCHAR(64),
                        error_message TEXT,
                        processing_time_ms FLOAT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_ingestion_status
                    ON kg_ingestion_results(status)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kg_ingestion_source
                    ON kg_ingestion_results(source_id)
                """)

            logger.info("✅ Ingestion tracking tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize DB tables: {e}")
            raise

    async def ingest_document(
        self,
        scraped_doc,
        target_collection: str = "legal_updates",
    ) -> IngestionResult:
        """
        Ingest a single scraped document.

        Args:
            scraped_doc: ScrapedDocument from scraper
            target_collection: Qdrant collection name

        Returns:
            IngestionResult with status and details
        """
        start_time = datetime.now()
        result = IngestionResult(
            document_id=scraped_doc.document_id,
            status=IngestionStatus.PENDING,
            started_at=start_time,
        )

        logger.info(f"📥 Ingesting: {scraped_doc.title[:60]}...")

        try:
            # Step 1: Extract structured data
            result.status = IngestionStatus.EXTRACTING
            extracted = await self._extract_document(scraped_doc)
            result.extracted_document = extracted

            # Step 2: Quality validation
            result.status = IngestionStatus.VALIDATING
            if self.quality:
                quality_report = await self.quality.validate(extracted)
                if not quality_report.is_acceptable:
                    result.status = IngestionStatus.REJECTED
                    result.error_message = f"Quality check failed: {quality_report.issues}"
                    self.ingestion_stats["rejected"] += 1
                    await self._save_result(result)
                    return result

            # Step 3: Generate embeddings and ingest to Qdrant
            result.status = IngestionStatus.EMBEDDING
            qdrant_id = await self._ingest_to_qdrant(extracted, target_collection)
            result.qdrant_id = qdrant_id

            # Complete
            result.status = IngestionStatus.COMPLETED
            result.completed_at = datetime.now()
            result.processing_time_ms = (result.completed_at - start_time).total_seconds() * 1000

            self.ingestion_stats["successful"] += 1
            self.ingestion_stats["total_chunks_ingested"] += len(extracted.key_points) + 1

            logger.info(f"✅ Ingested: {scraped_doc.title[:40]}... (ID: {qdrant_id})")

        except Exception as e:
            result.status = IngestionStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            result.processing_time_ms = (result.completed_at - start_time).total_seconds() * 1000

            self.ingestion_stats["failed"] += 1
            logger.error(f"❌ Ingestion failed for {scraped_doc.document_id}: {e}")

        self.ingestion_stats["total_processed"] += 1
        self.ingestion_stats["last_run"] = datetime.now().isoformat()

        await self._save_result(result)
        return result

    async def ingest_batch(
        self,
        scraped_docs: list,
        target_collection: str = "legal_updates",
    ) -> list[IngestionResult]:
        """
        Ingest multiple documents in batch.

        Args:
            scraped_docs: List of ScrapedDocument objects
            target_collection: Qdrant collection name

        Returns:
            List of IngestionResult objects
        """
        logger.info(f"📦 Batch ingestion: {len(scraped_docs)} documents")

        results = []
        for doc in scraped_docs:
            try:
                result = await self.ingest_document(doc, target_collection)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch ingestion error for {doc.document_id}: {e}")
                results.append(
                    IngestionResult(
                        document_id=doc.document_id,
                        status=IngestionStatus.FAILED,
                        started_at=datetime.now(),
                        completed_at=datetime.now(),
                        error_message=str(e),
                    )
                )

        # Send batch summary alert
        successful = sum(1 for r in results if r.status == IngestionStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == IngestionStatus.FAILED)
        rejected = sum(1 for r in results if r.status == IngestionStatus.REJECTED)

        if failed > 0 or rejected > 0:
            await self.alert_service.send_alert(
                title="📦 Batch Ingestion Summary",
                message=f"Processed {len(results)} documents: {successful} success, {failed} failed, {rejected} rejected",
                level=AlertLevel.WARNING if failed > 0 else AlertLevel.INFO,
                metadata={
                    "total": len(results),
                    "successful": successful,
                    "failed": failed,
                    "rejected": rejected,
                },
            )

        return results

    async def _extract_document(self, scraped_doc) -> ExtractedDocument:
        """Extract structured data from scraped document using LLM"""
        if not self.llm:
            # Fallback: create basic extracted document without LLM
            logger.warning("No LLM client, using basic extraction")
            return ExtractedDocument(
                document_id=scraped_doc.document_id,
                source_id=scraped_doc.source_id,
                title=scraped_doc.title,
                document_type=DocumentType.OTHER,
                full_text=scraped_doc.content,
                confidence_score=0.5,
            )

        # Build extraction prompt
        prompt = self.EXTRACTION_PROMPT.format(
            title=scraped_doc.title,
            source=scraped_doc.source_id,
            content=scraped_doc.content[:8000],  # Limit content length
        )

        try:
            # Call LLM for extraction
            response = await self.llm.conversational(
                message=prompt,
                user_id="auto_ingestion",
                conversation_history=[],
                max_tokens=4096,
            )

            # Parse JSON response
            text = response.get("text", "")
            # Extract JSON from response (handle markdown code blocks)
            json_str = self._extract_json(text)
            data = json.loads(json_str)

            # Create ExtractedDocument
            doc_type = DocumentType(data.get("document_type", "other"))

            return ExtractedDocument(
                document_id=scraped_doc.document_id,
                source_id=scraped_doc.source_id,
                title=scraped_doc.title,
                document_type=doc_type,
                document_number=data.get("document_number", ""),
                publication_date=data.get("publication_date", ""),
                effective_date=data.get("effective_date", ""),
                issuing_authority=data.get("issuing_authority", ""),
                subject=data.get("subject", ""),
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                related_documents=data.get("related_documents", []),
                full_text=scraped_doc.content,
                metadata=scraped_doc.metadata,
                confidence_score=float(data.get("confidence_score", 0.0)),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {text[:500]}")
            # Fallback
            return ExtractedDocument(
                document_id=scraped_doc.document_id,
                source_id=scraped_doc.source_id,
                title=scraped_doc.title,
                document_type=DocumentType.OTHER,
                full_text=scraped_doc.content,
                confidence_score=0.3,
            )

        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            raise

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response text"""
        # Try to find JSON in markdown code blocks
        import re

        # Look for ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        # Look for raw JSON object
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1)

        # Return original if no JSON found
        return text

    async def _ingest_to_qdrant(
        self,
        extracted: ExtractedDocument,
        collection: str,
    ) -> str | None:
        """Ingest extracted document to Qdrant"""
        if not self.qdrant or not self.embedding:
            logger.warning("Qdrant or embedding service not available")
            return None

        try:
            # Prepare chunks for ingestion
            chunks = self._create_chunks(extracted)

            # Generate embeddings and ingest
            qdrant_ids = []
            for chunk in chunks:
                embedding = await self.embedding.embed(chunk["text"])

                # Ingest to Qdrant
                qdrant_id = await self.qdrant.upsert(
                    collection=collection,
                    vector=embedding,
                    payload=chunk["metadata"],
                )
                qdrant_ids.append(qdrant_id)

            # Return first ID as document ID
            return qdrant_ids[0] if qdrant_ids else None

        except Exception as e:
            logger.error(f"Qdrant ingestion error: {e}")
            raise

    def _create_chunks(self, extracted: ExtractedDocument) -> list[dict[str, Any]]:
        """Create text chunks for embedding"""
        chunks = []

        # Main document chunk
        main_text = f"""{extracted.title}

Document Type: {extracted.document_type.value}
Number: {extracted.document_number}
Authority: {extracted.issuing_authority}
Subject: {extracted.subject}

Summary:
{extracted.summary}

Full Text:
{extracted.full_text[:4000]}
"""
        chunks.append(
            {
                "text": main_text,
                "metadata": {
                    "document_id": extracted.document_id,
                    "source_id": extracted.source_id,
                    "title": extracted.title,
                    "document_type": extracted.document_type.value,
                    "document_number": extracted.document_number,
                    "publication_date": extracted.publication_date,
                    "issuing_authority": extracted.issuing_authority,
                    "subject": extracted.subject,
                    "chunk_type": "main",
                },
            }
        )

        # Key points chunks
        for i, point in enumerate(extracted.key_points):
            chunks.append(
                {
                    "text": f"{extracted.title} - Key Point {i + 1}: {point}",
                    "metadata": {
                        "document_id": extracted.document_id,
                        "source_id": extracted.source_id,
                        "title": extracted.title,
                        "document_type": extracted.document_type.value,
                        "chunk_type": "key_point",
                        "point_index": i,
                    },
                }
            )

        return chunks

    async def _save_result(self, result: IngestionResult) -> None:
        """Save ingestion result to database"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kg_ingestion_results (
                        document_id, source_id, status, started_at,
                        completed_at, extracted_data, qdrant_id,
                        error_message, processing_time_ms, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    ON CONFLICT (document_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        extracted_data = EXCLUDED.extracted_data,
                        qdrant_id = EXCLUDED.qdrant_id,
                        error_message = EXCLUDED.error_message,
                        processing_time_ms = EXCLUDED.processing_time_ms,
                        updated_at = NOW()
                    """,
                    result.document_id,
                    result.extracted_document.source_id if result.extracted_document else "",
                    result.status.value,
                    result.started_at,
                    result.completed_at,
                    json.dumps(result.extracted_document.to_dict())
                    if result.extracted_document
                    else None,
                    result.qdrant_id,
                    result.error_message,
                    result.processing_time_ms,
                )
        except Exception as e:
            logger.error(f"Failed to save ingestion result: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get ingestion statistics"""
        total = self.ingestion_stats["total_processed"]
        success = self.ingestion_stats["successful"]
        success_rate = (success / total * 100) if total > 0 else 0

        return {
            **self.ingestion_stats,
            "success_rate": f"{success_rate:.1f}%",
        }

    async def get_recent_results(
        self,
        hours: int = 24,
        status: IngestionStatus | None = None,
    ) -> list[IngestionResult]:
        """Get recent ingestion results"""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                query = f"""
                    SELECT * FROM kg_ingestion_results
                    WHERE started_at > NOW() - INTERVAL '{hours} hours'
                """

                if status:
                    query += f" AND status = '{status.value}'"

                query += " ORDER BY started_at DESC"

                rows = await conn.fetch(query)

                return [
                    IngestionResult(
                        document_id=row["document_id"],
                        status=IngestionStatus(row["status"]),
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        extracted_document=ExtractedDocument(**row["extracted_data"])
                        if row["extracted_data"]
                        else None,
                        qdrant_id=row["qdrant_id"],
                        error_message=row["error_message"],
                        processing_time_ms=row["processing_time_ms"],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get recent results: {e}")
            return []
