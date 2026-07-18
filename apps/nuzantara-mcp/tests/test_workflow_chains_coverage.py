"""Focused coverage for the operational workflow chains.

These tests stay at the MCP boundary: every backend call is mocked and no
external service, database, or model is contacted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from nuzantara_mcp.workflows import chains


def _register_chains(
    mock_mcp: Any,
    mock_call: AsyncMock,
    mock_call_safe: AsyncMock,
) -> dict[str, Callable[..., Any]]:
    """Register all chains and capture their undecorated callables."""
    tools: dict[str, Callable[..., Any]] = {}

    def capture_tool() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tools[fn.__name__] = fn
            return fn

        return decorator

    mock_mcp.tool = capture_tool
    chains.register(mock_mcp, mock_call, mock_call_safe, long_timeout=120)
    return tools


@pytest.fixture(autouse=True)
async def _clear_notification_dedup() -> AsyncIterator[None]:
    """Keep notification decisions independent between tests."""
    chains._notification_log.clear()
    yield
    chains._notification_log.clear()


@pytest.mark.asyncio
async def test_intel_pipeline_classifies_and_routes_every_confidence_band(
    mock_mcp: Any,
    mock_call: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """High confidence is approved, medium flagged, and low archived."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(chains.asyncio, "sleep", sleep_mock)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLEAISTUDIO_API_KEY", raising=False)

    async def call_safe(endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if endpoint == "/api/intel/scraper/submit":
            return {"job_id": "job-1"}
        if endpoint == "/api/intel/staging/pending":
            return {
                "items": [
                    {"id": "high", "title": "High-impact regulation"},
                    {"id": "medium", "title": "Possible policy change"},
                    {"id": "low", "title": "Unrelated local event"},
                    "malformed-item",
                ]
            }
        if endpoint == "/api/agentic-rag/query":
            query = kwargs["json"]["query"]
            if "High-impact" in query:
                return {"confidence": 0.91, "answer": "Yes, significant"}
            if "Possible" in query:
                return {"confidence": 0.50, "answer": "Needs review"}
            return {"confidence": 0.20, "answer": "Not relevant"}
        if endpoint.startswith("/api/intel/staging/approve/"):
            return {"approved": True}
        if endpoint == "/api/article-composer/compose":
            return {"article_id": "article-1"}
        if endpoint == "/api/intel/metrics":
            return {"pending": 3}
        if endpoint == "/api/memory/lam/episodes":
            return {"saved": True}
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    call_safe_mock = AsyncMock(side_effect=call_safe)
    tools = _register_chains(mock_mcp, mock_call, call_safe_mock)

    result = await tools["chain_intel_pipeline"](["oss.go.id"])

    assert result["chain"] == "intel_pipeline"
    assert result["stats"] == {
        "items_reviewed": 4,
        "auto_approved": 1,
        "flagged": 1,
        "archived": 1,
        "pipeline_metrics": {"pending": 3},
    }
    assert result["log"][0]["job"] == {"job_id": "job-1"}
    endpoints = [call.args[0] for call in call_safe_mock.await_args_list]
    assert "/api/intel/staging/approve/high" in endpoints
    assert endpoints.count("/api/article-composer/compose") == 1
    sleep_mock.assert_awaited_once_with(10)
    reflection_call = next(
        call
        for call in call_safe_mock.await_args_list
        if call.args[0] == "/api/memory/lam/episodes"
    )
    assert reflection_call.kwargs["json"]["outcome"] == "success"


@pytest.mark.asyncio
async def test_intel_pipeline_degrades_to_manual_review_on_failures(
    mock_mcp: Any,
    mock_call: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scraper and assessment failures are isolated and reflected as partial."""
    monkeypatch.setattr(chains.asyncio, "sleep", AsyncMock())
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLEAISTUDIO_API_KEY", raising=False)

    call_safe_mock = AsyncMock(
        side_effect=[
            RuntimeError("scraper offline"),
            {"items": [{"id": "review-me", "title": "Ambiguous update"}]},
            RuntimeError("assessment unavailable"),
            RuntimeError("metrics unavailable"),
            {"saved": True},
        ]
    )
    tools = _register_chains(mock_mcp, mock_call, call_safe_mock)

    result = await tools["chain_intel_pipeline"]()

    assert result["stats"]["flagged"] == 1
    assert result["stats"]["auto_approved"] == 0
    assert result["log"][0] == {
        "step": "submit_scraper",
        "status": "error",
        "detail": "scraper offline",
    }
    reflection_call = call_safe_mock.await_args_list[-1]
    assert reflection_call.args[0] == "/api/memory/lam/episodes"
    assert reflection_call.kwargs["json"]["outcome"] == "partial"


@pytest.mark.asyncio
async def test_weekly_report_preserves_section_errors_and_adds_nlm_context(
    mock_mcp: Any,
    mock_call: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One failed section must not prevent report compilation or delivery."""
    monkeypatch.setattr(chains, "_NB_INTEL_ID", "intel-notebook")
    grounding_mock = AsyncMock(return_value="Revenue is stable week over week.")
    monkeypatch.setattr(chains, "_nlm_grounding", grounding_mock)

    responses: dict[str, dict[str, Any]] = {
        "/api/crm/clients/stats": {"total": 120, "active_practices": 45},
        "/api/analytics/completion-rates": {"completion_rate": 88},
        "/api/analytics/response-times": {"median_minutes": 12},
        "/api/analytics/sla-compliance": {"percent": 97},
        "/api/query-analytics/volume": {"queries": 400},
        "/api/team-analytics/productivity": {"completed": 75},
        "/api/team-analytics/burnout": {"at_risk": ["team-a"]},
        "/api/intel/trends": {"high_activity_areas": ["tax"]},
        "/api/autonomous-agents/status": {"healthy": True},
    }

    async def call_safe(endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if endpoint == "/api/analytics/revenue":
            raise RuntimeError("revenue service unavailable")
        if endpoint == "/api/zoho/emails":
            return {"message_id": "weekly-1"}
        if endpoint == "/api/memory/lam/episodes":
            return {"saved": True}
        if endpoint in responses:
            return responses[endpoint]
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    call_safe_mock = AsyncMock(side_effect=call_safe)
    tools = _register_chains(mock_mcp, mock_call, call_safe_mock)

    result = await tools["chain_weekly_report"]("ops@example.test")

    assert result["chain"] == "weekly_report"
    assert result["report"]["revenue"] == {"error": "revenue service unavailable"}
    assert result["report"]["nlm_intel_context"] == (
        "Revenue is stable week over week."
    )
    email_call = next(
        call
        for call in call_safe_mock.await_args_list
        if call.args[0] == "/api/zoho/emails"
    )
    assert email_call.kwargs["json"]["to"] == "ops@example.test"
    assert "Total Clients: 120" in email_call.kwargs["json"]["body"]
    assert "Burnout risk detected" in email_call.kwargs["json"]["body"]
    assert "Revenue is stable" in email_call.kwargs["json"]["body"]
    grounding_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_health_monitor_routes_actions_and_churn_grounding(
    mock_mcp: Any,
    mock_call: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk, birthday, stalled-practice, and grounding paths can coexist."""
    monkeypatch.setattr(chains, "_NB_OPS_ID", "ops-notebook")
    grounding_mock = AsyncMock(return_value="Recent inactivity predicts churn.")
    monkeypatch.setattr(chains, "_nlm_grounding", grounding_mock)

    async def call_safe(endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if endpoint == "/api/autonomous-agents/client-value-predictor/run":
            return {"scored": 2}
        if endpoint == "/api/crm/clients":
            return {
                "clients": [
                    {
                        "id": "client-1",
                        "name": "Ada Lovelace",
                        "phone": "+620000001",
                        "email": "ada@example.test",
                        "risk_score": 75,
                        "days_since_last_interaction": 5,
                        "ltv_score": 91,
                        "birthday_within_7_days": True,
                    },
                    {
                        "id": "client-2",
                        "name": "No Phone",
                        "days_since_last_interaction": 45,
                    },
                    "malformed-client",
                ]
            }
        if endpoint == "/api/zoho/emails":
            return {"message_id": "birthday-1"}
        if endpoint == "/api/crm/practices":
            return {
                "practices": [
                    {"id": "practice-1", "client_id": "client-1", "type": "KITAS"},
                    "malformed-practice",
                ]
            }
        if endpoint == "/api/portal/messages":
            return {"message_id": "portal-1"}
        if endpoint == "/api/memory/lam/episodes":
            return {"saved": True}
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    call_safe_mock = AsyncMock(side_effect=call_safe)
    tools = _register_chains(mock_mcp, mock_call, call_safe_mock)

    result = await tools["chain_client_health_monitor"]()

    assert result["chain"] == "client_health_monitor"
    assert result["stats"]["re_engagements"] == 1
    assert result["stats"]["birthday_greetings"] == 1
    assert result["stats"]["stalled_reminders"] == 1
    assert result["stats"]["nlm_churn_insights"] == (
        "Recent inactivity predicts churn."
    )
    assert any(
        step["step"] == "client_health_check" and step["clients_checked"] == 3
        for step in result["log"]
    )
    endpoints = [call.args[0] for call in call_safe_mock.await_args_list]
    assert "/api/zoho/emails" in endpoints
    assert "/api/portal/messages" in endpoints
    grounding_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_health_monitor_isolates_backend_failures(
    mock_mcp: Any,
    mock_call: AsyncMock,
) -> None:
    """Independent backend failures remain visible and yield a partial outcome."""

    async def call_safe(endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if endpoint == "/api/autonomous-agents/client-value-predictor/run":
            raise RuntimeError("predictor failed")
        if endpoint == "/api/crm/clients":
            raise RuntimeError("crm failed")
        if endpoint == "/api/crm/practices":
            raise RuntimeError("practices failed")
        if endpoint == "/api/memory/lam/episodes":
            return {"saved": True}
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    call_safe_mock = AsyncMock(side_effect=call_safe)
    tools = _register_chains(mock_mcp, mock_call, call_safe_mock)

    result = await tools["chain_client_health_monitor"]()

    assert [step["status"] for step in result["log"]] == [
        "error",
        "error",
        "error",
    ]
    assert result["stats"] == {
        "re_engagements": 0,
        "stalled_reminders": 0,
        "birthday_greetings": 0,
        "surveys_sent": 0,
    }
    reflection_call = call_safe_mock.await_args_list[-1]
    assert reflection_call.args[0] == "/api/memory/lam/episodes"
    assert reflection_call.kwargs["json"]["outcome"] == "partial"
