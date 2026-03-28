"""
Intel Analytics Service

Handles analytics and metrics calculation for Intel articles.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from backend.app.core.constants import IntelConstants
from backend.app.metrics import intel_analytics_queries_total
from backend.services.intel.intel_staging_service import IntelStagingService

logger = logging.getLogger(__name__)


class IntelAnalyticsService:
    """
    Service for calculating Intel analytics and metrics.

    Provides historical analytics, trends, and statistics.
    """

    def __init__(self, staging_service: IntelStagingService) -> None:
        """
        Initialize the analytics service.

        Args:
            staging_service: IntelStagingService instance for accessing staging data
        """
        self.staging_service = staging_service

    def get_intelligence_analytics(
        self, days: int = IntelConstants.TRENDS_ANALYSIS_DAYS
    ) -> dict[str, Any]:
        """
        Get historical analytics and trends for Intelligence Center.

        Args:
            days: Number of days to analyze (default: from constants)

        Returns:
            Dictionary with analytics data including summary, daily trends, and breakdowns
        """
        logger.info("Analytics requested", extra={"days": days})

        # Track analytics query
        intel_analytics_queries_total.labels(period_days=str(days)).inc()

        cutoff_date = datetime.now() - timedelta(days=days)
        analytics = {
            "period_days": days,
            "summary": {
                "total_processed": 0,
                "total_approved": 0,
                "total_rejected": 0,
                "total_published": 0,
                "approval_rate": 0.0,
                "rejection_rate": 0.0,
            },
            "daily_trends": [],
            "type_breakdown": {
                "visa": {"processed": 0, "approved": 0, "rejected": 0},
                "news": {"processed": 0, "approved": 0, "rejected": 0, "published": 0},
            },
            "detection_type_breakdown": {
                "NEW": 0,
                "UPDATED": 0,
            },
        }

        # Count items from archived directories
        for archive_type in ["visa", "news"]:
            staging_dir = self.staging_service.get_staging_dir(archive_type)

            # Count approved
            approved_dir = staging_dir / "archived" / "approved"
            if approved_dir.exists():
                for file_path in approved_dir.glob("*.json"):
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            ingested_at = data.get("ingested_at")
                            if ingested_at:
                                ingested_dt = datetime.fromisoformat(
                                    ingested_at.replace("Z", "+00:00")
                                )
                                if ingested_dt >= cutoff_date:
                                    analytics["summary"]["total_approved"] += 1
                                    analytics["type_breakdown"][archive_type]["approved"] += 1
                                    analytics["type_breakdown"][archive_type]["processed"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to process approved file {file_path}: {e}")
                        continue

            # Count rejected
            rejected_dir = staging_dir / "archived" / "rejected"
            if rejected_dir.exists():
                for file_path in rejected_dir.glob("*.json"):
                    try:
                        with open(file_path) as f:
                            data = json.load(f)
                            rejected_at = data.get("rejected_at") or data.get("ingested_at")
                            if rejected_at:
                                rejected_dt = datetime.fromisoformat(
                                    rejected_at.replace("Z", "+00:00")
                                )
                                if rejected_dt >= cutoff_date:
                                    analytics["summary"]["total_rejected"] += 1
                                    analytics["type_breakdown"][archive_type]["rejected"] += 1
                                    analytics["type_breakdown"][archive_type]["processed"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to process rejected file {file_path}: {e}")
                        continue

            # Count published (news only)
            if archive_type == "news":
                published_dir = staging_dir / "archived" / "published"
                if published_dir.exists():
                    for file_path in published_dir.glob("*.json"):
                        try:
                            with open(file_path) as f:
                                data = json.load(f)
                                published_at = data.get("published_at")
                                if published_at:
                                    published_dt = datetime.fromisoformat(
                                        published_at.replace("Z", "+00:00")
                                    )
                                    if published_dt >= cutoff_date:
                                        analytics["summary"]["total_published"] += 1
                                        analytics["type_breakdown"]["news"]["published"] += 1
                        except Exception as e:
                            logger.warning(f"Failed to process published file {file_path}: {e}")
                            continue

        analytics["summary"]["total_processed"] = (
            analytics["summary"]["total_approved"] + analytics["summary"]["total_rejected"]
        )

        if analytics["summary"]["total_processed"] > 0:
            analytics["summary"]["approval_rate"] = round(
                (analytics["summary"]["total_approved"] / analytics["summary"]["total_processed"])
                * 100,
                2,
            )
            analytics["summary"]["rejection_rate"] = round(
                (analytics["summary"]["total_rejected"] / analytics["summary"]["total_processed"])
                * 100,
                2,
            )

        # Generate daily trends
        analytics["daily_trends"] = self._generate_daily_trends(days)

        logger.info(
            "Analytics calculated",
            extra={
                "total_processed": analytics["summary"]["total_processed"],
                "approval_rate": analytics["summary"]["approval_rate"],
            },
        )

        return analytics

    def _generate_daily_trends(self, days: int) -> list[dict[str, Any]]:
        """
        Generate daily trends for the specified period.

        Args:
            days: Number of days to analyze
            staging_dir: Staging directory path

        Returns:
            List of daily trend dictionaries
        """
        daily_trends = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            daily = {
                "date": date_str,
                "processed": 0,
                "approved": 0,
                "rejected": 0,
                "published": 0,
            }

            # Count items for this day
            for archive_type in ["visa", "news"]:
                staging_dir = self.staging_service.get_staging_dir(archive_type)

                for status in ["approved", "rejected"]:
                    status_dir = staging_dir / "archived" / status
                    if status_dir.exists():
                        for file_path in status_dir.glob("*.json"):
                            try:
                                with open(file_path) as f:
                                    data = json.load(f)
                                    item_date = data.get("ingested_at") or data.get("rejected_at")
                                    if item_date:
                                        item_dt = datetime.fromisoformat(
                                            item_date.replace("Z", "+00:00")
                                        )
                                        if item_dt.strftime("%Y-%m-%d") == date_str:
                                            daily["processed"] += 1
                                            if status == "approved":
                                                daily["approved"] += 1
                                            else:
                                                daily["rejected"] += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to process daily trend file {file_path}: {e}"
                                )
                                continue

                # Published (news only)
                if archive_type == "news":
                    published_dir = staging_dir / "archived" / "published"
                    if published_dir.exists():
                        for file_path in published_dir.glob("*.json"):
                            try:
                                with open(file_path) as f:
                                    data = json.load(f)
                                    published_at = data.get("published_at")
                                    if published_at:
                                        published_dt = datetime.fromisoformat(
                                            published_at.replace("Z", "+00:00")
                                        )
                                        if published_dt.strftime("%Y-%m-%d") == date_str:
                                            daily["published"] += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to process daily published file {file_path}: {e}"
                                )
                                continue

            daily_trends.append(daily)

        daily_trends.reverse()  # Oldest to newest
        return daily_trends
