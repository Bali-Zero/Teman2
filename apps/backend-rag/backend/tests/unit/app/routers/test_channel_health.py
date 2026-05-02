"""Verify /api/channels/{name}/health endpoint structure for Sprint 1.B Cell-side bridge.

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from fastapi.testclient import TestClient


def _build_app_with_db_pool(db_pool=None):
    """Build minimal FastAPI app with channel_health router only.

    Avoids importing backend.app.main (heavy startup deps).
    """
    from fastapi import FastAPI

    from backend.app.dependencies import get_optional_database_pool
    from backend.app.routers import channel_health

    app = FastAPI()
    app.include_router(channel_health.router)
    app.dependency_overrides[get_optional_database_pool] = lambda: db_pool
    return app


def _fake_pool(pending: int = 5, last_ts: float | None = 12345.0):
    """Build a fake db_pool that returns the given queue depth."""

    class FakePool:
        def acquire(self):
            class _Cm:
                async def __aenter__(self_inner):
                    class _Conn:
                        async def fetchrow(self_c, sql, *args):
                            return {"pending": pending, "last_ts": last_ts}

                    return _Conn()

                async def __aexit__(self_inner, *exc):
                    return False

            return _Cm()

    return FakePool()


def test_channel_health_returns_correct_schema_for_known_channels():
    """Endpoint returns the heartbeat schema for each of the 4 known channels."""
    app = _build_app_with_db_pool(db_pool=_fake_pool(pending=5))
    client = TestClient(app)

    for name in ("whatsapp", "telegram", "instagram", "web"):
        r = client.get(f"/api/channels/{name}/health")
        assert r.status_code == 200, f"{name} returned {r.status_code}"
        body = r.json()
        assert body["channel"] == name
        assert body["status"] in {"ok", "degraded", "fail"}
        assert isinstance(body["ts"], (int, float))
        assert isinstance(body["queue_depth"], int)
        assert "last_event_seen_at" in body  # may be null
        assert isinstance(body["metadata"], dict)


def test_channel_health_unknown_channel_returns_404():
    """Unknown channel name → 404 (whitelist of 4 known names)."""
    app = _build_app_with_db_pool(db_pool=None)
    client = TestClient(app)

    r = client.get("/api/channels/unknown_channel/health")
    assert r.status_code == 404


def test_channel_health_no_db_pool_returns_zero_queue_depth():
    """When db_pool is None (no DB available), endpoint returns ok with queue_depth=0."""
    app = _build_app_with_db_pool(db_pool=None)
    client = TestClient(app)

    r = client.get("/api/channels/whatsapp/health")
    assert r.status_code == 200
    body = r.json()
    assert body["queue_depth"] == 0
    assert body["status"] == "ok"
    assert body["last_event_seen_at"] is None


def test_channel_health_classifies_status_by_queue_depth():
    """Verify thresholds: <=20 ok, 21-100 degraded, >100 fail."""
    test_cases = [
        (0, "ok"),
        (20, "ok"),
        (21, "degraded"),
        (100, "degraded"),
        (101, "fail"),
        (5000, "fail"),
    ]

    for pending_count, expected_status in test_cases:
        app = _build_app_with_db_pool(db_pool=_fake_pool(pending=pending_count))
        client = TestClient(app)
        r = client.get("/api/channels/telegram/health")
        body = r.json()
        assert body["status"] == expected_status, (
            f"queue_depth={pending_count} → expected {expected_status}, got {body['status']}"
        )
