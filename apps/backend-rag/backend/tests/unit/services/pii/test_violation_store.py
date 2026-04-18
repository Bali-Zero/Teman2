"""
Unit tests for backend.services.pii.violation_store.

Coverage:
- severity_for() pattern → severity mapping
- hash_subject() deterministic + handles None/empty
- aggregate() folds duplicate patterns into occurrence_count
- record_violations() is safe with no loop, no app, empty list
- _write() swallows DB errors (never re-raises)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.pii import violation_store
from backend.services.pii.violation_store import (
    PIIViolation,
    aggregate,
    hash_subject,
    record_violations,
    severity_for,
    set_app,
)


class TestSeverityMapping:
    def test_high_for_gov_ids(self):
        assert severity_for("ID_KTP") == "high"
        assert severity_for("ID_NPWP") == "high"
        assert severity_for("ID_PASSPORT") == "high"

    def test_medium_for_contact(self):
        assert severity_for("PHONE_ID") == "medium"
        assert severity_for("EMAIL_ADDRESS") == "medium"

    def test_low_for_person(self):
        assert severity_for("PERSON") == "low"

    def test_unknown_defaults_low(self):
        assert severity_for("SOMETHING_NEW") == "low"


class TestHashSubject:
    def test_none(self):
        assert hash_subject(None) is None

    def test_empty(self):
        assert hash_subject("") is None

    def test_deterministic(self):
        assert hash_subject("user@x.com") == hash_subject("user@x.com")

    def test_distinct_for_different_inputs(self):
        assert hash_subject("a@x.com") != hash_subject("b@x.com")

    def test_length_is_stable(self):
        # We truncate to 32 hex chars for index efficiency
        assert len(hash_subject("anything")) == 32


class TestAggregate:
    def test_empty_input_returns_empty(self):
        assert aggregate([], request_id="r1", route="/x", user_hash=None) == []

    def test_distinct_patterns_become_separate_rows(self):
        vs = aggregate(
            ["ID_KTP", "EMAIL_ADDRESS"],
            request_id="r1",
            route="/api/agentic/ask",
            user_hash="h",
        )
        assert len(vs) == 2
        patterns = {v.pattern_matched for v in vs}
        assert patterns == {"ID_KTP", "EMAIL_ADDRESS"}
        # Severity is pattern-driven
        by_pattern = {v.pattern_matched: v.severity for v in vs}
        assert by_pattern["ID_KTP"] == "high"
        assert by_pattern["EMAIL_ADDRESS"] == "medium"

    def test_duplicate_patterns_fold_into_occurrence_count(self):
        vs = aggregate(
            ["ID_KTP", "ID_KTP", "ID_KTP", "EMAIL_ADDRESS"],
            request_id="r1",
            route="/api/agentic/ask",
            user_hash=None,
        )
        assert len(vs) == 2
        by_pattern = {v.pattern_matched: v.occurrence_count for v in vs}
        assert by_pattern["ID_KTP"] == 3
        assert by_pattern["EMAIL_ADDRESS"] == 1

    def test_result_is_sorted_for_deterministic_inserts(self):
        vs = aggregate(
            ["PHONE_ID", "ID_KTP", "EMAIL_ADDRESS"],
            request_id=None, route="/x", user_hash=None,
        )
        assert [v.pattern_matched for v in vs] == sorted({"PHONE_ID", "ID_KTP", "EMAIL_ADDRESS"})


class TestRecordViolations:
    def test_empty_list_is_no_op(self):
        # Must not raise, must not error even with no loop
        record_violations([])

    def test_outside_event_loop_is_noop(self):
        # Called synchronously → no running loop → silently skip
        record_violations([
            PIIViolation("r1", "/x", "ID_KTP", "high", None, 1),
        ])

    @pytest.mark.asyncio
    async def test_no_app_registered_is_noop(self):
        # Reset module state
        violation_store._app = None
        # Must not raise
        record_violations([
            PIIViolation("r1", "/x", "ID_KTP", "high", None, 1),
        ])
        # Yield so any spawned task (if any) runs
        await asyncio.sleep(0)

    @pytest.mark.asyncio
    async def test_writes_via_pool_when_app_has_pool(self):
        conn = MagicMock()
        conn.executemany = AsyncMock()

        class _PoolCtx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_PoolCtx())

        app = MagicMock()
        app.state.db_pool = pool
        set_app(app)
        try:
            record_violations([
                PIIViolation("r1", "/x", "ID_KTP", "high", None, 1),
                PIIViolation("r1", "/x", "EMAIL_ADDRESS", "medium", None, 1),
            ])
            # Let the spawned task run
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            # executemany was called exactly once with 2 rows
            conn.executemany.assert_awaited_once()
            args, _ = conn.executemany.call_args
            assert len(args[1]) == 2
        finally:
            violation_store._app = None

    @pytest.mark.asyncio
    async def test_db_failure_is_swallowed(self):
        conn = MagicMock()
        conn.executemany = AsyncMock(side_effect=RuntimeError("db offline"))

        class _PoolCtx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_PoolCtx())
        app = MagicMock()
        app.state.db_pool = pool
        set_app(app)
        try:
            record_violations([PIIViolation(None, "/x", "ID_KTP", "high", None, 1)])
            # If the error leaked, this would raise here.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            violation_store._app = None
