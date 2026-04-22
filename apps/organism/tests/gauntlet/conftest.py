"""Staging fixture for gauntlet scenario tests.

Provides a `staging_organism` fixture that wraps:
- Isolated fakeredis stream + consumer group already initialized
- Event emission helper that correctly simulates guardians
- Supervisor run_once helper that consumes + decides + records decisions
- Mock Telegram + WAL dir under tmp_path

Each scenario test calls `staging.inject_*` helpers to simulate a failure,
then calls `staging.drive_supervisor(iterations=N)` to let the Supervisor
process events, then asserts events/decisions.

Crucially this is NOT a live-daemon integration test — it's a unit-level
verification that the orchestration paths fire correctly when adversarial
inputs hit the event bus.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fakeredis
import fakeredis.aioredis
import pytest

from organism.schemas import Event, Severity
from organism.redis_bus import EventBus
from organism.supervisor.daemon import run_once
from organism.supervisor.incident_context import IncidentStore


BASE_YAML = """
rules:
  - id: cron_agent_failure_restart
    match: {kind: cron_agent_failure, severity: [error, critical]}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95

  - id: zombie_detected_restart
    match: {kind: zombie_detected}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.85

  - id: disk_fill_cleanup
    match: {kind: disk_fill, payload.percent_gte: 85}
    action: {actuator: cleanup_log, params: {min_age_days: 30}}
    confidence: 0.90

  - id: deploy_failure_rollback
    match: {kind: deploy_failure}
    action: {actuator: rollback_deploy, params: {target: "{payload.target}"}}
    confidence: 0.90
"""


@dataclass
class StagingOrganism:
    """Test-only wrapper around a fakeredis-backed organism pipeline."""
    redis: Any
    bus: EventBus
    store: IncidentStore
    decisions_log: Path
    rules_yaml: str = BASE_YAML
    telegram_calls: list[dict] = field(default_factory=list)
    injected_crashes: list[str] = field(default_factory=list)

    async def emit(
        self,
        *,
        kind: str,
        source: str = "guardian.test",
        severity: Severity = Severity.ERROR,
        payload: dict | None = None,
        correlation_id: str = "c-gauntlet",
        is_actuation: bool = False,
    ) -> None:
        """Emit an event to the bus as a guardian would."""
        e = Event(
            severity=severity,
            source=source,
            kind=kind,
            payload=payload or {},
            correlation_id=correlation_id,
            is_actuation=is_actuation,
            host="Pro",
        )
        await self.bus.emit(e)

    async def drive_supervisor(self, iterations: int = 1) -> list[int]:
        """Run the stateless Supervisor run_once N times. Returns events processed per iteration."""
        results = []
        for _ in range(iterations):
            count = await run_once(
                redis=self.redis,
                rules_yaml=self.rules_yaml,
                decisions_log=self.decisions_log,
                shadow_mode=True,
                block_ms=10,
            )
            results.append(count)
        return results

    async def events_in_stream(self) -> list[dict]:
        """Decode all events currently in organism:events stream."""
        entries = await self.redis.xrange("organism:events")
        decoded = []
        for _, fields in entries:
            raw = fields.get(b"data") if isinstance(fields, dict) else fields["data"]
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            decoded.append(json.loads(raw))
        return decoded

    async def events_of_kind(self, kind: str) -> list[dict]:
        all_events = await self.events_in_stream()
        return [e for e in all_events if e.get("kind") == kind]

    def decisions(self) -> list[dict]:
        if not self.decisions_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.decisions_log.read_text().strip().splitlines()
            if line.strip()
        ]

    def decisions_for_actuator(self, actuator: str) -> list[dict]:
        return [d for d in self.decisions() if d.get("actuator") == actuator]

    def inject_crash(self, component: str) -> None:
        """Record that a component was killed. Tests use this to simulate
        guardian/service failure. The actual crash simulation is
        cooperative: guardian emitters detect and emit events accordingly.
        """
        self.injected_crashes.append(component)


@pytest.fixture
async def staging_organism(tmp_path, monkeypatch):
    """Build a clean organism staging environment per-test."""
    # Per-test fakeredis (FakeServer isolates from other tests)
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server)

    jsonl_path = tmp_path / "events.jsonl"
    decisions_log = tmp_path / "decisions.jsonl"
    bus = EventBus(redis=redis, jsonl_path=jsonl_path)

    # Override the emit singleton so other code paths that call emit_event
    # (e.g. via guardians in tests) reach our staging bus.
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    store = IncidentStore(redis=redis)
    staging = StagingOrganism(
        redis=redis,
        bus=bus,
        store=store,
        decisions_log=decisions_log,
    )
    yield staging
    await redis.aclose()
