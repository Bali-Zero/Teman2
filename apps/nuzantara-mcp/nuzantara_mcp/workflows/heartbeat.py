"""
LAM Grounding Bootstrap (Heartbeat)
Provides lam_grounding_snapshot — called at agent startup or on demand
to give the agent a full situational awareness snapshot.
"""

import logging
from typing import Callable

logger = logging.getLogger("nuzantara-mcp.heartbeat")


def register(mcp, _call: Callable, _call_safe: Callable) -> None:

    @mcp.tool()
    async def lam_grounding_snapshot() -> dict:
        """
        LAM STARTUP GROUNDING — Call this first at the start of any session.

        Fetches a full situational awareness snapshot:
        1. Critical alerts (expiring visas, overdue practices)
        2. Recent agent activity (what ran last 24h)
        3. System health (backend, Qdrant, Redis)
        4. 5 most recent LAM memory episodes

        Returns a unified dict with all four sections so the agent can
        orient itself without making 4 separate calls.
        """
        import asyncio

        alerts_task = _call_safe("/api/crm/expiry-alerts", params={"days_ahead": 30})
        activity_task = _call_safe("/api/generals/activity", params={"hours": 24})
        health_task = _call_safe("/health/detailed")
        memory_task = _call_safe("/api/memory/lam/episodes", params={"limit": 5})

        alerts, activity, health, memory = await asyncio.gather(
            alerts_task, activity_task, health_task, memory_task,
            return_exceptions=True,
        )

        def _safe(result, label: str):
            if isinstance(result, Exception):
                logger.warning(f"Heartbeat: {label} failed — {result}")
                return {"error": True, "detail": str(result)}
            return result

        snapshot = {
            "critical_alerts": _safe(alerts, "critical_alerts"),
            "recent_activity": _safe(activity, "recent_activity"),
            "system_health": _safe(health, "system_health"),
            "recent_memory": _safe(memory, "recent_memory"),
        }

        # Quick summary for logging
        try:
            n_alerts = len((alerts or {}).get("alerts", []))
            n_episodes = (memory or {}).get("total", 0)
            health_status = (health or {}).get("status", "unknown")
            logger.info(
                f"LAM grounding: health={health_status}, "
                f"alerts={n_alerts}, memory_episodes={n_episodes}"
            )
        except Exception:
            pass

        return snapshot
