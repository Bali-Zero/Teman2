"""Per-file pipeline orchestrator for GARUDA Curator Agent.

Step order is CRITICAL per spec:
  1. Size cap check
  2. Download file bytes
  3. Extract content (type-specific handler)
  4. DLP check → quarantine if PII
  5. Compute content_hash + SELECT dedup
  6. Embedding (OpenAI)
  7. Qdrant upsert FIRST  ← atomic ordering guarantee
  8. Postgres commit ONLY after Qdrant OK
  9. Error isolated per file (batch continues)
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

from .drive_client import DriveFile
from .embedder import Embedder
from .handlers import extract_content
from .postgres_writer import PostgresWriter
from .qdrant_writer import QdrantWriter
from ..security.dlp import dlp_check

logger = logging.getLogger(__name__)

SIZE_CAP_BYTES = 500_000_000  # 500 MB

# ---------------------------------------------------------------------------
# Folder → category mapping
# ---------------------------------------------------------------------------

_FOLDER_TO_CATEGORY: dict[str, str] = {
    "1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq": "photos",
    "1QZ6hnEqUAxIwhz6yhWeXh6m3QsgFnJ6G": "videos",
    "1CX2K-MtRQVMqDwlbcT9gLTGf4mGmGVh3": "audio",
    "1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1": "intelligence",
    "1b7ERuRssLPAxKYHtAhv2Kx-G81ot0Ulb": "drafts",
    "18E-rHjO94JFqao1xMCoA2mmy4oK9Waw7": "research",
    "1dX87C514aOZO82NTxl8meHiiO3dhIJNl": "published",
}

_KEYWORD_TAGS: list[str] = [
    "bali",
    "visa",
    "property",
    "tax",
    "kbli",
    "company",
    "tourism",
]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def guess_category(parent_folder_id: str) -> str:
    """Map parent folder ID to category string."""
    return _FOLDER_TO_CATEGORY.get(parent_folder_id, "intelligence")


def auto_tag(text: str, mime_type: str) -> list[str]:
    """Simple auto-tagger based on content and mime type."""
    tags: list[str] = []
    if "video/" in mime_type:
        tags.append("video")
    elif "image/" in mime_type:
        tags.append("image")
    elif "audio/" in mime_type:
        tags.append("audio")
    elif "pdf" in mime_type:
        tags.append("document")

    text_lower = (text or "").lower()
    for kw in _KEYWORD_TAGS:
        if kw in text_lower:
            tags.append(kw)

    return list(set(tags))


def compute_content_hash(file_id: str, text: str) -> str:
    """SHA-256 of file_id + first 1000 chars of text (per spec)."""
    raw = file_id + (text[:1000] if text else "")
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    file_id: str
    status: str  # "indexed" | "skipped_dedup" | "quarantined" | "skipped_size" | "error"
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class Pipeline:
    def __init__(
        self,
        embedder: Embedder,
        qdrant_writer: QdrantWriter,
        postgres_writer: PostgresWriter,
        drive_client: Any,  # DriveClient — typed as Any to avoid circular import issues
    ) -> None:
        self.embedder = embedder
        self.qdrant = qdrant_writer
        self.pg = postgres_writer
        self.drive = drive_client

    async def index_file_safe(self, file: DriveFile) -> PipelineResult:
        """Full per-file pipeline with error isolation.

        Each file is fully independent; an exception in one does NOT abort
        the batch — it is caught, logged, and returned as status="error".
        """
        try:
            # ------------------------------------------------------------------
            # Step 1: Size cap
            # ------------------------------------------------------------------
            if file.size > SIZE_CAP_BYTES:
                logger.info(
                    "Skipping %s: too large (%d bytes)", file.id, file.size
                )
                return PipelineResult(file.id, "skipped_size", reason="too_large")

            # ------------------------------------------------------------------
            # Step 2: Download
            # ------------------------------------------------------------------
            file_bytes: bytes = await self.drive.download_file(file.id)

            # ------------------------------------------------------------------
            # Step 3: Extract content
            # ------------------------------------------------------------------
            text, extraction_meta = await extract_content(
                file_bytes, file.mime_type, file.name
            )

            # ------------------------------------------------------------------
            # Step 4: DLP check
            # ------------------------------------------------------------------
            dlp_result = await dlp_check(text, file.name)
            if dlp_result.has_pii:
                logger.warning(
                    "PII detected in %s: %s", file.name, dlp_result.patterns
                )
                # Quarantine record saved to Postgres — no Qdrant entry for quarantined files
                await self.pg.mark_quarantined(
                    file.id,
                    {
                        "patterns": dlp_result.patterns,
                        "confidence": dlp_result.confidence,
                    },
                )
                return PipelineResult(
                    file.id, "quarantined", reason=str(dlp_result.patterns)
                )

            # ------------------------------------------------------------------
            # Step 5: Content hash + dedup
            # ------------------------------------------------------------------
            content_hash = compute_content_hash(file.id, text)
            existing_file_id = await self.pg.check_content_hash(
                content_hash, file.id
            )
            if existing_file_id:
                logger.info(
                    "Skipping %s: duplicate of %s", file.id, existing_file_id
                )
                return PipelineResult(
                    file.id,
                    "skipped_dedup",
                    reason=f"duplicate_of:{existing_file_id}",
                )

            # ------------------------------------------------------------------
            # Step 6: Embedding
            # ------------------------------------------------------------------
            description: str = extraction_meta.get(
                "description", text[:500] if text else ""
            )
            embed_text = description if description else text
            vector = await self.embedder.embed_text(embed_text)

            # ------------------------------------------------------------------
            # Step 7: Qdrant upsert FIRST (CRITICAL: atomic order per spec)
            # ------------------------------------------------------------------
            category = guess_category(
                file.parents[0] if file.parents else ""
            )
            tags = auto_tag(text, file.mime_type)
            qdrant_payload: dict[str, Any] = {
                "file_id": file.id,
                "category": category,
                "mime": file.mime_type,
                "name": file.name,
                "path": "/".join(file.parents),
                "description": (description or text)[:500],
                "tags": tags,
                "modified_at": file.modified_time.isoformat(),
                "drive_version": file.version,
                "content_hash": content_hash,
                "archived": False,
                "quarantined": False,
            }
            await self.qdrant.upsert(file.id, vector, qdrant_payload)

            # ------------------------------------------------------------------
            # Step 8: Postgres ONLY after Qdrant success
            # ------------------------------------------------------------------
            await self.pg.upsert_index_record(
                file_id=file.id,
                name=file.name,
                path="/".join(file.parents),
                parent_folder=file.parents[0] if file.parents else "",
                category=category,
                mime_type=file.mime_type,
                size_bytes=file.size,
                modified_at=file.modified_time,
                drive_version=file.version,
                extracted_text=text,
                description=description or "",
                tags=tags,
                content_hash=content_hash,
                metadata=extraction_meta,
            )

            logger.info(
                "Indexed %s (%s, %s)", file.name, file.id, category
            )
            return PipelineResult(file.id, "indexed")

        except Exception as e:
            # Step 9: Log error per file, DON'T re-raise (batch continues)
            logger.error(
                "Failed to index file %s: %s", file.id, e, exc_info=True
            )
            return PipelineResult(file.id, "error", reason=str(e))
