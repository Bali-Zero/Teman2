import pytest
from unittest.mock import AsyncMock, patch
from organism.scheduled_tick import main as tick_main


@pytest.mark.asyncio
async def test_emits_scheduled_tick_event():
    with patch("organism.scheduled_tick.emit_event", AsyncMock()) as mock_emit:
        await tick_main()
    mock_emit.assert_called_once()
    kwargs = mock_emit.call_args.kwargs
    assert kwargs["kind"] == "scheduled_tick"
    assert kwargs["source"] == "cron.scheduled_tick"


@pytest.mark.asyncio
async def test_payload_has_hour_and_day_of_week():
    with patch("organism.scheduled_tick.emit_event", AsyncMock()) as mock_emit:
        await tick_main()
    payload = mock_emit.call_args.kwargs["payload"]
    assert "hour" in payload
    assert "day_of_week" in payload
    assert "ts_utc" in payload
    assert 0 <= payload["hour"] <= 23
    assert 0 <= payload["day_of_week"] <= 6


@pytest.mark.asyncio
async def test_severity_is_info():
    from organism.schemas import Severity
    with patch("organism.scheduled_tick.emit_event", AsyncMock()) as mock_emit:
        await tick_main()
    assert mock_emit.call_args.kwargs["severity"] == Severity.INFO
