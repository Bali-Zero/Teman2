"""
Intel Staging Service

Handles staging area operations for Intel articles.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime, timedelta
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

    def __init__(self):
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
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B",
                        "location": "intel_staging_service.py:108",
                        "message": "save_staging_item entry",
                        "data": {
                            "intel_type": intel_type,
                            "item_id": item_id,
                            "has_staging_data": bool(staging_data),
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion
        staging_dir = self.get_staging_dir(intel_type)
        staging_file = staging_dir / f"{item_id}.json"

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B",
                        "location": "intel_staging_service.py:115",
                        "message": "Before file write",
                        "data": {
                            "staging_file": str(staging_file),
                            "file_exists_before": staging_file.exists(),
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion

        # Atomic write: write to temp file first, then rename
        json_content = json.dumps(staging_data, indent=2)
        temp_file = staging_file.with_suffix(".json.tmp")

        try:
            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "intel_staging_service.py:123",
                            "message": "Writing to temp file",
                            "data": {
                                "temp_file": str(temp_file),
                                "content_length": len(json_content),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion

            temp_file.write_text(json_content)

            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "intel_staging_service.py:128",
                            "message": "Before atomic rename",
                            "data": {
                                "temp_file": str(temp_file),
                                "target_file": str(staging_file),
                                "temp_exists": temp_file.exists(),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion

            # Atomic rename (works on most filesystems)
            temp_file.replace(staging_file)

            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "intel_staging_service.py:135",
                            "message": "save_staging_item success",
                            "data": {
                                "staging_file": str(staging_file),
                                "file_exists_after": staging_file.exists(),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion

        except Exception as e:
            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "intel_staging_service.py:140",
                            "message": "save_staging_item error",
                            "data": {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "temp_file": str(temp_file),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion
            # Clean up temp file on error
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
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
        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "intel_staging_service.py:157",
                        "message": "check_duplicate entry",
                        "data": {"intel_type": intel_type, "source_url": source_url, "days": days},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion
        staging_dir = self.get_staging_dir(intel_type)
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "intel_staging_service.py:162",
                        "message": "Before glob scan",
                        "data": {
                            "staging_dir": str(staging_dir),
                            "dir_exists": staging_dir.exists(),
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion

        file_paths = list(staging_dir.glob("*.json"))

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "intel_staging_service.py:167",
                        "message": "After glob scan",
                        "data": {"files_found": len(file_paths)},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion

        for file_path in file_paths:
            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "intel_staging_service.py:171",
                            "message": "Checking file",
                            "data": {
                                "file_path": str(file_path),
                                "file_exists": file_path.exists(),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion
            try:
                # #region agent log - DISABLED
                with open(
                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                ) as log_file:
                    log_file.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A",
                                "location": "intel_staging_service.py:175",
                                "message": "Before file read",
                                "data": {"file_path": str(file_path)},
                                "timestamp": int(datetime.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
                # #endregion

                with open(file_path) as f:
                    data = json.load(f)

                # #region agent log - DISABLED
                with open(
                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                ) as log_file:
                    log_file.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A",
                                "location": "intel_staging_service.py:182",
                                "message": "After file read",
                                "data": {
                                    "file_path": str(file_path),
                                    "has_source_url": bool(data.get("source_url")),
                                    "source_url_match": data.get("source_url") == source_url,
                                },
                                "timestamp": int(datetime.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
                # #endregion

                if data.get("source_url") == source_url:
                    detected_at = data.get("detected_at")
                    if detected_at:
                        try:
                            detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                            if detected_dt >= cutoff_date:
                                # #region agent log - DISABLED
                                with open(
                                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                                ) as log_file:
                                    log_file.write(
                                        json.dumps(
                                            {
                                                "sessionId": "debug-session",
                                                "runId": "run1",
                                                "hypothesisId": "A",
                                                "location": "intel_staging_service.py:193",
                                                "message": "Duplicate found",
                                                "data": {
                                                    "file_path": str(file_path),
                                                    "detected_at": detected_at,
                                                    "cutoff_date": cutoff_date.isoformat(),
                                                },
                                                "timestamp": int(datetime.now().timestamp() * 1000),
                                            }
                                        )
                                        + "\n"
                                    )
                                # #endregion
                                return data
                        except (ValueError, TypeError) as e:
                            # #region agent log - DISABLED
                            with open(
                                "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                            ) as log_file:
                                log_file.write(
                                    json.dumps(
                                        {
                                            "sessionId": "debug-session",
                                            "runId": "run1",
                                            "hypothesisId": "E",
                                            "location": "intel_staging_service.py:199",
                                            "message": "Date parse error",
                                            "data": {
                                                "file_path": str(file_path),
                                                "error": str(e),
                                                "error_type": type(e).__name__,
                                            },
                                            "timestamp": int(datetime.now().timestamp() * 1000),
                                        }
                                    )
                                    + "\n"
                                )
                            # #endregion
                            # If date parsing fails, consider it a duplicate anyway
                            return data
                    else:
                        # #region agent log - DISABLED
                        with open(
                            "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                        ) as log_file:
                            log_file.write(
                                json.dumps(
                                    {
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "A",
                                        "location": "intel_staging_service.py:206",
                                        "message": "Duplicate found (no date)",
                                        "data": {"file_path": str(file_path)},
                                        "timestamp": int(datetime.now().timestamp() * 1000),
                                    }
                                )
                                + "\n"
                            )
                        # #endregion
                        # No date, consider it a duplicate
                        return data
            except json.JSONDecodeError as e:
                # #region agent log - DISABLED
                with open(
                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                ) as log_file:
                    log_file.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "E",
                                "location": "intel_staging_service.py:213",
                                "message": "JSON decode error",
                                "data": {
                                    "file_path": str(file_path),
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                "timestamp": int(datetime.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
                # #endregion
                logger.warning(f"Invalid JSON in staging file {file_path}: {e}")
                continue
            except PermissionError as e:
                # #region agent log - DISABLED
                with open(
                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                ) as log_file:
                    log_file.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "E",
                                "location": "intel_staging_service.py:220",
                                "message": "Permission error",
                                "data": {
                                    "file_path": str(file_path),
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                "timestamp": int(datetime.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
                # #endregion
                logger.warning(f"Permission denied reading {file_path}: {e}")
                continue
            except Exception as e:
                # #region agent log - DISABLED
                with open(
                    "/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a"
                ) as log_file:
                    log_file.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "E",
                                "location": "intel_staging_service.py:227",
                                "message": "Unexpected error",
                                "data": {
                                    "file_path": str(file_path),
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                "timestamp": int(datetime.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
                # #endregion
                logger.error(f"Error reading staging file {file_path}: {e}", exc_info=True)
                continue

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "intel_staging_service.py:233",
                        "message": "check_duplicate no duplicate",
                        "data": {"source_url": source_url},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion
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
        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C",
                        "location": "intel_staging_service.py:278",
                        "message": "archive_item entry",
                        "data": {
                            "intel_type": intel_type,
                            "item_id": item_id,
                            "archive_type": archive_type,
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion
        staging_dir = self.get_staging_dir(intel_type)
        file_path = staging_dir / f"{item_id}.json"

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C",
                        "location": "intel_staging_service.py:283",
                        "message": "Before file check",
                        "data": {"file_path": str(file_path), "file_exists": file_path.exists()},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion

        if not file_path.exists():
            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "C",
                            "location": "intel_staging_service.py:287",
                            "message": "File not found error",
                            "data": {"file_path": str(file_path), "item_id": item_id},
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion
            raise FileNotFoundError(f"Staging item not found: {item_id}")

        archive_dir = staging_dir / "archived" / archive_type
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / file_path.name

        # #region agent log - DISABLED
        # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
            log_file.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C",
                        "location": "intel_staging_service.py:295",
                        "message": "Before shutil.move",
                        "data": {
                            "source": str(file_path),
                            "dest": str(archive_path),
                            "source_exists": file_path.exists(),
                            "dest_exists": archive_path.exists(),
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                )
                + "\n"
            )
        # #endregion

        try:
            shutil.move(str(file_path), str(archive_path))

            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "C",
                            "location": "intel_staging_service.py:301",
                            "message": "archive_item success",
                            "data": {
                                "source": str(file_path),
                                "dest": str(archive_path),
                                "source_exists_after": file_path.exists(),
                                "dest_exists_after": archive_path.exists(),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion

        except Exception as e:
            # #region agent log - DISABLED
            # with open("/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log", "a") as log_file:
                log_file.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "C",
                            "location": "intel_staging_service.py:307",
                            "message": "archive_item error",
                            "data": {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "source": str(file_path),
                                "dest": str(archive_path),
                            },
                            "timestamp": int(datetime.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
            # #endregion
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
