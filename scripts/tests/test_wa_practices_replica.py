"""T5 P4 tests — no real DB: `run_sync` runs against a fake pool/conn/txn
that mutates an in-memory Pro-shaped state, proving insert/update/unchanged/
idempotent/skip/keep-pro-only/rollback semantics without touching Postgres.
`_fetch_fly_rows`/`_unescape_copy_field` are tested against canned
`subprocess.run` output, never a live pg.sh. See
test_wa_practices_replica_real_pg.py for the opt-in real-PG companion.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest

import scripts.wa_practices_replica as wpr
from scripts.wa_practices_replica import (
    _DATA_COLUMNS,
    _PRACTICE_TYPES_DATA_COLUMNS,
    _PRACTICE_TYPES_UPSERT_SQL,
    _PRACTICES_UPSERT_SQL,
    _PRO_CLIENTS_UUID_MAP_SQL,
    _PRO_ONLY_COUNT_SQL,
    EnvGuardError,
    FlyReadError,
    SyncMetrics,
    _coerce_param,
    _fail_line,
    _guard_pro_local_env,
    _success_line,
    _unescape_copy_field,
    cli_main,
    run_sync,
)

_N_DATA_COLS = len(_DATA_COLUMNS)

# run_sync calls the REAL _coerce_param even against the fake pool below, so
# every placeholder must survive it — a bare f"v-{col}" string blew up
# date.fromisoformat()/bool-comparison the moment _coerce_param stopped
# passing date/timestamptz through unchanged (see _coerce_param's docstring).
_PLACEHOLDER_BY_TYPE = {
    "text": "v-text", "numeric": "1.00", "date": "2026-01-01",
    "timestamptz": "2026-01-01 00:00:00+00", "jsonb": "{}", "boolean": "true",
    "integer": "1", "text[]": "[]",
}


def _fly_row(uuid: str, client_uuid: str | None, **overrides) -> dict[str, str | None]:
    row: dict[str, str | None] = {"uuid": uuid, "client_uuid": client_uuid}
    for col, pgtype in _DATA_COLUMNS:
        row[col] = overrides.get(col, _PLACEHOLDER_BY_TYPE[pgtype])
    return row


def _pt_row(code: str, **overrides) -> dict[str, str | None]:
    row: dict[str, str | None] = {"code": code}
    for col, pgtype in _PRACTICE_TYPES_DATA_COLUMNS:
        row[col] = overrides.get(col, _PLACEHOLDER_BY_TYPE[pgtype])
    return row


# --- Fakes: mirror real asyncpg semantics — explicit tx.start/commit/
# rollback for the OUTER transaction (matching run_sync's own
# `tx = conn.transaction(); await tx.start()` shape), AND `__aenter__`/
# `__aexit__` for the NESTED per-practices-row transaction run_sync opens as
# `async with conn.transaction():` (a real SAVEPOINT once already inside an
# outer transaction) — mutates in-memory Pro `practices`/`practice_types`
# state keyed by uuid/code so a second run_sync call sees the first call's
# writes (idempotency needs persistence across calls).


class _FakeTxn:
    def __init__(self, log):
        self._log = log

    async def start(self):
        self._log.append("BEGIN")

    async def commit(self):
        self._log.append("COMMIT")

    async def rollback(self):
        self._log.append("ROLLBACK")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await (self.rollback() if exc_type is not None else self.commit())
        return False  # never swallow — same contract as asyncpg's own Transaction


class _FakeConn:
    def __init__(self, log, clients, practices, practice_types=None, *,
                 fail_on_uuid=None, fk_violation_on_uuid=None):
        self._log = log
        self._clients = clients  # list[{"id": int, "uuid": str}]
        self._practices = practices  # dict[uuid] -> {"client_id": int, "data": list}
        self._practice_types = {} if practice_types is None else practice_types  # dict[code] -> data list
        self._fail_on_uuid = fail_on_uuid
        self._fk_violation_on_uuid = fk_violation_on_uuid

    def transaction(self):
        return _FakeTxn(self._log)

    async def fetch(self, sql, *params):
        assert sql == _PRO_CLIENTS_UUID_MAP_SQL
        return [dict(r) for r in self._clients]

    async def fetchrow(self, sql, *params):
        if sql == _PRACTICE_TYPES_UPSERT_SQL:
            code, *data = params
            existing = self._practice_types.get(code)
            if existing is None:
                self._practice_types[code] = list(data)
                return {"inserted": True}
            if existing == list(data):
                return None
            self._practice_types[code] = list(data)
            return {"inserted": False}
        assert sql == _PRACTICES_UPSERT_SQL
        uuid_, client_id, *data = params
        if self._fail_on_uuid is not None and uuid_ == self._fail_on_uuid:
            raise RuntimeError("synthetic column-set mismatch")
        if self._fk_violation_on_uuid is not None and uuid_ == self._fk_violation_on_uuid:
            raise wpr.asyncpg.exceptions.ForeignKeyViolationError("synthetic FK violation")
        existing = self._practices.get(uuid_)
        if existing is None:
            self._practices[uuid_] = {"client_id": client_id, "data": list(data)}
            return {"inserted": True}
        if existing["client_id"] == client_id and existing["data"] == list(data):
            return None
        self._practices[uuid_] = {"client_id": client_id, "data": list(data)}
        return {"inserted": False}

    async def fetchval(self, sql, *params):
        assert sql == _PRO_ONLY_COUNT_SQL
        (fly_uuids,) = params
        return sum(1 for u in self._practices if u not in fly_uuids)


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


# --- A — run_sync: insert / update / unchanged / idempotent / re-key /
#         skip-no-client / pro-only-kept / rollback-on-error


@pytest.mark.asyncio
async def test_run_sync_insert_then_idempotent_second_run_is_all_unchanged():
    log: list = []
    clients = [{"id": 501, "uuid": "client-uuid-a"}]
    practices: dict = {}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)
    rows = [_fly_row("prac-uuid-1", "client-uuid-a")]

    m1 = await run_sync(pool, rows, [], dry_run=False)
    assert (m1.fly, m1.inserted, m1.updated, m1.unchanged, m1.skipped_no_client) == (1, 1, 0, 0, 0)
    assert log[-1] == "COMMIT"

    m2 = await run_sync(pool, rows, [], dry_run=False)
    assert (m2.inserted, m2.updated, m2.unchanged) == (0, 0, 1)


@pytest.mark.asyncio
async def test_run_sync_changed_row_counts_as_updated_not_inserted():
    log: list = []
    clients = [{"id": 501, "uuid": "client-uuid-a"}]
    practices: dict = {}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)

    await run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-a")], [], dry_run=False)
    changed_row = _fly_row("prac-uuid-1", "client-uuid-a", status="revised")
    m2 = await run_sync(pool, [changed_row], [], dry_run=False)
    assert (m2.inserted, m2.updated, m2.unchanged) == (0, 1, 0)


@pytest.mark.asyncio
async def test_run_sync_reky_client_id_through_uuid_when_numeric_ids_differ():
    """Fly's client_id and Pro's client id for the SAME client can be
    different numbers — only the uuid is a safe cross-DB join key."""
    log: list = []
    clients = [{"id": 999, "uuid": "client-uuid-a"}]  # Pro's id for this client is 999
    practices: dict = {}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)
    # Fly's own client_id never appears in the row at all — only client_uuid
    # crosses the wire (see _FLY_SELECT_SQL) — so there is nothing Fly-side
    # to re-key FROM; this proves the row lands under Pro's id (999).
    await run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-a")], [], dry_run=False)
    assert practices["prac-uuid-1"]["client_id"] == 999


# --- A0 — practice_types: replicated FIRST, in the same transaction, by
#          `code` (never Fly's serial `id`) — the FK census's fix for
#          practice_type_code's dependency.


@pytest.mark.asyncio
async def test_run_sync_practice_types_insert_then_idempotent_second_run():
    log: list = []
    conn = _FakeConn(log, [], {})
    pool = _FakePool(conn)
    pt_rows = [_pt_row("visa_c1_tourism")]

    m1 = await run_sync(pool, [], pt_rows, dry_run=False)
    assert (m1.types_inserted, m1.types_updated) == (1, 0)

    m2 = await run_sync(pool, [], pt_rows, dry_run=False)
    assert (m2.types_inserted, m2.types_updated) == (0, 0)  # unchanged, not re-inserted


@pytest.mark.asyncio
async def test_run_sync_practice_types_changed_row_counts_as_updated():
    log: list = []
    conn = _FakeConn(log, [], {})
    pool = _FakePool(conn)
    await run_sync(pool, [], [_pt_row("visa_c1_tourism")], dry_run=False)
    m2 = await run_sync(pool, [], [_pt_row("visa_c1_tourism", name="renamed")], dry_run=False)
    assert (m2.types_inserted, m2.types_updated) == (0, 1)


@pytest.mark.asyncio
async def test_run_sync_practice_types_replicated_before_practices_satisfies_the_fk():
    """The scenario the FK-census ruling exists for: a code that is on Fly
    but was never on Pro — with practice_types synced first, IN THE SAME
    transaction, the practices row referencing it lands cleanly."""
    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    conn = _FakeConn(log, clients, {})
    pool = _FakePool(conn)
    m = await run_sync(
        pool,
        [_fly_row("prac-uuid-1", "client-uuid-a", practice_type_code="visa_c1_tourism")],
        [_pt_row("visa_c1_tourism")],
        dry_run=False,
    )
    assert m.types_inserted == 1
    assert m.inserted == 1
    assert m.skipped_fk == 0


@pytest.mark.asyncio
async def test_run_sync_residual_fk_violation_is_skipped_and_counted_not_a_crash():
    """Guilt case: even after practice_types sync, a residual FK violation
    on ONE practices row must not abort the rest of the run."""
    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    conn = _FakeConn(log, clients, {}, fk_violation_on_uuid="prac-uuid-bad")
    pool = _FakePool(conn)
    m = await run_sync(
        pool,
        [
            _fly_row("prac-uuid-bad", "client-uuid-a"),
            _fly_row("prac-uuid-good", "client-uuid-a"),
        ],
        [],
        dry_run=False,
    )
    assert m.skipped_fk == 1
    assert m.inserted == 1  # the OTHER row still lands — the run did not abort
    assert log[-1] == "COMMIT"  # the outer transaction still commits


def test_run_sync_innocence_no_fk_violation_configured_skipped_fk_stays_zero():
    import asyncio

    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    conn = _FakeConn(log, clients, {})
    pool = _FakePool(conn)
    m = asyncio.run(
        run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-a")], [], dry_run=False)
    )
    assert m.skipped_fk == 0


@pytest.mark.asyncio
async def test_run_sync_fly_client_absent_on_pro_is_counted_and_skipped_not_created():
    log: list = []
    clients: list = []  # Pro has no client at all
    practices: dict = {}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)
    m = await run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-missing")], [], dry_run=False)
    assert m.skipped_no_client == 1
    assert m.inserted == 0
    assert "prac-uuid-1" not in practices


@pytest.mark.asyncio
async def test_run_sync_fly_row_with_null_client_uuid_is_skipped_not_created():
    """A Fly practice whose client_id is NULL projects client_uuid=None —
    same bucket as client-absent-on-Pro, never a placeholder client."""
    log: list = []
    conn = _FakeConn(log, [{"id": 1, "uuid": "client-uuid-a"}], {})
    pool = _FakePool(conn)
    m = await run_sync(pool, [_fly_row("prac-uuid-1", None)], [], dry_run=False)
    assert m.skipped_no_client == 1


@pytest.mark.asyncio
async def test_run_sync_pro_only_row_kept_never_deleted():
    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    practices = {"pro-only-uuid": {"client_id": 1, "data": ["x"] * _N_DATA_COLS}}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)
    m = await run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-a")], [], dry_run=False)
    assert m.pro_only_kept == 1
    assert "pro-only-uuid" in practices  # untouched, never deleted


@pytest.mark.asyncio
async def test_run_sync_dry_run_rolls_back_but_reports_real_counts():
    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    practices: dict = {}
    conn = _FakeConn(log, clients, practices)
    pool = _FakePool(conn)
    m = await run_sync(pool, [_fly_row("prac-uuid-1", "client-uuid-a")], [], dry_run=True)
    assert m.inserted == 1
    # The fake mutates state directly in fetchrow (it has no real transaction
    # isolation) — what it CAN prove is which of commit/rollback run_sync
    # calls; that a real Postgres ROLLBACK actually undoes the writes is
    # test_real_pg_dry_run_leaves_no_trace in the real-PG suite. The middle
    # BEGIN/COMMIT pair is the one row's own nested transaction (a real
    # SAVEPOINT once inside the outer one) — it always commits/releases
    # regardless of dry_run; only the OUTER transaction's own end (last
    # entry) responds to dry_run.
    assert log == ["BEGIN", "BEGIN", "COMMIT", "ROLLBACK"]


@pytest.mark.asyncio
async def test_run_sync_column_set_mismatch_rolls_back_not_partial_commit():
    log: list = []
    clients = [{"id": 1, "uuid": "client-uuid-a"}]
    practices: dict = {}
    conn = _FakeConn(log, clients, practices, fail_on_uuid="prac-uuid-bad")
    pool = _FakePool(conn)
    with pytest.raises(RuntimeError):
        await run_sync(pool, [_fly_row("prac-uuid-bad", "client-uuid-a")], [], dry_run=False)
    assert log[-1] == "ROLLBACK"


# --- B — Pro-local connection guard (identical posture to
#         wa_team_promises.py's own tests)


def test_guard_guilt_rejects_fly_app_name_present_even_when_empty(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "")
    with pytest.raises(EnvGuardError):
        _guard_pro_local_env()


def test_guard_innocence_ignores_pghost(monkeypatch):
    for k in list(os.environ):
        if k.startswith("FLY_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PGHOST", "example.invalid")
    assert _guard_pro_local_env() is None


@pytest.mark.asyncio
async def test_cli_main_exits_2_on_fly_env_before_any_io_including_fly_read(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "")

    def _must_not_fetch():
        raise AssertionError("Fly read attempted despite FLY_* guard")

    async def _must_not_connect(**_kwargs):
        raise AssertionError("connect attempted despite FLY_* guard")

    monkeypatch.setattr(wpr, "_fetch_fly_rows", _must_not_fetch)
    monkeypatch.setattr(wpr, "_fetch_fly_practice_types_rows", _must_not_fetch)
    monkeypatch.setattr(wpr.asyncpg, "create_pool", _must_not_connect)
    rc = await cli_main(["--sync"])
    assert rc == 2


@pytest.mark.asyncio
async def test_cli_main_clears_pg_env_and_passes_exact_kwargs_before_connect(monkeypatch):
    for var in wpr._PG_ENV_VARS_TO_CLEAR:
        monkeypatch.setenv(var, "leak-me-if-not-cleared")
    monkeypatch.setattr(wpr, "_fetch_fly_rows", lambda: [])
    monkeypatch.setattr(wpr, "_fetch_fly_practice_types_rows", lambda: [])
    spy: dict = {}

    async def _spy_create_pool(**kwargs):
        spy["kwargs"] = kwargs
        spy["pg_env_at_connect"] = {v: os.environ.get(v) for v in wpr._PG_ENV_VARS_TO_CLEAR}
        raise RuntimeError("stop before a real connect — spy only")

    monkeypatch.setattr(wpr.asyncpg, "create_pool", _spy_create_pool)
    rc = await cli_main(["--sync"])
    assert rc == 1
    assert spy["pg_env_at_connect"] == {v: None for v in wpr._PG_ENV_VARS_TO_CLEAR}
    assert spy["kwargs"] == {**wpr.PRO_LOCAL_CONNECT_KWARGS,
                              "min_size": 1, "max_size": 1,
                              "statement_cache_size": 0, "command_timeout": 60}


def test_missing_sync_flag_exits_2():
    import asyncio

    rc = asyncio.run(cli_main([]))
    assert rc == 2


# --- C — errors and success both never carry a value


def test_fail_line_never_leaks_client_id_from_message_or_detail():
    class SyntheticFKViolation(Exception):
        sqlstate = "23503"

    exc = SyntheticFKViolation(
        'insert or update on table "practices" violates foreign key '
        'constraint "practices_client_id_fkey"\nDETAIL:  Key (client_id)'
        "=(424242) is not present in table \"clients\"."
    )
    line = _fail_line(exc, "sync")
    assert line == "wa_practices_replica: FAIL SyntheticFKViolation sqlstate=23503 stage=sync counts=n/a"
    assert "424242" not in line
    assert "DETAIL" not in line


_SUCCESS_LINE_RE = re.compile(
    r"^wa_practices_replica: sync OK fly=\d+ inserted=\d+ updated=\d+ unchanged=\d+ "
    r"skipped_no_client=\d+ skipped_fk=\d+ pro_only_kept=\d+ types_inserted=\d+ "
    r"types_updated=\d+ wall_ms=\d+\n$"
)


def test_success_line_is_ints_only():
    metrics = SyncMetrics(fly=1097, inserted=950, updated=3, unchanged=140,
                           skipped_no_client=4, skipped_fk=0, pro_only_kept=8,
                           types_inserted=66, types_updated=2, wall_ms=1234)
    line = _success_line(metrics)
    assert _SUCCESS_LINE_RE.match(line)


@pytest.mark.parametrize("argv,token", [
    (["--bogus-flag", "SYNTHETIC_PRIVATE_TOKEN_9999"], "SYNTHETIC_PRIVATE_TOKEN_9999"),
], ids=["unrecognized-flag"])
@pytest.mark.asyncio
async def test_cli_main_never_echoes_a_private_token(argv, token, capsys):
    rc = await cli_main(argv)
    assert rc == 2
    out = capsys.readouterr()
    assert token not in out.out and token not in out.err


# --- D0 — type coercion: asyncpg's extended-query protocol binds each
#          parameter with a codec fixed by the query's own `::type` cast —
#          boolean/date/timestamptz all reject a Python `str` outright
#          (round-1 finding, from the real-PG suite: `DataError: invalid
#          input for query argument $32` on 'true'::boolean; round-2
#          finding, from the Pro pre-PR dry-run against REAL Fly data: the
#          same class of failure on a non-null date/timestamptz column that
#          every real-PG fixture up to that point had left NULL — see
#          run_sync's use of _coerce_param, and the real-PG suite's
#          _fly_row() defaults, which no longer leave those two NULL).


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("false", False), (None, None),
], ids=["true", "false", "none"])
def test_coerce_param_boolean_guilt_and_innocence(value, expected):
    assert _coerce_param(value, "boolean") is expected


def test_coerce_param_date_parses_pg_default_text_output():
    import datetime

    assert _coerce_param("2026-09-28", "date") == datetime.date(2026, 9, 28)


def test_coerce_param_timestamptz_parses_pg_default_text_output():
    import datetime

    got = _coerce_param("2026-09-28 12:30:00.123456+08", "timestamptz")
    assert got == datetime.datetime(2026, 9, 28, 12, 30, 0, 123456,
                                     tzinfo=datetime.timezone(datetime.timedelta(hours=8)))


@pytest.mark.parametrize("pgtype", ["date", "timestamptz", "boolean", "integer"],
                         ids=["date", "timestamptz", "boolean", "integer"])
def test_coerce_param_none_passes_through_every_typed_branch(pgtype):
    assert _coerce_param(None, pgtype) is None


@pytest.mark.parametrize("pgtype", ["text", "numeric", "jsonb", "uuid", "text[]"])
def test_coerce_param_string_family_passes_through_unchanged(pgtype):
    assert _coerce_param("123.45", pgtype) == "123.45"


def test_coerce_param_integer_guilt_and_innocence():
    """practice_types.typical_duration_days — asyncpg's int4 codec rejects a
    raw str the same way boolean/date/timestamptz do (probed against a real
    cluster: `'42'::integer` bind param -> DataError)."""
    assert _coerce_param("42", "integer") == 42
    assert isinstance(_coerce_param("42", "integer"), int)


# --- D — COPY TEXT unescape + _fetch_fly_rows parsing (never a live pg.sh)


def test_unescape_copy_field_null_sentinel():
    assert _unescape_copy_field("\\N") is None


def test_unescape_copy_field_empty_is_empty_string_not_none():
    assert _unescape_copy_field("") == ""


@pytest.mark.parametrize("raw,expected", [
    ("a\\tb", "a\tb"),
    ("a\\nb", "a\nb"),
    ("a\\\\b", "a\\b"),
    ('{"a": "line1\\\\nline2"}', '{"a": "line1\\nline2"}'),
], ids=["tab", "newline", "backslash", "json-escaped-newline-round-trips"])
def test_unescape_copy_field_reverses_pg_copy_escaping(raw, expected):
    assert _unescape_copy_field(raw) == expected


def test_fetch_fly_rows_parses_canned_copy_output(monkeypatch):
    header = "\t".join(wpr._FLY_COPY_COLUMNS)  # not actually emitted by COPY; used for column count only
    n = len(wpr._FLY_COPY_COLUMNS)
    line = "\t".join(["u1", "cu1"] + ["\\N"] * (n - 2))

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=line + "\n", stderr="")

    monkeypatch.setattr(wpr.subprocess, "run", _fake_run)
    rows = wpr._fetch_fly_rows()
    assert len(rows) == 1
    assert rows[0]["uuid"] == "u1"
    assert rows[0]["client_uuid"] == "cu1"
    assert rows[0][_DATA_COLUMNS[0][0]] is None
    assert len(header.split("\t")) == n  # sanity on the fixture itself


def test_fetch_fly_practice_types_rows_parses_canned_copy_output(monkeypatch):
    n = len(wpr._FLY_PRACTICE_TYPES_COPY_COLUMNS)
    line = "\t".join(["visa_c1_tourism"] + ["\\N"] * (n - 1))

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=line + "\n", stderr="")

    monkeypatch.setattr(wpr.subprocess, "run", _fake_run)
    rows = wpr._fetch_fly_practice_types_rows()
    assert len(rows) == 1
    assert rows[0]["code"] == "visa_c1_tourism"
    assert rows[0][_PRACTICE_TYPES_DATA_COLUMNS[0][0]] is None


def test_build_upsert_sql_uses_jsonb_bridge_for_text_array_never_a_plain_cast():
    """required_documents is the one column whose bind parameter is NOT a
    plain `$n::type` — asyncpg's array codec rejects a raw str (probed
    against a real cluster), so the JSON-array-text bridge is load-bearing,
    not cosmetic."""
    assert "jsonb_array_elements_text" in _PRACTICE_TYPES_UPSERT_SQL
    assert "$6::text[]" not in _PRACTICE_TYPES_UPSERT_SQL


def test_fetch_fly_rows_column_count_mismatch_raises_fly_read_error(monkeypatch):
    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="too\tfew\n", stderr="")

    monkeypatch.setattr(wpr.subprocess, "run", _fake_run)
    with pytest.raises(FlyReadError):
        wpr._fetch_fly_rows()


def test_fetch_fly_rows_nonzero_exit_raises_fly_read_error_never_leaks_stderr(monkeypatch):
    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[], returncode=2, stdout="", stderr="password authentication failed for SECRET_TOKEN",
        )

    monkeypatch.setattr(wpr.subprocess, "run", _fake_run)
    with pytest.raises(FlyReadError) as exc_info:
        wpr._fetch_fly_rows()
    assert "SECRET_TOKEN" not in str(exc_info.value)
