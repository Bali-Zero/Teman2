#!/usr/bin/env python3
"""Metabolic rollup — daily cron entry point for SYMBIOSIS Pillar 7.

Collect → Store → Trend → Telegram → JSONL log.

Usage:
    python scripts/metabolic_rollup.py                         # full run
    python scripts/metabolic_rollup.py --dry-run               # print snapshot, don't store
    python scripts/metabolic_rollup.py --notify                # send Telegram report
    python scripts/metabolic_rollup.py --db-path /tmp/test.db  # custom DB path

# Organo: scripts/ (L1 integration)
# Produce: SQLite snapshot, JSONL log, Telegram report, Redis stream event
# Consuma: cell_pulse_log (PG), kg_nodes/kg_edges (PG), cron JSONL,
#          MOS SQLite, escalations JSONL
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add packages/cell-core to path so we can import cell_core
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "packages" / "cell-core"))

from cell_core.metabolic.collector import MetabolicCollector
from cell_core.metabolic.definitions import (
    ALL_METRICS,
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)
from cell_core.metabolic.storage import MetabolicStore
from cell_core.metabolic.trend import TrendAnalyzer

# ── Config ─────────────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = os.path.expanduser("~/.agent/decisions/organism_metrics.db")
DEFAULT_CRON_LOG_DIR = os.path.expanduser("~/logs/cron")
DEFAULT_ESCALATION_PATH = str(_repo_root / "shared" / "escalations_pro.jsonl")
DEFAULT_MOS_DB_PATH = os.path.expanduser("~/.claude/memory.db")
STATE_FILE = os.path.expanduser("~/.agent/decisions/state/metabolic_rollup.last.json")
LOG_FILE = os.path.expanduser("~/logs/cron/metabolic-rollup.jsonl")

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

# PG DSN — optional (Fly tunnel on Air)
PG_DSN = os.environ.get("METABOLIC_PG_DSN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("metabolic_rollup")


def send_telegram(text: str) -> bool:
    """Send a message to Telegram via Bot API. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return False
    try:
        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def write_state_file(snapshot: MetabolicSnapshot, success: bool) -> None:
    """Write CronSensor-compatible state file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state = {
        "job": "metabolic_rollup",
        "ts": time.time(),
        "status": "ok" if success else "failed",
        "host": os.uname().nodename,
        "snapshot_at": snapshot.calculated_at,
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def write_log_entry(snapshot: MetabolicSnapshot, duration_s: float, success: bool) -> None:
    """Append JSONL entry to cron log."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = {
        "job": "metabolic-rollup",
        "status": "ok" if success else "failed",
        "exit_code": 0 if success else 1,
        "attempts": 1,
        "duration_s": round(duration_s, 1),
        "host": os.uname().nodename,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def try_redis_push(snapshot: MetabolicSnapshot) -> None:
    """Optionally push to Redis organism:metrics stream."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()

        import uuid
        for metric_type in ALL_METRICS:
            metric = snapshot.get_metric(metric_type)
            if metric is None:
                continue
            envelope = {
                "id": str(uuid.uuid4()),
                "type": f"metric.{metric_type}",
                "source": "metabolic_rollup",
                "timestamp": snapshot.calculated_at,
                "priority": "3",
                "payload": json.dumps(metric.to_dict()),
            }
            r.xadd("organism:metrics", envelope)
        logger.info("[metabolic] pushed 4 metrics to Redis organism:metrics stream")
    except ImportError:
        logger.debug("redis-py not installed, skipping Redis push")
    except Exception as e:
        logger.debug(f"Redis push failed (non-fatal): {e}")


def _project_scope(snapshot: MetabolicSnapshot, scope: str) -> MetabolicSnapshot:
    """Return a copy of `snapshot` with non-scope metrics nulled out.

    Schema v2: global scope exposes TTR+DO only; host scope exposes IA+FE only.
    Non-scope metrics are replaced with a None MetricValue carrying
    `metadata.error='not_applicable_by_design'` (distinguishes from collector failures).
    """
    not_applicable = {"error": "not_applicable_by_design"}

    def _null_metric(metric_type: str, calculated_at: str) -> MetricValue:
        return MetricValue(
            metric_type=metric_type, value=None,
            calculated_at=calculated_at, metadata=not_applicable,
        )

    ts = snapshot.calculated_at
    if scope == "global":
        return MetabolicSnapshot(
            ttr=snapshot.ttr,
            ontology_density=snapshot.ontology_density,
            autonomy_index=_null_metric(METRIC_AUTONOMY_INDEX, ts),
            escalation_freq=_null_metric(METRIC_ESCALATION_FREQ, ts),
            calculated_at=ts,
        )
    elif scope == "host":
        return MetabolicSnapshot(
            ttr=_null_metric(METRIC_TTR, ts),
            ontology_density=_null_metric(METRIC_ONTOLOGY_DENSITY, ts),
            autonomy_index=snapshot.autonomy_index,
            escalation_freq=snapshot.escalation_freq,
            calculated_at=ts,
        )
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Metabolic metrics daily rollup")
    parser.add_argument("--dry-run", action="store_true", help="Print snapshot without storing")
    parser.add_argument("--notify", action="store_true", help="Send Telegram report")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite DB path")
    parser.add_argument("--pg-dsn", default=PG_DSN, help="PostgreSQL DSN for TTR/DO metrics")
    parser.add_argument(
        "--mode",
        choices=["air", "pro", "auto"],
        default="auto",
        help="air=writes global+host rows, pro=writes host row only, auto=decide from PG_DSN",
    )
    parser.add_argument(
        "--collector-host",
        default=None,
        help="Host identifier for v2 schema ('pro'|'air'). Default: inferred from hostname.",
    )
    args = parser.parse_args()

    # Resolve mode: auto → air if PG_DSN set, else pro
    mode = args.mode
    if mode == "auto":
        mode = "air" if args.pg_dsn else "pro"

    # Resolve collector_host: explicit flag > inferred from hostname
    collector_host = args.collector_host
    if not collector_host:
        import socket
        hostname = socket.gethostname().lower()
        if "nuzantara-9" in hostname:
            collector_host = "air"
        elif "nuzantara" in hostname:
            collector_host = "pro"
        else:
            collector_host = hostname.split(".")[0]

    start_time = time.time()
    success = True

    try:
        # 1. Collect
        collector = MetabolicCollector(
            cron_log_dir=DEFAULT_CRON_LOG_DIR,
            escalation_path=DEFAULT_ESCALATION_PATH,
            mos_db_path=DEFAULT_MOS_DB_PATH,
            pg_dsn=args.pg_dsn or None,
        )
        snapshot = collector.collect()

        if args.dry_run:
            print(json.dumps(snapshot.to_dict(), indent=2))
            return

        # 2. Store — schema v2: write 1 row (pro) or 2 rows (air)
        store = MetabolicStore(db_path=args.db_path)
        if mode == "air":
            snap_global = _project_scope(snapshot, "global")
            snap_host = _project_scope(snapshot, "host")
            store.store(snap_global, collector_host=collector_host, metric_scope="global")
            store.store(snap_host, collector_host=collector_host, metric_scope="host")
        elif mode == "pro":
            snap_host = _project_scope(snapshot, "host")
            store.store(snap_host, collector_host=collector_host, metric_scope="host")
        else:
            store.store(snapshot, collector_host=collector_host, metric_scope=None)

        # 3. Trends
        analyzer = TrendAnalyzer(store)
        trends = analyzer.classify_all()

        # 4. Telegram
        report = snapshot.format_telegram(trends)
        if args.notify:
            sent = send_telegram(f"<pre>{report}</pre>")
            logger.info(f"Telegram report {'sent' if sent else 'failed'}")
        else:
            logger.info("Telegram notification skipped (use --notify to enable)")

        # 5. Redis (best-effort)
        try_redis_push(snapshot)

        # 6. Log
        logger.info(f"Snapshot stored: TTR={snapshot.ttr.value}, DO={snapshot.ontology_density.value}, "
                     f"IA={snapshot.autonomy_index.value}, FE={snapshot.escalation_freq.value}")
        print(report)

    except Exception as e:
        logger.error(f"Rollup failed: {e}", exc_info=True)
        success = False
    finally:
        duration = time.time() - start_time
        try:
            write_state_file(snapshot, success)
        except NameError:
            pass  # snapshot not created
        write_log_entry(
            snapshot if "snapshot" in dir() else MetabolicSnapshot.__new__(MetabolicSnapshot),
            duration, success,
        )


if __name__ == "__main__":
    main()
