"""
Client Portal Service (façade).

PortalService composes four internal mixins, each owning a cohesive slice of
the portal API surface:

    - PortalDashboardMixin   dashboard / visa / companies / tax / timeline
    - PortalDocumentsMixin   documents list + upload pipeline (virus / OCR / Drive)
    - PortalBillingMixin     invoices + profile update
    - PortalMessagingMixin   messages + preferences

This module keeps only:
    - the PortalService class itself (MRO composition + constructor + shared
      state: pool, _metrics, _upload_rate_limits, rate-limit constants)
    - DB-error classifiers shared across mixins
      (_is_undefined_column_error / _is_undefined_table_error)
    - cross-cutting operations (cleanup_orphaned_documents, get_upload_metrics,
      health_check)
    - backward-compat re-exports of document_processing helpers so existing
      callers can keep doing
      `from backend.services.portal.portal_service import VirusScanner`.
"""

from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.portal._mixins.billing import PortalBillingMixin
from backend.services.portal._mixins.dashboard import PortalDashboardMixin
from backend.services.portal._mixins.documents import PortalDocumentsMixin
from backend.services.portal._mixins.messaging import PortalMessagingMixin

# Re-exported for backward compatibility — see module docstring.
from backend.services.portal.document_processing import (
    MAGIC_AVAILABLE,
    PDF_VISION_AVAILABLE,
    PYMUPDF_AVAILABLE,
    DocumentOCR,
    ExpiryDetector,
    VirusScanner,
)

logger = get_logger(__name__)

__all__ = [
    "PortalService",
    # Re-exports for backward compatibility:
    "VirusScanner",
    "DocumentOCR",
    "ExpiryDetector",
    "PDF_VISION_AVAILABLE",
    "PYMUPDF_AVAILABLE",
    "MAGIC_AVAILABLE",
]


class PortalService(
    PortalBillingMixin,
    PortalDashboardMixin,
    PortalDocumentsMixin,
    PortalMessagingMixin,
):
    """Service for client portal data access."""

    # Rate limiting: max uploads per client per window (15 min)
    _upload_rate_limits: dict[int, list[float]] = {}
    MAX_UPLOADS_PER_WINDOW = 10
    RATE_WINDOW_SECONDS = 900  # 15 minutes

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self._metrics = {
            "uploads_total": 0,
            "uploads_failed": 0,
            "virus_blocked": 0,
            "drive_uploads": 0,
            "ocr_processed": 0,
        }

    @staticmethod
    def _is_undefined_column_error(exc: Exception) -> bool:
        # PostgreSQL: undefined_column = 42703
        return getattr(exc, "sqlstate", None) == "42703"

    @staticmethod
    def _is_undefined_table_error(exc: Exception) -> bool:
        # PostgreSQL: undefined_table = 42P01
        return getattr(exc, "sqlstate", None) == "42P01"

    # ================================================
    # CLEANUP & HEALTH CHECK
    # ================================================

    async def cleanup_orphaned_documents(self, days: int = 7) -> dict[str, Any]:
        """
        Cleanup documents that failed to upload to Drive (storage_type='pending').

        Args:
            days: Delete documents older than this many days

        Returns:
            {"deleted": int, "errors": int}
        """
        result = {"deleted": 0, "errors": 0, "checked": 0}

        async with self.pool.acquire() as conn:
            # Find orphaned documents
            orphaned = await conn.fetch(
                """
                SELECT id, file_name, client_id, created_at
                FROM documents
                WHERE storage_type = 'pending'
                AND created_at < NOW() - INTERVAL '$1 days'
                """,
                days,
            )

            result["checked"] = len(orphaned)

            for doc in orphaned:
                try:
                    await conn.execute("DELETE FROM documents WHERE id = $1", doc["id"])
                    result["deleted"] += 1
                    logger.info(f"Deleted orphaned document: {doc['file_name']} (ID: {doc['id']})")
                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Failed to delete orphaned document {doc['id']}: {e}")

        return result

    async def get_upload_metrics(self) -> dict[str, Any]:
        """
        Get metrics about document uploads.

        Returns:
            Metrics dictionary with upload statistics
        """
        metrics = dict(self._metrics)  # Copy current metrics

        async with self.pool.acquire() as conn:
            # Get DB stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_docs,
                    COUNT(*) FILTER (WHERE storage_type = 'google_drive') as drive_uploads,
                    COUNT(*) FILTER (WHERE expiry_date IS NOT NULL) as with_expiry,
                    COUNT(*) FILTER (WHERE extracted_text IS NOT NULL AND extracted_text != '') as with_ocr
                FROM documents
                WHERE uploaded_source = 'client'
                AND created_at > NOW() - INTERVAL '24 hours'
                """,
            )

            metrics["last_24h"] = {
                "total": stats["total_docs"],
                "drive_uploads": stats["drive_uploads"],
                "with_expiry": stats["with_expiry"],
                "with_ocr": stats["with_ocr"],
            }

        return metrics

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for the document upload pipeline.

        Returns:
            Health status dictionary
        """
        checks = {
            "virus_scanner": False,
            "drive_configured": False,
            "drive_token": False,
            "ocr_available": False,
            "database": False,
        }

        # Check virus scanner
        try:
            result = VirusScanner.scan(b"test", "test.pdf")
            checks["virus_scanner"] = result.get("clean") is not None
        except Exception as e:
            logger.debug(f"Virus scanner check failed (non-critical): {e}")

        # Check Drive configuration
        try:
            from backend.services.integrations.google_drive_service import GoogleDriveService

            drive_service = GoogleDriveService(self.pool)
            checks["drive_configured"] = drive_service.is_configured()

            if checks["drive_configured"]:
                token = await drive_service.get_valid_token("SYSTEM")
                checks["drive_token"] = token is not None
        except Exception as e:
            logger.debug(f"Drive config check failed (non-critical): {e}")

        # Check OCR availability
        checks["ocr_available"] = PDF_VISION_AVAILABLE or PYMUPDF_AVAILABLE

        # Check database
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                checks["database"] = True
        except Exception as e:
            logger.debug(f"Database health check failed: {e}")

        all_healthy = all(checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

