"""OlympusGuardian — The Immortal Database Custodian."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from backend.services.monitoring.alert_service import AlertLevel, AlertService
from backend.services.olympus.alerts import OlympusAlerts
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse
from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.guardian")


class OlympusGuardian:
    """Orchestrates heartbeat and pulse rhythms with alert integration."""

    def __init__(self, db_pool: asyncpg.Pool, alert_service: AlertService) -> None:
        self._pool = db_pool
        self.alerts = OlympusAlerts(alert_service)
        self.rules_engine: RulesEngine | None = None
        self.heartbeat: Heartbeat | None = None
        self.pulse: Pulse | None = None
        self._running: bool = False
        self._tasks: list[asyncio.Task[None]] = []

    async def initialize(self) -> None:
        """Create sub-components and load rules from the database."""
        self.rules_engine = RulesEngine(self._pool)
        await self.rules_engine.load_rules()

        self.heartbeat = Heartbeat(self._pool, self.rules_engine)
        self.heartbeat.on_alert(self.alerts.send_alert)

        self.pulse = Pulse(self._pool, self.rules_engine)

        logger.info("OlympusGuardian initialized — %d rules loaded", len(self.rules_engine.rules))

    # ------------------------------------------------------------------
    # Single-shot executions
    # ------------------------------------------------------------------

    async def run_heartbeat_once(self) -> None:
        """Collect metrics, evaluate alerts, persist snapshot."""
        assert self.heartbeat is not None, "Call initialize() first"
        snapshot = await self.heartbeat.collect_metrics()
        await self.heartbeat.check_alerts(snapshot)
        await self.heartbeat.persist(snapshot)

    async def run_pulse_once(self) -> list[PulseAction]:
        """Run full pulse, persist actions, send summary, return actions."""
        assert self.pulse is not None, "Call initialize() first"
        assert self.rules_engine is not None, "Call initialize() first"

        actions = await self.pulse.run_full_pulse()

        # Persist each action to olympus_actions
        for action in actions:
            await self._persist_action(action)

        # Record rules that were applied
        applied_rules: set[str] = set()
        for action in actions:
            if action.rule_applied and action.rule_applied not in applied_rules:
                await self.rules_engine.record_applied(action.rule_applied)
                applied_rules.add(action.rule_applied)

        # Send summary via alerts
        failures = sum(1 for a in actions if a.outcome == "error")
        await self.alerts.send_pulse_summary(len(actions), failures)

        logger.info(
            "Pulse complete: %d actions, %d failures",
            len(actions), failures,
        )
        return actions

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Run heartbeat on interval until stopped."""
        while self._running:
            try:
                await self.run_heartbeat_once()
            except Exception:
                logger.exception("Heartbeat cycle failed")
            interval = self._get_heartbeat_interval()
            await asyncio.sleep(interval)

    async def _pulse_loop(self) -> None:
        """Run pulse on interval (with initial delay) until stopped."""
        await asyncio.sleep(60)  # initial delay
        while self._running:
            try:
                await self.run_pulse_once()
            except Exception:
                logger.exception("Pulse cycle failed")
                try:
                    await self.alerts.send_alert(
                        "Pulse cycle failed — check logs", AlertLevel.ERROR,
                    )
                except Exception:
                    logger.exception("Failed to send pulse failure alert")
            interval_hours = self._get_pulse_interval_hours()
            await asyncio.sleep(interval_hours * 3600)

    async def start(self) -> None:
        """Start background heartbeat and pulse loops."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._pulse_loop()),
        ]
        logger.info("OlympusGuardian started — heartbeat and pulse loops running")

    async def stop(self) -> None:
        """Stop background loops and cancel tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("OlympusGuardian stopped")

    # ------------------------------------------------------------------
    # Health summary
    # ------------------------------------------------------------------

    async def get_health_summary(self) -> dict[str, Any]:
        """Return current health status: last heartbeat, recent actions, rules count."""
        last_heartbeat: dict[str, Any] | None = None
        recent_actions: list[dict[str, Any]] = []
        rules_count: int = 0

        try:
            async with self._pool.acquire() as conn:
                hb_row = await conn.fetchrow(
                    "SELECT * FROM olympus_heartbeats ORDER BY recorded_at DESC LIMIT 1",
                )
                if hb_row:
                    last_heartbeat = dict(hb_row)

                action_rows = await conn.fetch(
                    "SELECT * FROM olympus_actions ORDER BY executed_at DESC LIMIT 10",
                )
                recent_actions = [dict(r) for r in action_rows]
        except Exception:
            logger.exception("Failed to query health summary")

        if self.rules_engine is not None:
            rules_count = len(self.rules_engine.rules)

        return {
            "status": "alive",
            "running": self._running,
            "rules_count": rules_count,
            "last_heartbeat": last_heartbeat,
            "recent_actions": recent_actions,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _persist_action(self, action: PulseAction) -> None:
        """INSERT a PulseAction into olympus_actions."""
        query = """
            INSERT INTO olympus_actions (
                rhythm, action_type, target, detail, outcome,
                duration_ms, rule_applied, reflection, executed_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    action.rhythm,
                    action.action_type,
                    action.target,
                    json.dumps(action.detail),
                    action.outcome,
                    action.duration_ms,
                    action.rule_applied,
                    action.reflection,
                    action.executed_at,
                )
        except Exception:
            logger.exception("Failed to persist action: %s", action.action_type)

    def _get_heartbeat_interval(self) -> int:
        """Return heartbeat interval in seconds from rules, default 300."""
        if self.rules_engine is None:
            return 300
        return int(self.rules_engine.get_threshold("heartbeat_interval_seconds", default=300))

    def _get_pulse_interval_hours(self) -> int:
        """Return pulse interval in hours from rules, default 6."""
        if self.rules_engine is None:
            return 6
        return int(self.rules_engine.get_threshold("pulse_interval_hours", default=6))
