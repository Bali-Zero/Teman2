"""Unit tests for ``backend.db.schema_audit``.

The audit module is mostly orchestration around two collaborators:

* ``MigrationManager`` — exposes ``get_status()``.
* ``asyncpg.Pool`` — yields connections we query for tracking-table state
  and ``information_schema`` lookups.

We mock both. The tests intentionally avoid spinning up Postgres because
the contract being validated here is "given input X, produce finding Y" —
not "schema_migrations works on PG". Real-PG smoke is covered separately
by ``test_migration_114_115_116_roundtrip.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db import schema_audit
from backend.db.schema_audit import AuditReport, Finding, run_audit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeAcquireCtx:
    """Async context manager wrapping a single connection mock."""

    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _build_conn(
    *,
    legacy_table_exists: bool,
    canonical_table_exists: bool,
    legacy_numbers: list[int],
    canonical_numbers: list[int],
    extra_tables: set[str] | None = None,
) -> AsyncMock:
    """Build a connection that responds to the SQL the audit issues.

    The audit only ever calls:
    - ``fetchval`` for ``information_schema.tables`` existence checks
    - ``fetch`` against the two tracking tables

    We dispatch on the SQL string to keep the fake light.
    """
    extra_tables = extra_tables or set()
    conn = AsyncMock()

    async def _fetchval(sql: str, name: str) -> bool:
        if "information_schema.tables" not in sql:
            raise AssertionError(f"unexpected fetchval SQL: {sql!r}")
        if name == "_schema_versions":
            return legacy_table_exists
        if name == "schema_migrations":
            return canonical_table_exists
        return name in extra_tables

    async def _fetch(sql: str) -> list[dict[str, int]]:
        if "_schema_versions" in sql:
            return [{"migration_number": n} for n in legacy_numbers]
        if "schema_migrations" in sql:
            return [{"migration_number": n} for n in canonical_numbers]
        raise AssertionError(f"unexpected fetch SQL: {sql!r}")

    conn.fetchval.side_effect = _fetchval
    conn.fetch.side_effect = _fetch
    return conn


def _patch_manager(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pending_list: list[int],
    conn: AsyncMock,
) -> None:
    """Replace ``MigrationManager`` with a stub returning the desired state."""

    pool = MagicMock()
    pool.acquire = lambda: _FakeAcquireCtx(conn)

    class _StubManager:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            self.pool = pool

        async def connect(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def get_status(self) -> dict[str, Any]:
            return {"pending_list": list(pending_list)}

    monkeypatch.setattr(schema_audit, "MigrationManager", _StubManager)


# ---------------------------------------------------------------------------
# Pending-migrations check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_migrations_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2, 3],
        canonical_numbers=[1, 2, 3],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    assert report.ok
    assert "pending_migrations" not in {f.code for f in report.findings}


@pytest.mark.asyncio
async def test_pending_migrations_present(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2],
        canonical_numbers=[1, 2],
    )
    _patch_manager(monkeypatch, pending_list=[3, 4], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    assert not report.ok
    [finding] = [f for f in report.findings if f.code == "pending_migrations"]
    assert finding.severity == "error"
    assert finding.details["pending"] == [3, 4]


# ---------------------------------------------------------------------------
# Tracking-table divergence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tracking_tables_in_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2, 3, 114],
        canonical_numbers=[1, 2, 3, 114],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    codes = {f.code for f in report.findings}
    assert "tracking_divergence_legacy_only" not in codes
    assert "tracking_divergence_canonical_only" not in codes


@pytest.mark.asyncio
async def test_tracking_legacy_duplicate_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2, 2, 3],
        canonical_numbers=[1, 2, 3],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    [finding] = [f for f in report.findings if f.code == "tracking_duplicate_legacy"]
    assert finding.severity == "error"
    assert finding.details["duplicates"] == {2: 2}


@pytest.mark.asyncio
async def test_tracking_canonical_duplicate_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2, 3],
        canonical_numbers=[1, 2, 3, 3, 130, 130, 130],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    [finding] = [f for f in report.findings if f.code == "tracking_duplicate_canonical"]
    assert finding.severity == "error"
    assert finding.details["duplicates"] == {3: 2, 130: 3}


@pytest.mark.asyncio
async def test_tracking_legacy_only_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migration N exists in _schema_versions but not in schema_migrations.

    This is the exact divergence the runner fix targets: a legacy half-
    success during the transition. The canonical writer never recorded
    it. Audit must flag it.
    """
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2, 3, 4],
        canonical_numbers=[1, 2, 3],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    [finding] = [f for f in report.findings if f.code == "tracking_divergence_legacy_only"]
    assert finding.severity == "error"
    assert finding.details["only_in_legacy"] == [4]


@pytest.mark.asyncio
async def test_tracking_canonical_only_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1, 2],
        canonical_numbers=[1, 2, 3],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    [finding] = [f for f in report.findings if f.code == "tracking_divergence_canonical_only"]
    assert finding.details["only_in_canonical"] == [3]


@pytest.mark.asyncio
async def test_brand_new_db_no_tracking_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh DB, no tracking tables yet. Divergence check must be a no-op.

    The first migration creates these tables; until then the audit
    cannot — and must not — assert anything about their contents.
    """
    conn = _build_conn(
        legacy_table_exists=False,
        canonical_table_exists=False,
        legacy_numbers=[],
        canonical_numbers=[],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    codes = {f.code for f in report.findings}
    assert codes == set()
    assert report.ok


@pytest.mark.asyncio
async def test_canonical_only_table_is_not_divergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-deprecation state: legacy table dropped, only canonical remains.

    Once Step 3 (backfill) lands and Step 4 drops the legacy table, the
    audit must keep working — `_schema_versions` is treated as empty,
    not as a missing dependency.
    """
    conn = _build_conn(
        legacy_table_exists=False,
        canonical_table_exists=True,
        legacy_numbers=[],
        canonical_numbers=[1, 2, 3, 114, 128],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake", required_tables=[])

    assert report.ok
    codes = {f.code for f in report.findings}
    assert "tracking_divergence_legacy_only" not in codes
    assert "tracking_divergence_canonical_only" not in codes


# ---------------------------------------------------------------------------
# Required-tables check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_required_tables_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1],
        canonical_numbers=[1],
        extra_tables={"clients", "team_members"},
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(
        database_url="postgres://fake",
        required_tables=["clients", "team_members"],
    )

    assert report.ok
    assert "required_table_missing" not in {f.code for f in report.findings}


@pytest.mark.asyncio
async def test_required_tables_some_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1],
        canonical_numbers=[1],
        extra_tables={"clients"},
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(
        database_url="postgres://fake",
        required_tables=["clients", "team_members", "lkpm_reports"],
    )

    [finding] = [f for f in report.findings if f.code == "required_table_missing"]
    assert finding.severity == "error"
    assert sorted(finding.details["missing"]) == ["lkpm_reports", "team_members"]


@pytest.mark.asyncio
async def test_required_tables_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env var, no override → check is a no-op."""
    monkeypatch.delenv("SCHEMA_AUDIT_REQUIRED_TABLES", raising=False)
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1],
        canonical_numbers=[1],
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake")

    codes = {f.code for f in report.findings}
    assert "required_table_missing" not in codes


@pytest.mark.asyncio
async def test_required_tables_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEMA_AUDIT_REQUIRED_TABLES", " clients , conversations ")
    conn = _build_conn(
        legacy_table_exists=True,
        canonical_table_exists=True,
        legacy_numbers=[1],
        canonical_numbers=[1],
        extra_tables={"clients"},  # 'conversations' missing
    )
    _patch_manager(monkeypatch, pending_list=[], conn=conn)

    report = await run_audit(database_url="postgres://fake")

    [finding] = [f for f in report.findings if f.code == "required_table_missing"]
    assert finding.details["missing"] == ["conversations"]
    assert finding.details["configured_via"] == "SCHEMA_AUDIT_REQUIRED_TABLES"


# ---------------------------------------------------------------------------
# Report serialisation
# ---------------------------------------------------------------------------


def test_report_to_dict_round_trips() -> None:
    report = AuditReport(
        checks_run=["pending_migrations"],
        findings=[
            Finding(
                code="pending_migrations",
                severity="error",
                message="2 pending",
                details={"pending": [3, 4]},
            ),
        ],
    )
    payload = report.to_dict()
    assert payload["ok"] is False
    assert payload["checks_run"] == ["pending_migrations"]
    assert payload["findings"][0]["details"] == {"pending": [3, 4]}


def test_report_ok_when_only_warnings() -> None:
    report = AuditReport(
        checks_run=["x"],
        findings=[Finding(code="x", severity="warning", message="heads-up")],
    )
    assert report.ok is True
