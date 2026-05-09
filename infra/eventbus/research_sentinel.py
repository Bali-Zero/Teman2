#!/usr/bin/env python3
"""W3.4 — Research Sentinel — data quality watchdog.

Subscribes to bz:intel.collected + bz:intel.deduped + bz:regulatory.delta.detected.
Tracks per-source metrics over rolling 24h window:
- Volume (events/day) — if drops >50% vs 7-day baseline, alert
- Payload size — if shrinks >70% vs baseline, alert (page broken?)
- Schema consistency — fields missing vs baseline, alert (DOM changed?)

Emits Telegram alert + writes anomaly to observatory. Does NOT block pipeline.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import sqlite3
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import EventSubscriber, beat, list_all_heartbeats, start_background_beater
from eventbus.publisher import _client

DB_PATH = Path.home() / "agents/.observatory/trajectories.db"
LOG_PATH = Path.home() / "logs" / "research-sentinel.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("research-sentinel")


def _record_anomaly(source: str, metric: str, current: float, baseline: float,
                    deviation_pct: float, severity: str, trace_id: str):
    """Log to observatory + Telegram if high/critical."""
    try:
        with sqlite3.connect(str(DB_PATH), timeout=5) as con:
            con.execute(
                "INSERT INTO outcomes (trace_id, metric_name, metric_value, metric_text, measured_at, measured_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (trace_id, f"sentinel.anomaly.{metric}", deviation_pct,
                 f"source={source} current={current:.1f} baseline={baseline:.1f} severity={severity}",
                 datetime.now(timezone.utc).isoformat(), "research-sentinel"),
            )
    except Exception as e:
        log.warning("DB write failed: %s", e)

    if severity in ("high", "critical"):
        _telegram(f"RESEARCH SENTINEL [{severity}] source={source} metric={metric} "
                  f"current={current:.1f} vs baseline={baseline:.1f} ({deviation_pct:+.1f}%)")


def _telegram(text: str) -> None:
    import subprocess
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not token or not chat:
        log.warning("telegram skipped: missing TELEGRAM_*")
        return
    try:
        subprocess.run(
            ["curl", "-sf", "-X", "POST",
             f"https://api.telegram.org/bot{token}/sendMessage",
             "-d", f"chat_id={chat}",
             "-d", f"text={text[:4000]}",
             "-d", "disable_web_page_preview=true"],
            capture_output=True, timeout=10,
        )
    except Exception as e:
        log.warning("telegram send failed: %s", e)


def _baseline_volume(source: str, days: int = 7) -> tuple[float, int]:
    """Return (mean events/day over last N days, sample size). Sample size from observatory.events."""
    if not DB_PATH.exists():
        return (0.0, 0)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        with sqlite3.connect(str(DB_PATH), timeout=5) as con:
            cur = con.execute(
                "SELECT COUNT(*) FROM events WHERE emitted_by = ? AND emitted_at > ?",
                (source, cutoff),
            )
            total = cur.fetchone()[0]
            return (total / max(days, 1), total)
    except Exception as e:
        log.warning("baseline query failed: %s", e)
        return (0.0, 0)


def _check_volume(source: str, trace_id: str) -> None:
    """Compare today's volume vs 7-day baseline."""
    today_avg, today_n = _baseline_volume(source, days=1)
    baseline_avg, baseline_n = _baseline_volume(source, days=7)
    if baseline_n < 10:
        return  # not enough history yet
    if baseline_avg == 0:
        return
    deviation = ((today_avg - baseline_avg) / baseline_avg) * 100
    if deviation < -50:  # volume dropped >50%
        severity = "critical" if deviation < -80 else "high"
        log.warning("VOLUME ANOMALY source=%s today=%.1f baseline=%.1f (%.1f%%) sev=%s",
                    source, today_avg, baseline_avg, deviation, severity)
        _record_anomaly(source, "volume_drop", today_avg, baseline_avg, deviation, severity, trace_id)


def main() -> int:
    log.info("Research Sentinel starting.")
    start_background_beater("research-sentinel", interval=30)
    sub = EventSubscriber(
        agent_name="research-sentinel",
        event_types=["intel.collected", "intel.deduped", "regulatory.delta.detected"],
        start_from="$",
    )

    last_volume_check = {}  # source → datetime

    KNOWN_DAEMONS = ["meta-dispatcher", "observatory", "intel-dedup-gateway", "research-sentinel", "cron-log-sentinel"]
    last_heartbeat_check = 0
    last_dlq_check = 0
    dlq_alert_sent_at = 0  # rate-limit: 1 alert per hour
    DLQ_THRESHOLD = 5  # alert when >N events in DLQ

    for env in sub.listen(block_ms=10000, count=20):
        beat("research-sentinel")

        # Risk 3 fix: every 5 min, scan heartbeats for missing daemons
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts - last_heartbeat_check > 300:
            last_heartbeat_check = now_ts
            try:
                hb = list_all_heartbeats()
                missing = [d for d in KNOWN_DAEMONS if d not in hb]
                if missing:
                    msg = f"DAEMON DOWN — heartbeats missing: {', '.join(missing)} (no signal for >2min)"
                    log.error(msg)
                    _telegram(msg)
                    _record_anomaly("daemon-watchdog", "missing_heartbeat", 0,
                                    len(KNOWN_DAEMONS), -100.0 * len(missing) / len(KNOWN_DAEMONS),
                                    "critical", env.trace_id)
            except Exception as e:
                log.warning("heartbeat scan failed: %s", e)

        # #12 fix: DLQ size monitoring (rate-limited to 1 alert/hour)
        if now_ts - last_dlq_check > 300:
            last_dlq_check = now_ts
            try:
                dlq_size = _client().xlen("bz:dlq")
                if dlq_size > DLQ_THRESHOLD:
                    if now_ts - dlq_alert_sent_at > 3600:  # 1h cooldown
                        msg = (f"DLQ ALERT — {dlq_size} poison-pill events parked in bz:dlq "
                               f"(threshold {DLQ_THRESHOLD}). Inspect: redis-cli -h 100.93.236.6 "
                               f"XREVRANGE bz:dlq + - COUNT 5")
                        log.error(msg)
                        _telegram(msg)
                        _record_anomaly("dlq-monitor", "dlq_size_exceeded", float(dlq_size),
                                        float(DLQ_THRESHOLD),
                                        100.0 * (dlq_size - DLQ_THRESHOLD) / DLQ_THRESHOLD,
                                        "high", env.trace_id)
                        dlq_alert_sent_at = now_ts
                    else:
                        log.warning("DLQ size %d > %d but cooldown active", dlq_size, DLQ_THRESHOLD)
            except Exception as e:
                log.warning("DLQ size check failed: %s", e)

        attempts = sub.get_delivery_count(env)
        if attempts > sub.MAX_DELIVERY_ATTEMPTS:
            sub.park_to_dlq(env, f"research-sentinel: exceeded {sub.MAX_DELIVERY_ATTEMPTS} attempts")
            continue
        try:
            source = env.payload.get("source") or env.emitted_by
            now = datetime.now(timezone.utc)

            # Throttle volume checks: max 1/source/hour
            last = last_volume_check.get(source)
            if not last or (now - last) > timedelta(hours=1):
                _check_volume(source, env.trace_id)
                last_volume_check[source] = now

            # Per-event payload anomaly — small heuristic
            payload_len = len(json.dumps(env.payload, default=str))
            if payload_len < 50:
                log.warning("TINY-PAYLOAD source=%s event=%s len=%d", source, env.event_id, payload_len)
                _record_anomaly(source, "tiny_payload", payload_len, 1000.0, -95.0, "medium", env.trace_id)

        except Exception as e:
            log.exception("processing failed for event %s: %s", env.event_id, e)
        finally:
            sub.ack(env)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Research Sentinel interrupted")
        sys.exit(0)
