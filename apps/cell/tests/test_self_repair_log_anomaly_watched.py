"""Self-repair blind-spot #2 — log_anomaly must watch ~/logs/cron-agent/.

Audit 2026-04-19 found log_anomaly had no notion of filesystem paths to scan:
the detector exposed `detect_anomaly(lines)` only, so cron-agent logs under
`~/logs/cron-agent*/*.log` were never read by any consumer. This test pins the
new `WATCHED_LOG_PATHS` constant + `scan_watched_paths()` glob expansion.
"""
from __future__ import annotations

from pathlib import Path

from cell.fast import log_anomaly


def test_watched_log_paths_contains_cron_agent_glob() -> None:
    """The constant must ship with the cron-agent glob so consumers inherit it."""
    paths = log_anomaly.WATCHED_LOG_PATHS
    assert any(
        "cron-agent" in str(p) and str(p).endswith("*.log")
        for p in paths
    ), f"cron-agent/*.log glob missing from WATCHED_LOG_PATHS: {paths}"
    # pathlib.Path.expanduser() — never hardcoded /Users/
    for p in paths:
        assert isinstance(p, Path)
        assert "~" not in str(p), f"{p!r} must already be expanded"


def test_scan_watched_paths_flags_cron_agent_errors(
    tmp_path: Path, monkeypatch
) -> None:
    """When a cron-agent log has ERROR lines, scan must return an anomaly."""
    cron_agent_dir = tmp_path / "logs" / "cron-agent-foo"
    cron_agent_dir.mkdir(parents=True)
    bad_log = cron_agent_dir / "job.log"
    bad_log.write_text(
        "[2026-04-20 03:00:01] INFO: starting\n"
        "[2026-04-20 03:00:02] ERROR: kb-ingest exit code 2\n"
        "[2026-04-20 03:00:03] FATAL: aborting run\n"
    )

    # Point the constant at our fixture (monkeypatch the module attribute).
    monkeypatch.setattr(
        log_anomaly,
        "WATCHED_LOG_PATHS",
        [cron_agent_dir / "*.log"],
    )

    report = log_anomaly.scan_watched_paths()
    assert report.anomaly is True
    assert any(
        "FATAL" in kw or "SIGKILL" in kw for kw in report.critical_keywords
    ) or "error" in report.reason.lower()
    # Every offending path should be surfaced so system_doctor can cite it.
    assert any(str(bad_log) == str(p) for p in report.sources), report.sources


def test_scan_watched_paths_missing_dir_is_low_severity(
    tmp_path: Path, monkeypatch
) -> None:
    """Missing cron-agent dir must not crash — backward-compat (severity LOW)."""
    missing = tmp_path / "logs" / "does-not-exist" / "*.log"
    monkeypatch.setattr(log_anomaly, "WATCHED_LOG_PATHS", [missing])

    report = log_anomaly.scan_watched_paths()
    assert report.anomaly is False
    assert report.severity == "low"
    assert "missing" in report.reason.lower() or "no files" in report.reason.lower()


def test_scan_watched_paths_clean_logs_no_anomaly(
    tmp_path: Path, monkeypatch
) -> None:
    """Clean logs must return anomaly=False, severity='ok'."""
    cron_agent_dir = tmp_path / "logs" / "cron-agent-clean"
    cron_agent_dir.mkdir(parents=True)
    (cron_agent_dir / "ok.log").write_text(
        "[2026-04-20 03:00:01] INFO: started\n"
        "[2026-04-20 03:00:02] INFO: completed ok\n"
    )
    monkeypatch.setattr(
        log_anomaly, "WATCHED_LOG_PATHS", [cron_agent_dir / "*.log"]
    )

    report = log_anomaly.scan_watched_paths()
    assert report.anomaly is False
    assert report.severity == "ok"
