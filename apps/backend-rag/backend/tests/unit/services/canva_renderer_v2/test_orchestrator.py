"""Orchestrator top-level: kill-switch + per-draft pipeline + happy path."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.canva_renderer_v2.orchestrator import (
    ExitCode,
    process_draft,
    run,
)


@pytest.mark.asyncio
async def test_run_exits_quiet_when_kill_switch_off():
    with patch("backend.services.canva_renderer_v2.orchestrator._connect", new=AsyncMock()) as mc:
        conn = AsyncMock()
        conn.fetchval.return_value = "false"  # kill switch off
        mc.return_value = conn
        result = await run()
        assert result == ExitCode.KILL_SWITCH_OFF


@pytest.mark.asyncio
async def test_process_draft_happy_path(tmp_path, monkeypatch):
    """Full happy path: schema adapt → render → upload → import → persist."""
    monkeypatch.setenv("TIGRIS_BUCKET", "test-bucket")

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "abc-uuid", "topic": "Test",
        "tone": "ped", "slides_json": json.dumps({"slides": []}),
    }

    mcp_client = AsyncMock()
    mcp_client.import_design_from_url.return_value = ("DAG123", "https://canva.com/design/DAG123/edit")
    mcp_client.move_item_to_folder = AsyncMock()

    s3 = MagicMock()

    with patch(
        "backend.services.canva_renderer_v2.orchestrator.render_pdf",
        return_value=tmp_path / "fake.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.upload_pdf",
        return_value="https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc-uuid.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.delete_pdf",
    ):
        (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4")
        ok = await process_draft(
            conn=conn, mcp_client=mcp_client, s3=s3,
            draft_id="abc-uuid", lease_owner="pid@host",
        )
        assert ok is True
        # persist_canva_result was called → status='rendered'
        sql_calls = [c.args[0] for c in conn.execute.call_args_list]
        assert any("status = 'rendered'" in s for s in sql_calls)


@pytest.mark.asyncio
async def test_process_draft_429_releases_transient_and_deletes_pdf(tmp_path):
    """429 from MCP → release_lease_transient + Tigris delete."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "abc-uuid", "topic": "T", "tone": "ped",
        "slides_json": json.dumps({"slides": []}),
    }

    mcp_client = AsyncMock()
    err = Exception("429")
    err.status_code = 429
    mcp_client.import_design_from_url.side_effect = err

    s3 = MagicMock()
    deleted: list[str] = []

    def fake_delete(s3_, **kwargs):
        deleted.append(kwargs.get("draft_id", ""))

    with patch(
        "backend.services.canva_renderer_v2.orchestrator.render_pdf",
        return_value=tmp_path / "fake.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.upload_pdf",
        return_value="https://test/wr2-pdf/abc-uuid.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.delete_pdf",
        side_effect=fake_delete,
    ):
        (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4")
        ok = await process_draft(
            conn=conn, mcp_client=mcp_client, s3=s3,
            draft_id="abc-uuid", lease_owner="pid@host",
        )
        assert ok is False
        assert "abc-uuid" in deleted
        # release_lease_transient called → status='drafts_imaged_checked'
        sql_calls = [c.args[0] for c in conn.execute.call_args_list]
        assert any("status = 'drafts_imaged_checked'" in s for s in sql_calls)
