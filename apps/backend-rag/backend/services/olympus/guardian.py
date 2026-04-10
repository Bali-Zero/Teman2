"""Olympus v2 — Guardian orchestrator.

Wires heartbeat, pulse, rules, and alerts together. Closes the feedback loop:
- record_applied() on every successful rule-governed action
- lower_confidence() on every failed rule-governed action
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from backend.services.olympus.alerts import OlympusAlerts
from backend.services.olympus.insights import InsightsCollector
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse
from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.guardian")


class OlympusGuardian:
    def __init__(self, db_pool: asyncpg.Pool, alert_service: Any | None) -> None:
        self._pool = db_pool
        self.alerts = OlympusAlerts(alert_service)
        self.rules_engine: RulesEngine | None = None
        self.heartbeat: Heartbeat | None = None
        self.pulse: Pulse | None = None
        self._running: bool = False
        self._tasks: list[asyncio.Task[None]] = []
        self.insights: InsightsCollector | None = None

    async def initialize(self) -> None:
        self.rules_engine = RulesEngine(self._pool)
        await self.rules_engine.load_rules()
        self.heartbeat = Heartbeat(self._pool, self.rules_engine)
        self.heartbeat.on_alert(self.alerts.send_alert)
        self.pulse = Pulse(self._pool, self.rules_engine)
        self.insights = InsightsCollector(self._pool, self.rules_engine)
        self.insights.set_alert_callback(self.alerts.send_alert)
        logger.info("OlympusGuardian initialized — %d rules", len(self.rules_engine.rules))

    async def run_heartbeat_once(self) -> None:
        assert self.heartbeat is not None
        snapshot = await self.heartbeat.collect_metrics()
        await self.heartbeat.check_alerts(snapshot)
        await self.heartbeat.persist(snapshot)

    async def run_pulse_once(self) -> list[PulseAction]:
        assert self.pulse is not None
        assert self.rules_engine is not None

        actions = await self.pulse.run_full_pulse()

        # v3: Insights collection
        if self.insights is not None:
            try:
                actions.extend(await self.insights.collect_query_insights())
                actions.extend(await self.insights.collect_bloat_insights())
            except Exception:
                logger.exception("Insights collection failed")

        for action in actions:
            await self._persist_action(action)

        # --- FEEDBACK LOOP ---
        applied_rules: set[str] = set()
        failed_rules: set[str] = set()

        for action in actions:
            if action.rule_applied:
                if action.outcome == "failure":
                    failed_rules.add(action.rule_applied)
                elif action.outcome == "success":
                    applied_rules.add(action.rule_applied)

        for rule_name in applied_rules:
            await self.rules_engine.record_applied(rule_name)

        for rule_name in failed_rules:
            await self.rules_engine.lower_confidence(rule_name)

        failures = sum(1 for a in actions if a.outcome == "failure")
        await self.alerts.send_pulse_summary(len(actions), failures)

        # v4 readiness check: enough insights to activate Voyager skills?
        await self._check_v4_readiness()

        logger.info("Pulse complete: %d actions, %d failures", len(actions), failures)
        return actions

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await self.run_heartbeat_once()
            except Exception:
                logger.exception("Heartbeat cycle failed")
            await asyncio.sleep(self._get_heartbeat_interval())

    async def _pulse_loop(self) -> None:
        await asyncio.sleep(60)
        while self._running:
            try:
                await self.run_pulse_once()
            except Exception:
                logger.exception("Pulse cycle failed")
                await self.alerts.send_alert("Pulse cycle failed — check logs")
            await asyncio.sleep(self._get_pulse_interval_hours() * 3600)

    async def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._pulse_loop()),
        ]
        logger.info("OlympusGuardian started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("OlympusGuardian stopped")

    async def get_health_summary(self) -> dict[str, Any]:
        last_heartbeat: dict[str, Any] | None = None
        recent_actions: list[dict[str, Any]] = []
        rules_count = len(self.rules_engine.rules) if self.rules_engine else 0

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

        return {
            "status": "alive",
            "running": self._running,
            "rules_count": rules_count,
            "last_heartbeat": last_heartbeat,
            "recent_actions": recent_actions,
        }

    async def _persist_action(self, action: PulseAction) -> None:
        query = """
            INSERT INTO olympus_actions (
                rhythm, action_type, target, detail, outcome,
                duration_ms, rule_applied, reflection, executed_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query, action.rhythm, action.action_type, action.target,
                    json.dumps(action.detail), action.outcome, action.duration_ms,
                    action.rule_applied, action.reflection, action.executed_at,
                )
        except Exception:
            logger.exception("Failed to persist action: %s", action.action_type)

    _V4_INSIGHTS_THRESHOLD = 500

    async def _check_v4_readiness(self) -> None:
        """Check if enough insights have accumulated to activate v4 Voyager skills."""
        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM olympus_insights")
            if count and count >= self._V4_INSIGHTS_THRESHOLD:
                logger.info(
                    "v4 READY: %d insights accumulated (threshold: %d) — Voyager skills activatable",
                    count, self._V4_INSIGHTS_THRESHOLD,
                )
        except Exception:
            pass  # non-critical

    def _get_heartbeat_interval(self) -> int:
        if self.rules_engine is None:
            return 300
        return int(self.rules_engine.get_threshold("heartbeat_interval_seconds", default=300))

    def _get_pulse_interval_hours(self) -> int:
        if self.rules_engine is None:
            return 6
        return int(self.rules_engine.get_threshold("pulse_interval_hours", default=6))
