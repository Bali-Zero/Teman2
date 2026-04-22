import pytest
from unittest.mock import AsyncMock, patch

from organism.actuators.notify_telegram import NotifyTelegram


@pytest.mark.asyncio
async def test_dry_run_returns_plan(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    result = await NotifyTelegram().run(
        params={"message": "test hello"},
        correlation_id="c",
        dry_run=True,
    )
    assert result["success"] is True
    assert "test hello" in result["would_send"]


@pytest.mark.asyncio
async def test_sends_http_post_to_telegram(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1234567890")

    resp = AsyncMock()
    resp.status_code = 200
    resp.json = lambda: {"ok": True}
    resp.raise_for_status = lambda: None

    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with patch("httpx.AsyncClient", return_value=client):
        result = await NotifyTelegram().run(
            params={"message": "hello"},
            correlation_id="c",
        )
    assert result["success"] is True
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_missing_token_fails_gracefully(
    fake_redis, tmp_path, monkeypatch,
):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    result = await NotifyTelegram().run(
        params={"message": "x"},
        correlation_id="c",
    )
    assert result["success"] is False
    assert "TELEGRAM_BOT_TOKEN" in result["error"]
