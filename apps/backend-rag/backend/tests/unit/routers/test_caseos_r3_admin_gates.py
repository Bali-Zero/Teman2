"""Case OS Fase 0 — admin gates on R3 (world-visible) and agent-trigger actions.

Two surfaces were reachable by ANY authenticated team member:

* ``POST /api/intel/staging/publish/{type}/{item_id}`` — opens a PR against the
  public website repo (balizero.com).
* ``POST /api/autonomous-agents/*/run`` + the scheduler enable/disable pair —
  fire autonomous agents that write to the client book; the value predictor can
  message clients.

Each gate gets BOTH a guilt test (a legitimate non-admin team member is blocked)
and an innocence test (an admin still gets through) — cicatrix family #3: a guard
merged with only one of the two is how over/under-match ships.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user

ADMIN_USER: dict[str, Any] = {"id": "u-1", "email": "zero@balizero.com", "role": "admin"}
TEAM_USER: dict[str, Any] = {"id": "u-2", "email": "ari@balizero.com", "role": "consultant"}


def _client(router: Any, user: dict[str, Any]) -> AsyncClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# intel_scraper: publish to the public website
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_blocked_for_non_admin_team_member() -> None:
    """GUILT: a normal team member cannot publish to the public site."""
    from backend.app.routers.intel_scraper import router

    async with _client(router, TEAM_USER) as client:
        resp = await client.post("/api/intel/staging/publish/news/item-1")

    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_publish_allowed_for_admin() -> None:
    """INNOCENCE: an admin passes the gate and reaches the handler.

    404 (item not found) proves the gate let the request through — the staging
    lookup is the first thing the body does.
    """
    from backend.app.routers import intel_scraper

    with patch.object(intel_scraper.staging_service, "load_staging_item", return_value=None):
        async with _client(intel_scraper.router, ADMIN_USER) as client:
            resp = await client.post("/api/intel/staging/publish/news/item-1")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_internal_bypasses_http_gate_with_named_actor() -> None:
    """The Telegram quorum path publishes without a JWT, but names its authority.

    It must NOT require a `current_user` (it has none) and must not 403.
    """
    from backend.app.routers import intel_scraper

    with patch.object(intel_scraper.staging_service, "load_staging_item", return_value=None):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await intel_scraper.publish_staging_item_internal(
                "news",
                "item-1",
                actor="telegram:quorum:2",
            )

    assert exc.value.status_code == 404  # reached the body, was not gated out


def test_telegram_webhook_imports_the_real_publish_symbol() -> None:
    """Regression: the webhook imported `publish_staging_item` from `intel`.

    That symbol lives in `intel_scraper` — the stale import raised ImportError,
    which the surrounding `except Exception` swallowed, so an approved article
    was never actually published (scar family #2: it looked armed, it was not).
    """
    from backend.app.routers import intel, intel_scraper

    assert not hasattr(intel, "publish_staging_item")
    assert hasattr(intel_scraper, "publish_staging_item_internal")


# ---------------------------------------------------------------------------
# autonomous_agents: agent triggers + scheduler
# ---------------------------------------------------------------------------

AGENT_TRIGGERS = [
    "/api/autonomous-agents/conversation-trainer/run",
    "/api/autonomous-agents/client-value-predictor/run",
    "/api/autonomous-agents/knowledge-graph-builder/run",
    "/api/autonomous-agents/scheduler/task/some_task/enable",
    "/api/autonomous-agents/scheduler/task/some_task/disable",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", AGENT_TRIGGERS)
async def test_agent_trigger_blocked_for_non_admin(path: str) -> None:
    """GUILT: a normal team member cannot fire an autonomous agent."""
    from backend.app.routers.autonomous_agents import router

    async with _client(router, TEAM_USER) as client:
        resp = await client.post(path)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_trigger_allowed_for_admin() -> None:
    """INNOCENCE: an admin still fires the agent (background task scheduled)."""
    from backend.app.routers.autonomous_agents import router

    async with _client(router, ADMIN_USER) as client:
        resp = await client.post("/api/autonomous-agents/client-value-predictor/run")

    assert resp.status_code == 200
    assert resp.json()["agent_name"] == "client_value_predictor"


@pytest.mark.asyncio
async def test_agent_status_stays_open_to_team() -> None:
    """INNOCENCE (scope): read-only status is NOT gated — only the triggers are."""
    from backend.app.routers.autonomous_agents import router

    async with _client(router, TEAM_USER) as client:
        resp = await client.get("/api/autonomous-agents/executions")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# client_value_predictor: outbound-to-client is fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nurturing_outbound_disabled_by_default() -> None:
    """GUILT: with the flag off, no WhatsApp leaves — even if Twilio is armed."""
    from backend.agents.agents.client_value_predictor import ClientValuePredictor
    from backend.app.core import config

    with (
        patch("backend.agents.agents.client_value_predictor.ClientScoringService"),
        patch("backend.agents.agents.client_value_predictor.ClientSegmentationService"),
        patch("backend.agents.agents.client_value_predictor.NurturingMessageService"),
        patch("backend.agents.agents.client_value_predictor.WhatsAppNotificationService"),
    ):
        predictor = ClientValuePredictor(db_pool=MagicMock())

    predictor.whatsapp_service.send_message = AsyncMock(return_value="SM-should-not-happen")

    with patch.object(config.settings, "client_nurturing_outbound_enabled", False):
        result = await predictor.send_whatsapp_message("+6281234567890", "hello")

    assert result is None
    predictor.whatsapp_service.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_nurturing_outbound_sends_when_armed() -> None:
    """INNOCENCE: flipping the flag restores the send path (no dead code)."""
    from backend.agents.agents.client_value_predictor import ClientValuePredictor
    from backend.app.core import config

    with (
        patch("backend.agents.agents.client_value_predictor.ClientScoringService"),
        patch("backend.agents.agents.client_value_predictor.ClientSegmentationService"),
        patch("backend.agents.agents.client_value_predictor.NurturingMessageService"),
        patch("backend.agents.agents.client_value_predictor.WhatsAppNotificationService"),
    ):
        predictor = ClientValuePredictor(db_pool=MagicMock())

    predictor.whatsapp_service.send_message = AsyncMock(return_value="SM-123")

    with patch.object(config.settings, "client_nurturing_outbound_enabled", True):
        result = await predictor.send_whatsapp_message("+6281234567890", "hello")

    assert result == "SM-123"
    predictor.whatsapp_service.send_message.assert_awaited_once()
