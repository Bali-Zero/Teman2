"""T3 gate conditions C1 + C5 — statement-level SQL/constant cross-check.

test_wa_team_promises.py's `test_required_columns_...` already proves every
NAME the SQL file declares is a key in `_REQUIRED_COLUMNS` (and vice versa).
This file goes further: it parses each declared column's TYPE and NOT-NULL-
ness out of the SQL text itself, normalizes the handful of type aliases the
file uses, and compares by SET EQUALITY of (name, type, notnull) tuples
against `_REQUIRED_COLUMNS` — so a column that exists under the right name
but the WRONG type or NOT NULL-ness, not just a missing/extra name, is
caught.

C5 (PASS-WITH-CONDITIONS follow-up on PR #7366's own gate) — ROUND 0: the C1
parser above was itself an UNDER-match — its two regexes silently skipped
any statement they didn't literally match, so a schema-qualified `ALTER
TABLE public.x`, a multi-action ALTER, a lowercase-keyword statement, or an
`ALTER COLUMN ... DROP NOT NULL` would never show up in `declared` at all —
invisible to the cross-check rather than caught by it. Round 0 made
`parse_declared_columns` allowlist-based on those three statement SHAPES via
regex.

ROUND 1 (Codex FIX-FIRST on Round 0): regex-over-text is not a parser —
comments/strings/quoting are CONTEXT-SENSITIVE, and no regex splits
correctly on `;`/`,` when either can legally sit inside a string or a
`/* */`/`$$...$$` block a regex doesn't know about. `parse_declared_columns`
is now backed by an actual TOKENIZER (`_tokenize`): a single left-to-right
pass that recognizes string literals and `--` comments IN CONTEXT (so `;`,
`,` and keyword-looking text INSIDE either are just data, never structure),
splits statements on `;` TOKENS, and REJECTS outright — never silently — on
`/`, `*`, `$` or `"` appearing OUTSIDE a string (this file uses none of them
for real syntax: they mean an unsupported `/* */` comment, `$$...$$`
dollar-quoting, or a quoted identifier). Column definitions are parsed by an
explicit grammar (`ident type [(args)] [NOT NULL|NULL|DEFAULT <allowed
value>|PRIMARY KEY|CHECK (...)]*`, any order) instead of a NOT-NULL
substring scan, so a CHECK/DEFAULT clause's own contents can never leak a
fake NOT NULL (or hide a real one) into the column's own nullability. See
`test_round1_column_body_is_parsed_or_rejected_never_silently_passed` for
the 16 shapes this closes.

Purely static — no DB, no asyncpg. See test_wa_team_promises_real_pg.py for
the real-Postgres companion (catalog row count against the SAME
`_REQUIRED_COLUMNS`, opt-in).
"""
from __future__ import annotations

from typing import NamedTuple

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

# serial-family pseudo-types create a NOT NULL column (backed by a DEFAULT
# nextval(...)) regardless of PRIMARY KEY — Round-1 finding: a bare `id
# BIGSERIAL` (no explicit PRIMARY KEY on IT) was wrongly read as nullable.
_IMPLICIT_NOT_NULL_TYPES = frozenset({"SERIAL", "BIGSERIAL", "SMALLSERIAL"})

# Characters this file never uses for real syntax OUTSIDE a string literal —
# Round-1 finding: round-0's regex-over-text let a `/* ... */` block
# comment, a `$$...$$` dollar-quoted string, or a `"quoted identifier"` hide
# an arbitrary statement/column (or fake/erase a NOT NULL) from it. The
# tokenizer refuses the moment one appears anywhere outside a string.
_BANNED_OUTSIDE_STRINGS = frozenset("/*$\"")
_PUNCT_CHARS = "(),;."

# Top-level CREATE TABLE body elements this file never uses — a bare table
# constraint, not a column definition. REJECTED rather than misread as a
# column literally named e.g. "constraint" (Round-1 finding).
_NON_COLUMN_TABLE_ELEMENTS = frozenset(
    {"CONSTRAINT", "CHECK", "PRIMARY", "UNIQUE", "FOREIGN", "LIKE"}
)


class UnrecognizedSqlShapeError(AssertionError):
    """C5 fail-closed guard: raised by `parse_declared_columns` when a
    statement — or an action/column/DEFAULT/table-element inside one —
    doesn't match the allowlist of shapes team_promises.sql uses today.
    Carries the STATEMENT's 0-based index and first keyword so a failure
    names exactly which statement tripped it, rather than a regex's silent
    skip of anything it didn't literally match."""

    def __init__(self, index: int, keyword: str, statement: str):
        self.index = index
        self.keyword = keyword
        super().__init__(
            f"statement #{index} (starts {keyword!r}) is outside the C5 "
            f"allowlist: {statement[:160]!r}"
        )


class _Token(NamedTuple):
    kind: str  # "WORD" | "NUMBER" | "STRING" | "PUNCT"
    value: str  # for STRING: the UNESCAPED content (quotes/`''` resolved)
    start: int
    end: int


def _tokenize(sql: str) -> list[_Token]:
    """Round-1: a single left-to-right lexer pass, not a regex pre-pass —
    string literals and `--` comments are recognized IN CONTEXT, so neither
    can hide inside the other (round-0's separate, string-blind comment
    stripper is exactly how `DEFAULT '--' NOT NULL` used to lose its own NOT
    NULL: it "commented out" text that was really inside a string).
    Statement boundaries (`;`) are TOKENS, never character offsets, so one
    can't hide inside a string either. Rejects outright — never silently —
    the instant `/`, `*`, `$` or `"` appears OUTSIDE a string: this file
    uses none of them for real syntax, so any of the four means a `/* */`
    comment, a `$$...$$` dollar-quoted string, a quoted identifier, or a
    stray character — every one of them outside today's allowlist."""
    tokens: list[_Token] = []
    i, n = 0, len(sql)
    stmt_index = 0
    pending = False
    while i < n:
        c = sql[i]
        if c in " \t\r\n":
            i += 1
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if c == "'":
            j = i + 1
            buf: list[str] = []
            while True:
                if j >= n:
                    raise UnrecognizedSqlShapeError(
                        stmt_index, "'",
                        f"unterminated string literal starting at offset {i}",
                    )
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    j += 1
                    break
                buf.append(sql[j])
                j += 1
            tokens.append(_Token("STRING", "".join(buf), i, j))
            pending = True
            i = j
            continue
        if c in _BANNED_OUTSIDE_STRINGS:
            raise UnrecognizedSqlShapeError(
                stmt_index, c,
                f"banned character {c!r} outside a string literal at offset "
                f"{i} — block comments, dollar-quoting and quoted "
                "identifiers are outside today's allowlist",
            )
        if sql.startswith("::", i):
            tokens.append(_Token("PUNCT", "::", i, i + 2))
            pending = True
            i += 2
            continue
        if c == ";":
            tokens.append(_Token("PUNCT", ";", i, i + 1))
            if pending:
                stmt_index += 1
            pending = False
            i += 1
            continue
        if c in _PUNCT_CHARS:
            tokens.append(_Token("PUNCT", c, i, i + 1))
            pending = True
            i += 1
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            tokens.append(_Token("WORD", sql[i:j], i, j))
            pending = True
            i = j
            continue
        if c.isdigit():
            j = i
            while j < n and sql[j].isdigit():
                j += 1
            tokens.append(_Token("NUMBER", sql[i:j], i, j))
            pending = True
            i = j
            continue
        raise UnrecognizedSqlShapeError(
            stmt_index, c, f"unexpected character {c!r} at offset {i}"
        )
    return tokens


def _split_into_statements(tokens: list[_Token]) -> list[list[_Token]]:
    """Splits on `;` TOKENS — never possible inside a string, since a `;`
    inside quotes is folded into a STRING token's value, never emitted as
    its own PUNCT token. Empty statements (a stray leading/trailing/doubled
    `;`) are dropped, matching the `pending`-gated numbering `_tokenize`
    already uses for its own mid-lex errors."""
    statements: list[list[_Token]] = []
    current: list[_Token] = []
    for tok in tokens:
        if tok.kind == "PUNCT" and tok.value == ";":
            if current:
                statements.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        statements.append(current)
    return statements


def _kw(tok: _Token | None) -> str | None:
    return tok.value.upper() if tok is not None and tok.kind == "WORD" else None


def _stmt_text(sql: str, stmt_tokens: list[_Token]) -> str:
    return sql[stmt_tokens[0].start: stmt_tokens[-1].end]


def _find_matching_close(
    tokens: list[_Token], open_pos: int, index: int, sql: str, stmt_tokens: list[_Token]
) -> int:
    depth = 0
    for p in range(open_pos, len(tokens)):
        tok = tokens[p]
        if tok.kind == "PUNCT" and tok.value == "(":
            depth += 1
        elif tok.kind == "PUNCT" and tok.value == ")":
            depth -= 1
            if depth == 0:
                return p
    raise UnrecognizedSqlShapeError(index, "(", _stmt_text(sql, stmt_tokens))


def _split_top_level_commas_tok(tokens: list[_Token]) -> list[list[_Token]]:
    """Token-level top-level-comma split: depth is tracked over PUNCT
    `(`/`)` tokens only, so a comma INSIDE a STRING token (the whole literal
    is already one opaque token — Round-1 finding: `DEFAULT 'x, ghost
    INTEGER'` must never fracture into two columns) or inside a CHECK/args
    parenthesis never counts as a separator."""
    parts: list[list[_Token]] = []
    current: list[_Token] = []
    depth = 0
    for tok in tokens:
        if tok.kind == "PUNCT" and tok.value == "(":
            depth += 1
        elif tok.kind == "PUNCT" and tok.value == ")":
            depth -= 1
        if tok.kind == "PUNCT" and tok.value == "," and depth == 0:
            parts.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        parts.append(current)
    return parts


def _read_qualified_name(
    tokens: list[_Token], pos: int, index: int, sql: str, stmt_tokens: list[_Token]
) -> tuple[str, int]:
    """A bare or `public.`-qualified identifier — the schema prefix (any
    case) is discarded, keeping only the bare name, lowercased (unquoted
    Postgres identifiers fold to lowercase; quoted ones are rejected
    outright at the tokenizer, so lowercasing here is always correct)."""
    if pos >= len(tokens) or tokens[pos].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
    name = tokens[pos].value
    pos += 1
    if pos < len(tokens) and tokens[pos].kind == "PUNCT" and tokens[pos].value == ".":
        pos += 1
        if pos >= len(tokens) or tokens[pos].kind != "WORD":
            raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
        name = tokens[pos].value
        pos += 1
    return name.lower(), pos


def _parse_default_value(
    tokens: list[_Token], pos: int, index: int, sql: str, stmt_tokens: list[_Token]
) -> int:
    """Consumes ONE allowed DEFAULT value, returns the position right after
    it. Allowed shapes are exactly the ones team_promises.sql uses today: a
    boolean literal, an integer literal, `now()`, or a single-quoted string
    literal (optionally `::type`-cast — not used yet, allowed defensively).
    ANYTHING else — a parenthesised expression, `IS NOT NULL`, an unlisted
    function call — is REJECTED (Round-1 finding: `DEFAULT (NULL IS NOT
    NULL)` used to be read as a real, if odd, default and left `resolved`
    nullable)."""
    if pos >= len(tokens):
        raise UnrecognizedSqlShapeError(index, "DEFAULT", _stmt_text(sql, stmt_tokens))
    tok = tokens[pos]
    if tok.kind == "WORD" and tok.value.upper() in {"TRUE", "FALSE"}:
        return pos + 1
    if tok.kind == "NUMBER":
        return pos + 1
    if tok.kind == "WORD" and tok.value.upper() == "NOW":
        if (
            pos + 2 < len(tokens)
            and tokens[pos + 1].kind == "PUNCT" and tokens[pos + 1].value == "("
            and tokens[pos + 2].kind == "PUNCT" and tokens[pos + 2].value == ")"
        ):
            return pos + 3
        raise UnrecognizedSqlShapeError(index, "DEFAULT", _stmt_text(sql, stmt_tokens))
    if tok.kind == "STRING":
        pos += 1
        if (
            pos + 1 < len(tokens)
            and tokens[pos].kind == "PUNCT" and tokens[pos].value == "::"
            and tokens[pos + 1].kind == "WORD"
        ):
            pos += 2
        return pos
    raise UnrecognizedSqlShapeError(index, "DEFAULT", _stmt_text(sql, stmt_tokens))


def _parse_column_def(
    tokens: list[_Token], index: int, sql: str, stmt_tokens: list[_Token]
) -> tuple[str, str, bool]:
    """`ident type [(args)] [NOT NULL | NULL | DEFAULT <allowed value> |
    PRIMARY KEY | CHECK (...)]*`, clauses in ANY order (the real file mixes
    them: `resolved BOOLEAN NOT NULL DEFAULT false`, `status TEXT NOT NULL
    DEFAULT 'unjudged' CHECK (...)`). NOT NULL is explicit, implied by
    PRIMARY KEY, or implied by a serial-family type (Round-1: `id
    BIGSERIAL` alone). `(args)` and `CHECK (...)` are consumed as balanced,
    OPAQUE parens — their contents are never scanned for keywords, which is
    exactly what stops `CHECK (c IS NOT NULL OR true)` from leaking a fake
    NOT NULL into this column's own nullability (Round-1 finding: round-0's
    NOT-NULL check scanned the whole clause tail as one string)."""
    if not tokens or tokens[0].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
    name = tokens[0].value.lower()
    if len(tokens) < 2 or tokens[1].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))
    raw_type = tokens[1].value.upper()
    pos = 2
    if pos < len(tokens) and tokens[pos].kind == "PUNCT" and tokens[pos].value == "(":
        pos = _find_matching_close(tokens, pos, index, sql, stmt_tokens) + 1
    notnull_explicit = False
    primary_key = False
    while pos < len(tokens):
        w = _kw(tokens[pos])
        nxt = _kw(tokens[pos + 1]) if pos + 1 < len(tokens) else None
        if w == "NOT" and nxt == "NULL":
            notnull_explicit = True
            pos += 2
            continue
        if w == "NULL":
            pos += 1
            continue
        if w == "DEFAULT":
            pos = _parse_default_value(tokens, pos + 1, index, sql, stmt_tokens)
            continue
        if w == "PRIMARY" and nxt == "KEY":
            primary_key = True
            pos += 2
            continue
        if w == "CHECK":
            if pos + 1 >= len(tokens) or not (
                tokens[pos + 1].kind == "PUNCT" and tokens[pos + 1].value == "("
            ):
                raise UnrecognizedSqlShapeError(index, "CHECK", _stmt_text(sql, stmt_tokens))
            pos = _find_matching_close(tokens, pos + 1, index, sql, stmt_tokens) + 1
            continue
        raise UnrecognizedSqlShapeError(
            index, w or tokens[pos].value, _stmt_text(sql, stmt_tokens)
        )
    pg_type = _TYPE_ALIASES.get(raw_type, raw_type.lower())
    notnull = notnull_explicit or primary_key or raw_type in _IMPLICIT_NOT_NULL_TYPES
    return name, pg_type, notnull


def _parse_create_table(
    index: int, stmt_tokens: list[_Token], sql: str,
    declared: dict[str, set[tuple[str, str, bool]]],
) -> None:
    table, pos = _read_qualified_name(stmt_tokens, 5, index, sql, stmt_tokens)
    if pos >= len(stmt_tokens) or not (
        stmt_tokens[pos].kind == "PUNCT" and stmt_tokens[pos].value == "("
    ):
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    close_pos = _find_matching_close(stmt_tokens, pos, index, sql, stmt_tokens)
    if close_pos != len(stmt_tokens) - 1:
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    body = stmt_tokens[pos + 1: close_pos]
    for element in _split_top_level_commas_tok(body):
        if not element:
            raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
        first_kw = _kw(element[0])
        if first_kw in _NON_COLUMN_TABLE_ELEMENTS:
            raise UnrecognizedSqlShapeError(index, first_kw, _stmt_text(sql, stmt_tokens))
        name, pg_type, notnull = _parse_column_def(element, index, sql, stmt_tokens)
        declared.setdefault(table, set()).add((name, pg_type, notnull))


def _parse_alter_table(
    index: int, stmt_tokens: list[_Token], sql: str,
    declared: dict[str, set[tuple[str, str, bool]]],
) -> None:
    table, pos = _read_qualified_name(stmt_tokens, 2, index, sql, stmt_tokens)
    action_tokens = stmt_tokens[pos:]
    if not action_tokens:
        raise UnrecognizedSqlShapeError(index, "ALTER", _stmt_text(sql, stmt_tokens))
    for action in _split_top_level_commas_tok(action_tokens):
        ok = (
            len(action) >= 5
            and _kw(action[0]) == "ADD"
            and _kw(action[1]) == "COLUMN"
            and _kw(action[2]) == "IF"
            and _kw(action[3]) == "NOT"
            and _kw(action[4]) == "EXISTS"
        )
        if not ok:
            raise UnrecognizedSqlShapeError(index, "ALTER", _stmt_text(sql, stmt_tokens))
        name, pg_type, notnull = _parse_column_def(action[5:], index, sql, stmt_tokens)
        declared.setdefault(table, set()).add((name, pg_type, notnull))


def _parse_create_unique_index(index: int, stmt_tokens: list[_Token], sql: str) -> None:
    pos = 6  # past CREATE UNIQUE INDEX IF NOT EXISTS
    if pos >= len(stmt_tokens) or stmt_tokens[pos].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    pos += 1  # the index's own name — never schema-qualified in real syntax
    on_kw = _kw(stmt_tokens[pos]) if pos < len(stmt_tokens) else None
    if on_kw != "ON":
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    pos += 1
    _, pos = _read_qualified_name(stmt_tokens, pos, index, sql, stmt_tokens)
    if pos >= len(stmt_tokens) or not (
        stmt_tokens[pos].kind == "PUNCT" and stmt_tokens[pos].value == "("
    ):
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    close_pos = _find_matching_close(stmt_tokens, pos, index, sql, stmt_tokens)
    if close_pos != len(stmt_tokens) - 1:
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))


def parse_declared_columns(sql: str) -> dict[str, set[tuple[str, str, bool]]]:
    """Every column the SQL text declares (CREATE TABLE body columns, plus
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS), as {table: {(name, type,
    notnull), ...}}. Round-1: tokenizer-based, not regex-over-text (see
    `_tokenize`'s docstring for why that distinction is load-bearing).
    FAIL-CLOSED: any statement — or column/DEFAULT/top-level table element
    inside one — outside the allowlist raises `UnrecognizedSqlShapeError`
    naming its statement index and first keyword, never silently skipping
    it."""
    tokens = _tokenize(sql)
    statements = _split_into_statements(tokens)
    declared: dict[str, set[tuple[str, str, bool]]] = {}
    for index, stmt_tokens in enumerate(statements):
        if not stmt_tokens:
            continue

        def kw(pos: int, _toks: list[_Token] = stmt_tokens) -> str | None:
            return _kw(_toks[pos]) if pos < len(_toks) else None

        if kw(0) == "CREATE" and kw(1) == "TABLE" and kw(2) == "IF" and kw(3) == "NOT" and kw(4) == "EXISTS":
            _parse_create_table(index, stmt_tokens, sql, declared)
        elif kw(0) == "ALTER" and kw(1) == "TABLE":
            _parse_alter_table(index, stmt_tokens, sql, declared)
        elif (
            kw(0) == "CREATE" and kw(1) == "UNIQUE" and kw(2) == "INDEX"
            and kw(3) == "IF" and kw(4) == "NOT" and kw(5) == "EXISTS"
        ):
            _parse_create_unique_index(index, stmt_tokens, sql)
        else:
            raise UnrecognizedSqlShapeError(
                index, kw(0) or stmt_tokens[0].value, _stmt_text(sql, stmt_tokens)
            )
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


# --- C5 Round 0: 8 shapes the pre-tokenizer regex parser under-matched
# (stayed silently green on), each fed as a synthetic single-statement SQL
# string. Still exercised against the Round-1 tokenizer below — same
# expected outcomes, stronger implementation. ---

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
    """Each of the 8 Round-0 C5 shapes must be either correctly parsed
    (support: schema-qualified table names, multi-action ALTER, lowercase
    keywords, a DEFAULT string literal that merely CONTAINS the words NOT
    NULL) or REJECTED outright with UnrecognizedSqlShapeError naming the
    offending statement's index and first keyword — never silently
    skipped."""
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


# --- Round 1 (Codex FIX-FIRST on the Round-0 regex parser): 16 column
# bodies the regex accepted SILENTLY with a WRONG result (invented columns,
# dropped columns, flipped nullability), each wrapped as a complete
# `CREATE TABLE IF NOT EXISTS t (<body>);`. Some are shapes we choose to
# SUPPORT (parsed to the column set actually shown); the rest are outside
# today's allowlist and must be REJECTED. ---

_ROUND1_COLUMN_BODY_CASES = [
    pytest.param("c TEXT /* NOT NULL */", None, id="block-comment-hides-not-null"),
    pytest.param("c TEXT NULL /* NOT NULL */", None, id="explicit-null-then-block-comment"),
    pytest.param("c TEXT /* , ghost INTEGER NOT NULL */", None, id="block-comment-hides-a-comma"),
    pytest.param("c TEXT /* ( */, hidden INTEGER", None, id="block-comment-hides-an-open-paren"),
    pytest.param("c TEXT DEFAULT $$NOT NULL$$", None, id="dollar-quoted-default"),
    pytest.param(
        'c TEXT CONSTRAINT "NOT NULL" CHECK (true)', None,
        id="quoted-identifier-constraint-name",
    ),
    pytest.param("c BOOLEAN DEFAULT (NULL IS NOT NULL)", None, id="parenthesised-default-expression"),
    pytest.param(
        "c TEXT CHECK (c IS NOT NULL OR true)",
        {("c", "text", False)},
        id="check-clause-is-opaque-to-notnull-scanning",
    ),
    pytest.param(
        "c TEXT DEFAULT '(', hidden INTEGER",
        {("c", "text", False), ("hidden", "integer", False)},
        id="string-default-containing-a-paren-does-not-hide-the-next-column",
    ),
    pytest.param(
        "c TEXT DEFAULT '--' NOT NULL",
        {("c", "text", True)},
        id="string-default-containing-a-dash-dash-does-not-eat-not-null",
    ),
    pytest.param("c TEXT NOT /* comment */ NULL", None, id="block-comment-inside-not-null"),
    pytest.param("c TEXT, CONSTRAINT pk PRIMARY KEY (c)", None, id="table-level-constraint-rejected"),
    pytest.param('"C" TEXT', None, id="quoted-identifier-column-name"),
    pytest.param(
        'c TEXT CHECK ("NOT NULL" IS NULL), "NOT NULL" TEXT', None,
        id="quoted-identifier-inside-check-and-as-a-name",
    ),
    pytest.param(
        "c TEXT DEFAULT 'x, ghost INTEGER'",
        {("c", "text", False)},
        id="string-default-containing-a-comma-does-not-invent-a-column",
    ),
    pytest.param("c BIGSERIAL", {("c", "bigint", True)}, id="bare-bigserial-implies-not-null"),
]


@pytest.mark.parametrize("body, expected", _ROUND1_COLUMN_BODY_CASES)
def test_round1_column_body_is_parsed_or_rejected_never_silently_passed(body, expected):
    """Codex Round-1 FIX-FIRST finding: these 16 column bodies were each
    accepted SILENTLY by the Round-0 regex parser with a WRONG result
    (invented a phantom column, dropped a real one, or flipped a
    nullability flag). Each must now either be REJECTED (comments,
    dollar-quotes, quoted identifiers, an unsupported DEFAULT expression, a
    table-level constraint misread as a column) or parsed to the column set
    actually shown — never silently passed with the wrong answer."""
    sql = f"CREATE TABLE IF NOT EXISTS t ({body});"
    if expected is None:
        with pytest.raises(UnrecognizedSqlShapeError):
            parse_declared_columns(sql)
    else:
        declared = parse_declared_columns(sql)
        assert declared["t"] == expected


# The first trick's two apparent `;`s are BOTH inside what a string-aware
# reader sees as one long single-quoted literal (opened by the `'` right
# after the first DEFAULT, closed only by the SECOND `'` — the one right
# before the trailing `');` supplies `t`'s own missing `)` for free): a
# text-level `;`-split sees two CREATE TABLEs; the tokenizer correctly sees
# ONE statement, ONE table `t`, ONE column `c` whose DEFAULT value happens
# to be a garbled string — never a `ghost` table. Verified directly against
# `_tokenize`'s own token stream, not just by eye (round-1's own lesson).
_ROUND1_SEMICOLON_TRICK_STRING_HIDES_A_STATEMENT = (
    "CREATE TABLE IF NOT EXISTS t (c TEXT DEFAULT '); "
    "CREATE TABLE IF NOT EXISTS ghost (x TEXT DEFAULT ');"
)
# The second trick's `;` sits inside what LOOKS like a `/* ... */` block
# comment to a human — but this file supports no block comments at all, so
# the tokenizer rejects on the very first `/`, long before it would matter
# whether a `ghost` table appears anywhere in the (never parsed) rest.
_ROUND1_SEMICOLON_TRICK_COMMENT_HIDES_A_STATEMENT = (
    "CREATE TABLE IF NOT EXISTS t (c TEXT /* ); "
    "CREATE TABLE IF NOT EXISTS ghost (x TEXT */);"
)


def test_round1_semicolon_trick_string_hides_a_statement_but_creates_only_t():
    """Codex Round-1 finding: this SQL LOOKS like two `CREATE TABLE`
    statements split on two `;`s; read with real string semantics it's ONE
    statement whose string literal happens to contain `; CREATE TABLE ...`
    as inert data. `ghost` must never appear — and it doesn't, because it
    was never a real table to begin with once quoting is honored."""
    declared = parse_declared_columns(_ROUND1_SEMICOLON_TRICK_STRING_HIDES_A_STATEMENT)
    assert declared == {"t": {("c", "text", False)}}
    assert "ghost" not in declared


def test_round1_semicolon_trick_comment_hides_a_statement_is_rejected():
    """Codex Round-1 finding: same shape as above but via a `/* */` block
    comment instead of a string — this file supports NO block comments, so
    the tokenizer rejects on the first `/`, well before any `ghost` table
    text is ever reached."""
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(_ROUND1_SEMICOLON_TRICK_COMMENT_HIDES_A_STATEMENT)


def _assert_mutation_does_not_stay_silently_green(mutated_sql: str, table: str) -> None:
    """A Round-1 mutation of the REAL file must not leave the full-file
    comparison green: either the parser now REJECTS the file outright (a
    raise is not a silent pass), or it parses fine but the resulting set no
    longer equals `_REQUIRED_COLUMNS[table]`."""
    try:
        declared = parse_declared_columns(mutated_sql)
    except UnrecognizedSqlShapeError:
        return  # rejected outright — not a silent pass
    required = _required_as_tuples()
    assert declared[table] != required[table], "mutation stayed silently green"


_ROUND1_PROMISE_TEXT_BYPASSES = [
    pytest.param("promise_text              TEXT /* NOT NULL */,", id="comment-hides-not-null"),
    pytest.param(
        "promise_text              TEXT DEFAULT $$NOT NULL$$,", id="dollar-quote-hides-not-null"
    ),
    pytest.param(
        'promise_text              TEXT CONSTRAINT "NOT NULL" CHECK (true),',
        id="quoted-constraint-hides-not-null",
    ),
]


@pytest.mark.parametrize("replacement", _ROUND1_PROMISE_TEXT_BYPASSES)
def test_round1_bypass_promise_text_not_null_is_never_silently_dropped(replacement):
    """Codex Round-1 FIX-FIRST bypass #1-3: replacing the real
    `promise_text TEXT NOT NULL,` with a comment/dollar-quote/quoted-
    constraint trick that VISUALLY still says "NOT NULL" but doesn't REALLY
    constrain it must not leave the full-file contract comparison green.
    All three now REJECT the whole file outright (the tokenizer refuses
    `/`, `$` and `"` outside a string) — stronger than merely detecting the
    mismatch."""
    sql = _SQL_PATH.read_text().replace(
        "promise_text              TEXT NOT NULL,", replacement
    )
    assert replacement in sql  # the replace actually matched something
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_round1_bypass_resolved_default_expression_is_rejected():
    """Codex Round-1 FIX-FIRST bypass #4: `resolved BOOLEAN DEFAULT (NULL IS
    NOT NULL)` swaps in a parenthesised expression for the real `NOT NULL
    DEFAULT false` — an allowed-DEFAULT shape team_promises.sql never uses —
    so it's REJECTED rather than left nullable."""
    sql = _SQL_PATH.read_text().replace(
        "resolved                  BOOLEAN NOT NULL DEFAULT false,",
        "resolved                  BOOLEAN DEFAULT (NULL IS NOT NULL),",
    )
    assert "(NULL IS NOT NULL)" in sql
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_round1_bypass_multi_action_alter_hidden_column_is_detected():
    """Codex Round-1 FIX-FIRST bypass #5: the multi-action ALTER's SECOND
    action adds a column the FIRST action's own string DEFAULT (`'('`) used
    to hide from the round-0 parser's char-based paren-depth tracker.
    Token-based splitting treats the whole string as ONE opaque token, so
    the real top-level comma right after it is correctly seen — `hidden` is
    parsed, not silently omitted, and the contract comparison correctly
    goes red for it."""
    sql = _SQL_PATH.read_text() + (
        "\n\nALTER TABLE team_promise_candidates\n"
        "  ADD COLUMN IF NOT EXISTS cue TEXT DEFAULT '(',\n"
        "  ADD COLUMN IF NOT EXISTS hidden TEXT;\n"
    )
    declared = parse_declared_columns(sql)
    assert ("hidden", "text", False) in declared["team_promise_candidates"]
    required = _required_as_tuples()
    assert declared["team_promise_candidates"] != required["team_promise_candidates"]
