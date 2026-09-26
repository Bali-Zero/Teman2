"""T3 gate condition C1 — statement-level SQL/constant cross-check.

test_wa_team_promises.py's `test_required_columns_...` already proves every
NAME the SQL file declares is a key in `_REQUIRED_COLUMNS` (and vice versa).
This file goes further: it parses each declared column's TYPE and NOT-NULL-
ness out of the SQL text itself (CREATE TABLE bodies and both single-line and
multi-line `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`), normalizes the
handful of type aliases the file uses, and compares by SET EQUALITY of
(name, type, notnull) tuples against `_REQUIRED_COLUMNS` — so a column that
exists under the right name but the WRONG type or NOT NULL-ness, not just a
missing/extra name, is caught. Three in-memory mutations (never touching the
real file on disk) prove the parser actually discriminates rather than
rubber-stamping: a multi-line ALTER adding an untracked column, a core column
retyped to a VARCHAR alias, and an ALTER-added column losing its NOT NULL.

Purely static — no DB, no asyncpg. See test_wa_team_promises_real_pg.py for
the real-Postgres companion (catalog row count against the SAME
`_REQUIRED_COLUMNS`, opt-in).
"""
from __future__ import annotations

import re

from scripts.wa_team_promises import _REQUIRED_COLUMNS, _SQL_PATH

# Every type keyword the SQL file actually uses, mapped to the canonical
# pg_catalog spelling `_REQUIRED_COLUMNS` is written in (verified by hand
# against format_type() output — see test_wa_team_promises_real_pg.py's
# 26-row catalog-completeness test for the real-PG proof this alias table
# is right, not just internally consistent).
_TYPE_ALIASES = {
    "BIGSERIAL": "bigint",
    "SERIAL": "integer",
    "BIGINT": "bigint",
    "INT8": "bigint",
    "INTEGER": "integer",
    "INT": "integer",
    "INT4": "integer",
    "TEXT": "text",
    "VARCHAR": "character varying",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "TIMESTAMPTZ": "timestamp with time zone",
}

_CREATE_TABLE_RE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\)\s*$", re.DOTALL)
_ALTER_ADD_COLUMN_RE = re.compile(
    r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)\s+(.*)$", re.DOTALL
)


def _strip_comments(sql: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def _statements(sql: str) -> list[str]:
    """Comments stripped, split on `;`, each statement's internal whitespace
    (including the newline inside a multi-line ALTER) collapsed to single
    spaces — so a statement spanning several lines parses identically to the
    same statement written on one line."""
    stripped = _strip_comments(sql)
    return [
        re.sub(r"\s+", " ", stmt).strip()
        for stmt in stripped.split(";")
        if re.sub(r"\s+", " ", stmt).strip()
    ]


def _parse_column_def(name: str, rest: str) -> tuple[str, str, bool]:
    """`rest` is everything after the column name up to (but not including)
    the statement's own trailing punctuation — e.g. "BIGINT NOT NULL DEFAULT
    0" or "TEXT". First token is the type (this file never uses a multi-word
    source type — TIMESTAMPTZ/BIGSERIAL/etc are each one keyword); NOT NULL
    is either explicit or implied by PRIMARY KEY, matching the production
    contract's own `notnull = explicit OR PRIMARY KEY` rule."""
    tokens = rest.split()
    raw_type = tokens[0].rstrip(",").upper()
    pg_type = _TYPE_ALIASES.get(raw_type, raw_type.lower())
    upper_rest = rest.upper()
    notnull = "NOT NULL" in upper_rest or "PRIMARY KEY" in upper_rest
    return (name, pg_type, notnull)


def _split_top_level_commas(body: str) -> list[str]:
    """Splits a CREATE TABLE body on commas that are NOT inside parens (so a
    type like NUMERIC(3, 2) — not used in this file today, but the split
    stays correct if one is added later — doesn't fracture a column def)."""
    parts, depth, current = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def parse_declared_columns(sql: str) -> dict[str, set[tuple[str, str, bool]]]:
    """Every column the SQL text declares (CREATE TABLE body columns, plus
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS), as {table: {(name, type,
    notnull), ...}}. This is the C1 cross-check parser — statement-level,
    comment-stripped, multi-line-safe, type-alias-normalized."""
    declared: dict[str, set[tuple[str, str, bool]]] = {}
    for stmt in _statements(sql):
        m = _CREATE_TABLE_RE.match(stmt)
        if m:
            table, body = m.group(1), m.group(2)
            for col_def in _split_top_level_commas(body):
                col_tokens = col_def.split(None, 1)
                if len(col_tokens) != 2:
                    continue  # a bare table-level constraint, none in this file
                name, rest = col_tokens
                declared.setdefault(table, set()).add(_parse_column_def(name, rest))
            continue
        m = _ALTER_ADD_COLUMN_RE.match(stmt)
        if m:
            table, name, rest = m.group(1), m.group(2), m.group(3)
            declared.setdefault(table, set()).add(_parse_column_def(name, rest))
    return declared


def _required_as_tuples() -> dict[str, set[tuple[str, str, bool]]]:
    return {table: set(cols) for table, cols in _REQUIRED_COLUMNS.items()}


# --- innocence: the real file, parsed, matches _REQUIRED_COLUMNS exactly ---


def test_sql_file_columns_match_required_columns_by_name_type_and_notnull():
    declared = parse_declared_columns(_SQL_PATH.read_text())
    required = _required_as_tuples()
    assert declared.keys() == required.keys()
    for table in required:
        assert declared[table] == required[table], (
            f"{table}: declared-vs-required mismatch — "
            f"declared-only={declared[table] - required[table]} "
            f"required-only={required[table] - declared[table]}"
        )


# --- guilt: three in-memory mutations, none touching the file on disk ---


def test_guilt_multiline_alter_adding_untracked_column_is_detected():
    """A genuinely multi-line ALTER (the newline sits INSIDE the statement,
    between table name and ADD COLUMN) — proves the collapse-then-split
    handles it, and that an extra column the contract never declared shows
    up as a declared-only surplus."""
    sql = _SQL_PATH.read_text() + (
        "\n\nALTER TABLE team_promises\n"
        "  ADD COLUMN IF NOT EXISTS drift_probe TEXT;\n"
    )
    declared = parse_declared_columns(sql)
    required = _required_as_tuples()
    assert ("drift_probe", "text", False) in declared["team_promises"]
    assert declared["team_promises"] != required["team_promises"]
    assert declared["team_promises"] - required["team_promises"] == {
        ("drift_probe", "text", False)
    }


def test_guilt_core_column_retyped_to_varchar_alias_is_detected():
    """promise_text is TEXT NOT NULL in the required contract; retype it to
    VARCHAR (a real Postgres alias, not a typo) and the normalized type no
    longer matches — this is exactly the round-2 gap C1 exists to close,
    since a bare name-only check would have stayed green."""
    sql = _SQL_PATH.read_text().replace(
        "promise_text              TEXT NOT NULL,",
        "promise_text              VARCHAR NOT NULL,",
    )
    assert "VARCHAR NOT NULL" in sql  # the replace actually matched something
    declared = parse_declared_columns(sql)
    required = _required_as_tuples()
    assert ("promise_text", "text", True) in required["team_promises"]
    assert ("promise_text", "text", True) not in declared["team_promises"]
    assert ("promise_text", "character varying", True) in declared["team_promises"]
    assert declared["team_promises"] != required["team_promises"]


def test_guilt_alter_added_column_missing_not_null_is_detected():
    """attempts is INTEGER NOT NULL DEFAULT 0 in the candidates table; drop
    the NOT NULL and the tuple's third element flips, so set equality
    against _REQUIRED_COLUMNS (which requires notnull=True) fails."""
    sql = _SQL_PATH.read_text().replace(
        "ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;",
        "ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;",
    )
    assert "ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;" in sql
    declared = parse_declared_columns(sql)
    required = _required_as_tuples()
    assert ("attempts", "integer", True) in required["team_promise_candidates"]
    assert ("attempts", "integer", False) in declared["team_promise_candidates"]
    assert ("attempts", "integer", True) not in declared["team_promise_candidates"]
    assert declared["team_promise_candidates"] != required["team_promise_candidates"]
