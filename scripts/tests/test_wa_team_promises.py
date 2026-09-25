"""T3 promise gate tests — PR-1 (schema + guard) of the #7316 re-spec. No
real DB: `run_init_schema` runs against a fake pool/conn/txn that records
statement order, proving verification runs INSIDE the DDL's transaction,
before COMMIT, and a mismatch leaves nothing committed.
"""
from __future__ import annotations

import os

import pytest

from scripts.wa_team_promises import (
    EnvGuardError,
    _fail_line,
    _guard_pro_local_env,
    run_init_schema,
)
import scripts.wa_team_promises as wa_team_promises

# Fake pool/conn/txn — mirrors real asyncpg transaction semantics: commit on
# clean exit, rollback (and re-raise, never suppress) on exception.


class _FakeTxn:
    def __init__(self, log):
        self._log = log

    async def __aenter__(self):
        self._log.append("BEGIN")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._log.append("ROLLBACK" if exc_type is not None else "COMMIT")
        return False


class _FakeConn:
    def __init__(self, log, index_rows):
        self._log, self._index_rows = log, index_rows

    def transaction(self):
        return _FakeTxn(self._log)

    async def execute(self, _ddl):
        self._log.append(("execute", "ddl"))

    async def fetchrow(self, _sql, table, index):
        self._log.append(("fetchrow", table, index))
        return self._index_rows.get((table, index))


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_exc):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


_TP_KEY = ("public.team_promises", "uix_team_promises_msg_type")
_TPC_KEY = ("public.team_promise_candidates", "uix_team_promise_candidates_msg_clause")

_GOOD_TP_ROW = {
    "indisunique": True, "indisvalid": True, "indnkeyatts": 2,
    "has_predicate": False, "has_expr": False,
    "key_columns": ["message_id", "promise_type"],
}
_GOOD_TPC_ROW = {
    "indisunique": True, "indisvalid": True, "indnkeyatts": 2,
    "has_predicate": False, "has_expr": False,
    "key_columns": ["message_id", "clause_idx"],
}


def _fetchrow_positions(log):
    return [i for i, x in enumerate(log) if isinstance(x, tuple) and x[0] == "fetchrow"]


# A — catalog index verification: guilt (incompatible index -> rollback,
# nothing committed) and innocence (matching index -> commit after verify)


@pytest.mark.parametrize("bad_tp_row", [
    {**_GOOD_TP_ROW, "indisunique": False},  # non-unique
    {**_GOOD_TP_ROW, "has_predicate": True},  # partial
    {**_GOOD_TP_ROW, "has_expr": True, "indnkeyatts": 3},  # extra expression column
    {**_GOOD_TP_ROW, "key_columns": ["promise_type", "message_id"]},  # different column order
], ids=["non-unique", "partial", "extra-expression", "different-column-order"])
@pytest.mark.asyncio
async def test_run_init_schema_guilt_incompatible_index_rolls_back_nothing_committed(bad_tp_row):
    log: list = []
    rows = {_TP_KEY: bad_tp_row, _TPC_KEY: _GOOD_TPC_ROW}
    pool = _FakePool(_FakeConn(log, rows))

    with pytest.raises(RuntimeError, match="uix_team_promises_msg_type"):
        await run_init_schema(pool)

    assert "COMMIT" not in log
    assert log[-1] == "ROLLBACK"
    begin_idx = log.index("BEGIN")
    execute_idx = next(i for i, x in enumerate(log) if isinstance(x, tuple) and x[0] == "execute")
    rollback_idx = log.index("ROLLBACK")
    # verification runs strictly between the DDL and the rollback — never after a commit.
    assert begin_idx < execute_idx < _fetchrow_positions(log)[0] < rollback_idx


@pytest.mark.asyncio
async def test_run_init_schema_innocence_matching_indexes_commit_after_verification():
    log: list = []
    rows = {_TP_KEY: _GOOD_TP_ROW, _TPC_KEY: _GOOD_TPC_ROW}
    pool = _FakePool(_FakeConn(log, rows))

    await run_init_schema(pool)

    assert "ROLLBACK" not in log
    commit_idx = log.index("COMMIT")
    assert all(i < commit_idx for i in _fetchrow_positions(log))
    assert len(_fetchrow_positions(log)) == 2  # both indexes verified


# B — Pro-local connection guard: refuses on ANY FLY_* var (even empty),
# ignores PG* env vars, and exits 2 BEFORE any connection attempt.


def test_guard_guilt_rejects_fly_app_name_present_even_when_empty(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "")
    with pytest.raises(EnvGuardError):
        _guard_pro_local_env()


def test_guard_innocence_ignores_pghost(monkeypatch):
    for k in list(os.environ):
        if k.startswith("FLY_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PGHOST", "example.invalid")
    assert _guard_pro_local_env() is None  # must not raise


@pytest.mark.asyncio
async def test_cli_main_exits_2_on_fly_env_before_any_connect_attempt(monkeypatch, capsys):
    monkeypatch.setenv("FLY_APP_NAME", "")

    async def _must_not_connect(**_kwargs):
        raise AssertionError("connect attempted despite FLY_* guard")

    monkeypatch.setattr(wa_team_promises.asyncpg, "create_pool", _must_not_connect)
    rc = await wa_team_promises.cli_main(["--init-schema"])
    assert rc == 2
    assert "FAIL EnvGuardError" in capsys.readouterr().err


# C — errors never carry data


def test_fail_line_never_leaks_client_id_from_message_or_detail():
    class SyntheticFKViolation(Exception):
        sqlstate = "23503"

    exc = SyntheticFKViolation(
        'insert or update on table "team_promises" violates foreign key '
        'constraint "team_promises_client_id_fkey"\nDETAIL:  Key (client_id)'
        '=(424242) is not present in table "clients".'
    )
    line = _fail_line(exc, "init_schema")
    assert line == "wa_team_promises: FAIL SyntheticFKViolation sqlstate=23503 stage=init_schema counts=n/a"
    assert "424242" not in line
    assert "DETAIL" not in line
    assert "clients" not in line
