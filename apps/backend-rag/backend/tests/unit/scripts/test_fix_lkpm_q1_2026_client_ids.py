"""
Tests for scripts/fix_lkpm_q1_2026_client_ids.py

15 tests covering:
- pick_director_from_links (6)
- make_decision (4)
- resolve_and_fix (5)
"""

from unittest.mock import AsyncMock, MagicMock

from scripts.fix_lkpm_q1_2026_client_ids import (
    KNOWN_FAKE_FOUNDER_IDS,
    make_decision,
    pick_director_from_links,
    resolve_and_fix,
)

# =====================================================================
# Helpers
# =====================================================================


def _link(
    client_id: int,
    is_primary: bool = False,
    role: str = "director",
    status: str = "active",
    full_name: str = "Test Person",
    deleted_at: object = None,
    deleted_by: object = None,
) -> dict:
    return {
        "client_id": client_id,
        "is_primary": is_primary,
        "role": role,
        "status": status,
        "full_name": full_name,
        "deleted_at": deleted_at,
        "deleted_by": deleted_by,
    }


def _lkpm_row(rid: int, client_id: int) -> dict:
    return {
        "id": rid,
        "client_id": client_id,
        "quarter": "Q1",
        "year": 2026,
        "company_name": f"PT Test {rid}",
    }


class _FakeRecord(dict):
    """Mimics asyncpg.Record: supports record["key"], dict(record), and iteration."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _make_pool_for_fix(
    lkpm_rows: list[dict],
    links_by_company: dict[int, list[dict]],
) -> AsyncMock:
    """Build a mock pool whose conn.fetch dispatches by SQL content."""
    pool = AsyncMock()
    conn = AsyncMock()

    async def fake_fetch(sql, *args):
        if "FROM lkpm_reports" in sql:
            return [_FakeRecord(row) for row in lkpm_rows]
        if "client_company_links" in sql:
            company_id = args[0]
            return [_FakeRecord(link) for link in links_by_company.get(company_id, [])]
        return []

    conn.fetch = fake_fetch

    # conn.execute must be awaitable
    conn.execute = AsyncMock()

    # conn.transaction() must be an async context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    # pool.acquire() must be an async context manager returning conn
    acq = AsyncMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)

    pool._conn = conn  # expose for assertions
    return pool


# =====================================================================
# TestPickDirectorFromLinks
# =====================================================================


class TestPickDirectorFromLinks:
    """6 tests for pick_director_from_links."""

    def test_empty_returns_none(self) -> None:
        assert pick_director_from_links([]) is None

    def test_single_active(self) -> None:
        links = [_link(100, is_primary=True, role="director")]
        result = pick_director_from_links(links)
        assert result is not None
        assert result["client_id"] == 100

    def test_prefers_alive_over_deleted(self) -> None:
        links = [
            _link(200, is_primary=True, role="director", deleted_at="2026-01-01"),
            _link(201, is_primary=False, role="commissioner"),
        ]
        result = pick_director_from_links(links)
        assert result is not None
        assert result["client_id"] == 201

    def test_prefers_primary_among_alive(self) -> None:
        links = [
            _link(300, is_primary=False, role="director"),
            _link(301, is_primary=True, role="director"),
        ]
        result = pick_director_from_links(links)
        assert result is not None
        assert result["client_id"] == 301

    def test_prefers_director_role(self) -> None:
        links = [
            _link(400, is_primary=True, role="commissioner"),
            _link(401, is_primary=True, role="director"),
        ]
        result = pick_director_from_links(links)
        assert result is not None
        assert result["client_id"] == 401

    def test_all_deleted_returns_best_deleted(self) -> None:
        links = [
            _link(500, is_primary=False, role="commissioner", deleted_at="2026-01-01"),
            _link(501, is_primary=True, role="director", deleted_at="2026-01-01"),
        ]
        result = pick_director_from_links(links)
        assert result is not None
        assert result["client_id"] == 501

    def test_filters_out_fake_founders(self) -> None:
        fake_id = next(iter(KNOWN_FAKE_FOUNDER_IDS))
        links = [
            _link(fake_id, is_primary=True, role="director"),
        ]
        assert pick_director_from_links(links) is None


# =====================================================================
# TestMakeDecision
# =====================================================================


class TestMakeDecision:
    """4 tests for make_decision."""

    def test_no_links_orphan(self) -> None:
        row = _lkpm_row(1, 1000)
        result = make_decision(row, None)
        assert result["action"] == "orphan"
        assert result["new_client_id"] is None

    def test_active_director_fix_client_id(self) -> None:
        row = _lkpm_row(2, 1000)
        picked = _link(2000, is_primary=True, role="director")
        result = make_decision(row, picked)
        assert result["action"] == "fix_client_id"
        assert result["new_client_id"] == 2000

    def test_deleted_director_undelete_and_fix(self) -> None:
        row = _lkpm_row(3, 1000)
        picked = _link(3000, is_primary=True, role="director", deleted_at="2026-01-01")
        result = make_decision(row, picked)
        assert result["action"] == "undelete_and_fix"
        assert result["new_client_id"] == 3000

    def test_already_correct_noop(self) -> None:
        row = _lkpm_row(4, 5000)
        picked = _link(5000, is_primary=True, role="director")
        result = make_decision(row, picked)
        assert result["action"] == "noop"


# =====================================================================
# TestResolveAndFix
# =====================================================================


class TestResolveAndFix:
    """5 tests for resolve_and_fix (with mock pool)."""

    async def test_dry_run_never_writes(self) -> None:
        lkpm_rows = [_lkpm_row(10, 1000)]
        links = {1000: [_link(2000, is_primary=True, role="director")]}
        pool = _make_pool_for_fix(lkpm_rows, links)

        report = await resolve_and_fix(pool, dry_run=True)

        assert len(report) == 1
        assert report[0]["action"] == "fix_client_id"
        # execute should never be called in dry run
        pool._conn.execute.assert_not_called()

    async def test_commit_performs_updates(self) -> None:
        lkpm_rows = [_lkpm_row(11, 1000)]
        links = {1000: [_link(2000, is_primary=True, role="director")]}
        pool = _make_pool_for_fix(lkpm_rows, links)

        report = await resolve_and_fix(pool, dry_run=False)

        assert len(report) == 1
        assert report[0]["action"] == "fix_client_id"
        # Should have called execute for lkpm_reports and lkpm_client_config
        assert pool._conn.execute.call_count >= 2

    async def test_deleted_director_undelete_and_fix(self) -> None:
        lkpm_rows = [_lkpm_row(12, 1000)]
        links = {1000: [_link(3000, is_primary=True, role="director", deleted_at="2026-01-01")]}
        pool = _make_pool_for_fix(lkpm_rows, links)

        report = await resolve_and_fix(pool, dry_run=False)

        assert report[0]["action"] == "undelete_and_fix"
        # 3 executes: undelete, fix lkpm_reports, fix lkpm_client_config
        assert pool._conn.execute.call_count >= 3

    async def test_orphan_skipped(self) -> None:
        lkpm_rows = [_lkpm_row(13, 1000)]
        links = {1000: []}  # No links
        pool = _make_pool_for_fix(lkpm_rows, links)

        report = await resolve_and_fix(pool, dry_run=False)

        assert report[0]["action"] == "orphan"
        pool._conn.execute.assert_not_called()

    async def test_noop_when_already_correct(self) -> None:
        lkpm_rows = [_lkpm_row(14, 5000)]
        links = {5000: [_link(5000, is_primary=True, role="director")]}
        pool = _make_pool_for_fix(lkpm_rows, links)

        report = await resolve_and_fix(pool, dry_run=False)

        assert report[0]["action"] == "noop"
        pool._conn.execute.assert_not_called()
