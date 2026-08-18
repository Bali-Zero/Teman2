#!/usr/bin/env python3
"""Pure tests for intake_health_report.py — NO database (W87/W96).

Every test here works against canned dicts/lists or a FakeConn whose
fetchrow/fetch/execute dispatch on a SQL-text fingerprint — never against a
live connection, and never against `nuzantara_dev` (the local Intake/WhatsApp
queue). Covers: JSON-shape stability, the rate/count math in build_report(),
guilt+innocence for every threshold rule in evaluate_breaches(), the blob
presence sampler against tmp_path, the SQL-shape assertions the orchestrator
asked for (document_routing_proposal named, the corrected 7-status live set
embedded), and that --dry-run sends nothing through a fake tg_notify.

Run:  python3 scripts/tests/test_intake_health_report.py
      python3 -m pytest scripts/tests/test_intake_health_report.py -q
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import intake_health_report as ihr  # noqa: E402


# ---------------------------------------------------------------- build_report shape


def _base_kwargs(**overrides):
    kwargs = dict(
        status_counts={
            "review_pending_total": 100,
            "review_pending_wa": 40,
            "quarantine_total": 20,
            "duplicate_total": 5,
            "zero_candidate_count": 30,
        },
        all_pages_empty_rows=[
            {"status": "quarantine", "all_empty": 8, "denominator": 10},
            {"status": "review_pending", "all_empty": 2, "denominator": 20},
        ],
        blob_newest=["/tmp/a.jpg", "/tmp/missing.jpg"],
        blob_oldest=["/tmp/b.jpg"],
        companies_rows=5,
        orphan_rows=[{"source": "whatsapp", "n": 3}, {"source": "drive", "n": 1}],
        superseded_orphans=2,
        zombie_count=0,
        undelivered={"undelivered": 1, "total": 10},
        worker_log_exists=True,
        worker_plist_source="repo",
        dead_last_24h=4,
        wa_media_last_24h=7,
        generated_at="2026-08-15T00:00:00Z",
    )
    kwargs.update(overrides)
    return kwargs


def test_build_report_has_stable_top_level_keys():
    report = ihr.build_report(**_base_kwargs())
    assert set(report.keys()) == {
        "generated_at",
        "review_pending_wa",
        "review_pending_total",
        "quarantine_total",
        "duplicate_total",
        "zero_candidate_rate",
        "all_pages_empty",
        "blob_present",
        "companies_rows",
        "orphans_done_without_proposal",
        "superseded_orphans_true",
        "zombie_review_claimed_null_lease",
        "undelivered_committed",
        "worker_log_inode_exists",
        "worker_plist_source",
        "dead_last_24h",
        "wa_media_last_24h",
    }


def test_zero_candidate_rate_math():
    report = ihr.build_report(**_base_kwargs())
    zc = report["zero_candidate_rate"]
    assert zc == {"count": 30, "denominator": 100, "rate": 0.3}


def test_zero_candidate_rate_none_when_no_review_pending():
    kwargs = _base_kwargs()
    kwargs["status_counts"] = {
        "review_pending_total": 0,
        "review_pending_wa": 0,
        "quarantine_total": 0,
        "duplicate_total": 0,
        "zero_candidate_count": 0,
    }
    report = ihr.build_report(**kwargs)
    assert report["zero_candidate_rate"]["rate"] is None


def test_all_pages_empty_by_status_and_overall():
    report = ihr.build_report(**_base_kwargs())
    empty = report["all_pages_empty"]
    assert empty["by_status"]["quarantine"] == {"count": 8, "denominator": 10, "rate": 0.8}
    assert empty["by_status"]["review_pending"] == {"count": 2, "denominator": 20, "rate": 0.1}
    # overall = (8+2)/(10+20)
    assert empty["overall_rate"] == round(10 / 30, 4)


def test_all_pages_empty_defaults_present_even_with_no_rows():
    kwargs = _base_kwargs(all_pages_empty_rows=[])
    report = ihr.build_report(**kwargs)
    empty = report["all_pages_empty"]
    assert empty["by_status"]["quarantine"] == {"count": 0, "denominator": 0, "rate": None}
    assert empty["by_status"]["review_pending"] == {"count": 0, "denominator": 0, "rate": None}
    assert empty["overall_rate"] is None


def test_orphans_by_source_and_superseded_passthrough():
    report = ihr.build_report(**_base_kwargs())
    assert report["orphans_done_without_proposal"] == {"whatsapp": 3, "drive": 1}
    assert report["superseded_orphans_true"] == 2


def test_superseded_orphans_null_on_timeout_passthrough():
    report = ihr.build_report(**_base_kwargs(superseded_orphans=None))
    assert report["superseded_orphans_true"] is None


# ---------------------------------------------------------------- blob_presence


def test_blob_presence_counts_present_and_missing(tmp_path):
    present = tmp_path / "present.jpg"
    present.write_bytes(b"x")
    missing = tmp_path / "missing.jpg"
    result = ihr.blob_presence([str(present), str(missing)])
    assert result == {"sampled": 2, "present": 1, "rate": 0.5}


def test_blob_presence_empty_sample_rate_is_none():
    assert ihr.blob_presence([]) == {"sampled": 0, "present": 0, "rate": None}


# ---------------------------------------------------------------- evaluate_breaches (guilt + innocence)


_THRESHOLDS = {
    "companies_min_rows": 1.0,
    "blob_present_min": 0.5,
    "all_empty_max": 0.5,
    "zombie_max": 0.0,
}


def _report_with(**overrides):
    """A genuinely HEALTHY baseline report — every threshold rule innocent
    unless a test explicitly overrides the field it means to breach."""
    report = ihr.build_report(**_base_kwargs(
        companies_rows=5,
        zombie_count=0,
        worker_log_exists=True,
        blob_newest=[],
        blob_oldest=[],
        all_pages_empty_rows=[
            {"status": "quarantine", "all_empty": 1, "denominator": 10},
            {"status": "review_pending", "all_empty": 1, "denominator": 20},
        ],
    ))
    report.update(overrides)
    return report


def test_guilt_companies_rows_zero_breaches():
    report = _report_with(companies_rows=0)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert any(b["metric"] == "companies_rows" for b in breaches)


def test_innocence_companies_rows_positive_no_breach():
    report = _report_with(companies_rows=5)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "companies_rows" for b in breaches)


def test_guilt_blob_present_newest_below_threshold():
    report = _report_with(blob_present={"newest": {"sampled": 10, "present": 3, "rate": 0.3},
                                         "oldest": {"sampled": 5, "present": 5, "rate": 1.0}})
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert any(b["metric"] == "blob_present_newest" for b in breaches)


def test_innocence_blob_present_newest_at_or_above_threshold():
    report = _report_with(blob_present={"newest": {"sampled": 10, "present": 6, "rate": 0.6},
                                         "oldest": {"sampled": 5, "present": 5, "rate": 1.0}})
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "blob_present_newest" for b in breaches)


def test_innocence_blob_present_newest_zero_sample_is_inconclusive_not_a_breach():
    report = _report_with(blob_present={"newest": {"sampled": 0, "present": 0, "rate": None},
                                         "oldest": {"sampled": 0, "present": 0, "rate": None}})
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "blob_present_newest" for b in breaches)


def test_guilt_all_pages_empty_quarantine_above_threshold():
    report = _report_with(all_pages_empty={
        "by_status": {
            "quarantine": {"count": 9, "denominator": 10, "rate": 0.9},
            "review_pending": {"count": 0, "denominator": 10, "rate": 0.0},
        },
        "overall_rate": 0.45,
    })
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert any(b["metric"] == "all_pages_empty_quarantine" for b in breaches)


def test_innocence_all_pages_empty_quarantine_at_or_below_threshold():
    report = _report_with(all_pages_empty={
        "by_status": {
            "quarantine": {"count": 4, "denominator": 10, "rate": 0.4},
            "review_pending": {"count": 0, "denominator": 10, "rate": 0.0},
        },
        "overall_rate": 0.2,
    })
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "all_pages_empty_quarantine" for b in breaches)


def test_guilt_zombie_above_max():
    report = _report_with(zombie_review_claimed_null_lease=1)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert any(b["metric"] == "zombie_review_claimed" for b in breaches)


def test_innocence_zombie_at_max():
    report = _report_with(zombie_review_claimed_null_lease=0)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "zombie_review_claimed" for b in breaches)


def test_guilt_worker_log_missing():
    report = _report_with(worker_log_inode_exists=False)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert any(b["metric"] == "worker_log_missing" for b in breaches)


def test_innocence_worker_log_present():
    report = _report_with(worker_log_inode_exists=True)
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert not any(b["metric"] == "worker_log_missing" for b in breaches)


def test_no_breaches_when_everything_healthy():
    report = _report_with()
    breaches = ihr.evaluate_breaches(report, _THRESHOLDS)
    assert breaches == []


# ---------------------------------------------------------------- SQL shape (orphan query)


def test_superseded_orphan_sql_names_the_table_and_the_corrected_live_set():
    sql = ihr.SUPERSEDED_ORPHAN_SQL
    assert "document_routing_proposal" in sql
    expected_live_set = (
        "review_pending", "review_claimed", "routed", "rejected",
        "auto_routed", "quarantine", "duplicate",
    )
    assert expected_live_set == ihr._LIVE_PROPOSAL_STATUSES
    for status in expected_live_set:
        assert f"'{status}'" in sql, f"{status!r} missing from SUPERSEDED_ORPHAN_SQL"
    # 'dead' and 'superseded' are deliberately OUT of the live set (terminal-loss).
    assert "'dead'" not in sql
    assert "'superseded'" not in sql


def test_orphan_done_sql_left_joins_proposal_and_groups_by_source():
    sql = ihr.ORPHAN_DONE_SQL
    assert "document_routing_proposal" in sql
    assert "LEFT JOIN" in sql
    assert "q.source" in sql


# ---------------------------------------------------------------- --dry-run sends nothing (fake tg + fake conn)


class _FakeConn:
    """Dispatches fetchrow/fetch/execute on a SQL-text fingerprint — no DB."""

    async def fetchrow(self, query, *args):
        if "review_pending_total" in query:
            return {
                "review_pending_total": 10, "review_pending_wa": 4,
                "quarantine_total": 2, "duplicate_total": 1, "zero_candidate_count": 3,
            }
        if "FROM companies" in query:
            return {"n": 5}
        if "review_claimed' AND lease_expires_at IS NULL" in query:
            return {"n": 0}
        if "FROM documents" in query:
            return {"undelivered": 0, "total": 2}
        if "'dead'" in query and "intake_queue" in query:
            return {"n": 0}
        if "whatsapp_message_context" in query:
            return {"n": 1}
        if "NOT EXISTS" in query and "document_routing_proposal" in query:
            return {"n": 0}
        raise AssertionError(f"FakeConn.fetchrow: unrecognized query fingerprint: {query[:80]!r}")

    async def fetch(self, query, *args):
        if "jsonb_array_elements" in query:
            return []
        if "blob_path" in query:
            return []
        if "LEFT JOIN document_routing_proposal" in query:
            return [{"source": "whatsapp", "n": 0}]
        raise AssertionError(f"FakeConn.fetch: unrecognized query fingerprint: {query[:80]!r}")

    async def execute(self, query, *args):
        return "SET"

    async def close(self, *, timeout=None):
        return None


class _TrackingConn(_FakeConn):
    def __init__(self):
        self.closed = False
        self.close_timeout = None
        self.terminated = False

    async def close(self, *, timeout=None):
        self.close_timeout = timeout
        self.closed = True

    def terminate(self):
        self.terminated = True


class _CloseFailureConn(_FakeConn):
    def __init__(self):
        self.terminated = False

    async def close(self, *, timeout=None):
        raise RuntimeError("client-close-detail-should-never-reach-heartbeat")

    def terminate(self):
        self.terminated = True


class _CancellationResistantCloseConn(_FakeConn):
    def __init__(self):
        self.close_cancellations = 0
        self.close_returned = False
        self.close_timeout = None
        self.terminated = False
        self._terminated = asyncio.Event()

    async def close(self, *, timeout=None):
        self.close_timeout = timeout
        # Test-process failsafe only: a regression must FAIL after a measurable
        # 500ms instead of hanging the whole pytest worker forever.  Production
        # is required to call terminate near the configured 10ms deadline.
        safety_release = asyncio.get_running_loop().call_later(
            0.5,
            self._terminated.set,
        )
        try:
            while not self._terminated.is_set():
                try:
                    await self._terminated.wait()
                except asyncio.CancelledError:
                    # Intentionally suppress every cancellation.  The old
                    # asyncio.wait_for implementation waited here until the
                    # failsafe; the production helper must reach its
                    # synchronous terminate watchdog instead.
                    self.close_cancellations += 1
            self.close_returned = True
        finally:
            safety_release.cancel()

    def terminate(self):
        self.terminated = True
        self._terminated.set()


def _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats):
    async def _fake_connect(*_args, **_kwargs):
        return conn

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setattr(ihr, "_tg_notify", lambda *a, **k: True)
    monkeypatch.setattr(
        ihr,
        "_heartbeat",
        lambda status, note="": heartbeats.append((status, note)),
    )
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(
        ihr,
        "worker_log_path",
        lambda: (tmp_path / "does-not-exist.log", "repo"),
    )
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")
    monkeypatch.delenv("INTAKE_HEALTH_SUPERSEDED_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", raising=False)


# ---------------------------------------------------------------- connect timeouts (verbale #7)


def test_connect_sets_session_statement_timeout_and_connect_timeout(tmp_path, monkeypatch):
    # Records the actual args/kwargs asyncpg.connect() was called with — a
    # fake connection object at the connect boundary, not just a canned
    # return value, so a regression to the un-timed-out connect call is
    # caught even though every individual query still "succeeds" in the fake.
    recorded = {}

    async def _recording_connect(dsn, **kwargs):
        recorded["dsn"] = dsn
        recorded["kwargs"] = kwargs
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _recording_connect)
    monkeypatch.setattr(ihr, "_tg_notify", lambda *a, **k: True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 0
    assert recorded["kwargs"].get("timeout") is not None and recorded["kwargs"]["timeout"] <= 20
    assert recorded["kwargs"]["server_settings"]["statement_timeout"] == "120000"
    assert recorded["kwargs"]["server_settings"]["default_transaction_read_only"] == "on"


@pytest.mark.parametrize(
    ("env_name", "invalid_value"),
    (
        ("INTAKE_HEALTH_SUPERSEDED_TIMEOUT_MS", "client-name-not-an-integer"),
        ("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "client-name-not-a-float"),
        ("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "nan"),
        ("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "0"),
    ),
)
def test_invalid_timeout_configuration_is_reported_before_connect(
    tmp_path,
    monkeypatch,
    env_name,
    invalid_value,
):
    heartbeats = []
    connect_calls = []

    async def _unexpected_connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _unexpected_connect)
    monkeypatch.setattr(
        ihr,
        "_heartbeat",
        lambda status, note="": heartbeats.append((status, note)),
    )
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")
    monkeypatch.delenv("INTAKE_HEALTH_SUPERSEDED_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv(env_name, invalid_value)

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 1
    assert connect_calls == []
    assert heartbeats == [("error", "timeout configuration failed: ValueError")]
    assert "client-name" not in heartbeats[0][1]


def test_connect_failure_emits_type_only_error_heartbeat(tmp_path, monkeypatch):
    heartbeats = []

    async def _failing_connect(*_args, **_kwargs):
        raise RuntimeError("client-record-should-never-reach-heartbeat")

    monkeypatch.setattr(ihr.asyncpg, "connect", _failing_connect)
    monkeypatch.setattr(
        ihr,
        "_heartbeat",
        lambda status, note="": heartbeats.append((status, note)),
    )
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 1
    assert heartbeats == [("error", "db connect failed: RuntimeError")]
    assert "client-record" not in heartbeats[0][1]


def test_connection_close_failure_emits_type_only_error_heartbeat(tmp_path, monkeypatch):
    conn = _CloseFailureConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 1
    assert conn.terminated is True
    assert heartbeats == [("error", "connection close failed: RuntimeError")]
    assert "client-close-detail" not in heartbeats[0][1]


def test_connection_close_timeout_is_bounded_and_releases_lock(tmp_path, monkeypatch):
    conn = _CancellationResistantCloseConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)
    monkeypatch.setenv("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "0.01")

    started_at = time.monotonic()
    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))
    elapsed = time.monotonic() - started_at

    assert rc == 1
    assert elapsed < 0.25
    assert conn.close_cancellations >= 1
    assert conn.close_returned is True
    assert conn.close_timeout == pytest.approx(0.01)
    assert conn.terminated is True
    assert heartbeats == [("error", "connection close failed: TimeoutError")]

    # The timeout path must reach run()'s outer finally and release its flock;
    # otherwise the next scheduled tick would remain lock-held forever.
    next_lock_fd = ihr._acquire_lock_or_exit()
    try:
        assert next_lock_fd is not None
    finally:
        if next_lock_fd is not None:
            fcntl.flock(next_lock_fd, fcntl.LOCK_UN)
            os.close(next_lock_fd)


@pytest.mark.parametrize("primary_phase", ("gather", "report", "persist"))
def test_primary_failure_is_preserved_when_connection_close_also_fails(
    tmp_path,
    monkeypatch,
    primary_phase,
):
    conn = _CloseFailureConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)

    if primary_phase == "gather":
        async def _fail_gather(*_args, **_kwargs):
            raise LookupError("primary-detail-must-stay-private")

        monkeypatch.setattr(ihr, "gather", _fail_gather)
    elif primary_phase == "report":
        def _fail_report():
            raise LookupError("primary-detail-must-stay-private")

        monkeypatch.setattr(ihr, "_thresholds_from_env", _fail_report)
    else:
        def _fail_persist(_report):
            raise LookupError("primary-detail-must-stay-private")

        monkeypatch.setattr(ihr, "_write_state", _fail_persist)

    rc = asyncio.run(
        ihr.run(
            dry_run=primary_phase != "persist",
            json_only=primary_phase != "persist",
        )
    )

    assert rc == 1
    assert conn.terminated is True
    assert heartbeats == [("error", f"{primary_phase} failed: LookupError")]
    assert "connection close failed" not in heartbeats[0][1]


def test_primary_failure_is_preserved_when_connection_close_times_out(
    tmp_path,
    monkeypatch,
):
    conn = _CancellationResistantCloseConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)
    monkeypatch.setenv("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "0.01")

    async def _fail_gather(*_args, **_kwargs):
        raise LookupError("primary-detail-must-stay-private")

    monkeypatch.setattr(ihr, "gather", _fail_gather)

    started_at = time.monotonic()
    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))
    elapsed = time.monotonic() - started_at

    assert rc == 1
    assert elapsed < 0.25
    assert conn.close_cancellations >= 1
    assert conn.close_returned is True
    assert conn.terminated is True
    assert heartbeats == [("error", "gather failed: LookupError")]
    assert "connection close failed" not in heartbeats[0][1]


def test_cooperative_connection_close_uses_driver_timeout_without_terminate(
    tmp_path,
    monkeypatch,
):
    conn = _TrackingConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)
    monkeypatch.setenv("INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS", "0.05")

    started_at = time.monotonic()
    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))
    elapsed = time.monotonic() - started_at

    assert rc == 0
    assert elapsed < 0.25
    assert conn.closed is True
    assert conn.close_timeout == pytest.approx(0.05)
    assert conn.terminated is False
    assert heartbeats == []


def test_gather_failure_emits_error_heartbeat_and_closes_connection(tmp_path, monkeypatch):
    conn = _TrackingConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)

    async def _failing_gather(*_args, **_kwargs):
        raise LookupError("passport-value-should-never-reach-heartbeat")

    monkeypatch.setattr(ihr, "gather", _failing_gather)

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 1
    assert conn.closed is True
    assert heartbeats == [("error", "gather failed: LookupError")]
    assert "passport-value" not in heartbeats[0][1]


def test_report_failure_emits_error_heartbeat_and_closes_connection(tmp_path, monkeypatch):
    conn = _TrackingConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)

    def _failing_thresholds():
        raise ValueError("company-name-should-never-reach-heartbeat")

    monkeypatch.setattr(ihr, "_thresholds_from_env", _failing_thresholds)

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 1
    assert conn.closed is True
    assert heartbeats == [("error", "report failed: ValueError")]
    assert "company-name" not in heartbeats[0][1]


def test_persist_failure_emits_error_heartbeat_and_closes_connection(tmp_path, monkeypatch):
    conn = _TrackingConn()
    heartbeats = []
    _install_run_fakes(monkeypatch, tmp_path, conn, heartbeats)

    def _failing_replace(*_args, **_kwargs):
        raise PermissionError("client-path-should-never-reach-heartbeat")

    monkeypatch.setattr(ihr.os, "replace", _failing_replace)

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 1
    assert conn.closed is True
    assert heartbeats == [("error", "persist failed: PermissionError")]
    assert "client-path" not in heartbeats[0][1]


def test_wrapper_missing_or_non_executable_python_emits_error_heartbeat(tmp_path):
    for python_state in ("missing", "not-executable"):
        fake_repo = tmp_path / python_state / "repo"
        fake_scripts = fake_repo / "scripts"
        fake_lib = fake_scripts / "lib"
        fake_lib.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "scripts" / "intake_health_report_run.sh", fake_scripts)
        shutil.copy2(REPO_ROOT / "scripts" / "lib" / "heartbeat.sh", fake_lib)

        if python_state == "not-executable":
            fake_python = fake_repo / "apps" / "backend-rag" / ".venv" / "bin" / "python"
            fake_python.parent.mkdir(parents=True)
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o644)

        heartbeat_dir = tmp_path / python_state / "heartbeats"
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(tmp_path / python_state / "home"),
                "INTAKE_HEALTH_REPORT_ENABLED": "true",
                "ORGANISM_LAST_SEEN_DIR": str(heartbeat_dir),
            }
        )

        result = subprocess.run(
            ["/bin/bash", str(fake_scripts / "intake_health_report_run.sh")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        heartbeat = json.loads(
            (heartbeat_dir / "pro.intake_health_report.json").read_text(encoding="utf-8")
        )
        assert heartbeat["status"] == "error"
        assert heartbeat["note"] == "venv python unavailable"


# ---------------------------------------------------------------- worker plist resolution (verbale #8)


def test_resolve_worker_plist_path_prefers_installed_over_repo(tmp_path, monkeypatch):
    installed = tmp_path / "installed.plist"
    installed.write_text("<plist></plist>")
    monkeypatch.setattr(ihr, "INSTALLED_WORKER_PLIST_PATH", installed)

    path, source = ihr.resolve_worker_plist_path()

    assert path == installed
    assert source == "installed"


def test_resolve_worker_plist_path_falls_back_to_repo_when_installed_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ihr, "INSTALLED_WORKER_PLIST_PATH", tmp_path / "does-not-exist.plist")

    path, source = ihr.resolve_worker_plist_path()

    assert path == ihr.REPO_WORKER_PLIST_PATH
    assert source == "repo"


def test_worker_log_path_reads_installed_plist_when_present(tmp_path, monkeypatch):
    import plistlib

    installed = tmp_path / "installed.plist"
    installed.write_bytes(plistlib.dumps({"StandardErrorPath": str(tmp_path / "worker.err.log")}))
    monkeypatch.setattr(ihr, "INSTALLED_WORKER_PLIST_PATH", installed)

    log_path, source = ihr.worker_log_path()

    assert log_path == tmp_path / "worker.err.log"
    assert source == "installed"


def test_report_records_worker_plist_source(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ihr, "_tg_notify", lambda *a, **k: True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "installed"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=True, json_only=True))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"worker_plist_source": "installed"' in out


def test_dry_run_sends_no_telegram_and_writes_no_state(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: sent.append((tier, key)) or True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=True, json_only=False))

    assert rc == 0
    assert sent == []
    assert not (tmp_path / "state.json").exists()


def test_non_dry_run_writes_state_and_sends_digest(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: sent.append((tier, key)) or True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 0
    assert (tmp_path / "state.json").exists()
    # digest always sent + at least the worker_log_missing breach (file doesn't exist)
    tiers = {t for t, _k in sent}
    assert "digest" in tiers
    assert ("p0", "intake-health:worker_log_missing") in sent


def test_json_only_skips_all_side_effects(tmp_path, monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: sent.append((tier, key)) or True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: sent.append(("heartbeat", a)))
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=False, json_only=True))

    assert rc == 0
    assert sent == []
    assert not (tmp_path / "state.json").exists()
    out = capsys.readouterr().out
    assert '"review_pending_total"' in out


def test_json_only_help_distinguishes_success_from_failure_side_effects(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(sys, "argv", ["intake_health_report.py", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        ihr.main()

    assert exc_info.value.code == 0
    normalized_help = " ".join(capsys.readouterr().out.split())
    assert "no success side effects" in normalized_help
    assert "failures still emit heartbeat=error" in normalized_help
    assert "no success side effects" in (ihr.__doc__ or "")


def test_digest_dedup_key_is_date_stamped_not_a_bare_constant(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: sent.append((tier, key)) or True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 0
    digest_keys = [k for t, k in sent if t == "digest"]
    assert len(digest_keys) == 1
    assert digest_keys[0].startswith("intake-health:daily:")
    assert digest_keys[0] != "intake-health:daily"


def test_heartbeat_is_ok_even_with_breaches_organ_not_finding(tmp_path, monkeypatch):
    hb = []
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: True)
    monkeypatch.setattr(ihr, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setattr(ihr, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(ihr, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(ihr, "worker_log_path", lambda: (tmp_path / "does-not-exist.log", "repo"))

    async def _fake_connect(*_args, **_kwargs):
        return _FakeConn()

    monkeypatch.setattr(ihr.asyncpg, "connect", _fake_connect)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 0
    # worker_log_missing breach fires (file doesn't exist) — heartbeat must
    # still read "ok", never "degraded" (verbale #2's twin, this organ).
    assert hb
    status, note = hb[-1]
    assert status == "ok"
    assert "breaches=" in note


def test_lock_held_preserves_nonhealthy_sidecar_and_consumer_verdict(
    tmp_path,
    monkeypatch,
):
    sidecar_dir = tmp_path / "last_seen"
    sidecar_dir.mkdir()
    sidecar_path = sidecar_dir / "pro.intake_health_report.json"
    previous_payload = {
        "ts": "2026-08-19T00:00:00Z",
        "status": "error",
        "note": "previous run failed: RuntimeError",
    }
    previous_bytes = (json.dumps(previous_payload) + "\n").encode("utf-8")
    sidecar_path.write_bytes(previous_bytes)

    heartbeat_calls = []
    sent = []
    real_heartbeat = ihr._heartbeat

    def _recording_heartbeat(status, note=""):
        heartbeat_calls.append((status, note))
        real_heartbeat(status, note)

    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(sidecar_dir))
    monkeypatch.setattr(ihr, "_heartbeat", _recording_heartbeat)
    monkeypatch.setattr(ihr, "_tg_notify", lambda tier, key, text: sent.append((tier, key, text)) or True)
    monkeypatch.setattr(ihr, "_acquire_lock_or_exit", lambda: None)
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "true")

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 0
    assert heartbeat_calls == []
    assert sidecar_path.read_bytes() == previous_bytes
    assert json.loads(sidecar_path.read_text(encoding="utf-8")) == previous_payload
    assert len(sent) == 1
    tier, key, _text = sent[0]
    assert tier == "digest"
    assert key.startswith("intake-health:lock-held:")

    # Consumer contract: a skipped contender cannot launder the lock owner's
    # last real error into HEALTHY_STATUSES.  Exercise the actual healer reader
    # against a minimal registry rather than restating its status vocabulary.
    import healer_receptor_registry as hrr

    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        json.dumps(
            {
                "organs": [
                    {
                        "id": "pro.intake_health_report",
                        "runtime": "pro_launchd",
                        "type": "cron",
                        "expected_hb_seconds": 90_000,
                        "severity_on_silence": "warning",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    consumer_report = hrr.run("pro", registry_path, sidecar_dir)

    assert consumer_report["exit"] == 1
    assert [entry["id"] for entry in consumer_report["dead"]] == [
        "pro.intake_health_report"
    ]
    assert consumer_report["ok"] == []


def test_acquire_lock_hardens_a_pre_existing_loose_lock_file(tmp_path, monkeypatch):
    lock = tmp_path / "state" / "intake_health_report.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    lock.chmod(0o644)  # simulate a pre-hardening-era lock file already on disk
    monkeypatch.setattr(ihr, "LOCK_FILE", lock)

    fd = ihr._acquire_lock_or_exit()
    try:
        assert fd is not None
        assert (lock.stat().st_mode & 0o777) == 0o600
    finally:
        if fd is not None:
            os.close(fd)


def test_kill_switch_disabled_short_circuits(monkeypatch, capsys):
    monkeypatch.setenv("INTAKE_HEALTH_REPORT_ENABLED", "false")
    called = []
    monkeypatch.setattr(ihr, "_heartbeat", lambda status, note="": called.append(status))

    rc = asyncio.run(ihr.run(dry_run=False, json_only=False))

    assert rc == 0
    assert called == ["disabled"]
    assert '"status": "disabled"' in capsys.readouterr().out


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
