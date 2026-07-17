"""Regression tests for `_process_query_traced` Langfuse fail-open behavior.

Incident (2026-07-05 -> 2026-07-17): dependabot bumped `langfuse` 3.14.6 ->
4.x. langfuse v4 renamed `Langfuse.start_as_current_span(...)` to
`Langfuse.start_as_current_observation(..., as_type="span")` and dropped the
old name entirely. `_process_query_traced` called the v3 name unconditionally
with the `with` statement itself unguarded -> every `/api/agentic-rag/query`
call raised `AttributeError` before `orchestrator.process_query` ever ran.
That is exactly what fed the WA bot's outbox: 61 failed sends vs 1 success
between 2026-07-05 and 2026-07-17, until `LANGFUSE_ENABLED=false` was flipped
as an emergency kill-switch.

These tests pin: (1) the query path survives when the langfuse client lacks
BOTH the v3 and v4 span methods (the exact incident shape), and (2) tracing
still actually works end-to-end against a realistic v4-shaped mock client.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.agentic_rag import _process_query_traced


@pytest.fixture
def mock_orchestrator():
    result = MagicMock()
    result.route_used = "flash"
    result.document_count = 5
    result.model_used = "gemini-3.5-flash"
    result.abstain = False
    result.evidence_score = 0.9

    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(return_value=result)
    return orchestrator


def _base_kwargs(orchestrator, query_kwargs=None):
    return {
        "orchestrator": orchestrator,
        "query_kwargs": query_kwargs or {"query": "berapa harga KITAS?"},
        "authenticated_user_id": "user-123",
        "session_id": "sess-1",
        "query_id": "q-1",
        "ab_variants": {"hybrid_vs_dense": "control"},
    }


@pytest.mark.asyncio
async def test_query_path_survives_broken_v4_client(mock_orchestrator) -> None:
    """The exact incident: langfuse client with neither v3 nor v4 span method."""
    broken_lf = MagicMock(spec=[])  # no start_as_current_span, no *_observation

    with (
        patch(
            "backend.app.routers.agentic_rag._lf_enabled",
            return_value=True,
        ),
        patch("langfuse.get_client", return_value=broken_lf),
    ):
        result = await _process_query_traced(**_base_kwargs(mock_orchestrator))

    mock_orchestrator.process_query.assert_awaited_once()
    assert result is mock_orchestrator.process_query.return_value


@pytest.mark.asyncio
async def test_query_path_survives_span_start_raising(mock_orchestrator) -> None:
    """Attribute present but calling it explodes — still must not crash."""
    exploding_lf = MagicMock(spec=["start_as_current_observation"])
    exploding_lf.start_as_current_observation.side_effect = AttributeError(
        "'Langfuse' object has no attribute 'start_as_current_span'",
    )

    with (
        patch(
            "backend.app.routers.agentic_rag._lf_enabled",
            return_value=True,
        ),
        patch("langfuse.get_client", return_value=exploding_lf),
    ):
        result = await _process_query_traced(**_base_kwargs(mock_orchestrator))

    mock_orchestrator.process_query.assert_awaited_once()
    assert result is mock_orchestrator.process_query.return_value


@pytest.mark.asyncio
async def test_query_path_traces_successfully_with_v4_client(mock_orchestrator) -> None:
    """Positive case: a realistic v4-shaped client actually gets traced."""
    span = MagicMock(name="span")
    span_cm = MagicMock()
    span_cm.__enter__ = MagicMock(return_value=span)
    span_cm.__exit__ = MagicMock(return_value=False)

    v4_lf = MagicMock(spec=["start_as_current_observation"])
    v4_lf.start_as_current_observation.return_value = span_cm

    with (
        patch(
            "backend.app.routers.agentic_rag._lf_enabled",
            return_value=True,
        ),
        patch("langfuse.get_client", return_value=v4_lf),
    ):
        result = await _process_query_traced(**_base_kwargs(mock_orchestrator))

    mock_orchestrator.process_query.assert_awaited_once()
    assert result is mock_orchestrator.process_query.return_value

    # Span was actually started via the v4 API, named correctly, as a span.
    _, call_kwargs = v4_lf.start_as_current_observation.call_args
    assert call_kwargs["name"] == "agentic_rag.query"
    assert call_kwargs["as_type"] == "span"

    # Output was recorded on the span (PII-safe: route/model/evidence only).
    span.update.assert_called_once()
    output = span.update.call_args.kwargs["output"]
    assert output["route_used"] == "flash"
    assert output["model_used"] == "gemini-3.5-flash"


@pytest.mark.asyncio
async def test_query_path_noop_when_langfuse_disabled(mock_orchestrator) -> None:
    with patch(
        "backend.app.routers.agentic_rag._lf_enabled",
        return_value=False,
    ):
        result = await _process_query_traced(**_base_kwargs(mock_orchestrator))

    mock_orchestrator.process_query.assert_awaited_once()
    assert result is mock_orchestrator.process_query.return_value
