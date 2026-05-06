"""End-to-end integration test for nb_monitor.

Runs execute_once with all I/O substituted: registry from tmpdir, collectors
faked via RunConfig injection, Telegram dispatch counted via a stub. Asserts
that metrics.db has the right shape and that alerts logic runs.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.run import RunConfig, execute_once


def _cfg(tmp_path, fake_bootstrap, **over):
    sent: list[tuple[str, str, str]] = []

    def stub_send(token, chat, text):
        sent.append((token, chat, text))
        return True

    cfg = RunConfig(
        bootstrap_path=fake_bootstrap,
        db_path=tmp_path / "metrics.db",
        feeder_log_path=tmp_path / "missing_feeder.log",
        report_dir=tmp_path / "report",
        deploy_date=datetime(2026, 5, 7, tzinfo=timezone.utc),
        telegram_bot_token="fake",
        telegram_chat_id="0",
        telegram_send=stub_send,
    )
    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 100, "uuid-B": 3, "uuid-C": 0}.get(
        u, 0
    )
    cfg.collect_read_freq_30d = lambda u: {"uuid-A": 400, "uuid-B": 12, "uuid-C": 0}.get(
        u, 0
    )
    cfg.collect_freshness = lambda u: 5
    cfg.collect_push_success = lambda: 0.99
    cfg.__dict__.update(over)
    return cfg, sent


def _now(date_str: str) -> int:
    return int(
        datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).timestamp()
    )


def test_first_run_persists_three_rows(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    rc = execute_once(cfg, now=_now("2026-05-15"))
    assert rc == 0

    conn = sqlite3.connect(cfg.db_path)
    rows = conn.execute(
        "SELECT uuid, tier, read_freq_7d, instrumentation_status "
        "FROM nb_metrics ORDER BY uuid"
    ).fetchall()
    conn.close()
    assert {r[0] for r in rows} == {"uuid-A", "uuid-B", "uuid-C"}
    by_uuid = {r[0]: r for r in rows}
    assert by_uuid["uuid-A"][1] == "ALIVE"
    assert by_uuid["uuid-B"][1] == "IDLE"
    assert by_uuid["uuid-C"][1] == "IDLE"


def test_first_run_does_not_alert_without_history(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    assert sent == []


def test_second_run_after_drop_emits_top5_drop_alert(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    sent.clear()

    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 5, "uuid-B": 3, "uuid-C": 0}.get(
        u, 0
    )
    execute_once(cfg, now=_now("2026-05-22"))

    msgs = [m[2] for m in sent]
    assert any("NB-A" in m and "drop" in m.lower() for m in msgs)


def test_alert_cooldown_suppresses_duplicate_within_window(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    sent.clear()
    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 5, "uuid-B": 3, "uuid-C": 0}.get(
        u, 0
    )
    execute_once(cfg, now=_now("2026-05-22"))
    n_first = len(sent)
    execute_once(cfg, now=_now("2026-05-22"))
    assert len(sent) == n_first


def test_report_written_on_sunday(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-17"))  # Sunday
    report_files = list((tmp_path / "report").glob("report-*.md"))
    assert len(report_files) == 1
    content = report_files[0].read_text()
    assert "NB-A" in content


def test_report_force_flag_writes_on_any_weekday(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"), force_report=True)  # Friday
    report_files = list((tmp_path / "report").glob("report-*.md"))
    assert len(report_files) == 1


def test_active_routing_false_gets_null_psr(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    conn = sqlite3.connect(cfg.db_path)
    psr_C = conn.execute(
        "SELECT push_success_rate FROM nb_metrics WHERE uuid='uuid-C'"
    ).fetchone()[0]
    conn.close()
    assert psr_C is None


def test_run_exits_zero_on_missing_registry(tmp_path):
    cfg = RunConfig(
        bootstrap_path=tmp_path / "absent.json",
        db_path=tmp_path / "m.db",
        feeder_log_path=tmp_path / "missing.log",
        report_dir=tmp_path / "report",
    )
    assert execute_once(cfg, now=_now("2026-05-15")) == 0
