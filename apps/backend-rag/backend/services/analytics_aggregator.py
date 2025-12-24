"""
Analytics Aggregator Service
Aggregates data from PostgreSQL, Qdrant, Prometheus metrics for the analytics dashboard.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """
    Aggregates analytics data from multiple sources:
    - PostgreSQL (conversations, CRM, team data)
    - Qdrant (vector database stats)
    - App metrics (system health, performance)
    """

    def __init__(self, app_state: Any):
        """
        Initialize aggregator with app state.

        Args:
            app_state: FastAPI app.state containing service instances
        """
        self.app_state = app_state
        self._boot_time = getattr(app_state, "boot_time", time.time())

    async def _get_db_pool(self):
        """Get database connection pool from app state"""
        pool = getattr(self.app_state, "db_pool", None)
        if not pool:
            # Try memory service
            memory_service = getattr(self.app_state, "memory_service", None)
            if memory_service:
                pool = getattr(memory_service, "pool", None)
        return pool

    # =========================================================================
    # OVERVIEW STATS
    # =========================================================================

    async def get_overview_stats(self) -> dict:
        """Get overview statistics"""
        from app.routers.analytics import OverviewStats

        stats = OverviewStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Conversations today
                    stats.conversations_today = await conn.fetchval(
                        "SELECT COUNT(*) FROM conversations WHERE created_at >= CURRENT_DATE"
                    ) or 0

                    # Conversations this week
                    stats.conversations_week = await conn.fetchval(
                        "SELECT COUNT(*) FROM conversations WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
                    ) or 0

                    # Active users (users with activity in last 24h)
                    stats.users_active = await conn.fetchval(
                        "SELECT COUNT(DISTINCT user_id) FROM conversations WHERE created_at >= NOW() - INTERVAL '24 hours'"
                    ) or 0

                    # Revenue pipeline (sum of quoted prices for active practices)
                    stats.revenue_pipeline = float(await conn.fetchval(
                        """SELECT COALESCE(SUM(quoted_price), 0) FROM practices
                        WHERE status NOT IN ('completed', 'cancelled')"""
                    ) or 0)

            # Uptime
            stats.uptime_seconds = time.time() - self._boot_time

            # Services health
            health_monitor = getattr(self.app_state, "health_monitor", None)
            if health_monitor:
                service_states = getattr(health_monitor, "_service_states", {})
                stats.services_total = len(service_states)
                stats.services_healthy = sum(1 for s in service_states.values() if s.get("healthy", False))

        except Exception as e:
            logger.error(f"Error fetching overview stats: {e}")

        return stats

    # =========================================================================
    # RAG STATS
    # =========================================================================

    async def get_rag_stats(self) -> dict:
        """Get RAG pipeline statistics"""
        from app.routers.analytics import RAGStats

        stats = RAGStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Query analytics
                    row = await conn.fetchrow("""
                        SELECT
                            COUNT(*) as total,
                            AVG(response_time_ms) as avg_latency
                        FROM query_analytics
                        WHERE created_at >= CURRENT_DATE
                    """)
                    if row:
                        stats.queries_today = row["total"] or 0
                        stats.avg_latency_ms = float(row["avg_latency"] or 0)

                    # Top queries (last 7 days)
                    top_queries = await conn.fetch("""
                        SELECT query_text, COUNT(*) as count
                        FROM query_analytics
                        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                        GROUP BY query_text
                        ORDER BY count DESC
                        LIMIT 10
                    """)
                    stats.top_queries = [
                        {"query": q["query_text"][:100], "count": q["count"]}
                        for q in top_queries
                    ]

            # Get Prometheus metrics if available
            try:
                from app.metrics import MetricsCollector
                collector = MetricsCollector()
                # These would come from actual Prometheus metrics
                stats.cache_hit_rate = 0.65  # Placeholder
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error fetching RAG stats: {e}")

        return stats

    # =========================================================================
    # CRM STATS
    # =========================================================================

    async def get_crm_stats(self) -> dict:
        """Get CRM statistics"""
        from app.routers.analytics import CRMStats

        stats = CRMStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Clients by status
                    client_rows = await conn.fetch("""
                        SELECT status, COUNT(*) as count
                        FROM clients
                        GROUP BY status
                    """)
                    stats.clients_by_status = {r["status"]: r["count"] for r in client_rows}
                    stats.clients_total = sum(stats.clients_by_status.values())
                    stats.clients_active = stats.clients_by_status.get("active", 0)

                    # Practices by status
                    practice_rows = await conn.fetch("""
                        SELECT status, COUNT(*) as count
                        FROM practices
                        GROUP BY status
                    """)
                    stats.practices_by_status = {r["status"]: r["count"] for r in practice_rows}
                    stats.practices_total = sum(stats.practices_by_status.values())

                    # Revenue
                    revenue_row = await conn.fetchrow("""
                        SELECT
                            COALESCE(SUM(quoted_price), 0) as quoted,
                            COALESCE(SUM(paid_amount), 0) as paid
                        FROM practices
                        WHERE status NOT IN ('cancelled')
                    """)
                    if revenue_row:
                        stats.revenue_quoted = float(revenue_row["quoted"])
                        stats.revenue_paid = float(revenue_row["paid"])

                    # Renewals
                    stats.renewals_30_days = await conn.fetchval("""
                        SELECT COUNT(*) FROM practices
                        WHERE next_renewal_date <= CURRENT_DATE + INTERVAL '30 days'
                        AND next_renewal_date > CURRENT_DATE
                        AND status NOT IN ('completed', 'cancelled')
                    """) or 0

                    stats.renewals_60_days = await conn.fetchval("""
                        SELECT COUNT(*) FROM practices
                        WHERE next_renewal_date <= CURRENT_DATE + INTERVAL '60 days'
                        AND next_renewal_date > CURRENT_DATE + INTERVAL '30 days'
                        AND status NOT IN ('completed', 'cancelled')
                    """) or 0

                    stats.renewals_90_days = await conn.fetchval("""
                        SELECT COUNT(*) FROM practices
                        WHERE next_renewal_date <= CURRENT_DATE + INTERVAL '90 days'
                        AND next_renewal_date > CURRENT_DATE + INTERVAL '60 days'
                        AND status NOT IN ('completed', 'cancelled')
                    """) or 0

                    # Pending documents
                    stats.documents_pending = await conn.fetchval("""
                        SELECT COUNT(*) FROM documents
                        WHERE status = 'pending'
                    """) or 0

        except Exception as e:
            logger.error(f"Error fetching CRM stats: {e}")

        return stats

    # =========================================================================
    # TEAM STATS
    # =========================================================================

    async def get_team_stats(self) -> dict:
        """Get team productivity statistics"""
        from app.routers.analytics import TeamStats

        stats = TeamStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Hours worked today
                    stats.hours_today = float(await conn.fetchval("""
                        SELECT COALESCE(SUM(duration_minutes), 0) / 60.0
                        FROM team_work_sessions
                        WHERE session_start >= CURRENT_DATE
                    """) or 0)

                    # Hours worked this week
                    stats.hours_week = float(await conn.fetchval("""
                        SELECT COALESCE(SUM(duration_minutes), 0) / 60.0
                        FROM team_work_sessions
                        WHERE session_start >= CURRENT_DATE - INTERVAL '7 days'
                    """) or 0)

                    # Conversations by agent
                    agent_rows = await conn.fetch("""
                        SELECT team_member, COUNT(*) as count
                        FROM interactions
                        WHERE interaction_date >= CURRENT_DATE - INTERVAL '7 days'
                        AND team_member IS NOT NULL
                        GROUP BY team_member
                    """)
                    stats.conversations_by_agent = {
                        r["team_member"]: r["count"]
                        for r in agent_rows
                    }

                    # Active sessions
                    stats.active_sessions = await conn.fetchval("""
                        SELECT COUNT(*) FROM team_work_sessions
                        WHERE status = 'active'
                    """) or 0

                    # Open action items
                    stats.action_items_open = await conn.fetchval("""
                        SELECT COUNT(*) FROM interactions
                        WHERE action_items IS NOT NULL
                        AND action_items != '[]'::jsonb
                    """) or 0

        except Exception as e:
            logger.error(f"Error fetching team stats: {e}")

        return stats

    # =========================================================================
    # SYSTEM STATS
    # =========================================================================

    async def get_system_stats(self) -> dict:
        """Get system health statistics"""
        from app.routers.analytics import SystemStats

        stats = SystemStats()

        try:
            # System metrics via psutil
            stats.cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            stats.memory_mb = memory.used / (1024 * 1024)
            stats.memory_percent = memory.percent

            # Database connections
            pool = await self._get_db_pool()
            if pool:
                stats.db_connections_active = pool.get_size() - pool.get_idle_size()
                stats.db_connections_idle = pool.get_idle_size()

            # Services health
            services = []
            health_monitor = getattr(self.app_state, "health_monitor", None)
            if health_monitor:
                service_states = getattr(health_monitor, "_service_states", {})
                for name, state in service_states.items():
                    services.append({
                        "name": name,
                        "healthy": state.get("healthy", False),
                        "last_check": state.get("last_check", ""),
                        "error": state.get("error", "")
                    })
            stats.services = services

        except Exception as e:
            logger.error(f"Error fetching system stats: {e}")

        return stats

    # =========================================================================
    # QDRANT STATS
    # =========================================================================

    async def get_qdrant_stats(self) -> dict:
        """Get Qdrant vector database statistics"""
        from app.routers.analytics import QdrantStats

        stats = QdrantStats()

        try:
            search_service = getattr(self.app_state, "search_service", None)
            if search_service and hasattr(search_service, "qdrant_db"):
                qdrant = search_service.qdrant_db
                if hasattr(qdrant, "client"):
                    # Get collections
                    collections_response = await qdrant.client.get_collections()
                    collections = []
                    total_docs = 0

                    for coll in collections_response.collections:
                        try:
                            info = await qdrant.client.get_collection(coll.name)
                            count = info.points_count or 0
                            total_docs += count
                            collections.append({
                                "name": coll.name,
                                "documents": count,
                                "status": info.status.value if hasattr(info.status, 'value') else str(info.status)
                            })
                        except Exception:
                            collections.append({
                                "name": coll.name,
                                "documents": 0,
                                "status": "unknown"
                            })

                    stats.total_documents = total_docs
                    stats.collections = sorted(collections, key=lambda x: x["documents"], reverse=True)

        except Exception as e:
            logger.error(f"Error fetching Qdrant stats: {e}")

        return stats

    # =========================================================================
    # FEEDBACK STATS
    # =========================================================================

    async def get_feedback_stats(self) -> dict:
        """Get feedback and quality statistics"""
        from app.routers.analytics import FeedbackStats

        stats = FeedbackStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Average rating
                    stats.avg_rating = float(await conn.fetchval("""
                        SELECT COALESCE(AVG(rating), 0)::numeric(3,2)
                        FROM conversation_ratings
                        WHERE created_at >= NOW() - INTERVAL '30 days'
                    """) or 0)

                    # Rating distribution
                    dist_rows = await conn.fetch("""
                        SELECT rating, COUNT(*) as count
                        FROM conversation_ratings
                        WHERE created_at >= NOW() - INTERVAL '30 days'
                        GROUP BY rating
                    """)
                    stats.rating_distribution = {
                        str(r["rating"]): r["count"]
                        for r in dist_rows
                    }
                    stats.total_ratings = sum(stats.rating_distribution.values())

                    # Negative feedback
                    stats.negative_feedback_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM conversation_ratings
                        WHERE rating <= 2
                        AND created_at >= NOW() - INTERVAL '30 days'
                    """) or 0

                    # Recent negative feedback
                    negative = await conn.fetch("""
                        SELECT session_id, rating, feedback_text, created_at
                        FROM conversation_ratings
                        WHERE rating <= 2
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    stats.recent_negative_feedback = [
                        {
                            "session_id": str(r["session_id"]),
                            "rating": r["rating"],
                            "feedback": r["feedback_text"][:100] if r["feedback_text"] else "",
                            "date": r["created_at"].isoformat() if r["created_at"] else ""
                        }
                        for r in negative
                    ]

                    # Quality trend (last 7 days)
                    trend = await conn.fetch("""
                        SELECT DATE(created_at) as date, AVG(rating)::numeric(3,2) as avg
                        FROM conversation_ratings
                        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                        GROUP BY DATE(created_at)
                        ORDER BY date
                    """)
                    stats.quality_trend = [
                        {"date": r["date"].isoformat(), "rating": float(r["avg"])}
                        for r in trend
                    ]

        except Exception as e:
            logger.error(f"Error fetching feedback stats: {e}")

        return stats

    # =========================================================================
    # ALERT STATS
    # =========================================================================

    async def get_alert_stats(self) -> dict:
        """Get alert and error statistics"""
        from app.routers.analytics import AlertStats

        stats = AlertStats()

        try:
            pool = await self._get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Auth failures today
                    stats.auth_failures_today = await conn.fetchval("""
                        SELECT COUNT(*) FROM auth_audit_log
                        WHERE success = false
                        AND created_at >= CURRENT_DATE
                    """) or 0

                    # Recent errors from audit
                    errors = await conn.fetch("""
                        SELECT action, email, failure_reason, created_at
                        FROM auth_audit_log
                        WHERE success = false
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    stats.recent_errors = [
                        {
                            "action": r["action"],
                            "email": r["email"],
                            "reason": r["failure_reason"],
                            "time": r["created_at"].isoformat() if r["created_at"] else ""
                        }
                        for r in errors
                    ]

            # Active alerts from health monitor
            health_monitor = getattr(self.app_state, "health_monitor", None)
            if health_monitor:
                active = getattr(health_monitor, "_active_alerts", [])
                stats.active_alerts = [
                    {"service": a.get("service"), "message": a.get("message"), "severity": a.get("severity")}
                    for a in active[:10]
                ]

        except Exception as e:
            logger.error(f"Error fetching alert stats: {e}")

        return stats
