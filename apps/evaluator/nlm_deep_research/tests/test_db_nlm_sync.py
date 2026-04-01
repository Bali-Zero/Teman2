"""Tests for DB→NLM Sync pipeline.

Covers: state persistence, templates, diff logic, PID lock.
Does NOT require a live DB or NLM — all mocked.

Run: PYTHONPATH=. pytest apps/evaluator/nlm_deep_research/tests/test_db_nlm_sync.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.evaluator.nlm_deep_research.db_nlm_state import (
    DBNLMLockError,
    DBNLMPIDLock,
    DBNLMStatePersistence,
    DBNLMSyncState,
    SourceHash,
)
from apps.evaluator.nlm_deep_research.db_nlm_templates import (
    render_client_segments,
    render_company_overview,
    render_compliance_radar,
    render_portfolio_snapshot,
    render_practices_pipeline,
    render_recent_changes,
    render_revenue_dashboard,
    render_system_health,
    render_tax_compliance,
    render_team_activity,
)


# ---------------------------------------------------------------------------
# State Tests
# ---------------------------------------------------------------------------


class TestDBNLMSyncState:
    def test_is_source_changed_new(self) -> None:
        state = DBNLMSyncState()
        assert state.is_source_changed("test", "content") is True

    def test_is_source_changed_same(self) -> None:
        state = DBNLMSyncState()
        content = "hello world"
        sha = hashlib.sha256(content.encode()).hexdigest()
        state.source_hashes["test"] = SourceHash(name="test", sha256=sha)
        assert state.is_source_changed("test", content) is False

    def test_is_source_changed_different(self) -> None:
        state = DBNLMSyncState()
        state.source_hashes["test"] = SourceHash(name="test", sha256="old_hash")
        assert state.is_source_changed("test", "new content") is True

    def test_record_upload(self) -> None:
        state = DBNLMSyncState()
        state.record_upload("src1", "content1", "nlm-id-1")
        assert state.source_hashes["src1"].nlm_source_id == "nlm-id-1"
        assert state.total_uploads == 1
        expected_hash = hashlib.sha256(b"content1").hexdigest()
        assert state.source_hashes["src1"].sha256 == expected_hash

    def test_record_skip(self) -> None:
        state = DBNLMSyncState()
        state.record_skip()
        state.record_skip()
        assert state.total_skipped == 2

    def test_circuit_breaker_db(self) -> None:
        state = DBNLMSyncState()
        assert state.cb_db_status == "CLOSED"
        state.record_db_failure()
        state.record_db_failure()
        assert state.cb_db_status == "CLOSED"
        state.record_db_failure()
        assert state.cb_db_status == "OPEN"
        state.reset_db_cb()
        assert state.cb_db_status == "CLOSED"
        assert state.cb_db_failure_count == 0

    def test_circuit_breaker_nlm(self) -> None:
        state = DBNLMSyncState()
        for _ in range(3):
            state.record_nlm_failure()
        assert state.cb_nlm_status == "OPEN"
        state.reset_nlm_cb()
        assert state.cb_nlm_status == "CLOSED"

    def test_increment_run_same_day(self) -> None:
        state = DBNLMSyncState()
        state.increment_run()
        assert state.runs_today == 1
        state.increment_run()
        assert state.runs_today == 2

    def test_increment_run_new_day(self) -> None:
        state = DBNLMSyncState()
        state.run_date = "2025-01-01"
        state.runs_today = 5
        state.increment_run()  # New day → reset
        assert state.runs_today == 1


class TestDBNLMStatePersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        persistence = DBNLMStatePersistence(path=state_file)

        state = DBNLMSyncState(
            nb_ops_id="ops-123",
            nb_intel_id="intel-456",
        )
        state.record_upload("src1", "content", "nlm-src-1")
        state.increment_run()

        persistence.save(state)
        assert state_file.exists()

        loaded = persistence.load()
        assert loaded.nb_ops_id == "ops-123"
        assert loaded.nb_intel_id == "intel-456"
        assert "src1" in loaded.source_hashes
        assert loaded.source_hashes["src1"].nlm_source_id == "nlm-src-1"
        assert loaded.runs_today == 1
        assert loaded.total_uploads == 1

    def test_load_missing_file(self, tmp_path: Path) -> None:
        persistence = DBNLMStatePersistence(path=tmp_path / "nonexistent.json")
        state = persistence.load()
        assert state.last_run_status == "never"

    def test_load_corrupt_file(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        persistence = DBNLMStatePersistence(path=bad_file)
        state = persistence.load()
        assert state.last_run_status == "never"


class TestDBNLMPIDLock:
    def test_acquire_and_release(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        lock = DBNLMPIDLock(lock_path=lock_path)
        lock.acquire()
        assert lock_path.exists()
        assert lock_path.read_text().strip() == str(os.getpid())
        lock.release()
        assert not lock_path.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        with DBNLMPIDLock(lock_path=lock_path):
            assert lock_path.exists()
        assert not lock_path.exists()

    def test_stale_lock_cleanup(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        lock_path.write_text("99999999")  # Non-existent PID
        lock = DBNLMPIDLock(lock_path=lock_path)
        lock.acquire()  # Should clean up stale lock
        assert lock_path.read_text().strip() == str(os.getpid())
        lock.release()

    def test_active_lock_raises(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        lock_path.write_text(str(os.getpid()))  # Our own PID — alive
        lock = DBNLMPIDLock(lock_path=lock_path)
        with pytest.raises(DBNLMLockError, match="already running"):
            lock.acquire()


# ---------------------------------------------------------------------------
# Template Tests
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_portfolio_snapshot(self) -> None:
        md = render_portfolio_snapshot(
            stats={"active": 847, "total": 1023, "new_7d": 12, "new_30d": 45, "prospect": 87},
            segments=[
                {"category": "Visa", "clients": 289, "pipeline_value": 450000000},
                {"category": "Company Setup", "clients": 312, "pipeline_value": 800000000},
            ],
            nationalities=[
                {"nationality": "Australian", "count": 120},
                {"nationality": "Russian", "count": 95},
            ],
            today="2026-04-01",
        )
        assert "847" in md
        assert "Client Portfolio Snapshot" in md
        assert "Visa" in md
        assert "Australian" in md
        assert "2026-04-01" in md

    def test_practices_pipeline(self) -> None:
        md = render_practices_pipeline(
            by_status=[
                {"status": "on_process", "count": 120},
                {"status": "inquiry", "count": 80},
            ],
            bottlenecks=[
                {"practice_type": "KITAS", "status": "waiting_documents", "avg_days_in_status": 15, "count": 8},
            ],
            avg_duration=[
                {"practice_type": "PT PMA Setup", "avg_days": 45, "completed": 12},
            ],
            today="2026-04-01",
        )
        assert "200 total" in md
        assert "KITAS" in md
        assert "15 days" in md

    def test_compliance_radar(self) -> None:
        md = render_compliance_radar(
            expiring_30=[{"client_id": 1, "practice_type": "KITAS", "expiry_date": "2026-04-20", "days_remaining": 19}],
            expiring_60=[],
            expiring_90=[],
            missing_docs=[{"client_id": 2, "practice_type": "PT PMA", "missing_count": 3}],
            today="2026-04-01",
        )
        assert "1 practices" in md
        assert "Client #1" in md
        assert "missing **3**" in md

    def test_revenue_dashboard(self) -> None:
        md = render_revenue_dashboard(
            monthly_revenue=[{"month": "2026-03", "revenue": 150000000, "practices_completed": 15}],
            unpaid_aging=[{"bucket": "0-30 days", "count": 5, "total_outstanding": 25000000}],
            top_services=[{"practice_type": "KITAS", "total_revenue": 80000000, "count": 20, "avg_price": 4000000}],
            today="2026-04-01",
        )
        assert "Revenue Dashboard" in md
        assert "IDR 150.000.000" in md
        assert "KITAS" in md

    def test_system_health(self) -> None:
        md = render_system_health(
            db_stats={"active_connections": 5, "db_size": "2.3 GB", "longest_query_seconds": 0.5},
            qdrant_stats={"total_collections": 10, "total_vectors": 93283},
            today="2026-04-01",
        )
        assert "System Health" in md
        assert "2.3 GB" in md

    def test_empty_data_doesnt_crash(self) -> None:
        """All templates must handle empty data gracefully."""
        today = "2026-04-01"
        render_portfolio_snapshot({}, [], [], today)
        render_practices_pipeline([], [], [], today)
        render_compliance_radar([], [], [], [], today)
        render_team_activity([], [], [], today)
        render_recent_changes([], [], [], today)
        render_revenue_dashboard([], [], [], today)
        render_client_segments([], [], [], today)
        render_company_overview([], [], [], today)
        render_tax_compliance([], [], today)
        render_system_health({}, {}, today)

    def test_no_pii_in_output(self) -> None:
        """Templates should reference client IDs, not PII."""
        md = render_compliance_radar(
            expiring_30=[{
                "client_id": 42,
                "practice_type": "KITAS",
                "expiry_date": "2026-04-15",
                "days_remaining": 14,
            }],
            expiring_60=[],
            expiring_90=[],
            missing_docs=[],
            today="2026-04-01",
        )
        assert "Client #42" in md
        # Should NOT contain email, phone, etc.
        assert "@" not in md
        assert "+62" not in md
