"""The Pulse — CELL's heartbeat.
Every 60 seconds: verify DNA → check safety → sense → evaluate → THINK → act → remember."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cell.core import db as cell_db
from cell.fast.health_triage import HealthStatus

logger = logging.getLogger("cell.pulse")


@dataclass
class PulseResult:
    timestamp: datetime
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: HealthStatus | None = None
    action_taken: str | None = None
    action_reason: str | None = None
    thought_tier: int | None = None
    error: str | None = None


class PulseEngine:
    def __init__(
        self,
        dna_loader: Any,
        safety_gate: Any,
        health_sensor: Any,
        metabolism: Any,
        reasoner: Any = None,
        dna_interpreter: Any = None,
        dna_expected_hash: str = "",
        alerter: Any = None,
        fly_effector: Any = None,
        logs_effector: Any = None,
        local_effector: Any = None,
        db_sensor: Any = None,
        qdrant_sensor: Any = None,
        error_rate_sensor: Any = None,
        ollama_sensor: Any = None,
        backup_sensor: Any = None,
        cron_sensor: Any = None,
        vercel_sensor: Any = None,
        stm: Any = None,
        ltm: Any = None,
        trend_detector: Any = None,
        homeostatic: Any = None,
        episodic: Any = None,
        self_model: Any = None,
    ) -> None:
        self._dna = dna_loader
        self._safety = safety_gate
        self._health = health_sensor
        self._metabolism = metabolism
        self._reasoner = reasoner
        self._interpreter = dna_interpreter
        self._dna_hash = dna_expected_hash
        self._alerter = alerter
        self._fly = fly_effector
        self._logs = logs_effector
        self._local = local_effector
        self._db_sensor = db_sensor
        self._qdrant_sensor = qdrant_sensor
        self._error_rate_sensor = error_rate_sensor
        self._ollama_sensor = ollama_sensor
        self._backup_sensor = backup_sensor
        self._cron_sensor = cron_sensor
        self._vercel_sensor = vercel_sensor
        self._stm = stm
        self._ltm = ltm
        self._trend = trend_detector
        self._homeostatic = homeostatic
        self._episodic = episodic
        self._self_model = self_model
        self._recent_pulses: list[dict] = []
        self._ltm_cache: str = ""
        self._ltm_cache_pulse: int = -999  # refresh every 60 pulses (~1h)

    async def single_pulse(self, pulse_number: int = 0) -> PulseResult:
        now = datetime.now(timezone.utc)

        # 1. DNA INTEGRITY
        if self._dna_hash and not self._dna.verify_integrity(self._dna_hash):
            logger.critical("DNA INTEGRITY FAILURE — HALTING")
            return PulseResult(timestamp=now, halted=True, halt_reason="DNA integrity check failed")

        # 2. SAFETY GATES
        safety = await self._safety.check()
        if not safety.can_proceed:
            logger.info(f"Pulse skipped: {safety.reason} — {safety.detail}")
            return PulseResult(timestamp=now, skipped=True, skip_reason=safety.reason)

        # 3. SENSE
        reading = await self._health.read()

        # 4. EVALUATE (FAST) — aggregate all sensors
        if reading.reachable and reading.status_code == 200:
            http_status = HealthStatus.GREEN
        elif reading.reachable:
            http_status = HealthStatus.YELLOW
        else:
            http_status = HealthStatus.RED

        response_ms = int(reading.response_time_seconds * 1000) if reading.reachable else 0

        # Update homeostasis with actual reading
        if self._homeostatic is not None:
            self._homeostatic.update(
                response_time_ms=response_ms,
                health_status=http_status.value,
                hour_utc=datetime.now(timezone.utc).hour,
            )

        # Secondary sensors (reuse /health body, no extra HTTP)
        sensor_metadata: dict[str, Any] = {}
        db_ok: float = 1.0
        qdrant_ok: float = 1.0
        error_rate_norm: float = 0.0

        if self._db_sensor is not None:
            db_reading = self._db_sensor.read(reading)
            sensor_metadata["db"] = db_reading.metadata
            if db_reading.status == "red":
                db_ok = 0.0
            elif db_reading.status == "yellow":
                db_ok = 0.5

        if self._qdrant_sensor is not None:
            qdrant_reading = self._qdrant_sensor.read(reading)
            sensor_metadata["qdrant"] = qdrant_reading.metadata
            if qdrant_reading.status == "red":
                qdrant_ok = 0.0
            elif qdrant_reading.status == "yellow":
                qdrant_ok = 0.5

        if self._error_rate_sensor is not None:
            error_reading = await self._error_rate_sensor.read()
            sensor_metadata["error_rate"] = error_reading.metadata
            error_rate_norm = error_reading.error_rate_norm

        # New sensors — local visibility
        ollama_status = "green"
        if self._ollama_sensor is not None:
            ollama_reading = await self._ollama_sensor.read()
            sensor_metadata["ollama"] = ollama_reading.metadata
            ollama_status = ollama_reading.status

        backup_status = "green"
        if self._backup_sensor is not None:
            backup_reading = self._backup_sensor.read()
            sensor_metadata["backup"] = backup_reading.metadata
            backup_status = backup_reading.status

        cron_status = "green"
        if self._cron_sensor is not None:
            cron_reading = self._cron_sensor.read()
            sensor_metadata["cron"] = cron_reading.metadata
            cron_status = cron_reading.status

        vercel_status = "green"
        if self._vercel_sensor is not None:
            vercel_reading = await self._vercel_sensor.read()
            sensor_metadata["vercel"] = vercel_reading.metadata
            vercel_status = vercel_reading.status

        # Aggregate: final status is the worst across all sensors
        sensor_statuses = [http_status.value]
        if self._db_sensor is not None:
            sensor_statuses.append(db_reading.status)  # type: ignore[possibly-undefined]
        if self._qdrant_sensor is not None:
            sensor_statuses.append(qdrant_reading.status)  # type: ignore[possibly-undefined]
        if self._error_rate_sensor is not None:
            sensor_statuses.append(error_reading.status)  # type: ignore[possibly-undefined]
        sensor_statuses.extend([ollama_status, backup_status, cron_status, vercel_status])

        _severity = {"green": 0, "yellow": 1, "red": 2}
        worst = max(sensor_statuses, key=lambda s: _severity.get(s, 0))
        status = HealthStatus(worst)

        logger.info(
            f"Pulse: health={status.value} (http={http_status.value}), "
            f"reachable={reading.reachable}, "
            f"status_code={reading.status_code}, "
            f"response_time={reading.response_time_seconds:.3f}s"
            + (f", sensors={sensor_metadata}" if sensor_metadata else "")
        )

        # Track recent history for reasoner context
        self._recent_pulses.append({
            "pulse_number": pulse_number,
            "health_status": status.value,
            "response_time_ms": response_ms,
        })
        if len(self._recent_pulses) > 50:
            self._recent_pulses = self._recent_pulses[-50:]

        # 5. THINK (SLOW) — only if not GREEN and reasoner is available
        action = None
        action_reason = None
        thought_tier = None

        # STM write — every pulse regardless of status
        if self._stm is not None:
            from cell.memory.short_term import Observation
            try:
                await self._stm.store(Observation(
                    event_type="pulse",
                    data={
                        "pulse_number": pulse_number,
                        "health_status": status.value,
                        "response_time_ms": response_ms,
                        "ollama": ollama_status,
                        "backup": backup_status,
                        "vercel": vercel_status,
                        "stress": self._homeostatic.state.stress_level if self._homeostatic else 0.0,
                        "energy": self._homeostatic.state.energy_level if self._homeostatic else 1.0,
                        "circadian": self._homeostatic.state.circadian_phase if self._homeostatic else "awake",
                    },
                ))
            except Exception as e:
                logger.debug(f"STM write failed: {e}")

        # Trend detection (FAST layer, <5ms)
        trend_context = ""
        if self._trend is not None:
            trend = self._trend.detect(self._recent_pulses)
            parts = []
            if trend.monotonic_drift:
                parts.append("⚠ MONOTONIC DRIFT: response time rising every pulse")
            if trend.flapping:
                parts.append("⚠ FLAPPING: health status alternating rapidly")
            if trend.sustained_degraded:
                parts.append("⚠ SUSTAINED DEGRADED: multiple consecutive non-green pulses")
            trend_context = "\n".join(parts)
            if trend_context:
                logger.info(f"TrendDetector: {trend_context}")

        # LTM context — refresh every 60 pulses (~1h)
        ltm_context = self._ltm_cache
        if self._ltm is not None and (pulse_number - self._ltm_cache_pulse) >= 60:
            try:
                rules = await self._ltm.load_rules()
                if rules:
                    ltm_context = self._ltm.format_for_prompt(rules)
                    self._ltm_cache = ltm_context
                    self._ltm_cache_pulse = pulse_number
            except Exception as e:
                logger.debug(f"LTM load failed: {e}")

        # STM context for reasoner — last 5 observations
        stm_context = ""
        if self._stm is not None:
            try:
                recent_obs = await self._stm.recent(event_type="pulse", limit=5)
                if recent_obs:
                    lines = []
                    for obs in recent_obs:
                        d = obs.get("data", {})
                        lines.append(
                            f"  {obs.get('timestamp', '?')[:19]}: "
                            f"health={d.get('health_status', '?')} "
                            f"rt={d.get('response_time_ms', 0)}ms "
                            f"ollama={d.get('ollama', '?')} "
                            f"backup={d.get('backup', '?')}"
                        )
                    stm_context = "\n".join(lines)
            except Exception as e:
                logger.debug(f"STM read failed: {e}")

        if status != HealthStatus.GREEN and self._reasoner and self._interpreter:
            try:
                proposal = await self._reasoner.think(
                    health_status=status.value,
                    response_time_ms=response_ms,
                    error_message=reading.error if not reading.reachable else "",
                    recent_history=self._recent_pulses,
                    budget_spent=self._metabolism.daily_spend,
                    budget_limit=self._metabolism._daily_limit,
                    db_ok=db_ok,
                    qdrant_ok=qdrant_ok,
                    error_rate_norm=error_rate_norm,
                    stm_context=stm_context,
                    trend_context=trend_context,
                    ltm_context=ltm_context,
                )

                thought_tier = proposal.tier_used

                # Record LLM cost
                if proposal.cost_usd > 0:
                    self._metabolism.record("llm", proposal.cost_usd, partition="incident")

                if proposal.action != "none":
                    # 6. VALIDATE against DNA
                    validation = self._interpreter.validate(
                        action_name=proposal.action,
                        budget_spent=self._metabolism.daily_spend,
                        budget_limit=self._metabolism._daily_limit,
                        confidence=proposal.confidence,
                    )

                    if validation.approved:
                        action = proposal.action
                        action_reason = proposal.reason
                        self._interpreter.record_action(proposal.action)
                        logger.info(
                            f"THINK → ACT: {proposal.action} "
                            f"(confidence={proposal.confidence:.2f}, tier={proposal.tier_used}, "
                            f"reason={proposal.reason[:60]})"
                        )
                        # Execute Fly.io actions (restart, scale up/down)
                        fly_actions = {"restart_service", "scale_up", "scale_down"}
                        if proposal.action in fly_actions and self._fly:
                            result = await self._fly.execute(proposal.action)
                            if result.success:
                                logger.info(f"FlyEffector OK: {result.detail}")
                                action_reason = f"{proposal.reason} | executed: {result.detail}"
                            else:
                                logger.error(f"FlyEffector FAILED: {result.detail}")
                                action_reason = f"{proposal.reason} | FAILED: {result.detail}"
                            # Notify via Telegram on Fly.io actions
                            if self._alerter:
                                status_emoji = "✅" if result.success else "❌"
                                await self._alerter.send(
                                    f"{status_emoji} *{proposal.action.upper()}*\n"
                                    f"{result.detail}\n"
                                    f"Health: {status.value.upper()} | Confidence: {proposal.confidence:.0%}"
                                )
                        # Execute read_logs — fetch Fly.io logs, store summary to DB
                        elif proposal.action == "read_logs" and self._logs:
                            logs_result = await self._logs.read_logs(limit=50)
                            if logs_result.success:
                                logger.info(f"LogsEffector: {logs_result.detail}")
                                action_reason = f"{proposal.reason} | {logs_result.summary}"
                            else:
                                logger.warning(f"LogsEffector failed: {logs_result.detail}")
                                action_reason = f"{proposal.reason} | logs unavailable: {logs_result.detail}"
                            # Write to cell_alerts for dashboard visibility
                            await cell_db.log_alert(
                                level="info",
                                action="read_logs",
                                message=logs_result.summary or logs_result.detail,
                                health_status=status.value,
                                pulse_number=pulse_number,
                            )
                        # Execute local actions (ollama_restart, run_backup)
                        elif proposal.action in {"ollama_restart", "run_backup"} and self._local:
                            local_result = await self._local.execute(proposal.action)
                            if local_result.success:
                                logger.info(f"LocalEffector {proposal.action} OK: {local_result.detail[:80]}")
                                action_reason = f"{proposal.reason} | executed: {local_result.detail}"
                            else:
                                logger.error(f"LocalEffector {proposal.action} FAILED: {local_result.detail[:80]}")
                                action_reason = f"{proposal.reason} | FAILED: {local_result.detail}"
                            if self._alerter:
                                emoji = "✅" if local_result.success else "❌"
                                await self._alerter.send(
                                    f"{emoji} *{proposal.action.upper()}*\n"
                                    f"{local_result.detail[:200]}\n"
                                    f"Health: {status.value.upper()} | Confidence: {proposal.confidence:.0%}"
                                )
                        # Execute alert_silent — write to cell_alerts (no Telegram)
                        elif proposal.action == "alert_silent":
                            await cell_db.log_alert(
                                level="warn",
                                action="alert_silent",
                                message=proposal.reason[:500],
                                health_status=status.value,
                                pulse_number=pulse_number,
                            )
                            logger.info(f"alert_silent written to DB: {proposal.reason[:80]}")
                        # Execute alert_human — Telegram + DB
                        elif proposal.action == "alert_human" and self._alerter:
                            msg = (
                                f"*Health: {status.value.upper()}*\n"
                                f"Reason: {proposal.reason[:200]}\n"
                                f"Confidence: {proposal.confidence:.0%} | Tier: {proposal.tier_used}"
                            )
                            await self._alerter.send(msg)
                            await cell_db.log_alert(
                                level="critical",
                                action="alert_human",
                                message=proposal.reason[:500],
                                health_status=status.value,
                                pulse_number=pulse_number,
                            )
                    else:
                        logger.info(
                            f"THINK → BLOCKED: {proposal.action} — {validation.reason} "
                            f"(rule {validation.rule_violated})"
                        )
                        action_reason = f"Proposed {proposal.action} but blocked: {validation.reason}"
                else:
                    action_reason = proposal.reason
                    logger.info(f"THINK → no action needed: {proposal.reason[:80]}")

            except Exception as e:
                logger.error(f"SLOW reasoner error: {e}", exc_info=True)
                action_reason = f"Reasoner error: {e}"

        # 7. PERSIST to PostgreSQL for dashboard
        try:
            await cell_db.log_pulse(
                pulse_number=pulse_number,
                health_status=status.value,
                response_time_ms=response_ms,
                dna_intact=True,
                budget_spent=self._metabolism.daily_spend,
                budget_limit=self._metabolism._daily_limit,
                action_taken=action,
                error_message=action_reason if status != HealthStatus.GREEN else None,
            )
        except Exception as e:
            logger.error(f"Pulse DB log failed: {e}")

        # 8. SELF-MODEL — record pulse
        if self._self_model is not None:
            self._self_model.record_pulse()
            if action:
                self._self_model.record_action()
            # Update sensor reliability based on reachability
            self._self_model.update_sensor_reliability("health_sensor", reading.reachable)
            # Save every 60 pulses (~1h)
            if pulse_number % 60 == 0:
                self._self_model.save()

        # 9. EPISODIC MEMORY — record significant events
        if self._episodic is not None and self._episodic.should_record(
            health_status=status.value, action_taken=action
        ):
            from cell.memory.episodic import Episode
            emotion = "calm"
            if status == HealthStatus.RED:
                emotion = "stressed"
            elif status == HealthStatus.YELLOW:
                emotion = "alert"
            if self._homeostatic and self._homeostatic.state.stress_level > 0.8:
                emotion = "panic"
            try:
                ep = Episode(
                    situation={
                        "health_status": status.value,
                        "response_time_ms": response_ms,
                        "sensors": sensor_metadata,
                    },
                    emotion=emotion,
                    action_taken=action or "observe",
                    outcome="partial",
                    lesson=action_reason or "no action needed",
                )
                await self._episodic.store(ep)
            except Exception as e:
                logger.debug(f"Episodic memory store failed: {e}")

        return PulseResult(
            timestamp=now,
            health_status=status,
            action_taken=action,
            action_reason=action_reason,
            thought_tier=thought_tier,
        )
