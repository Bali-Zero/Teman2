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


# A — init-schema + catalog index verification (both unique indexes)

_UNIQUE_INDEXES_TO_VERIFY = (
    ("public.team_promises", "uix_team_promises_msg_type", ["message_id", "promise_type"]),
    ("public.team_promise_candidates", "uix_team_promise_candidates_msg_clause",
     ["message_id", "clause_idx"]),
)

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
WHERE ix.indrelid = to_regclass($1)::oid AND i.relname = $2
"""


async def verify_unique_index(conn, table: str, index: str, columns: list[str]) -> None:
    """Verifies `index` on `table` by OID+catalog, never by name alone —
    `CREATE UNIQUE INDEX IF NOT EXISTS` silently no-ops on a same-named
    index with a DIFFERENT definition (non-unique, partial, an extra
    expression column, or a different column order). Raises RuntimeError
    naming the STATIC index name on ANY mismatch; the caller runs this
    inside the same transaction as the DDL so the exception rolls it back."""
    row = await conn.fetchrow(_INDEX_CHECK_SQL, table, index)
    if row is None:
        raise RuntimeError(f"index {index} missing or table {table} not found after init-schema")
    ok = (
        row["indisunique"] and row["indisvalid"]
        and not row["has_predicate"] and not row["has_expr"]
        and row["indnkeyatts"] == len(columns)
        and list(row["key_columns"] or []) == columns
    )
    if not ok:
        raise RuntimeError(
            f"{index} exists with an incompatible definition — abort, change nothing "
            f"(unique={row['indisunique']} valid={row['indisvalid']} "
            f"predicate={row['has_predicate']} expr={row['has_expr']} "
            f"nkeyatts={row['indnkeyatts']} columns={row['key_columns']})"
        )


async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
            for table, index, columns in _UNIQUE_INDEXES_TO_VERIFY:
                await verify_unique_index(conn, table, index, columns)


# C — errors never carry data

def _fail_line(exc: BaseException, stage: str, counts: dict[str, int] | None = None) -> str:
    sqlstate = getattr(exc, "sqlstate", None) or "-"
    counts_str = "n/a" if counts is None else ",".join(f"{k}={v}" for k, v in counts.items())
    return f"wa_team_promises: FAIL {type(exc).__name__} sqlstate={sqlstate} stage={stage} counts={counts_str}"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wa_team_promises")
    parser.add_argument("--init-schema", action="store_true",
                         help="Apply scripts/sql/pro_local/team_promises.sql "
                              "(idempotent) and verify both unique indexes, then exit. "
                              "Only mode this PR ships — scan/judge land in PR-2/PR-3.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    if not args.init_schema:
        parser.error("--init-schema is the only mode this PR ships")

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
