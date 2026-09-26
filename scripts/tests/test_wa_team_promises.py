"""T3 promise gate tests — PR-1 (schema + guard), round-1+2 fixes. No real
DB: `run_init_schema` runs against a fake pool/conn/txn that records the
REAL sql text of every statement, proving column+index verification runs
INSIDE the DDL's transaction, before COMMIT, and a mismatch leaves nothing
committed. See test_wa_team_promises_real_pg.py for the opt-in real-PG one.
"""
from __future__ import annotations

import os
import re

import pytest

from scripts.wa_team_promises import (
    EnvGuardError,
    SchemaMismatchError,
    _fail_line,
    _guard_pro_local_env,
    _REQUIRED_COLUMNS,
    _SQL_PATH,
    run_init_schema,
)
import scripts.wa_team_promises as wa_team_promises

# Fake pool/conn/txn — mirrors real asyncpg transaction semantics (commit on
# clean exit, rollback+re-raise on exception); execute/fetch/fetchrow record
# the REAL sql text passed in, so a test can assert on it.


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
    def __init__(self, log, index_rows, column_rows):
        self._log, self._index_rows, self._column_rows = log, index_rows, column_rows

    def transaction(self):
        return _FakeTxn(self._log)

    async def execute(self, ddl):
        self._log.append(("execute", ddl))

    async def fetch(self, sql, table, names, types, notnulls):
        self._log.append(("fetch", sql, table, names, types, notnulls))
        return self._column_rows.get(table, [])

    async def fetchrow(self, sql, table, index):
        self._log.append(("fetchrow", sql, table, index))
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


def _good_columns(table, **not_ok):
    """All columns `ok: True` except any name passed in `not_ok` (any
    truthy value) — the SQL comparison (type+notnull+existence) is fully
    server-side, so the fake only needs the final per-column verdict."""
    return [{"column_name": c, "ok": c not in not_ok} for c, _, _ in _REQUIRED_COLUMNS[table]]


def _good_rows(bad_tp_index=None, bad_tpc_index=None, tp_columns=None, tpc_columns=None):
    index_rows = {
        ("team_promises", "uix_team_promises_msg_type"): bad_tp_index or _GOOD_TP_ROW,
        ("team_promise_candidates", "uix_team_promise_candidates_msg_clause"):
            bad_tpc_index or _GOOD_TPC_ROW,
    }
    column_rows = {
        "team_promises": tp_columns if tp_columns is not None else _good_columns("team_promises"),
        "team_promise_candidates":
            tpc_columns if tpc_columns is not None else _good_columns("team_promise_candidates"),
    }
    return index_rows, column_rows


def _positions(log, tag):
    return [i for i, x in enumerate(log) if isinstance(x, tuple) and x[0] == tag]


# A — catalog verification: guilt (incompatible index or missing column ->
# rollback, nothing committed) and innocence (all checks pass -> commit)


@pytest.mark.parametrize("which,override,expect_id", [
    ("tp", {"indisunique": False}, "uix_team_promises_msg_type"),  # non-unique
    ("tp", {"has_predicate": True}, "uix_team_promises_msg_type"),  # partial
    ("tp", {"has_expr": True, "indnkeyatts": 3}, "uix_team_promises_msg_type"),  # extra expr column
    ("tp", {"key_columns": ["promise_type", "message_id"]}, "uix_team_promises_msg_type"),  # order
    # second index too (round-1 #4): first draft only ever broke the FIRST one.
    ("tpc", {"indisunique": False}, "uix_team_promise_candidates_msg_clause"),
], ids=["tp-non-unique", "tp-partial", "tp-extra-expr", "tp-column-order", "tpc-non-unique"])
@pytest.mark.asyncio
async def test_run_init_schema_guilt_incompatible_index_rolls_back(which, override, expect_id):
    log: list = []
    bad_row = {**(_GOOD_TP_ROW if which == "tp" else _GOOD_TPC_ROW), **override}
    rows, cols = _good_rows(bad_tp_index=bad_row if which == "tp" else None,
                             bad_tpc_index=bad_row if which == "tpc" else None)
    pool = _FakePool(_FakeConn(log, rows, cols))

    with pytest.raises(SchemaMismatchError) as exc_info:
        await run_init_schema(pool)

    assert exc_info.value.identifier == expect_id
    assert "COMMIT" not in log
    assert log[-1] == "ROLLBACK"


@pytest.mark.parametrize("column", [
    "message_id",  # round-2 #1: CORE column, wrong type (e.g. TEXT not BIGINT) — the
    # round-1 contract only covered ALTER-added columns, never checked at all.
    "conversation_id",  # round-2 #1: CORE column missing outright — same gap.
    "resolved",  # round-2 #1: NOT NULL mismatch on a CORE column — same gap.
    "resolution_kind",  # round-1 #1 regression guard: an ALTER-added column missing.
], ids=["core-wrong-type", "core-missing", "core-notnull-mismatch", "alter-missing"])
@pytest.mark.asyncio
async def test_run_init_schema_guilt_column_mismatch_rolls_back(column):
    """The comparison (existence+type+NOT NULL, via pg_attribute) runs entirely
    server-side — the fake only carries the final per-column verdict, so each
    parametrize case differs in WHICH column fails, not in how the fake
    represents "wrong type" vs "missing" vs "NOT NULL mismatch" (that
    distinction is what test_wa_team_promises_real_pg.py proves for real)."""
    log: list = []
    rows, cols = _good_rows(tp_columns=_good_columns("team_promises", **{column: True}))
    pool = _FakePool(_FakeConn(log, rows, cols))

    with pytest.raises(SchemaMismatchError) as exc_info:
        await run_init_schema(pool)

    assert exc_info.value.identifier == f"team_promises.{column}"
    assert "COMMIT" not in log
    assert log[-1] == "ROLLBACK"
    # the column check runs before either index check — never reached them.
    assert not _positions(log, "fetchrow")


@pytest.mark.asyncio
async def test_run_init_schema_innocence_complete_schema_commits_after_verification():
    log: list = []
    rows, cols = _good_rows()
    pool = _FakePool(_FakeConn(log, rows, cols))

    await run_init_schema(pool)

    assert "ROLLBACK" not in log
    commit_idx = log.index("COMMIT")
    assert all(i < commit_idx for i in _positions(log, "fetch") + _positions(log, "fetchrow"))
    assert len(_positions(log, "fetch")) == 2  # both tables' columns checked
    assert len(_positions(log, "fetchrow")) == 2  # both indexes checked


@pytest.mark.asyncio
async def test_run_init_schema_queries_carry_real_sql_text_not_a_placeholder():
    """The round-0 fake ignored the sql argument entirely — stripping
    `to_regclass`/`indnkeyatts` from the production query would have stayed
    green. Assert directly on what the fake actually received."""
    log: list = []
    rows, cols = _good_rows()
    pool = _FakePool(_FakeConn(log, rows, cols))
    await run_init_schema(pool)

    ddl = log[_positions(log, "execute")[0]][1]
    assert "ADD COLUMN IF NOT EXISTS thread_key" in ddl
    fetch_calls = [log[i] for i in _positions(log, "fetch")]
    assert all("pg_attribute" in c[1] and "atttypid" in c[1] and "regtype" in c[1] for c in fetch_calls)
    assert all("information_schema" not in c[1] for c in fetch_calls)  # round-2 #2: domains
    assert all("to_regclass" in c[1] and "indnkeyatts" in c[1] for c in
               [log[i] for i in _positions(log, "fetchrow")])


def test_required_columns_matches_every_column_declared_in_the_sql_file():
    """The spec addendum's single-source-of-truth requirement: every column
    the SQL file declares (CREATE TABLE body or ALTER ADD COLUMN) must be a
    key in _REQUIRED_COLUMNS, so the contract can never silently drift from
    the schema it is meant to be checking."""
    sql = _SQL_PATH.read_text()
    declared: dict[str, set[str]] = {}
    for table, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", sql, re.DOTALL):
        cols = {line.strip().split()[0] for line in body.strip().split(",") if line.strip()}
        declared.setdefault(table, set()).update(cols)
    for table, col in re.findall(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", sql):
        declared.setdefault(table, set()).add(col)
    assert declared  # sanity: the regexes actually matched something
    for table, cols in declared.items():
        known = {c for c, _, _ in _REQUIRED_COLUMNS[table]}
        assert cols <= known, f"{table}: SQL declares {cols - known}, missing from _REQUIRED_COLUMNS"
        assert known <= cols, f"{table}: _REQUIRED_COLUMNS declares {known - cols}, absent from the SQL"


def test_fail_line_identifier_allowlist_passthrough_and_unknown_downgrade():
    ok = SchemaMismatchError("uix_team_promises_msg_type", "should never leak this detail")
    line = _fail_line(ok, "init_schema")
    assert "identifier=uix_team_promises_msg_type" in line
    assert "should never leak this detail" not in line
    assert SchemaMismatchError("'; DROP TABLE team_promises; --").identifier == "unknown"


# B — Pro-local connection guard: refuses on ANY FLY_* var (even empty),
# ignores PG* env vars, clears them BEFORE connect, and passes exact kwargs.


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


@pytest.mark.asyncio
async def test_cli_main_clears_pg_env_and_passes_exact_kwargs_before_connect(monkeypatch):
    for var in wa_team_promises._PG_ENV_VARS_TO_CLEAR:
        monkeypatch.setenv(var, "leak-me-if-not-cleared")
    spy: dict = {}

    async def _spy_create_pool(**kwargs):
        spy["kwargs"] = kwargs
        spy["pg_env_at_connect"] = {v: os.environ.get(v) for v in wa_team_promises._PG_ENV_VARS_TO_CLEAR}
        raise RuntimeError("stop before a real connect — spy only")

    monkeypatch.setattr(wa_team_promises.asyncpg, "create_pool", _spy_create_pool)
    rc = await wa_team_promises.cli_main(["--init-schema"])
    assert rc == 1
    assert spy["pg_env_at_connect"] == {v: None for v in wa_team_promises._PG_ENV_VARS_TO_CLEAR}
    assert spy["kwargs"] == {**wa_team_promises.PRO_LOCAL_CONNECT_KWARGS,
                              "min_size": 1, "max_size": 1,
                              "statement_cache_size": 0, "command_timeout": 60}


# C — errors never carry data, and neither does argument/log-level parsing


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


@pytest.mark.parametrize("argv,token", [
    (["--bogus-flag", "SYNTHETIC_PRIVATE_TOKEN_9999"], "SYNTHETIC_PRIVATE_TOKEN_9999"),
    (["--init-schema", "--log-level", "SYNTHETIC_PRIVATE_TOKEN_5555"], "SYNTHETIC_PRIVATE_TOKEN_5555"),
], ids=["unrecognized-flag", "bad-log-level"])
@pytest.mark.asyncio
async def test_cli_main_never_echoes_a_private_token(argv, token, monkeypatch, capsys):
    monkeypatch.setenv("FLY_APP_NAME", "")  # short-circuits the log-level case before any connect
    rc = await wa_team_promises.cli_main(argv)
    assert rc == 2
    out = capsys.readouterr()
    assert token not in out.out and token not in out.err
    assert "Traceback" not in out.err
