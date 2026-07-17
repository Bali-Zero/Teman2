"""PG layer: kill switch + lease CAS fetch + persist + cleanup."""

from unittest.mock import AsyncMock

import pytest

from backend.services.canva_renderer_v2._pg import (
    acquire_html_lease_and_fetch,
    acquire_lease_and_fetch,
    fetch_pending_html_draft_ids,
    heartbeat_html_lease,
    inject_hero_paths,
    is_html_kill_switch_enabled,
    is_kill_switch_enabled,
    persist_canva_result,
    persist_html_result_and_enqueue_notifications,
    rebrief_draft,
    release_lease_permanent,
    release_lease_transient,
    requeue_draft_for_rerender,
    reset_stale_html_leases,
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
        conn,
        draft_id="abc",
        canva_design_id="DAG1",
        canva_edit_url="https://canva.com/...",
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
        conn,
        draft_id="abc",
        status="canva_import_failed",
        reason="400 invalid",
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
    slides = {
        "slides": [
            {"index": 1, "is_hero_image": True, "hero_image_path": "/tmp/slide1.jpg"},
            {"index": 2, "is_hero_image": False},
        ]
    }
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



# ── HTML lane (v4 wiring) ────────────────────────────────────────────────────


def _conn_with_txn():
    """AsyncMock conn whose .transaction() returns a working async context manager
    (real asyncpg: `async with conn.transaction():`)."""
    from contextlib import asynccontextmanager

    conn = AsyncMock()

    @asynccontextmanager
    async def _txn():
        yield

    conn.transaction = lambda: _txn()
    return conn



@pytest.mark.asyncio
async def test_html_kill_switch_reads_html_key():
    conn = AsyncMock()
    conn.fetchval.return_value = "true"
    assert await is_html_kill_switch_enabled(conn) is True
    # must query the dedicated HTML key, not a Canva key
    sql = conn.fetchval.call_args[0][0]
    assert "system_settings" in sql
    assert conn.fetchval.call_args[0][1] == "wr2_html_renderer_enabled"


@pytest.mark.asyncio
async def test_html_kill_switch_missing_is_false():
    conn = AsyncMock()
    conn.fetchval.return_value = None
    assert await is_html_kill_switch_enabled(conn) is False


@pytest.mark.asyncio
async def test_fetch_pending_html_selects_on_drive_url_not_canva_url():
    """Pre-cutover drafts carry a canva_edit_url from old Canva runs; the HTML
    lane must select on drive_url or those drafts starve forever in
    drafts_imaged_checked while the supervisor reconcile keeps kicking them."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    assert await fetch_pending_html_draft_ids(conn, limit=2) == []
    sql = conn.fetch.call_args[0][0]
    assert "drive_url IS NULL" in sql
    assert "canva_edit_url" not in sql
    assert "status = 'drafts_imaged_checked'" in sql
    assert "lease_owner IS NULL" in sql


@pytest.mark.asyncio
async def test_acquire_html_lease_sets_heartbeat_and_guards_drive_url():
    conn = AsyncMock()
    fake_row = {"id": "abc", "topic": "T", "tone": "analitico", "slides_json": "{}"}
    conn.fetchrow.return_value = fake_row
    row = await acquire_html_lease_and_fetch(conn, draft_id="abc", lease_owner="w1")
    assert row == fake_row
    sql = conn.fetchrow.call_args[0][0]
    assert "lease_heartbeat_at = NOW()" in sql
    assert "drive_url IS NULL" in sql
    assert "status = 'rendering'" in sql


@pytest.mark.asyncio
async def test_acquire_html_lease_loss_returns_none():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    assert await acquire_html_lease_and_fetch(conn, draft_id="abc", lease_owner="w1") is None


@pytest.mark.asyncio
async def test_heartbeat_true_when_one_row_updated():
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 1"
    assert await heartbeat_html_lease(conn, draft_id="abc", lease_owner="w1") is True
    sql = conn.execute.call_args[0][0]
    assert "lease_heartbeat_at = NOW()" in sql
    assert "lease_owner = $2" in sql


@pytest.mark.asyncio
async def test_heartbeat_false_when_lease_lost():
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 0"
    assert await heartbeat_html_lease(conn, draft_id="abc", lease_owner="w1") is False


@pytest.mark.asyncio
async def test_reset_stale_html_keys_off_heartbeat_and_scopes_drive_url():
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": "x"}, {"id": "y"}]
    out = await reset_stale_html_leases(conn, stale_after_minutes=10)
    assert out == ["x", "y"]
    sql = conn.fetch.call_args[0][0]
    assert "lease_heartbeat_at" in sql
    assert "drive_url IS NULL" in sql


@pytest.mark.asyncio
async def test_persist_html_lease_lost_raises():
    conn = _conn_with_txn()
    conn.execute.return_value = "UPDATE 0"  # promote affected 0 rows => lease lost
    with pytest.raises(RuntimeError, match="lease_lost"):
        await persist_html_result_and_enqueue_notifications(
            conn, draft_id="abc", lease_owner="w1", drive_url="https://d/x",
            recipients=["+62A"], message_body="link",
        )


@pytest.mark.asyncio
async def test_persist_html_enqueues_per_recipient_and_skips_duplicate():
    conn = _conn_with_txn()
    # promote OK
    conn.execute.return_value = "UPDATE 1"
    # fetchrow is called for: thread upsert, then message insert — per recipient.
    # recipient A: thread (window open) + ledger returns a row (new) -> enqueue
    # recipient B: thread (window closed) + ledger returns None (duplicate) -> skip
    thread_a = {"thread_id": 1, "window_open": True}
    ledger_a = {"id": 10}
    thread_b = {"thread_id": 2, "window_open": False}
    ledger_b = None
    conn.fetchrow.side_effect = [thread_a, ledger_a, thread_b, ledger_b]
    report = await persist_html_result_and_enqueue_notifications(
        conn, draft_id="abc", lease_owner="w1", drive_url="https://d/x",
        recipients=["+62A", "+62B"], message_body="link",
    )
    assert report["+62A"]["enqueued"] is True
    assert report["+62A"]["window_open"] is True
    assert report["+62B"]["enqueued"] is False
    assert report["+62B"]["duplicate"] is True
    assert report["+62B"]["window_open"] is False


@pytest.mark.asyncio
async def test_requeue_rerender_resets_gate_fields_with_guards():
    """GUILT (W82): the requeue verb must clear BOTH re-entry gates (status +
    drive_url) and carry the lease CAS + status whitelist in the same statement."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": "abc"}
    assert await requeue_draft_for_rerender(conn, "abc") is True
    sql = conn.fetchrow.call_args[0][0]
    assert "SET status = 'drafts_imaged_checked'" in sql
    assert "drive_url = NULL" in sql
    assert "html_render_attempts = 0" in sql  # fresh retry budget on re-entry
    assert "lease_owner IS NULL" in sql
    assert "status IN ('rendered', 'render_failed', 'drafts_imaged_checked')" in sql


@pytest.mark.asyncio
async def test_requeue_rerender_refused_returns_false():
    """INNOCENCE: a leased or pre-image draft is refused (0 rows) — the verb
    reports False instead of pretending the draft re-entered the lane."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    assert await requeue_draft_for_rerender(conn, "abc") is False


# ── rebrief_draft (B5 remake-hygiene verb) ────────────────────────────────────


@pytest.mark.asyncio
async def test_rebrief_resets_status_and_gate_trio_atomically():
    """GUILT: a draft in 'drafts_imaged_checked' with a stale fact_check_json,
    drive_url, and html_render_attempts=3 must come back with ALL of status,
    the fact-check trio, drive_url, and html_render_attempts reset — in ONE
    atomic statement (single fetchrow call) — and report True."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": "abc"}
    assert await rebrief_draft(conn, "abc") is True
    assert conn.fetchrow.call_count == 1  # atomic: one statement, not a sequence of UPDATEs
    sql = conn.fetchrow.call_args[0][0]
    # target reset — every field the fact-check trio + render leg gate on
    assert "SET status = 'briefed'" in sql
    assert "fact_check_json = NULL" in sql
    assert "fact_check_status = NULL" in sql
    assert "fact_check_at = NULL" in sql
    assert "drive_url = NULL" in sql
    assert "html_render_attempts = 0" in sql
    # guards
    assert "lease_owner IS NULL" in sql
    assert "status IN (" in sql
    for literal in (
        "'drafts'", "'drafts_checked'", "'drafts_imaged'", "'drafts_imaged_facted'",
        "'drafts_imaged_checked'", "'rendering'", "'rendered'", "'render_failed'",
        "'fact_check_failed'", "'image_failed'",
    ):
        assert literal in sql
    # never allow a deliberate human/terminal or pre-compose state into the whitelist
    for excluded in (
        "'rejected'", "'parked'", "'published'", "'approved'", "'pending_review'",
        "'missed'", "'briefed_facted'", "'researched'", "'concept'",
    ):
        assert excluded not in sql
    assert conn.fetchrow.call_args[0][1] == "abc"


@pytest.mark.asyncio
async def test_rebrief_refused_when_leased():
    """INNOCENCE 1: a draft with an active lease_owner must never be yanked
    mid-lane — the CAS guard filters it out (0 rows), the verb reports False."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    assert await rebrief_draft(conn, "abc") is False


@pytest.mark.asyncio
async def test_rebrief_refused_when_wrong_status():
    """INNOCENCE 2: a 'briefed' draft (pre-compose, already a no-op target) or a
    'rejected' draft (deliberate terminal) is outside the status whitelist — the
    guard filters it out (0 rows), the verb reports False, row untouched."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    assert await rebrief_draft(conn, "briefed-draft") is False
    assert await rebrief_draft(conn, "rejected-draft") is False
