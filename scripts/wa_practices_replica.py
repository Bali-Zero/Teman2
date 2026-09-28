"""T5 P4 — one-way Fly -> Pro `practices` (+ `practice_types`) replica
(owner ruling D3, 2026-09-28; FK-census ruling, same date).

Fly owns `practices`; Pro carries a stale 2026-07-20 snapshot (141 rows vs
Fly's ~1,097). Clients are NOT replicated, so `client_id` is not a safe join
key across the two databases (Pro has 276 mirror-born leads with ids above
Fly's max) — every row is re-keyed through the CLIENT's `uuid` instead, never
through the numeric id.

CLI:
  apps/backend-rag/.venv/bin/python scripts/wa_practices_replica.py --sync [--dry-run]

Fly read path: `scripts/pg.sh` (role `nuzantara_readonly`, db `nuzantara_rag`)
— the one sanctioned way to reach Fly Postgres read-only from any Mac
(Keychain first, then its 0600 cron-fallback credential file). Each SELECT
runs inside an explicit `BEGIN TRANSACTION READ ONLY` via
`COPY (...) TO STDOUT` (default TEXT format): every projected column is
`::text`-cast SERVER-SIDE first, so what crosses the wire is Postgres's own
canonical stringification, not this script's guess, and `\\N` is TEXT
format's unambiguous NULL sentinel (CSV's empty-field encoding cannot tell
NULL from an empty string, which would turn a NULL `metadata` into an
invalid `''::jsonb` on the write side).

Pro write path: local `nuzantara_dev` on 127.0.0.1:5432, explicit kwargs, no
DSN/URL parsing — same guard posture as `scripts/wa_team_promises.py`
(`_guard_pro_local_env`, `_clear_pg_env`, `PRO_LOCAL_CONNECT_KWARGS`,
duplicated here rather than imported: extracting a shared module would touch
a sibling file this PR does not otherwise need to change, for a ~20-line
block). `_guard_pro_local_env` refuses (exit 2) before ANY I/O — including
the Fly read — if any `FLY_*` env var is present at all, even empty: this
process also handles Pro's local client/practice data, the one thing
Symbiosis Law 2 forbids running inside a Fly-graded environment.

FK CENSUS (`pg_constraint` on Pro `practices`, contype='f', 2026-09-28) — every
foreign key `practices` carries, and how each is satisfied here:
  - `client_id` -> `clients(id)`. Re-keyed through `clients.uuid` (clients are
    NOT replicated; a Fly practice whose client uuid is absent on Pro, or
    whose Fly `client_id` is NULL, is COUNTED and skipped — `skipped_no_client`
    — never created with a placeholder client).
  - `practice_type_code` -> `practice_types(code)`. Pro's `practice_types` covered
    only 18/1097 Fly practices' codes before this PR (measured) — `practice_types`
    is Fly-owned reference data (a service catalog, no client PII), so it is
    replicated FIRST, in the SAME Pro transaction, same uuid-less
    upsert-by-natural-key shape as `practices` itself (see
    `_PRACTICE_TYPES_UPSERT_SQL`). `practice_types` has no foreign keys of its
    own (`pg_constraint` on it returns zero rows on both Fly and Pro,
    2026-09-28) — nothing further to chase.
  - `practice_type_id` -> `practice_types(id)`. Left OUT of the copied columns
    (unchanged from the original design) even though 1095/1097 Fly rows carry
    it (measured 2026-09-28) — it is a redundant numeric shadow of
    `practice_type_code`, which is now always resolvable after the step
    above; no consumer found that reads the numeric id instead of the code
    (P5's scorer falls back to code/keyword matching). Re-keying it too
    through a code->id map is a cheap follow-up if a consumer ever needs it.
  - `user_profile_id` -> `user_profiles(id)`. `user_profiles` holds people
    data (email, full_name, phone — a client-portal login table), so per the
    FK-census ruling this is reported rather than silently handled: left OUT
    of the copied columns, unchanged from the original design. 0/1097 Fly
    rows are non-NULL (measured 2026-09-28) — this replica never reads or
    writes `user_profiles` in any way.

UPSERT is by `uuid` for `practices` (`ON CONFLICT ON CONSTRAINT
practices_uuid_key`) and by `code` for `practice_types` (`ON CONFLICT ON
CONSTRAINT practice_types_code_key`) — never by either table's serial `id`,
which is not portable across databases. `practices`' copied columns are the
intersection of Fly's and Pro's schemas with identical types, minus the FK
exclusions above and two Fly-only columns Pro's schema does not have at all
(`family_member_id`, `source_idempotency_key`). `practice_types`' schema is
IDENTICAL on both sides (measured 2026-09-28) — every column except `id` is
copied, including `required_documents` (`text[]`): asyncpg's array codec
wants a real Python list, not the text `pg_array::text` produces, so it
crosses the wire as `to_jsonb(...)::text` instead and is rebuilt into a
`text[]` value on the Pro side via `jsonb_array_elements_text` (NULL stays
NULL, `[]` stays an empty array — verified against a real cluster, never
silently coerced into the other).

Never DELETEs, on either table — a Pro-only row is simply never visited by
the write loop. One transaction per run: `--dry-run` runs the identical
read/upsert path and always rolls back at the end, so the insert/update/
unchanged counts are the real ones PostgreSQL computed, not a separate
comparison this script would have to keep in sync by hand. A residual FK
violation on a `practices` row (there should be none, since `practice_types`
is synced first in the same transaction, but this is the fail-closed net the
FK-census ruling asked for) is caught per row via a nested
`asyncpg`-savepoint, counted as `skipped_fk`, and never aborts the rest of
the run.

Idempotent by construction: the `ON CONFLICT ... DO UPDATE ... WHERE (...)
IS DISTINCT FROM (...)` guard (same idiom as
`wa_team_promises._CANDIDATE_UPSERT_SQL`) means a second run against
unchanged Fly data updates nothing — `RETURNING` yields no row for those,
counted as `unchanged`.

Output: exactly one counts line on success —
`wa_practices_replica: sync OK fly=<n> inserted=<n> updated=<n>
unchanged=<n> skipped_no_client=<n> skipped_fk=<n> pro_only_kept=<n>
types_inserted=<n> types_updated=<n> wall_ms=<n>` — every field an int.
Every other path prints ONLY `wa_practices_replica: FAIL <Type>
sqlstate=<code|-> stage=<name> counts=n/a` — never the exception message,
DETAIL, a value, a name or a uuid.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import asyncpg

# --- Pro-local connection guard (explicit kwargs, no DSN/URL parsing) ------
# Identical posture to scripts/wa_team_promises.py's own block — see that
# file's module docstring for the round-2 review finding (a DSN-string guard
# is walkable via `?host=` or PGHOST) this design already closes.

PRO_LOCAL_CONNECT_KWARGS = {
    "host": "127.0.0.1", "port": 5432, "database": "nuzantara_dev", "user": "nuzantara",
}

_PG_ENV_VARS_TO_CLEAR = ("PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE")


class EnvGuardError(RuntimeError):
    """Raised by _guard_pro_local_env — never carries an env value in str()."""


def _guard_pro_local_env() -> None:
    """Refuses if ANY `FLY_*` var is present, even empty — presence alone
    means this process runs (or is probed) under a Fly-graded environment,
    the one place Symbiosis Law 2 forbids Pro's client/practice data from
    reaching."""
    import os

    if any(k.startswith("FLY_") for k in os.environ):
        raise EnvGuardError("fly_env_detected")


def _clear_pg_env() -> None:
    import os

    for var in _PG_ENV_VARS_TO_CLEAR:
        os.environ.pop(var, None)


class FlyReadError(RuntimeError):
    """Raised by _fetch_fly_rows/_fetch_fly_practice_types_rows — str(exc)
    never carries pg.sh's stderr, a query row value, or a credential."""


# --- practices column contract ----------------------------------------------
#
# (column, pg_type) pairs, in Fly-SELECT / Pro-INSERT order. Both sides cast
# through this exact type: Fly casts `col::text` in the SELECT (canonical
# stringification), Pro casts `$n::type` back out of that same text on
# INSERT — a single source of truth for the wire format in both directions.
#
# Deliberately excluded from the intersection (not "every shared column") —
# see the module docstring's FK CENSUS for `client_id`/`practice_type_id`/
# `user_profile_id`'s reasoning specifically:
#   - `id`                                  Fly's serial; `uuid` is the real key.
#   - `client_id`                           re-keyed, not copied verbatim.
#   - `family_member_id`, `source_idempotency_key`
#                                            Fly-only; Pro's schema lacks them.
#   - `user_profile_id`, `practice_type_id` per-database FKs — see FK CENSUS.
_DATA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("practice_type_code", "text"), ("title", "text"), ("description", "text"),
    ("status", "text"), ("priority", "text"),
    ("quoted_price", "numeric"), ("final_price", "numeric"), ("currency", "text"),
    ("assigned_to", "text"),
    ("start_date", "date"), ("expected_completion_date", "date"),
    ("actual_completion_date", "date"),
    ("notes", "text"), ("metadata", "jsonb"),
    ("created_at", "timestamptz"), ("created_by", "text"),
    ("updated_at", "timestamptz"), ("updated_by", "text"),
    ("expiry_date", "date"), ("next_renewal_date", "date"),
    ("inquiry_date", "timestamptz"), ("completion_date", "timestamptz"),
    ("actual_price", "numeric"), ("payment_status", "text"), ("paid_amount", "numeric"),
    ("documents", "jsonb"), ("missing_documents", "jsonb"), ("custom_fields", "jsonb"),
    ("internal_notes", "text"),
    ("client_visible", "boolean"), ("client_summary", "text"),
    ("client_notification_sent", "boolean"),
    ("discount_amount", "numeric"), ("discount_reason", "text"),
)

# practice_types' schema is identical on both sides (measured 2026-09-28) —
# every column but `id` is in the intersection. `required_documents` uses
# the special "text[]" pgtype handled by _value_expr below, never a plain
# `$n::text[]` cast (asyncpg's array codec rejects a raw str param).
_PRACTICE_TYPES_DATA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("name", "text"), ("description", "text"), ("category", "text"),
    ("base_price", "numeric"), ("typical_duration_days", "integer"),
    ("required_documents", "text[]"), ("is_active", "boolean"),
    ("created_at", "timestamptz"), ("updated_at", "timestamptz"),
)

_FLY_COPY_COLUMNS = ("uuid", "client_uuid") + tuple(c for c, _ in _DATA_COLUMNS)

_FLY_SELECT_SQL = (
    "SELECT p.uuid::text AS uuid, c.uuid::text AS client_uuid, "
    + ", ".join(f"p.{col}::text AS {col}" for col, _ in _DATA_COLUMNS)
    + " FROM practices p LEFT JOIN clients c ON c.id = p.client_id ORDER BY p.id"
)

_FLY_PRACTICE_TYPES_COPY_COLUMNS = ("code",) + tuple(c for c, _ in _PRACTICE_TYPES_DATA_COLUMNS)

_FLY_PRACTICE_TYPES_SELECT_SQL = (
    "SELECT code::text AS code, "
    + ", ".join(
        "to_jsonb(required_documents)::text AS required_documents" if col == "required_documents"
        else f"{col}::text AS {col}"
        for col, _ in _PRACTICE_TYPES_DATA_COLUMNS
    )
    + " FROM practice_types ORDER BY id"
)


def _value_expr(index: int, pgtype: str) -> str:
    """The VALUES-list expression for bind parameter `$index` of type
    `pgtype`. `text[]` is the one special case: the parameter itself carries
    JSON array text (see `_FLY_PRACTICE_TYPES_SELECT_SQL`), not array text,
    and this rebuilds a real `text[]` from it — NULL stays NULL (the CASE),
    an empty JSON array becomes an empty `text[]`, never the other."""
    if pgtype == "text[]":
        return (
            f"CASE WHEN ${index}::jsonb IS NULL THEN NULL::text[] "
            f"ELSE ARRAY(SELECT jsonb_array_elements_text(${index}::jsonb)) END"
        )
    return f"${index}::{pgtype}"


def _build_upsert_sql(
    table: str, key_column: str, key_cast: str, constraint: str,
    data_columns: tuple[tuple[str, str], ...],
) -> str:
    """Shared UPSERT-by-natural-key builder for both `practices` (key=uuid)
    and `practice_types` (key=code) — same `ON CONFLICT ... DO UPDATE ...
    WHERE (...) IS DISTINCT FROM (...) RETURNING (xmax = 0) AS inserted`
    idiom as `wa_team_promises._CANDIDATE_UPSERT_SQL`, generalized so the two
    tables' near-identical SQL isn't hand-duplicated."""
    all_columns = (key_column,) + tuple(c for c, _ in data_columns)
    casts = (key_cast,) + tuple(t for _, t in data_columns)
    non_key = [c for c in all_columns if c != key_column]
    values_sql = ", ".join(_value_expr(i + 1, cast) for i, cast in enumerate(casts))
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_key)
    row_a = ", ".join(f"{table}.{c}" for c in non_key)
    row_b = ", ".join(f"EXCLUDED.{c}" for c in non_key)
    return (
        f"INSERT INTO {table} ({', '.join(all_columns)})\n"
        f"VALUES ({values_sql})\n"
        f"ON CONFLICT ON CONSTRAINT {constraint} DO UPDATE SET\n"
        f"  {set_sql}\n"
        f"WHERE ({row_a})\n"
        f"      IS DISTINCT FROM ({row_b})\n"
        "RETURNING (xmax = 0) AS inserted"
    )


# client_id is a re-keyed column, not a member of _DATA_COLUMNS (which
# mirrors the Fly SELECT projection) — but it IS one of the columns this
# UPSERT writes, so it belongs in the INSERT column list alongside them.
_PRACTICES_INSERT_COLUMNS: tuple[tuple[str, str], ...] = (("client_id", "integer"),) + _DATA_COLUMNS

_PRACTICES_UPSERT_SQL = _build_upsert_sql(
    "practices", "uuid", "uuid", "practices_uuid_key", _PRACTICES_INSERT_COLUMNS,
)
_PRACTICE_TYPES_UPSERT_SQL = _build_upsert_sql(
    "practice_types", "code", "text", "practice_types_code_key", _PRACTICE_TYPES_DATA_COLUMNS,
)

_PRO_CLIENTS_UUID_MAP_SQL = "SELECT id, uuid::text AS uuid FROM clients"
_PRO_ONLY_COUNT_SQL = "SELECT count(*) FROM practices WHERE uuid <> ALL($1::uuid[])"

_PG_SH = Path(__file__).resolve().parent / "pg.sh"

_COPY_UNESCAPE_MAP = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}


def _unescape_copy_field(field: str) -> str | None:
    """Reverses COPY TEXT format's backslash-escaping. `\\N` (the WHOLE
    field, never a substring — PG escapes a real leading backslash-N so this
    can never collide) is the NULL sentinel; every other backslash sequence
    is a literal control character PG escaped on the way out."""
    if field == "\\N":
        return None
    out: list[str] = []
    i, n = 0, len(field)
    while i < n:
        ch = field[i]
        if ch == "\\" and i + 1 < n:
            out.append(_COPY_UNESCAPE_MAP.get(field[i + 1], field[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _copy_fetch(
    select_sql: str, copy_columns: tuple[str, ...], *, timeout_s: int = 120,
) -> list[dict[str, str | None]]:
    """Shells to scripts/pg.sh — the one sanctioned Fly read path — inside
    an explicit read-only transaction. `-q` suppresses psql's own
    BEGIN/COPY/COMMIT status lines so stdout is pure COPY data. Shared by
    `_fetch_fly_rows` and `_fetch_fly_practice_types_rows`."""
    import os

    sql = f"BEGIN TRANSACTION READ ONLY; COPY ({select_sql}) TO STDOUT; COMMIT;"
    env = dict(os.environ, PG_TARGET="prod")
    try:
        proc = subprocess.run(
            ["bash", str(_PG_SH), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True, text=True, timeout=timeout_s, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FlyReadError(type(exc).__name__) from exc
    if proc.returncode != 0:
        raise FlyReadError("pg_sh_nonzero_exit")
    rows: list[dict[str, str | None]] = []
    for line in proc.stdout.split("\n"):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != len(copy_columns):
            raise FlyReadError("column_count_mismatch")
        rows.append({col: _unescape_copy_field(f) for col, f in zip(copy_columns, fields)})
    return rows


def _fetch_fly_rows(*, timeout_s: int = 120) -> list[dict[str, str | None]]:
    return _copy_fetch(_FLY_SELECT_SQL, _FLY_COPY_COLUMNS, timeout_s=timeout_s)


def _fetch_fly_practice_types_rows(*, timeout_s: int = 120) -> list[dict[str, str | None]]:
    return _copy_fetch(
        _FLY_PRACTICE_TYPES_SELECT_SQL, _FLY_PRACTICE_TYPES_COPY_COLUMNS, timeout_s=timeout_s,
    )


def _coerce_param(value: str | None, pgtype: str) -> str | bool | int | date | datetime | None:
    """asyncpg's extended-query protocol fixes each parameter's wire type
    from the query's own `::type` cast, then decodes with a FIXED codec for
    that OID — unlike embedding a literal in SQL text, this is not a second
    parse-time cast PostgreSQL itself runs. `text`/`numeric`/`jsonb`/`uuid`
    (and the JSON-array text `_value_expr` builds for `text[]`) all accept a
    Python `str` through their codecs (proven against a real cluster in
    test_wa_practices_replica_real_pg.py and in an ad-hoc probe against the
    P4 build's own real dry-run); `boolean`/`date`/`timestamptz`/`integer`
    do not — each wants its native Python type, not the text
    `boolean::text`/`date::text`/`timestamptz::text`/`integer::text`
    produced on the Fly side. `date.fromisoformat`/`datetime.fromisoformat`
    both round-trip PostgreSQL's own default text output byte-for-byte
    (measured: 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS[.ffffff]+HH[:MM]',
    Python 3.11)."""
    if value is None:
        return None
    if pgtype == "boolean":
        return value == "true"
    if pgtype == "date":
        return date.fromisoformat(value)
    if pgtype == "timestamptz":
        return datetime.fromisoformat(value)
    if pgtype == "integer":
        return int(value)
    return value


@dataclass(slots=True)
class SyncMetrics:
    """Every field is a bare int — the output line is built ONLY from
    these, so a uuid, name or note has no path into it."""

    fly: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_no_client: int = 0
    skipped_fk: int = 0
    pro_only_kept: int = 0
    types_inserted: int = 0
    types_updated: int = 0
    wall_ms: int = 0


async def run_sync(
    pro_pool: asyncpg.Pool,
    fly_rows: list[dict[str, str | None]],
    fly_practice_types_rows: list[dict[str, str | None]],
    *,
    dry_run: bool,
) -> SyncMetrics:
    """The testable core: `fly_rows`/`fly_practice_types_rows` are
    already-fetched data, never a live Fly connection — a caller (real
    cli_main, or a test) supplies them. One transaction for the whole run:
    `--dry-run` executes the identical UPSERT path (so PostgreSQL itself
    computes real insert/update/unchanged counts) and always rolls back
    instead of committing.

    `practice_types` is upserted FIRST, in the same transaction, so every
    code a `practices` row references should already exist on Pro by the
    time that row is attempted — `skipped_fk` is the fail-closed net for any
    RESIDUAL foreign-key violation regardless: each `practices` row's UPSERT
    runs inside its own nested `asyncpg` transaction (a real SAVEPOINT once
    already inside the outer one), so a violation there rolls back only that
    row and never aborts the rest of the run."""
    t0 = time.monotonic()
    metrics = SyncMetrics(fly=len(fly_rows))
    async with pro_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            for pt_row in fly_practice_types_rows:
                pt_params = [pt_row["code"]] + [
                    _coerce_param(pt_row[c], t) for c, t in _PRACTICE_TYPES_DATA_COLUMNS
                ]
                pt_result = await conn.fetchrow(_PRACTICE_TYPES_UPSERT_SQL, *pt_params)
                if pt_result is not None:
                    if pt_result["inserted"]:
                        metrics.types_inserted += 1
                    else:
                        metrics.types_updated += 1

            client_rows = await conn.fetch(_PRO_CLIENTS_UUID_MAP_SQL)
            client_uuid_to_id = {r["uuid"]: r["id"] for r in client_rows}
            fly_uuids: list[str] = []
            for row in fly_rows:
                fly_uuids.append(row["uuid"])
                client_uuid = row["client_uuid"]
                pro_client_id = client_uuid_to_id.get(client_uuid) if client_uuid else None
                if pro_client_id is None:
                    metrics.skipped_no_client += 1
                    continue
                params = [row["uuid"], pro_client_id] + [
                    _coerce_param(row[c], t) for c, t in _DATA_COLUMNS
                ]
                try:
                    async with conn.transaction():  # nested -> real SAVEPOINT
                        result = await conn.fetchrow(_PRACTICES_UPSERT_SQL, *params)
                except asyncpg.exceptions.ForeignKeyViolationError:
                    metrics.skipped_fk += 1
                    continue
                if result is None:
                    metrics.unchanged += 1
                elif result["inserted"]:
                    metrics.inserted += 1
                else:
                    metrics.updated += 1
            metrics.pro_only_kept = await conn.fetchval(_PRO_ONLY_COUNT_SQL, fly_uuids)
        except Exception:
            await tx.rollback()
            raise
        else:
            await (tx.rollback() if dry_run else tx.commit())
    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# --- CLI --------------------------------------------------------------------


class _ArgSyntaxError(RuntimeError):
    """Raised in place of argparse's own error() — never carries the raw
    argv token argparse's default message would."""


class _SanitizingArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # message may embed raw argv — never used
        raise _ArgSyntaxError("argparse_error")


def _fail_line(exc: BaseException, stage: str) -> str:
    sqlstate = getattr(exc, "sqlstate", None) or "-"
    return f"wa_practices_replica: FAIL {type(exc).__name__} sqlstate={sqlstate} stage={stage} counts=n/a"


def _success_line(metrics: SyncMetrics) -> str:
    """Built ONLY from SyncMetrics' bare-int fields (see its docstring) —
    isolated from cli_main so a test can assert the exact wire format
    without a live pool."""
    return (
        f"wa_practices_replica: sync OK fly={metrics.fly} inserted={metrics.inserted} "
        f"updated={metrics.updated} unchanged={metrics.unchanged} "
        f"skipped_no_client={metrics.skipped_no_client} skipped_fk={metrics.skipped_fk} "
        f"pro_only_kept={metrics.pro_only_kept} types_inserted={metrics.types_inserted} "
        f"types_updated={metrics.types_updated} wall_ms={metrics.wall_ms}\n"
    )


async def cli_main(argv: list[str] | None = None) -> int:
    parser = _SanitizingArgumentParser(prog="wa_practices_replica")
    parser.add_argument("--sync", action="store_true",
                         help="Read Fly `practice_types`+`practices` (read-only), UPSERT both "
                              "into Pro by natural key (code / uuid), re-keying client_id "
                              "through clients.uuid.")
    parser.add_argument("--dry-run", action="store_true",
                         help="With --sync: run the identical UPSERT path and roll back — "
                              "counts are real, nothing is persisted.")
    try:
        args = parser.parse_args(argv)
    except _ArgSyntaxError as exc:
        sys.stderr.write(_fail_line(exc, "argparse") + "\n")
        return 2
    if not args.sync:
        sys.stderr.write(_fail_line(_ArgSyntaxError("missing_mode"), "argparse") + "\n")
        return 2

    stage = "env_guard"
    try:
        _guard_pro_local_env()
    except EnvGuardError as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 2
    _clear_pg_env()

    try:
        stage = "fly_read"
        fly_practice_types_rows = _fetch_fly_practice_types_rows()
        fly_rows = _fetch_fly_rows()
        stage = "connect_pro"
        pool = await asyncpg.create_pool(
            **PRO_LOCAL_CONNECT_KWARGS, min_size=1, max_size=1,
            statement_cache_size=0, command_timeout=60,
        )
        try:
            stage = "sync"
            metrics = await run_sync(
                pool, fly_rows, fly_practice_types_rows, dry_run=args.dry_run,
            )
        finally:
            await pool.close()
    except Exception as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 1

    sys.stdout.write(_success_line(metrics))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
