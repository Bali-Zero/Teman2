"""Tests for /api/research/control/* — SOTA WR2 Telegram kill-switch surface.

The router exposes 4 POST endpoints that owner-only (Telegram-invoked) flips:
  - /api/research/control/research    (body: {"action": "pause"|"resume"})
  - /api/research/control/publisher   (body: {"channel": "<name>", "action": "on"|"off"})
  - /api/research/control/retrain     (body: {"action": "off"|"on"})
  - /api/research/control/playbook    (body: {"action": "freeze"|"unfreeze"})

Each call:
  1) requires X-API-Key matching NUZANTARA_API_KEY env
  2) upserts the matching key into system_settings
  3) returns {"ok": True, "key": "<key>", "value": "<value>"}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeAcq:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return None


class _FakePool:
    def __init__(self, conn):
        self._conn = conn
        self.acquire_calls = 0

    def acquire(self):
        self.acquire_calls += 1
        return _FakeAcq(self._conn)


@pytest.fixture
def app_with_router(monkeypatch):
    """Build a minimal FastAPI app that includes the router and stubs db_pool."""
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-42")

    from backend.app.routers import research_control

    conn = MagicMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    pool = _FakePool(conn)

    app = FastAPI()
    app.include_router(research_control.router)
    app.state.db_pool = pool

    return app, conn, pool


def test_research_pause_persists_kill_switch(app_with_router):
    app, conn, pool = app_with_router
    client = TestClient(app)
    resp = client.post(
        "/api/research/control/research",
        headers={"X-API-Key": "test-key-42"},
        json={"action": "pause"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["key"] == "sota_research_enabled"
    assert body["value"] == "false"
    # DB write happened with correct key/value
    assert conn.execute.await_count == 1
    args, _kwargs = conn.execute.await_args
    assert "system_settings" in args[0]
    assert args[1] == "sota_research_enabled"
    assert args[2] == "false"


def test_publisher_off_per_channel(app_with_router):
    app, conn, _pool = app_with_router
    client = TestClient(app)
    resp = client.post(
        "/api/research/control/publisher",
        headers={"X-API-Key": "test-key-42"},
        json={"channel": "instagram", "action": "off"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "wr2_publisher_enabled_instagram"
    assert body["value"] == "false"


def test_rejects_missing_or_wrong_api_key(app_with_router):
    app, _conn, _pool = app_with_router
    client = TestClient(app)
    # Missing header
    resp = client.post(
        "/api/research/control/retrain",
        json={"action": "off"},
    )
    assert resp.status_code == 401
    # Wrong value
    resp = client.post(
        "/api/research/control/retrain",
        headers={"X-API-Key": "nope"},
        json={"action": "off"},
    )
    assert resp.status_code == 401


def test_rejects_unknown_action(app_with_router):
    """Pydantic Literal validation rejects unknown actions as 422 (FastAPI default)."""
    app, _conn, _pool = app_with_router
    client = TestClient(app)
    resp = client.post(
        "/api/research/control/research",
        headers={"X-API-Key": "test-key-42"},
        json={"action": "burn_everything"},
    )
    assert resp.status_code == 422


def test_playbook_freeze_persists(app_with_router):
    app, conn, _pool = app_with_router
    client = TestClient(app)
    resp = client.post(
        "/api/research/control/playbook",
        headers={"X-API-Key": "test-key-42"},
        json={"action": "freeze"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "sota_playbook_frozen"
    assert body["value"] == "true"
