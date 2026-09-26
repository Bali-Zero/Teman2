"""T3 gate conditions C1 + C5 — statement-level SQL/constant cross-check.

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

C5 (PASS-WITH-CONDITIONS follow-up on PR #7366's own gate): the C1 parser
above was itself an UNDER-match — round-1's `_CREATE_TABLE_RE`/
`_ALTER_ADD_COLUMN_RE` silently skipped any statement they didn't literally
match, so a schema-qualified `ALTER TABLE public.x`, a multi-action ALTER, a
lowercase-keyword statement, or an `ALTER COLUMN ... DROP NOT NULL` would
never show up in `declared` at all — invisible to the cross-check rather than
caught by it. `parse_declared_columns` is now FAIL-CLOSED: every statement
must match one of the three shapes the SQL file uses today (`CREATE TABLE IF
NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — one or more
top-level-comma-separated actions, `CREATE UNIQUE INDEX IF NOT EXISTS`),
case-insensitive, `public.`-qualified names normalized to bare names, or it
raises `UnrecognizedSqlShapeError(index, keyword, statement)` naming exactly
which statement tripped it. NOT NULL detection also now ignores string
literals (`DEFAULT 'NOT NULL'` must not be read as a constraint).

Purely static — no DB, no asyncpg. See test_wa_team_promises_real_pg.py for
the real-Postgres companion (catalog row count against the SAME
`_REQUIRED_COLUMNS`, opt-in).
"""
from __future__ import annotations

import re

import pytest

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

# C5 allowlist — exactly the three statement shapes team_promises.sql uses
# today. Case-insensitive; `public.`-qualified table/index-target names
# normalize to the bare name (the non-capturing `(?:public\.)?` group
# discards the prefix regardless of its case).
_CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS (?:public\.)?(\w+)\s*\((.*)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ALTER_TABLE_RE = re.compile(
    r"ALTER TABLE (?:public\.)?(\w+)\s+(.*)$", re.IGNORECASE | re.DOTALL
)
_ALTER_ACTION_ADD_COLUMN_RE = re.compile(
    r"^ADD COLUMN IF NOT EXISTS\s+(\w+)\s+(.*)$", re.IGNORECASE | re.DOTALL
)
_CREATE_UNIQUE_INDEX_RE = re.compile(
    r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON\s+(?:public\.)?\w+\s*\(.*?\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
# C5 shape 8: a keyword spelled INSIDE a string literal (e.g. `DEFAULT
# 'NOT NULL'`) must not be read as a real constraint — blank literal
# contents (keeping the quotes) before scanning for NOT NULL/PRIMARY KEY.
# `''` inside a literal is SQL's own escaped single quote, not a terminator.
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")


class UnrecognizedSqlShapeError(AssertionError):
    """C5 fail-closed guard: raised by `parse_declared_columns` when a
    statement — or one action inside a multi-action ALTER — doesn't match
    the allowlist of shapes team_promises.sql uses today. Carries the
    STATEMENT's 0-based index and first keyword so a failure names exactly
    which statement tripped it, rather than the round-1 parser's silent
    skip of anything its two narrow regexes didn't literally match."""

    def __init__(self, index: int, keyword: str, statement: str):
        self.index = index
        self.keyword = keyword
        super().__init__(
            f"statement #{index} (starts {keyword!r}) is outside the C5 "
            f"allowlist: {statement[:160]!r}"
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


def _strip_string_literals(s: str) -> str:
    return _STRING_LITERAL_RE.sub("''", s)


def _parse_column_def(name: str, rest: str) -> tuple[str, str, bool]:
    """`rest` is everything after the column name up to (but not including)
    the statement's own trailing punctuation — e.g. "BIGINT NOT NULL DEFAULT
    0" or "TEXT". First token is the type (this file never uses a multi-word
    source type — TIMESTAMPTZ/BIGSERIAL/etc are each one keyword); NOT NULL
    is either explicit or implied by PRIMARY KEY, matching the production
    contract's own `notnull = explicit OR PRIMARY KEY` rule. String-literal
    contents are blanked first (C5 shape 8) so a DEFAULT like `'NOT NULL'`
    is never mistaken for the constraint."""
    tokens = rest.split()
    raw_type = tokens[0].rstrip(",").upper()
    pg_type = _TYPE_ALIASES.get(raw_type, raw_type.lower())
    upper_rest = _strip_string_literals(rest).upper()
    notnull = bool(re.search(r"\bNOT\s+NULL\b", upper_rest)) or bool(
        re.search(r"\bPRIMARY\s+KEY\b", upper_rest)
    )
    return (name.lower(), pg_type, notnull)


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


def _parse_alter_table_actions(
    index: int, statement: str, table: str, rest: str,
    declared: dict[str, set[tuple[str, str, bool]]],
) -> None:
    """`rest` is everything after the table name in an ALTER TABLE statement
    — one or more TOP-LEVEL-comma-separated actions (C5 multi-action ALTER;
    `_split_top_level_commas` already ignores commas inside parens/CHECK
    lists). EVERY action must be `ADD COLUMN IF NOT EXISTS <name> <type...>`
    (case-insensitive) — a bare `ADD <name> ...` without COLUMN, an `ADD
    COLUMN` missing `IF NOT EXISTS`, or an `ALTER COLUMN ... DROP NOT NULL /
    TYPE ...` is outside today's allowlist, so the WHOLE statement fails
    closed rather than silently dropping just that one action."""
    for action in _split_top_level_commas(rest.rstrip(",")):
        m = _ALTER_ACTION_ADD_COLUMN_RE.match(action)
        if not m:
            keyword = statement.split(None, 1)[0] if statement else ""
            raise UnrecognizedSqlShapeError(index, keyword, statement)
        name, col_rest = m.group(1), m.group(2)
        declared.setdefault(table.lower(), set()).add(_parse_column_def(name, col_rest))


def parse_declared_columns(sql: str) -> dict[str, set[tuple[str, str, bool]]]:
    """Every column the SQL text declares (CREATE TABLE body columns, plus
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS), as {table: {(name, type,
    notnull), ...}}. This is the C1/C5 cross-check parser — statement-level,
    comment-stripped, multi-line-safe, type-alias-normalized, and FAIL-CLOSED
    (C5): any statement matching NONE of the three shapes team_promises.sql
    uses today (CREATE TABLE IF NOT EXISTS, ALTER TABLE ... ADD COLUMN IF
    NOT EXISTS [, ...], CREATE UNIQUE INDEX IF NOT EXISTS) raises
    `UnrecognizedSqlShapeError` naming its index and first keyword, rather
    than the round-1 parser's silent skip of anything its two narrow regexes
    didn't literally match."""
    declared: dict[str, set[tuple[str, str, bool]]] = {}
    for index, stmt in enumerate(_statements(sql)):
        m = _CREATE_TABLE_RE.match(stmt)
        if m:
            table, body = m.group(1).lower(), m.group(2)
            for col_def in _split_top_level_commas(body):
                col_tokens = col_def.split(None, 1)
                if len(col_tokens) != 2:
                    continue  # a bare table-level constraint, none in this file
                name, rest = col_tokens
                declared.setdefault(table, set()).add(_parse_column_def(name, rest))
            continue
        m = _ALTER_TABLE_RE.match(stmt)
        if m:
            table, rest = m.group(1), m.group(2)
            _parse_alter_table_actions(index, stmt, table, rest, declared)
            continue
        if _CREATE_UNIQUE_INDEX_RE.match(stmt):
            continue  # index shape — no columns to record, verified in real-PG tests
        keyword = stmt.split(None, 1)[0] if stmt else ""
        raise UnrecognizedSqlShapeError(index, keyword, stmt)
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


# --- C5: 8 shapes the round-1 parser under-matched (stayed silently green
# on), each fed as a synthetic single-statement SQL string. Four are shapes
# we choose to SUPPORT (parsed correctly, right column/nullability); four
# are outside today's allowlist and must be REJECTED — never silently
# skipped, which is exactly what let all 8 through the round-1 parser. ---

_C5_SHAPE_CASES = [
    pytest.param(
        "ALTER TABLE public.team_promises ADD COLUMN IF NOT EXISTS c5_schema_probe TEXT;",
        ("team_promises", {("c5_schema_probe", "text", False)}),
        id="schema-qualified-ALTER-normalizes-to-bare-table",
    ),
    pytest.param(
        "ALTER TABLE team_promises ADD COLUMN c5_no_ine_probe TEXT;",
        None,
        id="ADD-COLUMN-without-IF-NOT-EXISTS-is-rejected",
    ),
    pytest.param(
        "ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS c5_multi_a TEXT, "
        "ADD COLUMN IF NOT EXISTS c5_multi_b INTEGER NOT NULL DEFAULT 0;",
        ("team_promises", {
            ("c5_multi_a", "text", False),
            ("c5_multi_b", "integer", True),
        }),
        id="multi-action-ALTER-splits-on-top-level-commas",
    ),
    pytest.param(
        "alter table team_promises add column if not exists c5_lower_probe text;",
        ("team_promises", {("c5_lower_probe", "text", False)}),
        id="lowercase-keywords-still-parse",
    ),
    pytest.param(
        "ALTER TABLE team_promises ALTER COLUMN promise_text DROP NOT NULL;",
        None,
        id="ALTER-COLUMN-DROP-NOT-NULL-is-rejected",
    ),
    pytest.param(
        "ALTER TABLE team_promises ALTER COLUMN promise_type TYPE VARCHAR;",
        None,
        id="ALTER-COLUMN-TYPE-is-rejected",
    ),
    pytest.param(
        "ALTER TABLE team_promises ADD c5_add_no_column_probe TEXT;",
        None,
        id="ADD-without-COLUMN-keyword-is-rejected",
    ),
    pytest.param(
        "ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS c5_default_probe TEXT "
        "DEFAULT 'NOT NULL';",
        ("team_promises", {("c5_default_probe", "text", False)}),
        id="DEFAULT-NOT-NULL-string-literal-is-not-a-constraint",
    ),
]


@pytest.mark.parametrize("sql, expected", _C5_SHAPE_CASES)
def test_c5_shape_is_parsed_or_rejected_never_silently_passed(sql, expected):
    """Each of the 8 C5 shapes must be either correctly parsed (support:
    schema-qualified table names, multi-action ALTER, lowercase keywords, a
    DEFAULT string literal that merely CONTAINS the words NOT NULL) or
    REJECTED outright with UnrecognizedSqlShapeError naming the offending
    statement's index and first keyword (bare ADD without IF NOT EXISTS, ADD
    without the COLUMN keyword, ALTER COLUMN ... DROP NOT NULL / TYPE ...) —
    never silently skipped, which is what let all 8 through round-1."""
    if expected is None:
        with pytest.raises(UnrecognizedSqlShapeError) as exc_info:
            parse_declared_columns(sql)
        assert exc_info.value.index == 0
        assert exc_info.value.keyword == "ALTER"
    else:
        table, columns = expected
        declared = parse_declared_columns(sql)
        assert declared[table] == columns


def test_c5_real_sql_file_has_no_statement_outside_the_allowlist():
    """Innocence, restated for C5: parsing the real file raises nothing —
    every statement in it (both CREATE TABLE bodies, all 10 single-action
    ALTERs, both CREATE UNIQUE INDEXes) matches the allowlist, and both
    tables actually got recorded (a parser that raised on nothing merely by
    matching zero statements would be a false innocence, not a real one)."""
    declared = parse_declared_columns(_SQL_PATH.read_text())  # raises on any unrecognized shape
    assert declared.keys() == {"team_promises", "team_promise_candidates"}
