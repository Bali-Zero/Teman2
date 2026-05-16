"""Canva MCP wrapper: call_tool + transient-vs-permanent classifier."""
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio

from backend.services.canva_renderer_v2._canva_mcp import (
    CanvaMcpClient,
    is_transient_error,
    CanvaImportError,
)


def test_is_transient_429():
    err = Exception("429 Too Many Requests")
    err.status_code = 429
    assert is_transient_error(err) is True


def test_is_transient_503():
    err = Exception("503 Service Unavailable")
    err.status_code = 503
    assert is_transient_error(err) is True


def test_is_transient_400_permanent():
    err = Exception("400 Bad Request")
    err.status_code = 400
    assert is_transient_error(err) is False


def test_is_transient_network():
    import httpx
    assert is_transient_error(httpx.ConnectTimeout("boom")) is True
    assert is_transient_error(httpx.NetworkError("nope")) is True


def test_parse_design_id_from_mcp_result():
    from backend.services.canva_renderer_v2._canva_mcp import parse_design_id
    result_payload = {
        "content": [{"type": "text", "text": '{"design_id": "DAGabc1234"}'}]
    }
    assert parse_design_id(result_payload) == "DAGabc1234"


def test_parse_design_id_from_text_url():
    from backend.services.canva_renderer_v2._canva_mcp import parse_design_id
    result_payload = {
        "content": [{"type": "text",
                     "text": "Created: https://www.canva.com/design/DAGxyz9876/edit"}]
    }
    assert parse_design_id(result_payload) == "DAGxyz9876"


@pytest.mark.asyncio
async def test_import_design_calls_mcp_tool():
    client = CanvaMcpClient(server_url="https://mcp.canva.com/mcp")
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = type(
        "Result", (),
        {"content": [type("C", (), {"text": '{"design_id": "DAGabc"}'})()]},
    )()
    client._session = mock_session

    design_id, edit_url = await client.import_design_from_url(
        "https://example.com/foo.pdf", title="Test"
    )
    assert design_id == "DAGabc"
    assert edit_url == "https://www.canva.com/design/DAGabc/edit"
    mock_session.call_tool.assert_awaited_once_with(
        "import-design-from-url",
        arguments={
            "url": "https://example.com/foo.pdf",
            "name": "Test",
            "user_intent": "Import WR2 carousel PDF into Canva for editing",
        },
    )
