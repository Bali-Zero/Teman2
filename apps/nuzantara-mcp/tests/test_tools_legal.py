"""Unit tests for Legal tools."""

import pytest

from nuzantara_mcp.tools.legal import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register legal tools and capture them."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)
    return tools


@pytest.mark.asyncio
async def test_ingest_regulation_required_fields(mock_mcp, mock_call, mock_call_safe) -> None:
    """ingest_regulation with required fields only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "job_id": "job-1",
        "status": "pending",
        "nb_target": "NB-3",
    }

    result = await tools["ingest_regulation"](
        url="https://jdih.kemenkeu.go.id/doc.pdf",
        tipo="PP",
        nomor="28",
        anno="2025",
    )
    assert result["job_id"] == "job-1"
    assert result["status"] == "pending"
    mock_call.assert_called_once_with(
        "/api/legal/ingest-full",
        method="POST",
        json={
            "url": "https://jdih.kemenkeu.go.id/doc.pdf",
            "tipo": "PP",
            "nomor": "28",
            "anno": "2025",
        },
    )


@pytest.mark.asyncio
async def test_ingest_regulation_all_fields(mock_mcp, mock_call, mock_call_safe) -> None:
    """ingest_regulation with all optional fields."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"job_id": "job-2", "status": "pending"}

    await tools["ingest_regulation"](
        url="https://example.com/doc.pdf",
        tipo="PMK",
        nomor="10",
        anno="2024",
        titolo="Tata Cara Pelaporan",
        nb_target="NB-4",
    )
    call_json = mock_call.call_args[1]["json"]
    assert call_json["titolo"] == "Tata Cara Pelaporan"
    assert call_json["nb_target"] == "NB-4"


@pytest.mark.asyncio
async def test_ingest_regulation_omits_none_optional(mock_mcp, mock_call, mock_call_safe) -> None:
    """ingest_regulation should not include titolo/nb_target when not provided."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"job_id": "job-3"}

    await tools["ingest_regulation"](
        url="https://example.com/x.pdf", tipo="SE", nomor="5", anno="2025"
    )
    call_json = mock_call.call_args[1]["json"]
    assert "titolo" not in call_json
    assert "nb_target" not in call_json


@pytest.mark.asyncio
async def test_get_ingest_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_ingest_status should call correct endpoint with job_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "status": "qdrant_done",
        "qdrant_chunks": 42,
        "drive_url": None,
    }

    result = await tools["get_ingest_status"](job_id="job-uuid-abc")
    assert result["status"] == "qdrant_done"
    assert result["qdrant_chunks"] == 42
    mock_call.assert_called_once_with("/api/legal/ingest-full/job-uuid-abc")


@pytest.mark.asyncio
async def test_get_ingest_status_complete(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_ingest_status for a completed job."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "status": "complete",
        "qdrant_chunks": 58,
        "drive_url": "https://drive.google.com/file/d/abc",
        "nlm_source_id": "nlm-src-1",
        "sheets_row": 123,
    }

    result = await tools["get_ingest_status"](job_id="job-done")
    assert result["status"] == "complete"
    assert result["sheets_row"] == 123


@pytest.mark.asyncio
async def test_get_ingest_status_failed(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_ingest_status for a failed job should include error."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "status": "failed",
        "error": "PDF download timed out",
    }

    result = await tools["get_ingest_status"](job_id="job-fail")
    assert result["status"] == "failed"
    assert "timed out" in result["error"]


@pytest.mark.asyncio
async def test_ingest_regulation_error_propagates(mock_mcp, mock_call, mock_call_safe) -> None:
    """Network errors from _call should propagate."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("502 Bad Gateway")

    with pytest.raises(Exception, match="502 Bad Gateway"):
        await tools["ingest_regulation"](
            url="https://x.com/a.pdf", tipo="PP", nomor="1", anno="2025"
        )
