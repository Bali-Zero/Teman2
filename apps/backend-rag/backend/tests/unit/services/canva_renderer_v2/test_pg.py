"""PG layer: kill switch + lease CAS fetch + persist + cleanup."""
from unittest.mock import AsyncMock

import pytest

from backend.services.canva_renderer_v2._pg import (
    acquire_lease_and_fetch,
    inject_hero_paths,
    is_kill_switch_enabled,
    persist_canva_result,
    release_lease_permanent,
    release_lease_transient,
    reset_stale_leases,
)


@pytest.mark.asyncio
async def test_kill_switch_true():
    conn = AsyncMock()
    conn.fetchval.return_value = "true"
    assert await is_kill_switch_enabled(conn) is True


@pytest.mark.asyncio
async def test_kill_switch_false():
    conn = AsyncMock()
    conn.fetchval.return_value = "false"
    assert await is_kill_switch_enabled(conn) is False


@pytest.mark.asyncio
async def test_kill_switch_missing_row_treated_as_false():
    conn = AsyncMock()
    conn.fetchval.return_value = None
    assert await is_kill_switch_enabled(conn) is False


@pytest.mark.asyncio
async def test_acquire_lease_success_returns_row():
    conn = AsyncMock()
    fake_row = {"id": "abc", "topic": "T", "tone": "ped", "slides_json": "{}"}
    conn.fetchrow.return_value = fake_row
    row = await acquire_lease_and_fetch(conn, draft_id="abc", lease_owner="pid@host")
    assert row == fake_row
    args, kwargs = conn.fetchrow.call_args
    assert "UPDATE war_room_drafts" in args[0]
    assert args[1] == "pid@host"


@pytest.mark.asyncio
async def test_acquire_lease_loss_returns_none():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    row = await acquire_lease_and_fetch(conn, draft_id="abc", lease_owner="pid@host")
    assert row is None


@pytest.mark.asyncio
async def test_persist_canva_result_clears_lease():
    conn = AsyncMock()
    await persist_canva_result(
        conn, draft_id="abc",
        canva_design_id="DAG1", canva_edit_url="https://canva.com/...",
        canva_view_url=None,
    )
    sql = conn.execute.call_args[0][0]
    assert "status = 'rendered'" in sql
    assert "lease_owner = NULL" in sql
    assert "lease_acquired_at = NULL" in sql


@pytest.mark.asyncio
async def test_release_lease_transient_reverts_status():
    conn = AsyncMock()
    await release_lease_transient(conn, draft_id="abc", reason="429 rate limited")
    sql = conn.execute.call_args[0][0]
    assert "status = 'drafts_imaged_checked'" in sql
    assert "lease_owner = NULL" in sql


@pytest.mark.asyncio
async def test_release_lease_permanent_sets_terminal():
    conn = AsyncMock()
    await release_lease_permanent(
        conn, draft_id="abc", status="canva_import_failed", reason="400 invalid",
    )
    sql = conn.execute.call_args[0][0]
    assert "status = $2" in sql
    assert "lease_owner = NULL" in sql


@pytest.mark.asyncio
async def test_reset_stale_leases_returns_count():
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": "abc"}, {"id": "xyz"}]
    ids = await reset_stale_leases(conn, stale_after_minutes=15)
    assert ids == ["abc", "xyz"]


@pytest.mark.asyncio
async def test_inject_hero_paths_writes_slides_json():
    """inject_hero_paths updates slides_json with hero_image_path fields."""
    conn = AsyncMock()
    slides = {"slides": [
        {"index": 1, "is_hero_image": True, "hero_image_path": "/tmp/slide1.jpg"},
        {"index": 2, "is_hero_image": False},
    ]}
    await inject_hero_paths(conn, draft_id="abc-uuid", slides_json=slides)
    sql, draft_id_arg, slides_json_arg = conn.execute.call_args[0]
    assert "UPDATE war_room_drafts" in sql
    assert "slides_json = $2::jsonb" in sql
    assert draft_id_arg == "abc-uuid"
    import json
    parsed = json.loads(slides_json_arg)
    assert parsed["slides"][0]["hero_image_path"] == "/tmp/slide1.jpg"


@pytest.mark.asyncio
async def test_inject_hero_paths_blocked_during_rendering():
    """inject_hero_paths WHERE clause excludes status=rendering/rendered."""
    conn = AsyncMock()
    await inject_hero_paths(conn, draft_id="abc-uuid", slides_json={"slides": []})
    sql = conn.execute.call_args[0][0]
    assert "status NOT IN ('rendering', 'rendered')" in sql
