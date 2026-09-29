"""T3 promise gate tests — P2 (the linker), pure unit half. The guarded
UPDATEs and the judge's INSERT ... SELECT are proven against real Postgres in
test_wa_team_promises_link_real_pg.py; this half pins the wiring and the
statically checkable shape of the SQL. Synthetic fixtures only.
"""
from __future__ import annotations

import dataclasses

import pytest

import scripts.wa_team_promises as wtp


def test_affected_parses_asyncpg_command_tags():
    assert wtp._affected("UPDATE 3") == 3
    assert wtp._affected("UPDATE 0") == 0
    assert wtp._affected("INSERT 0 7") == 7


def test_link_metrics_every_field_is_a_bare_int():
    for f in dataclasses.fields(wtp.LinkMetrics):
        assert f.type == "int", f"{f.name} is {f.type}, not int"


@pytest.mark.parametrize("sql", [wtp._LINK_CLIENT_SQL, wtp._LINK_MEMBER_SQL])
def test_link_updates_only_fill_a_null_target_from_a_non_null_source(sql):
    assert "IS NULL" in sql and "IS NOT NULL" in sql


def test_email_normalisation_is_shared_by_insert_update_and_audit():
    norm = wtp._LINK_EMAIL_SQL
    assert "NULLIF" in norm and "lower" in norm and "btrim" in norm
    for sql in (wtp._JUDGE_INSERT_PROMISE_SQL, wtp._LINK_MEMBER_SQL, wtp._LINK_AUDIT_SQL):
        assert norm in sql


class _AuditPool:
    def __init__(self, row):
        self._row = row

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                class _Conn:
                    async def fetchrow(_self, _sql):
                        return pool._row

                return _Conn()

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_audit_returns_ints_only():
    row = {"total": 5, "client_null": 1, "member_null": 0}
    audit = await wtp.audit_link_counts(_AuditPool(row))
    assert audit == row
    assert all(type(v) is int for v in audit.values())


@pytest.mark.asyncio
async def test_cli_link_is_mutually_exclusive_with_other_modes():
    assert await wtp.cli_main(["--link", "--scan"]) == 2
    assert await wtp.cli_main(["--link", "--judge"]) == 2


class _NullPool:
    async def close(self):
        pass


@pytest.mark.asyncio
async def test_cli_link_dry_run_prints_audit_counts_and_never_runs_the_writer(monkeypatch, capsys):
    async def _fake_create_pool(**_kwargs):
        return _NullPool()

    async def _audit(_pool):
        return {"total": 4, "client_null": 2}

    async def _must_not_run(*_a, **_kw):
        raise AssertionError("run_link must not run under --dry-run")

    monkeypatch.setattr(wtp.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(wtp, "audit_link_counts", _audit)
    monkeypatch.setattr(wtp, "run_link", _must_not_run)
    assert await wtp.cli_main(["--link", "--dry-run"]) == 0
    assert "link DRY-RUN total=4 client_null=2" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cli_link_prints_counts_only(monkeypatch, capsys):
    async def _fake_create_pool(**_kwargs):
        return _NullPool()

    async def _run_link(_pool, *, dry_run):
        assert dry_run is False
        return wtp.LinkMetrics(client_linked=3, member_linked=4)

    monkeypatch.setattr(wtp.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(wtp, "run_link", _run_link)
    assert await wtp.cli_main(["--link"]) == 0
    assert "link OK client_linked=3 member_linked=4" in capsys.readouterr().out
