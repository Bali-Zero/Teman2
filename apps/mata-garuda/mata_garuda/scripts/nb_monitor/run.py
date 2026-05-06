"""Entrypoint for nb_monitor daily run.

Usage:
    python -m mata_garuda.scripts.nb_monitor.run         # full daily run
    python -m mata_garuda.scripts.nb_monitor.run --once  # alias, ad-hoc

Wires registry -> collectors -> tier classifier -> SQLite snapshot ->
alert evaluator -> optional Telegram dispatch -> optional weekly report.

Spec §3.3 data flow. All paths and external commands are injectable for
the integration test in tests/nb_monitor/test_integration_e2e.py.
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from mata_garuda.scripts.nb_monitor import (
    BOOTSTRAP_FILE,
    DATA_DIR,
    METRICS_DB,
)
from mata_garuda.scripts.nb_monitor.alerts import (
    AlertContext,
    AlertDecision,
    can_send,
    evaluate_alerts,
)
from mata_garuda.scripts.nb_monitor.collectors import (
    cite_rate,
    feeder_log,
    log_scraper,
    nlm_freshness,
    skill_derivation,
)
from mata_garuda.scripts.nb_monitor.persist import (
    AlertRecord,
    MetricRow,
    connect,
    ensure_schema,
    fetch_alert_last_sent,
    fetch_latest_per_uuid,
    insert_alert_record,
    insert_metric_row,
)
from mata_garuda.scripts.nb_monitor.registry import (
    NotebookEntry,
    RegistryLoadError,
    load_registry,
)
from mata_garuda.scripts.nb_monitor.report import (
    ReportEntry,
    render_weekly_report,
)
from mata_garuda.scripts.nb_monitor.telegram_send import send_telegram
from mata_garuda.scripts.nb_monitor.tier import Tier, TierInputs, classify

logger = logging.getLogger(__name__)

WINDOW_7D = 7 * 86400
WINDOW_30D = 30 * 86400


@dataclass
class RunConfig:
    bootstrap_path: Path = field(default_factory=lambda: BOOTSTRAP_FILE)
    db_path: Path = field(default_factory=lambda: METRICS_DB)
    feeder_log_path: Path = field(
        default_factory=lambda: Path.home() / "logs" / "matagaruda-nlm-feeder-stream.log"
    )
    report_dir: Path = field(
        default_factory=lambda: Path.home()
        / "Desktop"
        / "nuzantara"
        / "research"
        / "nb-monitor"
    )
    deploy_date: datetime = datetime(2026, 5, 7, tzinfo=timezone.utc)
    telegram_bot_token: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "1125336968")
    )
    collect_read_freq_7d: Callable[[str], int | None] | None = None
    collect_read_freq_30d: Callable[[str], int | None] | None = None
    collect_freshness: Callable[[str], int | None] | None = None
    collect_push_success: Callable[[], float | None] | None = None
    telegram_send: Callable[[str, str, str], bool] = send_telegram


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nb_monitor.run")
    parser.add_argument(
        "--once", action="store_true", help="alias; the run is always one-shot"
    )
    parser.add_argument(
        "--no-telegram", action="store_true", help="suppress Telegram dispatch"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="force-generate weekly report regardless of weekday",
    )
    args = parser.parse_args(argv)

    _configure_logging()
    cfg = RunConfig()
    if args.no_telegram:
        cfg.telegram_send = lambda *_a, **_kw: False  # type: ignore[assignment]

    return execute_once(cfg, force_report=args.report)


def execute_once(
    cfg: RunConfig, force_report: bool = False, now: float | None = None
) -> int:
    now = now if now is not None else time.time()
    ts_capture = int(now)
    logger.info("nb_monitor: starting run ts_capture=%d", ts_capture)

    try:
        entries = load_registry(cfg.bootstrap_path)
    except RegistryLoadError as e:
        logger.error("nb_monitor: cannot load registry: %s", e)
        return 0

    if len(entries) < 24:
        logger.warning(
            "nb_monitor: only %d notebooks in registry (expected up to 24 per FASE 2)",
            len(entries),
        )

    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    try:
        ensure_schema(conn)
        rows = _collect_all(entries, cfg, ts_capture)

        for entry, row, prev in rows:
            insert_metric_row(conn, row)
            decisions = _build_alert_decisions(entry, row, prev, conn, ts_capture, cfg)
            for d in decisions:
                _dispatch_alert(d, entry.uuid, conn, ts_capture, cfg)

        report_entries = _build_report_entries(rows)
        if force_report or _is_sunday(ts_capture):
            _write_report(cfg, report_entries, ts_capture)

        logger.info("nb_monitor: completed run, processed=%d", len(rows))
    except Exception as e:  # noqa: BLE001 (graceful-degrade per spec §7.2)
        logger.exception("nb_monitor: unhandled exception: %s", e)
    finally:
        conn.close()

    return 0


def _configure_logging() -> None:
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "nb-monitor.log")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)


def _collect_all(
    entries: list[NotebookEntry],
    cfg: RunConfig,
    ts_capture: int,
) -> list[tuple[NotebookEntry, MetricRow, MetricRow | None]]:
    if cfg.collect_read_freq_7d is not None and cfg.collect_read_freq_30d is not None:
        rf_7d_counts: dict[str, int] = {}
        rf_30d_counts: dict[str, int] = {}
    else:
        files = log_scraper.discover_session_files(
            cutoff_mtime=ts_capture - WINDOW_30D
        )
        rf_7d_counts = log_scraper.count_nlm_events_by_uuid(
            files, window_seconds=WINDOW_7D, now=ts_capture
        )
        rf_30d_counts = log_scraper.count_nlm_events_by_uuid(
            files, window_seconds=WINDOW_30D, now=ts_capture
        )

    if cfg.collect_push_success is not None:
        global_psr = cfg.collect_push_success()
    else:
        global_psr = feeder_log.compute_global_push_success_rate(
            cfg.feeder_log_path, window_seconds=WINDOW_7D, now=ts_capture
        )

    out: list[tuple[NotebookEntry, MetricRow, MetricRow | None]] = []
    conn = connect(cfg.db_path)
    try:
        for entry in entries:
            try:
                rf7 = (
                    cfg.collect_read_freq_7d(entry.uuid)
                    if cfg.collect_read_freq_7d is not None
                    else rf_7d_counts.get(entry.uuid, 0)
                )
                rf30 = (
                    cfg.collect_read_freq_30d(entry.uuid)
                    if cfg.collect_read_freq_30d is not None
                    else rf_30d_counts.get(entry.uuid, 0)
                )
                fresh = (
                    cfg.collect_freshness(entry.uuid)
                    if cfg.collect_freshness is not None
                    else nlm_freshness.fetch_source_freshness_age_days(entry.uuid)
                )
                psr = global_psr if entry.active_routing else None
                skill = skill_derivation.count_skills_for_uuid(entry.uuid)
                cite = cite_rate.compute_rate_for_uuid(entry.uuid)

                age = _age_days(entry.first_audited, ts_capture)
                tier = classify(
                    TierInputs(read_freq_7d=rf7, push_success_rate=psr, age_days=age)
                )
                row = MetricRow(
                    uuid=entry.uuid,
                    ts_capture=ts_capture,
                    tier=tier.value,
                    read_freq_7d=rf7,
                    read_freq_30d=rf30,
                    skill_derivation_count=skill,
                    downstream_cite_rate=cite,
                    source_freshness_age_days=fresh,
                    push_success_rate=psr,
                    instrumentation_status=_status(rf7, fresh, psr),
                )
                prev = fetch_latest_per_uuid(conn, entry.uuid)
                out.append((entry, row, prev))
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "nb_monitor: collector failure for %s: %s", entry.name, e
                )
    finally:
        conn.close()
    return out


def _build_alert_decisions(
    entry: NotebookEntry,
    row: MetricRow,
    prev: MetricRow | None,
    conn: sqlite3.Connection,
    ts_capture: int,
    cfg: RunConfig,
) -> list[AlertDecision]:
    age = _age_days(entry.first_audited, ts_capture)
    tier_now = Tier(row.tier)
    tier_lastweek = Tier(prev.tier) if prev else None

    consecutive_dying = _consecutive_dying_days(conn, entry.uuid, ts_capture)
    rf7_max_30d = _rf7_30d_window_max(conn, entry.uuid, ts_capture)
    in_top5 = _was_in_top5_alive_lastweek(conn, entry.uuid, ts_capture)

    ctx = AlertContext(
        uuid=entry.uuid,
        name=entry.name,
        tier_now=tier_now,
        tier_lastweek=tier_lastweek,
        read_freq_7d_now=row.read_freq_7d,
        read_freq_7d_lastweek=prev.read_freq_7d if prev else None,
        age_days=age,
        skill_derivation_count=row.skill_derivation_count,
        in_top5_alive_lastweek=in_top5,
        consecutive_dying_days=consecutive_dying,
        rf7_30d_window_max=rf7_max_30d,
    )
    return evaluate_alerts(ctx)


def _dispatch_alert(
    decision: AlertDecision,
    uuid: str,
    conn: sqlite3.Connection,
    ts_capture: int,
    cfg: RunConfig,
) -> None:
    last_sent = fetch_alert_last_sent(conn, uuid, decision.condition.value)
    if not can_send(uuid, decision.condition, last_sent, ts_capture):
        logger.info(
            "nb_monitor: alert suppressed by cooldown: %s %s",
            uuid,
            decision.condition.value,
        )
        return
    ok = cfg.telegram_send(
        cfg.telegram_bot_token, cfg.telegram_chat_id, decision.message
    )
    if not ok:
        logger.warning("nb_monitor: Telegram send failed; alert NOT recorded")
        return
    insert_alert_record(
        conn,
        AlertRecord(
            uuid=uuid,
            condition=decision.condition.value,
            sent_at=ts_capture,
            payload=decision.payload,
        ),
    )


def _build_report_entries(
    rows: list[tuple[NotebookEntry, MetricRow, MetricRow | None]],
) -> list[ReportEntry]:
    tier_order = {"ALIVE": 0, "IDLE": 1, "DYING": 2}
    sorted_rows = sorted(
        rows,
        key=lambda t: (
            tier_order[t[1].tier],
            -(t[1].read_freq_7d or 0),
            -(t[1].read_freq_30d or 0),
        ),
    )
    out: list[ReportEntry] = []
    for rank, (entry, row, prev) in enumerate(sorted_rows, start=1):
        delta = (
            (row.read_freq_7d - prev.read_freq_7d)
            if (prev and row.read_freq_7d is not None and prev.read_freq_7d is not None)
            else None
        )
        out.append(
            ReportEntry(
                rank=rank,
                uuid=entry.uuid,
                name=entry.name,
                tier=Tier(row.tier),
                read_freq_7d=row.read_freq_7d,
                read_freq_30d=row.read_freq_30d,
                delta_7d_vs_lastweek=delta,
                age_days=_age_days(entry.first_audited, row.ts_capture),
                skill_derivation_count=row.skill_derivation_count,
                downstream_cite_rate=row.downstream_cite_rate,
                source_freshness_age_days=row.source_freshness_age_days,
                push_success_rate=row.push_success_rate,
                instrumentation_status=row.instrumentation_status,
            )
        )
    return out


def _write_report(cfg: RunConfig, entries: list[ReportEntry], ts_capture: int) -> None:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.fromtimestamp(ts_capture, tz=timezone.utc)
    iy, iw, _ = now.isocalendar()
    path = cfg.report_dir / f"report-{iy}-W{iw:02d}.md"
    baseline = (now - cfg.deploy_date).days < 14
    content = render_weekly_report(entries, generated_at=now, baseline_window=baseline)
    path.write_text(content)
    logger.info("nb_monitor: weekly report written to %s", path)


def _age_days(first_audited: str, ts_capture: int) -> int:
    try:
        d = datetime.fromisoformat(first_audited).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    now = datetime.fromtimestamp(ts_capture, tz=timezone.utc)
    return max(0, (now - d).days)


def _is_sunday(ts_capture: int) -> bool:
    return datetime.fromtimestamp(ts_capture, tz=timezone.utc).weekday() == 6


def _consecutive_dying_days(
    conn: sqlite3.Connection, uuid: str, ts_capture: int
) -> int:
    cursor = conn.execute(
        "SELECT tier FROM nb_metrics WHERE uuid=? ORDER BY ts_capture DESC LIMIT 30",
        (uuid,),
    )
    streak = 0
    for (tier,) in cursor.fetchall():
        if tier == "DYING":
            streak += 1
        else:
            break
    return streak


def _rf7_30d_window_max(
    conn: sqlite3.Connection, uuid: str, ts_capture: int
) -> int:
    cutoff = ts_capture - WINDOW_30D
    r = conn.execute(
        "SELECT MAX(read_freq_7d) FROM nb_metrics WHERE uuid=? AND ts_capture >= ?",
        (uuid, cutoff),
    ).fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def _was_in_top5_alive_lastweek(
    conn: sqlite3.Connection, uuid: str, ts_capture: int
) -> bool:
    target = ts_capture - 7 * 86400
    target_low = target - 86400
    target_high = target + 86400
    rows = conn.execute(
        """
        SELECT uuid FROM nb_metrics
         WHERE tier='ALIVE'
           AND ts_capture BETWEEN ? AND ?
         ORDER BY read_freq_7d DESC
         LIMIT 5
        """,
        (target_low, target_high),
    ).fetchall()
    top5 = {r[0] for r in rows}
    return uuid in top5


def _status(rf7: int | None, freshness: int | None, psr: float | None) -> str:
    """Compose instrumentation_status from collector outcomes."""
    if rf7 is None:
        return "parse_failure"
    parts: list[str] = []
    if freshness is None:
        parts.append("cookie_refresh_pending")
    parts.append("pending_qdrant_local_post_fase1")
    parts.append("pending_oracle_logging_post_fase4")
    return "ok" if not parts else ";".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
