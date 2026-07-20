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
        2. System health (backend, Qdrant, Redis)
        3. 5 most recent LAM memory episodes

        ``recent_activity`` is always present but explicitly ``None`` — the
        "Generals" multi-agent system it reported on (Kodex/Gravity/Sentinel/
        Vox/Flash, Air-machine era) was retired along with `/api/generals/activity`
        (removed 2026-04-03) and has no successor surface: Guardian tracks a
        different domain (AI-safety/moderation decisions, not general agent
        runs), and `/api/admin/logs/activity` tracks human team-member audit
        actions, not agent activity. Kept as an explicit null field rather than
        silently dropped so callers can distinguish "no data" from "field
        removed" (W81 lesson — never leave a fetch-failure error masquerading
        as data).

        Returns a unified dict with all sections so the agent can orient
        itself without making separate calls.
        """
        import asyncio

        alerts_task = _call_safe("/api/crm/expiry-alerts", params={"days_ahead": 30})
        health_task = _call_safe("/health/detailed")
        memory_task = _call_safe("/api/memory/lam/episodes", params={"limit": 5})

        alerts, health, memory = await asyncio.gather(
            alerts_task, health_task, memory_task,
            return_exceptions=True,
        )

        def _safe(result, label: str):
            if isinstance(result, Exception):
                logger.warning(f"Heartbeat: {label} failed — {result}")
                return {"error": True, "detail": str(result)}
            return result

        snapshot = {
            "critical_alerts": _safe(alerts, "critical_alerts"),
            "recent_activity": None,  # retired — see docstring
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
