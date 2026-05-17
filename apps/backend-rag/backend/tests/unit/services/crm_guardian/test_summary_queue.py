"""Tests for crm_guardian.summary_queue.

Mocks asyncpg.Connection. The SQL contract (column names, table names,
priority values) is locked in here — any future schema change to
crm_guardian_summary_queue or the priority semantics must update these
tests in lockstep.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.crm_guardian.summary_queue import (
    PRIORITY_ARCHIVE,
    PRIORITY_STANDARD,
    PRIORITY_VIP,
    _priority_for_tier,
    enqueue_client,
    enqueue_clients_for_company_folder,
    is_enqueue_enabled,
)

# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


class TestPriorityForTier:
    def test_vip_priority(self) -> None:
        assert _priority_for_tier("VIP") == PRIORITY_VIP == 1

    def test_archive_priority(self) -> None:
        assert _priority_for_tier("archive") == PRIORITY_ARCHIVE == 100

    def test_standard_default(self) -> None:
        assert _priority_for_tier("standard") == PRIORITY_STANDARD == 50

    def test_unknown_falls_to_standard(self) -> None:
        assert _priority_for_tier("unknown") == PRIORITY_STANDARD

    def test_none_falls_to_standard(self) -> None:
        assert _priority_for_tier(None) == PRIORITY_STANDARD


# ---------------------------------------------------------------------------
# is_enqueue_enabled
# ---------------------------------------------------------------------------


class TestIsEnqueueEnabled:
    @pytest.mark.asyncio
    async def test_enabled_true_returns_true(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"enabled": True})
        assert await is_enqueue_enabled(conn) is True

    @pytest.mark.asyncio
    async def test_enabled_false_returns_false(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"enabled": False})
        assert await is_enqueue_enabled(conn) is False

    @pytest.mark.asyncio
    async def test_missing_row_returns_false(self) -> None:
        """Defensive: if I10b_summary_queue invariant row missing, treat as
        disabled (better safe than queueing into a void)."""
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        assert await is_enqueue_enabled(conn) is False

    @pytest.mark.asyncio
    async def test_query_targets_i10b_invariant(self) -> None:
        """SQL contract: must target invariant_id = 'I10b_summary_queue'."""
        captured: list[str] = []
        conn = MagicMock()

        async def mock_fetchrow(sql: str, *args) -> dict:
            captured.append(sql)
            return {"enabled": True}

        conn.fetchrow = mock_fetchrow
        await is_enqueue_enabled(conn)
        assert "'I10b_summary_queue'" in captured[0]
        assert "crm_guardian_state" in captured[0]


# ---------------------------------------------------------------------------
# enqueue_client
# ---------------------------------------------------------------------------


class TestEnqueueClient:
    @pytest.mark.asyncio
    async def test_skipped_when_disabled(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"enabled": False})  # is_enqueue_enabled
        result = await enqueue_client(conn, 42)
        assert result == {
            "client_id": 42, "queue_id": None,
            "action": "skipped_disabled", "priority": None,
        }

    @pytest.mark.asyncio
    async def test_force_bypasses_enabled_check(self) -> None:
        """force=True must skip the enabled gate (useful for manual reruns
        and for the 5-VIP pilot at Day 5)."""
        calls: list[tuple[str, tuple]] = []

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            calls.append((sql, args))
            if "crm_guardian_state" in sql:
                return {"enabled": False}  # should NOT be reached with force=True
            if "FROM clients" in sql:
                return {
                    "id": 1, "google_drive_folder_id": "folder_x",
                    "tier": "VIP",
                }
            if "status IN ('pending', 'running')" in sql:
                return None  # nothing existing
            if "INSERT INTO" in sql:
                return {"id": 999}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow

        result = await enqueue_client(conn, 1, force=True)
        # crm_guardian_state must NOT have been queried with force=True
        queried_sqls = [c[0] for c in calls]
        assert not any("crm_guardian_state" in s for s in queried_sqls)
        assert result["action"] == "inserted"
        assert result["priority"] == PRIORITY_VIP

    @pytest.mark.asyncio
    async def test_client_not_found(self) -> None:
        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return None
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        result = await enqueue_client(conn, 9999)
        assert result["action"] == "client_not_found"

    @pytest.mark.asyncio
    async def test_client_without_drive_folder_skipped(self) -> None:
        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return {"id": 1, "google_drive_folder_id": None, "tier": None}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        result = await enqueue_client(conn, 1)
        assert result["action"] == "client_not_found"

    @pytest.mark.asyncio
    async def test_already_pending_returns_existing(self) -> None:
        captured_sqls: list[str] = []

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            captured_sqls.append(sql)
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return {"id": 1, "google_drive_folder_id": "f", "tier": "standard"}
            if "status IN ('pending', 'running')" in sql:
                return {"id": 777}  # already pending
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        result = await enqueue_client(conn, 1)
        assert result == {
            "client_id": 1, "queue_id": 777,
            "action": "already_pending", "priority": PRIORITY_STANDARD,
        }
        # No INSERT executed
        assert not any("INSERT INTO" in s for s in captured_sqls)

    @pytest.mark.asyncio
    async def test_insert_new_pending_with_vip_priority(self) -> None:
        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return {"id": 5, "google_drive_folder_id": "vip_folder", "tier": "VIP"}
            if "status IN ('pending', 'running')" in sql:
                return None  # not pending
            if "INSERT INTO" in sql:
                return {"id": 4242}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        result = await enqueue_client(conn, 5)
        assert result == {
            "client_id": 5, "queue_id": 4242,
            "action": "inserted", "priority": PRIORITY_VIP,
        }

    @pytest.mark.asyncio
    async def test_insert_race_falls_back_to_existing(self) -> None:
        """ON CONFLICT DO NOTHING returns NULL when a parallel writer slipped
        in between our SELECT and INSERT. Function must re-query and report
        the winning row."""
        call_count = {"pending_check": 0}

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return {"id": 5, "google_drive_folder_id": "f", "tier": "standard"}
            if "status IN ('pending', 'running')" in sql:
                call_count["pending_check"] += 1
                if call_count["pending_check"] == 1:
                    return None  # first check: nothing
                return {"id": 888}  # second check: race winner
            if "INSERT INTO" in sql:
                return None  # ON CONFLICT DO NOTHING returned no row
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        result = await enqueue_client(conn, 5)
        assert result == {
            "client_id": 5, "queue_id": 888,
            "action": "already_pending", "priority": PRIORITY_STANDARD,
        }
        assert call_count["pending_check"] == 2

    @pytest.mark.asyncio
    async def test_insert_sql_uses_correct_columns(self) -> None:
        """SQL contract: INSERT must populate (client_id, status, priority,
        drive_folder_id, notes, enqueued_at)."""
        captured: list[tuple[str, tuple]] = []

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                return {"id": 1, "google_drive_folder_id": "drive_f", "tier": "standard"}
            if "status IN ('pending', 'running')" in sql:
                return None
            if "INSERT INTO" in sql:
                captured.append((sql, args))
                return {"id": 1}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        await enqueue_client(conn, 1, enqueued_by="test")
        assert len(captured) == 1
        sql, args = captured[0]
        assert "client_id" in sql
        assert "status" in sql
        assert "priority" in sql
        assert "drive_folder_id" in sql
        assert "notes" in sql
        assert "'pending'" in sql
        # Args: client_id, priority, drive_folder_id, notes
        assert args == (1, PRIORITY_STANDARD, "drive_f", "enqueued_by=test")


# ---------------------------------------------------------------------------
# enqueue_clients_for_company_folder (cascading)
# ---------------------------------------------------------------------------


class TestEnqueueClientsForCompanyFolder:
    @pytest.mark.asyncio
    async def test_unknown_folder_returns_empty(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        # fetch never called because folder lookup returns None
        result = await enqueue_clients_for_company_folder(conn, "unknown_folder")
        assert result == []

    @pytest.mark.asyncio
    async def test_company_with_no_active_clients_returns_empty(self) -> None:
        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "FROM companies" in sql:
                return {"id": 100, "company_name": "PT Lonely"}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        conn.fetch = AsyncMock(return_value=[])
        result = await enqueue_clients_for_company_folder(conn, "lonely_folder")
        assert result == []

    @pytest.mark.asyncio
    async def test_cascading_enqueue_per_client(self) -> None:
        """A company with 2 active client links must produce 2 enqueue
        results, each invoking enqueue_client with that client_id."""

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "FROM companies" in sql:
                return {"id": 100, "company_name": "PT Shared"}
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                # Per enqueue_client client lookup
                cid = args[0]
                return {"id": cid, "google_drive_folder_id": f"f_{cid}",
                        "tier": "standard"}
            if "status IN ('pending', 'running')" in sql:
                return None
            if "INSERT INTO" in sql:
                return {"id": 1000 + args[0]}  # queue_id derived from client_id
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        conn.fetch = AsyncMock(return_value=[{"client_id": 70}, {"client_id": 283}])

        results = await enqueue_clients_for_company_folder(conn, "shared_folder")
        assert len(results) == 2
        client_ids = {r["client_id"] for r in results}
        assert client_ids == {70, 283}
        assert all(r["action"] == "inserted" for r in results)
        assert all(r["queue_id"] is not None for r in results)

    @pytest.mark.asyncio
    async def test_cascading_with_one_client_already_pending(self) -> None:
        """If one of the cascaded clients is already in queue, that result
        must say 'already_pending' while others insert fresh."""

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "FROM companies" in sql:
                return {"id": 100, "company_name": "PT Mixed"}
            if "crm_guardian_state" in sql:
                return {"enabled": True}
            if "FROM clients" in sql:
                cid = args[0]
                return {"id": cid, "google_drive_folder_id": f"f_{cid}",
                        "tier": "standard"}
            if "status IN ('pending', 'running')" in sql:
                cid = args[0]
                if cid == 70:
                    return {"id": 555}  # already pending
                return None  # 283 not pending
            if "INSERT INTO" in sql:
                return {"id": 1000 + args[0]}
            return None

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        conn.fetch = AsyncMock(return_value=[{"client_id": 70}, {"client_id": 283}])

        results = await enqueue_clients_for_company_folder(conn, "f")
        assert len(results) == 2
        by_client = {r["client_id"]: r for r in results}
        assert by_client[70]["action"] == "already_pending"
        assert by_client[70]["queue_id"] == 555
        assert by_client[283]["action"] == "inserted"

    @pytest.mark.asyncio
    async def test_cascade_join_uses_active_status_filter(self) -> None:
        """SQL contract: the cascade must filter ccl.status = 'active' so
        resigned/terminated/pending links don't trigger phantom enqueues."""
        captured: list[str] = []

        async def mock_fetchrow(sql: str, *args) -> dict | None:
            if "FROM companies" in sql:
                return {"id": 1, "company_name": "PT X"}
            return None

        async def mock_fetch(sql: str, *args) -> list:
            captured.append(sql)
            return []

        conn = MagicMock()
        conn.fetchrow = mock_fetchrow
        conn.fetch = mock_fetch
        await enqueue_clients_for_company_folder(conn, "f")
        assert any("ccl.status = 'active'" in s for s in captured)
