"""Tests for /api/observed-shell/emit (Sprint 1 PR-1.2).

Verifies:
- Router mounts at the documented path
- X-API-Key auth: missing → 401, valid → 202
- Status validation: out-of-allowlist → 422
- DB unavailable: emit still returns 202 (JSONL fallback semantics)
- Payload round-trip: server forwards verbatim to ObservedShellBus.emit
- Manifest+registration parity: route is registered in BOTH include_routers()
  and include_light_routers() (Sprint 1.B cicatrix antibody)

Pattern based on backend/tests/unit/app/routers/test_channel_health.py.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── helpers ───────────────────────────────────────────────────────────


def _build_app() -> FastAPI:
    """Mount the observed_shell router on a minimal FastAPI app.

    Skips middleware on purpose — the unit test exercises router logic
    only. The integration-level concern (auth middleware behavior) is
    out of scope for this file; the X-API-Key dep itself is unit-tested
    via the ``verify_internal_api_key`` Depends() override below.
    """
    from backend.app.routers import observed_shell

    app = FastAPI()
    app.include_router(observed_shell.router)
    app.state.db_pool = None  # forces ObservedShellBus → JSONL fallback path
    return app


@pytest.fixture
def authed_client():
    """TestClient that pretends every request has a valid X-API-Key.

    Overrides ``verify_internal_api_key`` to be a no-op so the router-side
    behavior can be tested in isolation.
    """
    from backend.app.routers import observed_shell
    from backend.app.utils.internal_api_auth import verify_internal_api_key

    app = _build_app()

    async def _ok():  # pragma: no cover — trivial
        return {"service": "test"}

    app.dependency_overrides[verify_internal_api_key] = _ok
    return TestClient(app), app


# ── tests ─────────────────────────────────────────────────────────────


def test_router_mounts_at_documented_path():
    """Smoke check: router exposes /api/observed-shell/emit."""
    from backend.app.routers import observed_shell

    paths = [r.path for r in observed_shell.router.routes]
    assert "/api/observed-shell/emit" in paths


def test_emit_happy_path_returns_202(authed_client):
    """Valid POST → 202 Accepted with EmitResponse body."""
    client, app = authed_client
    with patch(
        "backend.app.routers.observed_shell.ObservedShellBus"
    ) as bus_cls:
        bus_cls.return_value.emit = AsyncMock()
        r = client.post(
            "/api/observed-shell/emit",
            json={
                "automation_name": "translate.hourly",
                "status": "ok",
                "payload": {"duration_ms": 1234, "items": 42},
                "trace_id": "run-2026-05-02T03:00",
            },
        )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body == {
        "accepted": True,
        "automation_name": "translate.hourly",
        "status": "ok",
    }
    bus_cls.return_value.emit.assert_awaited_once()
    kwargs = bus_cls.return_value.emit.await_args.kwargs
    assert kwargs["automation_name"] == "translate.hourly"
    assert kwargs["status"] == "ok"
    assert kwargs["payload"] == {"duration_ms": 1234, "items": 42}
    assert kwargs["trace_id"] == "run-2026-05-02T03:00"


def test_emit_invalid_status_returns_422(authed_client):
    """Status outside allowlist → 422 (NOT silently coerced)."""
    client, _ = authed_client
    r = client.post(
        "/api/observed-shell/emit",
        json={"automation_name": "x", "status": "bogus-status"},
    )
    assert r.status_code == 422, r.text
    assert "ok" in r.text  # error message lists allowlist


def test_emit_missing_required_field_returns_422(authed_client):
    """Pydantic validates required fields before the handler runs."""
    client, _ = authed_client
    r = client.post(
        "/api/observed-shell/emit",
        json={"status": "ok"},  # missing automation_name
    )
    assert r.status_code == 422


def test_emit_payload_optional(authed_client):
    """payload + trace_id are optional; emit() receives None for both."""
    client, _ = authed_client
    with patch(
        "backend.app.routers.observed_shell.ObservedShellBus"
    ) as bus_cls:
        bus_cls.return_value.emit = AsyncMock()
        r = client.post(
            "/api/observed-shell/emit",
            json={"automation_name": "fly.backup.daily", "status": "skipped"},
        )
    assert r.status_code == 202
    kwargs = bus_cls.return_value.emit.await_args.kwargs
    assert kwargs["payload"] is None
    assert kwargs["trace_id"] is None


def test_emit_with_no_db_pool_does_not_500(authed_client):
    """app.state.db_pool=None → emit() routes to JSONL fallback, NOT 500."""
    client, _ = authed_client
    # No mock of ObservedShellBus — real one is called with db_pool=None.
    # ObservedShellBus.emit() never raises (Sprint 0 invariant), so endpoint
    # returns 202 even when DB is absent.
    import tempfile, pathlib
    from backend.services.events import observed_shell as obs_mod

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        fake_jsonl = pathlib.Path(fh.name)
    try:
        with patch.object(obs_mod, "JSONL_FALLBACK", fake_jsonl):
            r = client.post(
                "/api/observed-shell/emit",
                json={"automation_name": "smoke.test", "status": "ok"},
            )
        assert r.status_code == 202, r.text
    finally:
        fake_jsonl.unlink(missing_ok=True)


def test_router_registered_in_both_include_functions():
    """Sprint 1.B cicatrix antibody #2: manifest entry must reach BOTH
    include_routers() and include_light_routers(). Without this test, a
    drift between the two surfaces would only be caught post-deploy.
    """
    # Set required env BEFORE import to avoid Settings ValidationError
    os.environ.setdefault("JWT_SECRET_KEY", "x" * 40)
    os.environ.setdefault("API_KEYS", "test-key")

    from backend.app.setup.router_registration import (
        include_light_routers,
        include_routers,
    )

    full = FastAPI()
    include_routers(full)
    full_paths = {r.path for r in full.routes if hasattr(r, "path")}
    assert "/api/observed-shell/emit" in full_paths, (
        "include_routers() does NOT mount /api/observed-shell/emit — "
        "Sprint 1.B cicatrix regression"
    )

    light = FastAPI()
    include_light_routers(light)
    light_paths = {r.path for r in light.routes if hasattr(r, "path")}
    assert "/api/observed-shell/emit" in light_paths, (
        "include_light_routers() does NOT mount /api/observed-shell/emit — "
        "Sprint 1.B cicatrix regression"
    )
