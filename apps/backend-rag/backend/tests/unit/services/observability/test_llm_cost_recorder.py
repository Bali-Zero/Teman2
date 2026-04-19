"""Tests for the LLM cost recorder (triple-write ledger).

Covers the invariants that make the recorder "indestructible":
- Failure of one sink does NOT prevent the others from landing.
- The recorder NEVER raises to the caller.
- JSONL write is atomic + rotated by UTC day.
- Each event is serialisable (datetime → ISO).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.observability.llm_cost_recorder import (
    LLMCallEvent,
    LLMCostRecorder,
)


def _sample_event(**overrides: object) -> LLMCallEvent:
    defaults: dict[str, object] = {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.000123,
        "success": True,
        "latency_ms": 1200,
        "endpoint": "unit_test",
        "request_id": "req-abc",
        "cache_hit_tokens": 20,
    }
    defaults.update(overrides)
    return LLMCallEvent(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_jsonl_write_creates_file_and_appends_line(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    ev = _sample_event()
    # Patch the other two sinks so we isolate JSONL.
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(rec, "_write_prometheus"):
        results = await rec.record(ev)

    assert results["jsonl"] is True
    files = list(tmp_path.glob("llm_cost_log.*.jsonl"))
    assert len(files) == 1
    line = files[0].read_text().splitlines()[0]
    obj = json.loads(line)
    assert obj["provider"] == "deepseek"
    assert obj["endpoint"] == "unit_test"
    assert obj["cost_usd"] == 0.000123
    assert obj["cache_hit_tokens"] == 20
    # Timestamp must be ISO-8601 parseable
    assert datetime.fromisoformat(obj["ts_utc"]).tzinfo is not None


@pytest.mark.asyncio
async def test_jsonl_rotates_by_utc_day(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    # Two events on two different UTC days
    day1 = datetime(2026, 4, 18, 0, 0, 1, tzinfo=timezone.utc)
    day2 = datetime(2026, 4, 19, 0, 0, 1, tzinfo=timezone.utc)
    ev1 = _sample_event(ts_utc=day1)
    ev2 = _sample_event(ts_utc=day2)
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(rec, "_write_prometheus"):
        await rec.record(ev1)
        await rec.record(ev2)

    files = sorted(f.name for f in tmp_path.glob("llm_cost_log.*.jsonl"))
    assert files == [
        "llm_cost_log.2026-04-18.jsonl",
        "llm_cost_log.2026-04-19.jsonl",
    ]


@pytest.mark.asyncio
async def test_postgres_failure_does_not_block_other_sinks(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    ev = _sample_event()
    pg_mock = AsyncMock(side_effect=RuntimeError("db is down"))
    with patch.object(rec, "_write_postgres", pg_mock), \
         patch.object(rec, "_write_prometheus"):
        results = await rec.record(ev)

    assert results["postgres"] is False
    assert results["prometheus"] is True
    assert results["jsonl"] is True
    # JSONL file landed anyway
    assert list(tmp_path.glob("llm_cost_log.*.jsonl"))


@pytest.mark.asyncio
async def test_prometheus_failure_does_not_block_other_sinks(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    ev = _sample_event()
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(
             rec,
             "_write_prometheus",
             side_effect=RuntimeError("prometheus registry missing"),
         ):
        results = await rec.record(ev)

    assert results["prometheus"] is False
    assert results["postgres"] is True
    assert results["jsonl"] is True


@pytest.mark.asyncio
async def test_jsonl_failure_does_not_block_other_sinks(tmp_path: Path) -> None:
    # Use a path that cannot be written to (a file, not a directory).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    rec = LLMCostRecorder(jsonl_root=blocker)
    ev = _sample_event()
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(rec, "_write_prometheus"):
        results = await rec.record(ev)

    assert results["jsonl"] is False
    assert results["postgres"] is True
    assert results["prometheus"] is True


@pytest.mark.asyncio
async def test_record_never_raises_even_if_all_sinks_fail(tmp_path: Path) -> None:
    # Simulate total blackout: DB, Prometheus, JSONL all broken.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    rec = LLMCostRecorder(jsonl_root=blocker)
    ev = _sample_event()
    with patch.object(rec, "_write_postgres", AsyncMock(side_effect=RuntimeError("db"))), \
         patch.object(rec, "_write_prometheus", side_effect=RuntimeError("prom")):
        # The call must return normally, not raise.
        results = await rec.record(ev)

    assert results == {"prometheus": False, "postgres": False, "jsonl": False}


@pytest.mark.asyncio
async def test_two_events_same_file_both_land(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    ev1 = _sample_event(endpoint="first")
    ev2 = _sample_event(endpoint="second")
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(rec, "_write_prometheus"):
        await rec.record(ev1)
        await rec.record(ev2)

    files = list(tmp_path.glob("llm_cost_log.*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["endpoint"] == "first"
    assert json.loads(lines[1])["endpoint"] == "second"


@pytest.mark.asyncio
async def test_error_event_records_error_class(tmp_path: Path) -> None:
    rec = LLMCostRecorder(jsonl_root=tmp_path)
    ev = _sample_event(success=False, error_class="DeepSeekError", output_tokens=0)
    with patch.object(rec, "_write_postgres", AsyncMock()), \
         patch.object(rec, "_write_prometheus"):
        await rec.record(ev)

    files = list(tmp_path.glob("llm_cost_log.*.jsonl"))
    obj = json.loads(files[0].read_text().splitlines()[0])
    assert obj["success"] is False
    assert obj["error_class"] == "DeepSeekError"
    assert obj["output_tokens"] == 0
