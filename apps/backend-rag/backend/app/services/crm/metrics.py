"""
CRM Metrics System - Business Operations KPIs
Tracks: active_clients_count, application_processing_time, and more
"""

import asyncio
import functools
import time
from datetime import datetime
from typing import Any

import asyncpg
from prometheus_client import Counter, Gauge, Histogram, Info

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)


# Prometheus Metrics Definition
class CRMMetrics:
    """CRM-specific metrics for business operations"""

    def __init__(self):
        # Client metrics
        self.active_clients_total = Gauge(
            "crm_active_clients_total",
            "Total number of active clients",
            ["assigned_to", "client_type"],
        )

        self.client_creation_duration = Histogram(
            "crm_client_creation_duration_seconds",
            "Time taken to create a new client",
            ["client_type", "lead_source"],
        )

        self.client_status_changes = Counter(
            "crm_client_status_changes_total",
            "Total number of client status changes",
            ["from_status", "to_status", "changed_by"],
        )

        # Application processing metrics
        self.application_processing_duration = Histogram(
            "crm_application_processing_duration_seconds",
            "Time from application start to completion",
            ["visa_type", "destination_country", "outcome"],
        )

        self.applications_in_progress = Gauge(
            "crm_applications_in_progress_total",
            "Number of applications currently in progress",
            ["stage", "priority"],
        )

        # Business metrics
        self.conversion_rate = Gauge(
            "crm_conversion_rate",
            "Conversion rate from prospect to active client",
            ["period", "source"],
        )

        self.client_lifecycle_duration = Histogram(
            "crm_client_lifecycle_duration_seconds",
            "Time from first contact to final resolution",
            ["outcome", "client_type"],
        )

        # Operational metrics
        self.interaction_response_time = Histogram(
            "crm_interaction_response_time_seconds",
            "Time between client interactions",
            ["interaction_type", "channel"],
        )

        self.document_processing_duration = Histogram(
            "crm_document_processing_duration_seconds",
            "Time to process client documents",
            ["document_type", "verification_status"],
        )

        # System info
        self.crm_info = Info("crm_info", "CRM system information")

        self.crm_info.info(
            {
                "version": "1.0.0",
                "environment": "production",
                "last_updated": datetime.now().isoformat(),
            }
        )


# Global metrics instance
crm_metrics = CRMMetrics()


class CRMMetricsCollector:
    """Collects and updates CRM metrics from database"""

    def __init__(self):
        self.pool = None

    def initialize(self, pool: asyncpg.Pool):
        """Initialize with a database pool"""
        self.pool = pool
        logger.info("✅ CRMMetricsCollector initialized with database pool")

    async def _get_pool(self):
        """Get database pool connection"""
        if not self.pool:
            raise RuntimeError("CRMMetricsCollector not initialized with pool. Call .initialize(pool) first.")
        return self.pool

    async def update_all_metrics(self) -> dict[str, Any]:
        """Update all CRM metrics"""
        start_time = time.time()

        try:
            results = {
                "timestamp": datetime.now().isoformat(),
                "metrics_updated": [],
                "errors": [],
                "success": True,
            }

            # Update client metrics
            await self.update_client_metrics(results)

            # Update application metrics
            await self.update_application_metrics(results)

            # Update business metrics
            await self.update_business_metrics(results)

            # Update operational metrics
            await self.update_operational_metrics(results)

            duration = time.time() - start_time
            logger.info(
                f"📊 [CRM METRICS] Updated {len(results['metrics_updated'])} metrics in {duration:.2f}s"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to update CRM metrics: {e}", exc_info=True)
            return {"error": str(e), "timestamp": datetime.now().isoformat(), "success": False}

    async def update_client_metrics(self, results: dict[str, Any]) -> None:
        """Update client-related metrics"""
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Active clients by assigned user and type
                active_clients = await conn.fetch("""
                    SELECT assigned_to, client_type, COUNT(*) as count
                    FROM clients
                    WHERE status = 'active'
                    GROUP BY assigned_to, client_type
                """)

                # Reset gauge
                crm_metrics.active_clients_total.clear()

                for row in active_clients:
                    crm_metrics.active_clients_total.labels(
                        assigned_to=row["assigned_to"] or "unassigned",
                        client_type=row["client_type"],
                    ).set(row["count"])

                results["metrics_updated"].append("active_clients_total")

                # Client status changes in last 24h
                status_changes = await conn.fetch("""
                    SELECT
                        COALESCE(old_data->>'status', 'unknown') as from_status,
                        COALESCE(new_data->>'status', 'unknown') as to_status,
                        metadata->>'user_email' as changed_by,
                        COUNT(*) as count
                    FROM crm_audit_log
                    WHERE entity_type = 'client'
                    AND change_type = 'status_change'
                    AND timestamp >= NOW() - INTERVAL '24 hours'
                    GROUP BY from_status, to_status, changed_by
                """)

                for row in status_changes:
                    crm_metrics.client_status_changes.labels(
                        from_status=row["from_status"],
                        to_status=row["to_status"],
                        changed_by=row["changed_by"] or "unknown",
                    ).inc(row["count"])

                results["metrics_updated"].append("client_status_changes")

        except Exception as e:
            logger.error(f"Failed to update client metrics: {e}")
            results["errors"].append(f"client_metrics: {str(e)}")

    async def update_application_metrics(self, results: dict[str, Any]) -> None:
        """Update application processing metrics"""
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Applications in progress by stage
                in_progress = await conn.fetch("""
                    SELECT
                        COALESCE(custom_fields->>'stage', 'unknown') as stage,
                        COALESCE(priority, 'normal') as priority,
                        COUNT(*) as count
                    FROM cases
                    WHERE status = 'active'
                    GROUP BY stage, priority
                """)

                # Reset gauge
                crm_metrics.applications_in_progress.clear()

                for row in in_progress:
                    crm_metrics.applications_in_progress.labels(
                        stage=row["stage"], priority=row["priority"]
                    ).set(row["count"])

                results["metrics_updated"].append("applications_in_progress")

                # Application processing times (completed in last 30 days)
                processing_times = await conn.fetch("""
                    SELECT
                        c.case_type,
                        c.custom_fields->>'visa_type' as visa_type,
                        c.custom_fields->>'destination_country' as destination_country,
                        c.custom_fields->>'outcome' as outcome,
                        EXTRACT(EPOCH FROM (c.updated_at - c.created_at)) as duration_seconds
                    FROM cases c
                    WHERE c.status = 'completed'
                    AND c.updated_at >= NOW() - INTERVAL '30 days'
                    AND c.custom_fields->>'outcome' IS NOT NULL
                """)

                for row in processing_times:
                    crm_metrics.application_processing_duration.labels(
                        visa_type=row["visa_type"] or "unknown",
                        destination_country=row["destination_country"] or "unknown",
                        outcome=row["outcome"] or "unknown",
                    ).observe(row["duration_seconds"])

                results["metrics_updated"].append("application_processing_duration")

        except Exception as e:
            logger.error(f"Failed to update application metrics: {e}")
            results["errors"].append(f"application_metrics: {str(e)}")

    async def update_business_metrics(self, results: dict[str, Any]) -> None:
        """Update business KPI metrics"""
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Conversion rates (prospect to active)
                conversion_data = await conn.fetch("""
                    SELECT
                        lead_source,
                        COUNT(*) FILTER (WHERE status = 'prospect') as prospects,
                        COUNT(*) FILTER (WHERE status = 'active') as active_clients,
                        CASE
                            WHEN COUNT(*) FILTER (WHERE status = 'prospect') > 0
                            THEN (COUNT(*) FILTER (WHERE status = 'active')::float / COUNT(*) FILTER (WHERE status = 'prospect')::float) * 100
                            ELSE 0
                        END as conversion_rate
                    FROM clients
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY lead_source
                """)

                for row in conversion_data:
                    conversion_rate = row.get("conversion_rate") or 0.0
                    crm_metrics.conversion_rate.labels(
                        period="30_days", source=row.get("lead_source") or "unknown"
                    ).set(conversion_rate)

                results["metrics_updated"].append("conversion_rate")

                # Client lifecycle durations
                lifecycle_data = await conn.fetch("""
                    SELECT
                        client_type,
                        custom_fields->>'outcome' as outcome,
                        EXTRACT(EPOCH FROM (updated_at - created_at)) as lifecycle_seconds
                    FROM clients
                    WHERE status = 'inactive'
                    AND custom_fields->>'completion_date' IS NOT NULL
                    AND updated_at >= NOW() - INTERVAL '90 days'
                """)

                for row in lifecycle_data:
                    lifecycle_seconds = row.get("lifecycle_seconds") or 0.0
                    crm_metrics.client_lifecycle_duration.labels(
                        outcome=row.get("outcome") or "unknown",
                        client_type=row.get("client_type") or "unknown",
                    ).observe(lifecycle_seconds)

                results["metrics_updated"].append("client_lifecycle_duration")

        except Exception as e:
            logger.error(f"Failed to update business metrics: {e}")
            results["errors"].append(f"business_metrics: {str(e)}")

    async def update_operational_metrics(self, results: dict[str, Any]) -> None:
        """Update operational efficiency metrics"""
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Interaction response times
                response_times = await conn.fetch("""
                    SELECT
                        i.interaction_type,
                        i.channel,
                        EXTRACT(EPOCH FROM (i.interaction_date - COALESCE(prev_interaction.interaction_date, i.interaction_date))) as response_time_seconds
                    FROM interactions i
                    LEFT JOIN LATERAL (
                        SELECT interaction_date
                        FROM interactions prev
                        WHERE prev.client_id = i.client_id
                        AND prev.interaction_date < i.interaction_date
                        ORDER BY prev.interaction_date DESC
                        LIMIT 1
                    ) prev_interaction ON true
                    WHERE i.interaction_date >= NOW() - INTERVAL '7 days'
                    AND i.interaction_date != COALESCE(prev_interaction.interaction_date, i.interaction_date)
                """)

                for row in response_times:
                    response_time_seconds = row.get("response_time_seconds") or 0.0
                    crm_metrics.interaction_response_time.labels(
                        interaction_type=row.get("interaction_type") or "unknown",
                        channel=row.get("channel") or "unknown",
                    ).observe(response_time_seconds)

                results["metrics_updated"].append("interaction_response_time")

        except Exception as e:
            logger.error(f"Failed to update operational metrics: {e}")
            results["errors"].append(f"operational_metrics: {str(e)}")

    async def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of current CRM metrics"""
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Get current stats
                summary = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'active') as active_clients,
                        COUNT(*) FILTER (WHERE status = 'prospect') as prospects,
                        COUNT(*) FILTER (WHERE status = 'inactive') as completed_clients,
                        COUNT(*) as total_clients,
                        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as new_clients_30d,
                        COUNT(*) FILTER (WHERE status = 'active' AND created_at >= NOW() - INTERVAL '30 days') as active_clients_30d
                    FROM clients
                """)

                # Get application stats
                app_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'active') as applications_in_progress,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_applications,
                        COUNT(*) as total_applications,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE status = 'completed') as avg_processing_days
                    FROM cases
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                """)

                return {
                    "timestamp": datetime.now().isoformat(),
                    "clients": {
                        "active": int(summary["active_clients"]),
                        "prospects": int(summary["prospects"]),
                        "completed": int(summary["completed_clients"]),
                        "total": int(summary["total_clients"]),
                        "new_last_30d": int(summary["new_clients_30d"]),
                        "active_last_30d": int(summary["active_clients_30d"]),
                    },
                    "applications": {
                        "in_progress": int(app_stats["applications_in_progress"]),
                        "completed": int(app_stats["completed_applications"]),
                        "total": int(app_stats["total_applications"]),
                        "avg_processing_days": float(app_stats["avg_processing_days"] or 0),
                    },
                }

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


# Global metrics collector instance
metrics_collector = CRMMetricsCollector()


# Decorator for timing operations
def track_client_creation(client_type: str = "individual", lead_source: str = "unknown"):
    """Decorator to track client creation time"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                crm_metrics.client_creation_duration.labels(
                    client_type=client_type, lead_source=lead_source
                ).observe(duration)

                return result
            except Exception:
                duration = time.time() - start_time
                crm_metrics.client_creation_duration.labels(
                    client_type=client_type, lead_source=lead_source
                ).observe(duration)
                raise

        return wrapper

    return decorator


def track_application_processing(visa_type: str = "unknown", destination_country: str = "unknown"):
    """Decorator to track application processing time"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                outcome = (
                    getattr(result, "outcome", "unknown")
                    if hasattr(result, "outcome")
                    else "unknown"
                )

                crm_metrics.application_processing_duration.labels(
                    visa_type=visa_type, destination_country=destination_country, outcome=outcome
                ).observe(duration)

                return result
            except Exception:
                duration = time.time() - start_time
                crm_metrics.application_processing_duration.labels(
                    visa_type=visa_type, destination_country=destination_country, outcome="error"
                ).observe(duration)
                raise

        return wrapper

    return decorator


# Scheduled task to update metrics
async def schedule_metrics_updates():
    """Schedule regular metrics updates"""
    while True:
        try:
            await metrics_collector.update_all_metrics()
            await asyncio.sleep(300)  # Update every 5 minutes
        except Exception as e:
            logger.error(f"Error in scheduled metrics update: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error
