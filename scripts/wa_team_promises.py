"""T3 promise gate — PRO-LOCAL (owner ruling 2026-09-25, Symbiosis Law 2:
data never leaves Pro). PR-1 of the #7316 re-spec: schema + connection guard
only; scanner and judge ship in PR-2/PR-3.

CLI: apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py --init-schema

Applies scripts/sql/pro_local/team_promises.sql in ONE transaction, verifies
both unique indexes against pg_catalog INSIDE it, ROLLBACK on any mismatch.
Connection is Pro-local ONLY via explicit kwargs (no DSN/URL parsing);
`_guard_pro_local_env` refuses (exit 2) before any connect attempt if any
`FLY_*` env var is present at all, even empty; PG* libpq vars are cleared so
they can never override the kwargs. Every other error path prints ONLY
`wa_team_promises: FAIL <Type> sqlstate=<code|-> stage=<name> counts=<...>`
— never the exception message, DETAIL or a traceback.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

logger = logging.getLogger("wa_team_promises")

_SQL_PATH = Path(__file__).resolve().parent / "sql" / "pro_local" / "team_promises.sql"

# B — Pro-local connection guard (explicit kwargs, no DSN/URL parsing)

PRO_LOCAL_CONNECT_KWARGS = {
    "host": "127.0.0.1", "port": 5432, "database": "nuzantara_dev", "user": "nuzantara",
}

# Cleared so libpq env vars can never override the kwargs above — round-2
# review on #7316 caught a DSN-string guard walkable via `?host=` or PGHOST.
_PG_ENV_VARS_TO_CLEAR = ("PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE")


class EnvGuardError(RuntimeError):
    """Raised by _guard_pro_local_env — never carries an env value in str()."""


def _guard_pro_local_env() -> None:
    """Refuses if ANY `FLY_*` var is present, even empty — presence alone
    means this process runs (or is probed) under a Fly-graded environment,
    the one place Symbiosis Law 2 forbids this data from reaching."""
    if any(k.startswith("FLY_") for k in os.environ):
        raise EnvGuardError("fly_env_detected")


def _clear_pg_env() -> None:
    for var in _PG_ENV_VARS_TO_CLEAR:
        os.environ.pop(var, None)


# A — init-schema + catalog verification (columns, then both unique indexes)

# Every identifier a SchemaMismatchError can carry — closed set, so the
# sanitized fail line can safely print `.identifier` without ever risking a
# caller-influenced string (round-1 review finding #2).
_ALLOWED_SCHEMA_IDENTIFIERS = frozenset({
    "uix_team_promises_msg_type", "uix_team_promise_candidates_msg_clause",
    "team_promises", "team_promise_candidates",
})


class SchemaMismatchError(RuntimeError):
    """Carries ONLY a STATIC allowlisted identifier; str(exc) (the raw
    diagnostic) is never what _fail_line prints — only .identifier is."""

    def __init__(self, identifier: str, detail: str = ""):
        self.identifier = identifier if identifier in _ALLOWED_SCHEMA_IDENTIFIERS else "unknown"
        super().__init__(detail or identifier)


_REQUIRED_COLUMNS = {
    "team_promises": {"thread_key": "text", "team_member_email": "text",
                       "extractor_version": "text", "resolution_kind": "text"},
    "team_promise_candidates": {"cue": "text", "due_at_hint": "text", "status": "text",
                                 "attempts": "integer", "last_attempt_at": "timestamp with time zone",
                                 "created_at": "timestamp with time zone"},
}

_COLUMN_CHECK_SQL = """
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = $1
"""


async def verify_required_columns(conn, table: str) -> None:
    """A pre-existing mig-200-shaped team_promises may be missing the
    columns this PR adds by ALTER; a same-named column of the WRONG type
    would no-op silently too. Verifies name+type via information_schema for
    every required column; raises SchemaMismatchError(table) on ANY gap."""
    rows = await conn.fetch(_COLUMN_CHECK_SQL, table)
    present = {r["column_name"]: r["data_type"] for r in rows}
    required = _REQUIRED_COLUMNS[table]
    if any(present.get(col) != typ for col, typ in required.items()):
        raise SchemaMismatchError(table, f"{table} missing/mistyped required column(s)")


_INDEX_CHECK_SQL = """
SELECT ix.indisunique, ix.indisvalid, ix.indnkeyatts,
       ix.indpred IS NOT NULL AS has_predicate,
       ix.indexprs IS NOT NULL AS has_expr,
       (SELECT array_agg(a.attname ORDER BY o.ord)
        FROM unnest(ix.indkey) WITH ORDINALITY AS o(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = o.attnum
        WHERE o.ord <= ix.indnkeyatts) AS key_columns
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
WHERE ix.indrelid = to_regclass('public.' || $1)::oid AND i.relname = $2
"""


async def verify_unique_index(conn, table: str, index: str, columns: list[str]) -> None:
    """Verifies `index` on `table` by OID+catalog, never by name alone —
    `CREATE UNIQUE INDEX IF NOT EXISTS` silently no-ops on a same-named
    index with a DIFFERENT definition. Raises SchemaMismatchError(index) on
    ANY mismatch, inside the DDL's own transaction, so it rolls back."""
    row = await conn.fetchrow(_INDEX_CHECK_SQL, table, index)
    if row is None:
        raise SchemaMismatchError(index, f"index {index} missing on {table} after init-schema")
    ok = (
        row["indisunique"] and row["indisvalid"]
        and not row["has_predicate"] and not row["has_expr"]
        and row["indnkeyatts"] == len(columns)
        and list(row["key_columns"] or []) == columns
    )
    if not ok:
        raise SchemaMismatchError(index, f"{index} exists with an incompatible definition")


_TABLES_TO_VERIFY = ("team_promises", "team_promise_candidates")
_UNIQUE_INDEXES_TO_VERIFY = (
    ("team_promises", "uix_team_promises_msg_type", ["message_id", "promise_type"]),
    ("team_promise_candidates", "uix_team_promise_candidates_msg_clause",
     ["message_id", "clause_idx"]),
)


async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
            for table in _TABLES_TO_VERIFY:
                await verify_required_columns(conn, table)
            for table, index, columns in _UNIQUE_INDEXES_TO_VERIFY:
                await verify_unique_index(conn, table, index, columns)


# C — errors never carry data, and neither does argument/log-level parsing

def _fail_line(exc: BaseException, stage: str, counts: dict[str, int] | None = None) -> str:
    sqlstate = getattr(exc, "sqlstate", None) or "-"
    counts_str = "n/a" if counts is None else ",".join(f"{k}={v}" for k, v in counts.items())
    line = f"wa_team_promises: FAIL {type(exc).__name__} sqlstate={sqlstate} stage={stage} counts={counts_str}"
    identifier = getattr(exc, "identifier", None)
    return line if identifier is None else f"{line} identifier={identifier}"


_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class _ArgSyntaxError(RuntimeError):
    """Raised in place of argparse's own error() — never carries the raw
    argv token argparse's default message would (round-1 review #3)."""


class _SanitizingArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # message may embed raw argv — never used
        raise _ArgSyntaxError("argparse_error")


async def cli_main(argv: list[str] | None = None) -> int:
    parser = _SanitizingArgumentParser(prog="wa_team_promises")
    parser.add_argument("--init-schema", action="store_true",
                         help="Apply scripts/sql/pro_local/team_promises.sql "
                              "(idempotent) and verify columns + both unique indexes, then exit. "
                              "Only mode this PR ships — scan/judge land in PR-2/PR-3.")
    parser.add_argument("--log-level", default="INFO")
    try:
        args = parser.parse_args(argv)
    except _ArgSyntaxError as exc:
        sys.stderr.write(_fail_line(exc, "argparse") + "\n")
        return 2
    log_level = args.log_level if args.log_level in _LOG_LEVELS else "INFO"
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    if not args.init_schema:
        sys.stderr.write(_fail_line(_ArgSyntaxError("missing_init_schema"), "argparse") + "\n")
        return 2

    stage = "env_guard"
    try:
        _guard_pro_local_env()
    except EnvGuardError as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 2
    _clear_pg_env()

    try:
        stage = "connect"
        pool = await asyncpg.create_pool(
            **PRO_LOCAL_CONNECT_KWARGS, min_size=1, max_size=1,
            statement_cache_size=0, command_timeout=60,
        )
        try:
            stage = "init_schema"
            await run_init_schema(pool)
        finally:
            await pool.close()
        sys.stdout.write("wa_team_promises: init-schema OK\n")
        return 0
    except Exception as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
