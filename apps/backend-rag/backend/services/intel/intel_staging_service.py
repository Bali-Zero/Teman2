"""
Intel Staging Service

Handles staging area operations for Intel articles.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal

from backend.app.core.config import settings
from backend.app.metrics import (
    intel_filter_usage_total,
    intel_search_queries_total,
    intel_sort_usage_total,
    intel_staging_queue_size,
)

logger = logging.getLogger(__name__)


class IntelStagingService:
    """
    Service for managing Intel staging area.

    Handles saving, reading, listing, and archiving staging items.
    """

    def __init__(self) -> None:
        """Initialize the staging service with directory paths."""
        self.base_staging_dir = Path(settings.get_intel_staging_base_dir)
        self.visa_staging_dir = self.base_staging_dir / "visa"
        self.news_staging_dir = self.base_staging_dir / "news"

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure staging directories exist, with fallback to /tmp if needed."""
        try:
            self.visa_staging_dir.mkdir(parents=True, exist_ok=True)
            self.news_staging_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Fallback to /tmp if configured path is not writable (local dev)
            self.base_staging_dir = Path("/tmp/staging")
            self.visa_staging_dir = self.base_staging_dir / "visa"
            self.news_staging_dir = self.base_staging_dir / "news"
            self.visa_staging_dir.mkdir(parents=True, exist_ok=True)
            self.news_staging_dir.mkdir(parents=True, exist_ok=True)

    def get_staging_dir(self, intel_type: Literal["visa", "news"]) -> Path:
        """
        Get staging directory for intel type.

        Args:
            intel_type: "visa" or "news"

        Returns:
            Path to staging directory
        """
        return self.visa_staging_dir if intel_type == "visa" else self.news_staging_dir

    def generate_item_id(
        self, intel_type: Literal["visa", "news"], title: str, source_url: str
    ) -> str:
        """
        Generate unique item ID for staging item.

        Args:
            intel_type: "visa" or "news"
            title: Article title
            source_url: Article source URL

        Returns:
            Unique item ID
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(f"{title}{source_url}".encode()).hexdigest()[:8]
        return f"{intel_type}_{timestamp}_{content_hash}"

    def save_staging_item(
        self,
        intel_type: Literal["visa", "news"],
        item_id: str,
        staging_data: dict[str, Any],
    ) -> Path:
        """
        Save staging item to file.

        Args:
            intel_type: "visa" or "news"
            item_id: Unique item identifier
            staging_data: Item data to save

        Returns:
            Path to saved file
        """
        staging_dir = self.get_staging_dir(intel_type)
        staging_file = staging_dir / f"{item_id}.json"

        # Atomic write: write to temp file first, then rename
        json_content = json.dumps(staging_data, indent=2)
        temp_file = staging_file.with_suffix(".json.tmp")

        try:
            temp_file.write_text(json_content)

            # Atomic rename (works on most filesystems)
            temp_file.replace(staging_file)

        except Exception:
            # Clean up temp file on error
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.debug(f"Failed to clean up temp file {temp_file}: {e}")
                    pass
            raise

        return staging_file

    def load_staging_item(
        self, intel_type: Literal["visa", "news"], item_id: str
    ) -> dict[str, Any] | None:
        """
        Load staging item from file.

        Args:
            intel_type: "visa" or "news"
            item_id: Unique item identifier

        Returns:
            Item data or None if not found
        """
        staging_dir = self.get_staging_dir(intel_type)
        file_path = staging_dir / f"{item_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                f"Error reading staging file {file_path}: {e}",
                exc_info=True,
                extra={"intel_type": intel_type, "item_id": item_id},
            )
            return None

    def check_duplicate(
        self, intel_type: Literal["visa", "news"], source_url: str, days: int = 7
    ) -> dict[str, Any] | None:
        """
        Check if article with same source_url exists in staging.

        Args:
            intel_type: "visa" or "news"
            source_url: Source URL to check
            days: Number of days to check back (default: 7)

        Returns:
            Existing item data if duplicate found, None otherwise
        """
        staging_dir = self.get_staging_dir(intel_type)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        file_paths = list(staging_dir.glob("*.json"))

        for file_path in file_paths:
            try:
                with open(file_path) as f:
                    data = json.load(f)

                if data.get("source_url") == source_url:
                    detected_at = data.get("detected_at")
                    if detected_at:
                        try:
                            detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                            if detected_dt >= cutoff_date:
                                return data
                        except (ValueError, TypeError):
                            # If date parsing fails, consider it a duplicate anyway
                            return data
                    else:
                        # No date, consider it a duplicate
                        return data
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in staging file {file_path}: {e}")
                continue
            except PermissionError as e:
                logger.warning(f"Permission denied reading {file_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error reading staging file {file_path}: {e}", exc_info=True)
                continue
        return None

    def list_pending_items(
        self,
        intel_type: str = "all",
        filter_type: str | None = None,
        sort_type: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        List items pending approval in staging area.

        Args:
            intel_type: "all", "visa", or "news"
            filter_type: Optional filter type
            sort_type: Optional sort type
            search: Optional search query

        Returns:
            Dictionary with items and count
        """
        # Track metrics
        if filter_type and filter_type != "all":
            intel_filter_usage_total.labels(intel_type=intel_type, filter_type=filter_type).inc()

        if sort_type:
            intel_sort_usage_total.labels(intel_type=intel_type, sort_type=sort_type).inc()

        if search:
            intel_search_queries_total.labels(intel_type=intel_type).inc()

        items: list[dict[str, Any]] = []

        dirs_to_check: list[tuple[str, Path]] = []
        if intel_type in ["all", "visa"]:
            dirs_to_check.append(("visa", self.visa_staging_dir))
        if intel_type in ["all", "news"]:
            dirs_to_check.append(("news", self.news_staging_dir))

        for category, directory in dirs_to_check:
            if not directory.exists():
                logger.warning(
                    f"Directory does not exist: {directory}",
                    extra={"category": category},
                )
                continue

            for file_path in directory.glob("*.json"):
                try:
                    with open(file_path) as f:
                        data = json.load(f)
                        # Add metadata useful for list view
                        items.append(
                            {
                                "id": file_path.stem,
                                "type": category,
                                "title": data.get("title", "Untitled"),
                                "status": data.get("status", "pending"),
                                "detected_at": data.get("detected_at"),
                                "source": data.get("source_url", data.get("url", "")),
                                "detection_type": data.get("detection_type", "NEW"),
                                "content": data.get("content"),
                                "cover_image": data.get("cover_image"),
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"Error reading staging file {file_path}: {e}",
                        exc_info=True,
                        extra={"file": str(file_path), "category": category},
                    )

        # Sort by date (newest first)
        items.sort(key=lambda x: x.get("detected_at", ""), reverse=True)

        return {"items": items, "count": len(items)}

    def archive_item(
        self,
        intel_type: Literal["visa", "news"],
        item_id: str,
        archive_type: Literal["approved", "rejected", "published"],
    ) -> Path:
        """
        Archive staging item to archive directory.

        Args:
            intel_type: "visa" or "news"
            item_id: Unique item identifier
            archive_type: "approved", "rejected", or "published"

        Returns:
            Path to archived file
        """
        staging_dir = self.get_staging_dir(intel_type)
        file_path = staging_dir / f"{item_id}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Staging item not found: {item_id}")

        archive_dir = staging_dir / "archived" / archive_type
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / file_path.name

        try:
            shutil.move(str(file_path), str(archive_path))

        except Exception as e:
            logger.error(f"Failed to archive file {file_path} to {archive_path}: {e}")
            raise

        return archive_path

    def update_staging_queue_metrics(self) -> None:
        """Update Prometheus gauge for staging queue sizes."""
        try:
            visa_count = (
                len(list(self.visa_staging_dir.glob("*.json")))
                if self.visa_staging_dir.exists()
                else 0
            )
            news_count = (
                len(list(self.news_staging_dir.glob("*.json")))
                if self.news_staging_dir.exists()
                else 0
            )

            intel_staging_queue_size.labels(intel_type="visa").set(visa_count)
            intel_staging_queue_size.labels(intel_type="news").set(news_count)
        except Exception as e:
            logger.warning(f"Failed to update staging queue size metrics: {e}")
