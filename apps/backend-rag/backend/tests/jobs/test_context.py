"""Tests for JobContext and CostMeter."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from backend.jobs.context import CostMeter, JobContext


def test_cost_meter_initial_state():
    m = CostMeter()
    assert m.total_cents == 0
    assert m.entries == []


def test_cost_meter_charge_appends_and_sums():
    m = CostMeter()
    m.charge(50, "openai:input")
    m.charge(25, "openai:output")
    assert m.total_cents == 75
    assert len(m.entries) == 2
    assert m.entries[0] == (50, "openai:input")


def test_cost_meter_charge_rejects_negative():
    m = CostMeter()
    with pytest.raises(ValueError):
        m.charge(-5, "neg")


def test_job_context_minimal_construction():
    ctx = JobContext(
        job_name="test",
        scheduled_tick=datetime(2026, 4, 18, tzinfo=timezone.utc),
        attempt=1,
        run_id=42,
        db_pool=None,
        logger=logging.getLogger("test"),
        meter=CostMeter(),
        claude_cli_available=False,
        source="scheduled",
    )
    assert ctx.job_name == "test"
    assert ctx.attempt == 1
    assert ctx.source == "scheduled"
