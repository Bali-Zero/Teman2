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

ROUND 2 (condition C-A, PASS-WITH-CONDITIONS follow-up on PR #7395's own
gate, pull/7395#issuecomment-5846140618): the Round-1 tokenizer was itself
fail-closed but had eight residuals where it was silent-wrong or accepted
SQL PG rejects, each judged against a throwaway PG17 catalog, not against
the parser's own expectations — R1 repeated CREATE TABLE/ADD COLUMN are
UNIONED here but PG keeps the first and no-ops the rest; R2 a bare `\\r`
ends PG's `--` comment where `_tokenize` only ended one at `\\n`; R3 an
`E'...\\''` escape string desyncs the tokenizer's doubled-quote-only string
scan, resynced by a `--` comment, hiding a column; R4 any schema qualifier
was discarded, not only `public.`; R5 typmods (`VARCHAR(n)`,
`TIMESTAMPTZ(p)`) are dropped — chosen to match the runtime guard's
atttypid-only contract (see `_TYPMOD_CAPABLE_TYPES`'s docstring); R6 SQL PG
rejects was silently accepted (trailing comma, conflicting NULL/NOT NULL,
duplicate DEFAULT/PRIMARY KEY, a non-boolean bare-literal CHECK, a typmod on
a type that doesn't support one, a reserved keyword used as an unquoted
column name); R7 a non-ASCII identifier (a Kelvin sign) was folded by
Python's `.lower()` but not by PG; R8 an empty `()` body silently produced
no `declared` entry for the table at all rather than being rejected.

REWORK (fresh gate on 18f82e1daf, pull/7413#issuecomment-5846951975,
verdict REWORK-BUILD — a fix-of-a-fix, last round per Builder Contract §1):
the round above closed all 8 residuals but its own R1 first-wins and R5
typmod-drop regressed three real-file mutations from RED (on origin/main)
to GREEN, and R5 had no discriminating guilt case. S1 (R5): typmods are now
rejected outright, not accepted-and-dropped — `_TYPMOD_CAPABLE_TYPES` is
empty. S2: a duplicate column NAME inside one CREATE body is rejected. S3:
a repeated `CREATE TABLE IF NOT EXISTS` body is still fully parsed and
validated (a syntax error in it still raises) — only a semantically valid
repeat is discarded, matching PG's own no-op. S4: an `ADD COLUMN IF NOT
EXISTS` that re-declares a column the table's OWN `CREATE TABLE` body
already defined, with a DIFFERENT `(type, notnull)`, is rejected — PG
would apply the CREATE body's definition (or the DDL fails/rolls back
against a Fly database that already carries the CREATE shape) and never
silently re-type or re-null it the ALTER's way. First-wins stays
unconditional between two CREATEs or two ALTERs (path-independent). S5:
23 more of PG's own catcode-`T` keywords (`left`, `is`, `join`, ...) join
the reserved-column-name set, and the real-PG R4/R6a companion cases now
also assert the static parser rejects, not just that PG does.

S6 (carried-forward condition on PR #7413's re-gate,
pull/7413#issuecomment-5847256465 — pre-existing, silent only in this
static layer, the runtime `SchemaMismatchError` guard already catches all
three against the real catalog): measured directly against a throwaway
PG17 17.10 cluster. (a) A `CREATE TABLE IF NOT EXISTS` whose name is
already occupied by an EARLIER `CREATE UNIQUE INDEX` in the same parse is
a PG no-op too — table and index names share ONE relation namespace per
schema, so `_parse_create_table`'s already-created check and
`_parse_create_unique_index` both read/write one shared
`occupied_relations` set, not `_parse_create_table`'s own private one.
(b) PG silently truncates any identifier over 63 bytes (NAMEDATALEN-1)
rather than erroring — collision-prone and impossible for this static
layer to reproduce faithfully, so every identifier (table, column, index)
over 63 bytes is now rejected outright, matching S1's typmod precedent.
(c) `SMALLSERIAL`/`FLOAT`/`CHAR`, once past `_parse_column_def`'s typmod
gate, used to fall through `_TYPE_ALIASES.get(raw_type, raw_type.lower())`
to `"smallserial"`/`"float"`/`"char"` — none of which `format_type()` ever
returns; PG's real spellings are `"smallint"`/`"double precision"`/
`"character"`, now in `_TYPE_ALIASES` alongside the existing serial/varchar
entries.

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
    "SMALLSERIAL": "smallint",
    "BIGINT": "bigint",
    "INT8": "bigint",
    "INTEGER": "integer",
    "INT": "integer",
    "INT4": "integer",
    "TEXT": "text",
    "VARCHAR": "character varying",
    "CHAR": "character",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "TIMESTAMPTZ": "timestamp with time zone",
    "FLOAT": "double precision",
}

# serial-family pseudo-types create a NOT NULL column (backed by a DEFAULT
# nextval(...)) regardless of PRIMARY KEY — Round-1 finding: a bare `id
# BIGSERIAL` (no explicit PRIMARY KEY on IT) was wrongly read as nullable.
_IMPLICIT_NOT_NULL_TYPES = frozenset({"SERIAL", "BIGSERIAL", "SMALLSERIAL"})

# Round-2 R5, REWORK (fresh-gate finding on 18f82e1daf, PWC #7395 C-A):
# empty by design — team_promises.sql uses NO typmod anywhere today, so a
# typmod on ANY type is outside this file's allowlist and REJECTED outright,
# never silently accepted-and-dropped. The original round accepted a typmod
# on VARCHAR/TIMESTAMPTZ and dropped it (matching the runtime guard's
# atttypid-only contract) — but that erased the only layer that noticed a
# typmod at all: `format_type(atttypid, atttypmod)` (the opt-in C1 real-PG
# test) DOES see it, and it is not cosmetic — `TIMESTAMPTZ(0)` on
# `created_at` rounds `now()` to the second, measured to move a row across
# the `_DIGEST_COUNTS_SQL` day-bucket boundary. Fail-closed is cheap here:
# nothing in `_REQUIRED_COLUMNS` needs a typmod, so rejecting every one of
# them costs nothing and C1's query is restored to `atttypmod` (not `NULL`)
# since the two now differ ONLY when something is actually silently wrong.
_TYPMOD_CAPABLE_TYPES: frozenset[str] = frozenset()

# PostgreSQL's OWN fully-reserved keywords (`SELECT word FROM
# pg_get_keywords() WHERE catcode = 'R'` on a throwaway PG17 — these can
# never be an unquoted identifier, column names included) — Round-2 R6
# finding: `_parse_column_def` accepted any of these as a bare column name
# even though PG raises a syntax error on all of them unquoted. REWORK
# S5(b): PG's 23 catcode-`T` keywords (`SELECT word FROM pg_get_keywords()
# WHERE catcode = 'T'` — "reserved, can be function or type name", the
# category directly below catcode-`R` in PG's own docs) syntax-error the
# same way as an unquoted COLUMN name even though the catcode-`R` set above
# is the complete `R` list — `left`/`is`/`join` etc. were still silently
# accepted here before this round.
_RESERVED_COLUMN_NAMES = frozenset({
    "ALL", "ANALYSE", "ANALYZE", "AND", "ANY", "ARRAY", "AS", "ASC",
    "ASYMMETRIC", "BOTH", "CASE", "CAST", "CHECK", "COLLATE", "COLUMN",
    "CONSTRAINT", "CREATE", "CURRENT_CATALOG", "CURRENT_DATE",
    "CURRENT_ROLE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_USER",
    "DEFAULT", "DEFERRABLE", "DESC", "DISTINCT", "DO", "ELSE", "END",
    "EXCEPT", "FALSE", "FETCH", "FOR", "FOREIGN", "FROM", "GRANT", "GROUP",
    "HAVING", "IN", "INITIALLY", "INTERSECT", "INTO", "LATERAL", "LEADING",
    "LIMIT", "LOCALTIME", "LOCALTIMESTAMP", "NOT", "NULL", "OFFSET", "ON",
    "ONLY", "OR", "ORDER", "PLACING", "PRIMARY", "REFERENCES", "RETURNING",
    "SELECT", "SESSION_USER", "SOME", "SYMMETRIC", "SYSTEM_USER", "TABLE",
    "THEN", "TO", "TRAILING", "TRUE", "UNION", "UNIQUE", "USER", "USING",
    "VARIADIC", "WHEN", "WHERE", "WINDOW", "WITH",
    # catcode-T (23, verified against the same throwaway PG17 cluster):
    "AUTHORIZATION", "BINARY", "COLLATION", "CONCURRENTLY", "CROSS",
    "CURRENT_SCHEMA", "FREEZE", "FULL", "ILIKE", "INNER", "IS", "ISNULL",
    "JOIN", "LEFT", "LIKE", "NATURAL", "NOTNULL", "OUTER", "OVERLAPS",
    "RIGHT", "SIMILAR", "TABLESAMPLE", "VERBOSE",
})

# S6(b): PG's NAMEDATALEN is 64 bytes, one of which is the null terminator,
# so any identifier over 63 BYTES (not characters — PG counts bytes) is
# silently truncated at CREATE time, never rejected. Measured directly: a
# 64-byte identifier lands in pg_attribute/pg_class already cut to exactly
# 63 bytes. Two different over-length names sharing the same 63-byte prefix
# would collide into ONE column/relation — a static parser cannot reproduce
# PG's truncation (or its collision) faithfully, so every over-length
# identifier is rejected outright instead, matching S1's typmod precedent.
_MAX_IDENTIFIER_BYTES = 63


def _check_identifier_length(
    name: str, index: int, sql: str, stmt_tokens: list[_Token]
) -> None:
    if len(name.encode("utf-8")) > _MAX_IDENTIFIER_BYTES:
        raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))


def _claim_implicit_relation(
    name: str, index: int, sql: str, stmt_tokens: list[_Token],
    occupied_relations: set[str],
) -> None:
    """C2 follow-up (council round on PR #7439's re-gate follow-up, both
    codex-gpt-5.6-sol and kimi-code/k3 independently confirmed the
    `_parse_alter_table` gap; codex additionally measured these two):
    PG's own name allocator (`ChooseRelationName`/`ChooseIndexName`)
    retries a taken implicit name with a numeric suffix (`t_pkey1`, ...),
    AND always truncates the FULL derived name — base plus suffix — to
    NAMEDATALEN-1 (63) bytes before allocating it (measured: a 60-byte
    table name's own `_pkey`/`_id_seq` derived names land truncated to
    exactly 63 bytes, cutting into the BASE name, not just the suffix).
    Reproducing either algorithm here would mean re-implementing PG's own
    catalog allocator; instead, an implicit name that is already occupied
    or that itself exceeds 63 bytes is rejected outright — S1/S6(b)/C1's
    fail-closed precedent — rather than silently claimed under a name PG
    would not actually have used."""
    if len(name.encode("utf-8")) > _MAX_IDENTIFIER_BYTES or name in occupied_relations:
        raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))
    occupied_relations.add(name)


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
            # Round-2 R2: PG's scanner ends a `--` comment at a bare `\r`
            # too, not only `\n` — a text-only newline search let a `\r`
            # (no `\n` following) hide real tokens (a column, a NOT NULL)
            # inside what this tokenizer used to still call comment text.
            j = i + 2
            while j < n and sql[j] not in "\r\n":
                j += 1
            i = j
            continue
        if c == "'":
            # Round-2 R3: an `E'...'` escape string uses BACKSLASH escaping
            # (`\'` is an escaped quote), which this tokenizer's plain
            # doubled-quote (`''`) scan below does not understand — it can
            # desync onto a much later quote (one inside a `--` comment,
            # say) and silently swallow real statements as "string content".
            # Never supported: rejected outright the instant an `E`/`e` word
            # sits immediately before the opening quote, before the (wrong)
            # scan below ever starts.
            if (
                tokens and tokens[-1].kind == "WORD"
                and tokens[-1].value.upper() == "E" and tokens[-1].end == i
            ):
                raise UnrecognizedSqlShapeError(
                    stmt_index, "E'",
                    f"E-string (escape string) literal at offset {i - 1} is "
                    "outside today's allowlist — backslash escaping inside "
                    "a string is not supported by this tokenizer",
                )
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
            word = sql[i:j]
            if not word.isascii():
                # Round-2 R7: Python's `str.isalpha()`/`.lower()` fold
                # non-ASCII letters PG's own unquoted-identifier downcasing
                # never touches (a Kelvin sign `K` lowercases to plain
                # ASCII `k` in Python, staying itself in PG) — rejected
                # outright rather than silently folded to a name PG would
                # never produce for the same input.
                raise UnrecognizedSqlShapeError(
                    stmt_index, word,
                    f"non-ASCII unquoted identifier {word!r} at offset {i} "
                    "is outside today's allowlist — this tokenizer's "
                    "lowercasing does not match PG's for non-ASCII letters",
                )
            tokens.append(_Token("WORD", word, i, j))
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
    parenthesis never counts as a separator. Round-2 R6a/R8: the final
    `current` is appended UNCONDITIONALLY, even when empty — a trailing
    top-level comma (`(c TEXT,)`, a PG syntax error) or a wholly empty body
    (`()`, R8 — never given even one entry in `declared`) used to leave
    nothing after the last real element for a caller's `if not element:
    raise` to ever see; now both surface as an empty trailing part, exactly
    like a double comma mid-list already did."""
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
    parts.append(current)
    return parts


def _read_qualified_name(
    tokens: list[_Token], pos: int, index: int, sql: str, stmt_tokens: list[_Token]
) -> tuple[str, int]:
    """A bare or `public.`-qualified identifier — the `public` schema prefix
    (any case) is discarded, keeping only the bare name, lowercased
    (unquoted Postgres identifiers fold to lowercase; quoted ones are
    rejected outright at the tokenizer, so lowercasing here is always
    correct). Round-2 R4: ANY OTHER schema qualifier used to be discarded
    the same way — `other.team_promises` silently read as plain
    `team_promises` — but on a fresh DB that statement errors in PG
    (undefined table `other.team_promises`), and on a DB where `other.t`
    happens to exist it would silently cross-check the WRONG table's
    columns. A non-`public` qualifier is now rejected outright."""
    if pos >= len(tokens) or tokens[pos].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
    name = tokens[pos].value
    pos += 1
    if pos < len(tokens) and tokens[pos].kind == "PUNCT" and tokens[pos].value == ".":
        if name.lower() != "public":
            raise UnrecognizedSqlShapeError(
                index, name, _stmt_text(sql, stmt_tokens)
            )
        pos += 1
        if pos >= len(tokens) or tokens[pos].kind != "WORD":
            raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
        name = tokens[pos].value
        pos += 1
    _check_identifier_length(name, index, sql, stmt_tokens)
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
) -> tuple[str, str, bool, str, bool]:
    """`ident type [(args)] [NOT NULL | NULL | DEFAULT <allowed value> |
    PRIMARY KEY | CHECK (...)]*`, clauses in ANY order (the real file mixes
    them: `resolved BOOLEAN NOT NULL DEFAULT false`, `status TEXT NOT NULL
    DEFAULT 'unjudged' CHECK (...)`). NOT NULL is explicit, implied by
    PRIMARY KEY, or implied by a serial-family type (Round-1: `id
    BIGSERIAL` alone). `(args)` and `CHECK (...)` are consumed as balanced,
    OPAQUE parens — their contents are never scanned for keywords, which is
    exactly what stops `CHECK (c IS NOT NULL OR true)` from leaking a fake
    NOT NULL into this column's own nullability (Round-1 finding: round-0's
    NOT-NULL check scanned the whole clause tail as one string). Round-2 R6
    findings: PG rejects a handful of shapes this used to accept silently —
    conflicting NULL/NOT NULL, more than one DEFAULT or PRIMARY KEY, a
    non-boolean bare-literal CHECK, and a typmod on a type that doesn't take
    one — each now REJECTED to match. R6/reserved-word: a column named
    after one of PG's own fully-reserved keywords is rejected the same way.

    Returns `(name, pg_type, notnull, raw_type, primary_key)` — C2 (PR
    #7439's re-gate) needs `raw_type` (to recognize a serial-family column,
    which gets its own implicit `<table>_<col>_seq` sequence) and
    `primary_key` (a table with one gets an implicit `<table>_pkey` index)
    as callers build `occupied_relations`. Both are internal to this parse;
    the public `declared`/`_REQUIRED_COLUMNS` shape stays `(name, pg_type,
    notnull)` triples, unchanged."""
    if not tokens or tokens[0].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "?", _stmt_text(sql, stmt_tokens))
    name = tokens[0].value.lower()
    if tokens[0].value.upper() in _RESERVED_COLUMN_NAMES:
        raise UnrecognizedSqlShapeError(index, tokens[0].value, _stmt_text(sql, stmt_tokens))
    _check_identifier_length(tokens[0].value, index, sql, stmt_tokens)
    if len(tokens) < 2 or tokens[1].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))
    raw_type = tokens[1].value.upper()
    pos = 2
    if pos < len(tokens) and tokens[pos].kind == "PUNCT" and tokens[pos].value == "(":
        if raw_type not in _TYPMOD_CAPABLE_TYPES:
            raise UnrecognizedSqlShapeError(index, raw_type, _stmt_text(sql, stmt_tokens))
        pos = _find_matching_close(tokens, pos, index, sql, stmt_tokens) + 1
    notnull_explicit = False
    saw_null_bare = False
    primary_key = False
    saw_default = False
    while pos < len(tokens):
        w = _kw(tokens[pos])
        nxt = _kw(tokens[pos + 1]) if pos + 1 < len(tokens) else None
        if w == "NOT" and nxt == "NULL":
            if saw_null_bare:
                raise UnrecognizedSqlShapeError(index, "NOT", _stmt_text(sql, stmt_tokens))
            notnull_explicit = True
            pos += 2
            continue
        if w == "NULL":
            if notnull_explicit:
                raise UnrecognizedSqlShapeError(index, "NULL", _stmt_text(sql, stmt_tokens))
            saw_null_bare = True
            pos += 1
            continue
        if w == "DEFAULT":
            if saw_default:
                raise UnrecognizedSqlShapeError(index, "DEFAULT", _stmt_text(sql, stmt_tokens))
            saw_default = True
            pos = _parse_default_value(tokens, pos + 1, index, sql, stmt_tokens)
            continue
        if w == "PRIMARY" and nxt == "KEY":
            if primary_key:
                raise UnrecognizedSqlShapeError(index, "PRIMARY", _stmt_text(sql, stmt_tokens))
            primary_key = True
            pos += 2
            continue
        if w == "CHECK":
            if pos + 1 >= len(tokens) or not (
                tokens[pos + 1].kind == "PUNCT" and tokens[pos + 1].value == "("
            ):
                raise UnrecognizedSqlShapeError(index, "CHECK", _stmt_text(sql, stmt_tokens))
            check_open = pos + 1
            check_close = _find_matching_close(tokens, check_open, index, sql, stmt_tokens)
            check_body = tokens[check_open + 1: check_close]
            if len(check_body) == 1 and check_body[0].kind == "NUMBER":
                # R6f: `CHECK (1)` — PG requires a boolean expression and
                # errors on a bare numeric literal ("argument of CHECK must
                # be type boolean, not type integer"); a bare TRUE/FALSE
                # keyword or string ('t') is fine (PG casts it), so only a
                # lone NUMBER token is rejected here.
                raise UnrecognizedSqlShapeError(index, "CHECK", _stmt_text(sql, stmt_tokens))
            pos = check_close + 1
            continue
        raise UnrecognizedSqlShapeError(
            index, w or tokens[pos].value, _stmt_text(sql, stmt_tokens)
        )
    if raw_type not in _TYPE_ALIASES:
        # C1 (PR #7439's re-gate, pull/7439#issuecomment-5848724154): the
        # OLD `_TYPE_ALIASES.get(raw_type, raw_type.lower())` fallback
        # silently passed through any type keyword this file's own alias
        # table doesn't list — measured against PG17: INT2/FLOAT4/FLOAT8,
        # DECIMAL/DEC, TIMESTAMP/TIME/TIMETZ, SERIAL2/SERIAL4/SERIAL8 (which
        # ALSO lose their implicit NOT NULL, since `_IMPLICIT_NOT_NULL_TYPES`
        # only lists the spelled-out serial names), and BPCHAR/NCHAR/VARBIT
        # are all silently-wrong this way — none of the 14 round-trips
        # through `raw_type.lower()` to what `format_type()` actually
        # returns. Closing the MECHANISM, not the 14 instances: an unknown
        # type keyword is now REJECTED outright, matching S1/S6(b)'s
        # fail-closed precedent, rather than trusted to already be the
        # canonical spelling.
        raise UnrecognizedSqlShapeError(index, raw_type, _stmt_text(sql, stmt_tokens))
    pg_type = _TYPE_ALIASES[raw_type]
    notnull = notnull_explicit or primary_key or raw_type in _IMPLICIT_NOT_NULL_TYPES
    return name, pg_type, notnull, raw_type, primary_key


def _parse_create_table(
    index: int, stmt_tokens: list[_Token], sql: str,
    declared: dict[str, dict[str, tuple[str, bool]]],
    occupied_relations: set[str],
    create_body_cols: set[tuple[str, str]],
) -> None:
    """Round-2 R1, REWORK S2/S3: `CREATE TABLE IF NOT EXISTS` on a table
    this parse has already created is a no-op in PG for the RESULT — the
    second body's columns never land — but PG still PARSES it: a syntax
    error in a repeated body (a double comma, a reserved bare word) still
    fails at apply time, so this file must not go silent on one either. The
    body is always fully parsed and validated (S2: a duplicate column NAME
    inside ONE body is rejected outright — PG itself raises
    `DuplicateColumnError`, never last-wins); only the RESULT of an
    already-created table's repeat is then discarded, matching PG's own
    no-op. `create_body_cols` records every (table, name) this parse ever
    saw in a winning CREATE body — S4 (`_parse_alter_table`) needs it to
    tell a CREATE-body column apart from an ALTER-added one. S6(a):
    `occupied_relations` is shared with `_parse_create_unique_index` — PG
    keeps tables and indexes in ONE relation namespace per schema, so a
    name an earlier `CREATE UNIQUE INDEX` already claimed makes THIS
    `CREATE TABLE IF NOT EXISTS` a no-op too, the same as an earlier
    `CREATE TABLE` of the same name would."""
    table, pos = _read_qualified_name(stmt_tokens, 5, index, sql, stmt_tokens)
    if pos >= len(stmt_tokens) or not (
        stmt_tokens[pos].kind == "PUNCT" and stmt_tokens[pos].value == "("
    ):
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    close_pos = _find_matching_close(stmt_tokens, pos, index, sql, stmt_tokens)
    if close_pos != len(stmt_tokens) - 1:
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    body = stmt_tokens[pos + 1: close_pos]
    already_created = table in occupied_relations
    this_body: dict[str, tuple[str, bool]] = {}
    has_primary_key = False
    serial_cols: list[str] = []
    for element in _split_top_level_commas_tok(body):
        if not element:
            raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
        first_kw = _kw(element[0])
        if first_kw in _NON_COLUMN_TABLE_ELEMENTS:
            raise UnrecognizedSqlShapeError(index, first_kw, _stmt_text(sql, stmt_tokens))
        name, pg_type, notnull, raw_type, primary_key = _parse_column_def(
            element, index, sql, stmt_tokens
        )
        if name in this_body:
            raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))
        this_body[name] = (pg_type, notnull)
        if primary_key:
            # PG: "cannot have more than one primary key" — a hard error,
            # not PG's own IF-NOT-EXISTS no-op semantics, so it is rejected
            # here rather than silently accepting the second one (found by
            # codex-gpt-5.6-sol's council review, measured against PG17).
            if has_primary_key:
                raise UnrecognizedSqlShapeError(index, "PRIMARY", _stmt_text(sql, stmt_tokens))
            has_primary_key = True
        if raw_type in _IMPLICIT_NOT_NULL_TYPES:  # serial family: id BIGSERIAL, ...
            serial_cols.append(name)
    if already_created:
        return
    per_table = declared.setdefault(table, {})
    for name, spec in this_body.items():
        per_table[name] = spec
        create_body_cols.add((table, name))
    occupied_relations.add(table)
    # C2 (PR #7439's re-gate): PG creates a PRIMARY KEY's backing unique
    # index (`<table>_pkey`) and a serial column's backing sequence
    # (`<table>_<col>_seq`) in the SAME statement as the table itself —
    # both occupy the shared relation namespace `occupied_relations`
    # already tracks for S6(a), so a later `CREATE TABLE IF NOT EXISTS`
    # (or `CREATE UNIQUE INDEX IF NOT EXISTS`) reusing either name must
    # see it as already taken, the same as an explicit CREATE would.
    if has_primary_key:
        _claim_implicit_relation(f"{table}_pkey", index, sql, stmt_tokens, occupied_relations)
    for col in serial_cols:
        _claim_implicit_relation(f"{table}_{col}_seq", index, sql, stmt_tokens, occupied_relations)


def _is_drop_constraint_if_exists(action: list[_Token]) -> bool:
    """`DROP CONSTRAINT IF EXISTS <name>` — T3 PR-3's half of the idempotent
    status-CHECK replacement. Exactly 5 tokens, the last a bare identifier
    (never schema-qualified, never punctuation)."""
    return (
        len(action) == 5
        and _kw(action[0]) == "DROP" and _kw(action[1]) == "CONSTRAINT"
        and _kw(action[2]) == "IF" and _kw(action[3]) == "EXISTS"
        and action[4].kind == "WORD"
    )


def _is_add_constraint_check(action: list[_Token]) -> bool:
    """`ADD CONSTRAINT <name> CHECK (...)` — the other half. Depth-tracked
    over the action's OWN tokens (same method as `_split_top_level_commas_
    tok`) so the requirement is "one balanced parenthesized expression
    filling the constraint body, nothing trailing it" rather than merely
    "starts with `(` and ends with `)`", which a stray `) FOO (` in between
    would satisfy."""
    if len(action) < 6:
        return False
    if not (
        _kw(action[0]) == "ADD" and _kw(action[1]) == "CONSTRAINT"
        and action[2].kind == "WORD" and _kw(action[3]) == "CHECK"
        and action[4].kind == "PUNCT" and action[4].value == "("
    ):
        return False
    depth = 0
    for i, tok in enumerate(action[4:], start=4):
        if tok.kind == "PUNCT" and tok.value == "(":
            depth += 1
        elif tok.kind == "PUNCT" and tok.value == ")":
            depth -= 1
            if depth == 0:
                return i == len(action) - 1
    return False


def _parse_alter_table(
    index: int, stmt_tokens: list[_Token], sql: str,
    declared: dict[str, dict[str, tuple[str, bool]]],
    create_body_cols: set[tuple[str, str]],
    occupied_relations: set[str],
) -> None:
    """Round-2 R1: `ADD COLUMN IF NOT EXISTS` on a column already present
    (from an earlier CREATE TABLE or ALTER in this same parse) is a no-op in
    PG — the FIRST definition wins, a later one with a DIFFERENT type/
    NOT-NULL is silently ignored, never unioned in. REWORK S4: that
    first-wins no-op is right between two CREATEs or two ALTERs (both are
    genuinely path-independent in PG), but WRONG when the earlier
    definition came from the table's own CREATE body: PG applies the CREATE
    body's shape, so an ALTER re-declaring that SAME column with a
    DIFFERENT `(type, notnull)` is not a harmless no-op to silently agree
    with — it is proof this file's own DDL disagrees with itself about what
    the column is. Rejected outright rather than silently kept at the
    CREATE body's (correct, but coincidentally so) value. C2: a genuinely
    NEW serial-family column added here also gets its own `<table>_<col>_
    seq` sequence, same as one declared in the CREATE body (see
    `_parse_create_table`'s own C2 comment); LIKEWISE a genuinely new
    PRIMARY KEY column claims `<table>_pkey` — the council round on this
    PR's own re-gate (codex-gpt-5.6-sol and kimi-code/k3, independently)
    found the original diff discarded `primary_key` here entirely, leaving
    `ALTER TABLE t ADD COLUMN IF NOT EXISTS id BIGINT PRIMARY KEY` able to
    fabricate the exact phantom `<table>_pkey` table C2 exists to prevent
    (measured: PG creates the same `t_pkey` index via this path too).

    T3 PR-3: two more action shapes are recognized and SKIPPED (never touch
    `per_table` — neither declares a column) — `DROP CONSTRAINT IF EXISTS
    <name>` and `ADD CONSTRAINT <name> CHECK (...)`, the idempotent
    status-CHECK replacement `wa_team_promises.py::verify_status_check`
    owns on the Python side. Anything else after ADD/DROP still falls
    through to the existing `UnrecognizedSqlShapeError` — this does not
    widen the allowlist beyond these two exact shapes."""
    table, pos = _read_qualified_name(stmt_tokens, 2, index, sql, stmt_tokens)
    action_tokens = stmt_tokens[pos:]
    if not action_tokens:
        raise UnrecognizedSqlShapeError(index, "ALTER", _stmt_text(sql, stmt_tokens))
    per_table = declared.setdefault(table, {})
    for action in _split_top_level_commas_tok(action_tokens):
        if _is_drop_constraint_if_exists(action) or _is_add_constraint_check(action):
            continue
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
        name, pg_type, notnull, raw_type, primary_key = _parse_column_def(
            action[5:], index, sql, stmt_tokens
        )
        if name in per_table:
            if (table, name) in create_body_cols and per_table[name] != (pg_type, notnull):
                raise UnrecognizedSqlShapeError(index, name, _stmt_text(sql, stmt_tokens))
            continue
        per_table[name] = (pg_type, notnull)
        if raw_type in _IMPLICIT_NOT_NULL_TYPES:
            _claim_implicit_relation(f"{table}_{name}_seq", index, sql, stmt_tokens, occupied_relations)
        if primary_key:
            _claim_implicit_relation(f"{table}_pkey", index, sql, stmt_tokens, occupied_relations)


def _parse_create_unique_index(
    index: int, stmt_tokens: list[_Token], sql: str, occupied_relations: set[str]
) -> None:
    """S6(a): the index's own name shares PG's ONE relation namespace with
    every table `_parse_create_table` claims in `occupied_relations` — an
    index has no columns of its own to cross-check, but claiming its name
    here is what lets a LATER `CREATE TABLE IF NOT EXISTS` of the same name
    correctly read itself as already-occupied (a PG no-op), instead of
    parsing a table PG never actually creates."""
    pos = 6  # past CREATE UNIQUE INDEX IF NOT EXISTS
    if pos >= len(stmt_tokens) or stmt_tokens[pos].kind != "WORD":
        raise UnrecognizedSqlShapeError(index, "CREATE", _stmt_text(sql, stmt_tokens))
    index_name = stmt_tokens[pos].value  # never schema-qualified in real syntax
    _check_identifier_length(index_name, index, sql, stmt_tokens)
    pos += 1
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
    occupied_relations.add(index_name.lower())


def parse_declared_columns(sql: str) -> dict[str, set[tuple[str, str, bool]]]:
    """Every column the SQL text declares (CREATE TABLE body columns, plus
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS), as {table: {(name, type,
    notnull), ...}}. Round-1: tokenizer-based, not regex-over-text (see
    `_tokenize`'s docstring for why that distinction is load-bearing).
    FAIL-CLOSED: any statement — or column/DEFAULT/top-level table element
    inside one — outside the allowlist raises `UnrecognizedSqlShapeError`
    naming its statement index and first keyword, never silently skipping
    it. Round-2 R1: `declared` is built as {table: {name: (type, notnull)}}
    internally — FIRST-WINS per column name, matching PG's own
    IF-NOT-EXISTS no-op semantics for a repeated CREATE TABLE or ADD COLUMN
    — then converted to the public {table: {(name, type, notnull), ...}}
    shape on return, so every existing caller's expected shape is
    unchanged. REWORK S4: `create_body_cols` is a per-call, LOCAL
    {(table, name), ...} of every column a winning CREATE body declared —
    threaded through so `_parse_alter_table` can tell a CREATE-body column
    apart from an ALTER-added one (only the former is path-DEPENDENT: PG
    applies the CREATE body's own shape over a later ALTER that disagrees).
    S6(a): `occupied_relations` is a per-call, LOCAL set shared by
    `_parse_create_table` and `_parse_create_unique_index` — PG keeps
    tables and indexes in ONE relation namespace per schema, so either one
    can claim a name that makes the OTHER's later same-named
    `IF NOT EXISTS` a no-op."""
    tokens = _tokenize(sql)
    statements = _split_into_statements(tokens)
    declared: dict[str, dict[str, tuple[str, bool]]] = {}
    occupied_relations: set[str] = set()
    create_body_cols: set[tuple[str, str]] = set()
    for index, stmt_tokens in enumerate(statements):
        if not stmt_tokens:
            continue

        def kw(pos: int, _toks: list[_Token] = stmt_tokens) -> str | None:
            return _kw(_toks[pos]) if pos < len(_toks) else None

        if kw(0) == "CREATE" and kw(1) == "TABLE" and kw(2) == "IF" and kw(3) == "NOT" and kw(4) == "EXISTS":
            _parse_create_table(index, stmt_tokens, sql, declared, occupied_relations, create_body_cols)
        elif kw(0) == "ALTER" and kw(1) == "TABLE":
            _parse_alter_table(index, stmt_tokens, sql, declared, create_body_cols, occupied_relations)
        elif (
            kw(0) == "CREATE" and kw(1) == "UNIQUE" and kw(2) == "INDEX"
            and kw(3) == "IF" and kw(4) == "NOT" and kw(5) == "EXISTS"
        ):
            _parse_create_unique_index(index, stmt_tokens, sql, occupied_relations)
        else:
            raise UnrecognizedSqlShapeError(
                index, kw(0) or stmt_tokens[0].value, _stmt_text(sql, stmt_tokens)
            )
    return {
        table: {(name, pg_type, notnull) for name, (pg_type, notnull) in cols.items()}
        for table, cols in declared.items()
    }


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


def test_guilt_s1_create_body_typmod_is_rejected():
    """REWORK S1: `due_at` is bare `TIMESTAMPTZ` in the real file; a typmod
    with the WRONG argument count (`TIMESTAMPTZ(3,4)`) is a genuine
    PostgreSQL type-modifier error at apply time — the static parser must
    reject it outright, never silently drop the typmod and accept the
    column as if it were the plain type."""
    sql = _SQL_PATH.read_text().replace(
        "due_at                    TIMESTAMPTZ,",
        "due_at                    TIMESTAMPTZ(3,4),",
    )
    assert "TIMESTAMPTZ(3,4)" in sql  # the replace actually matched something
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s1_alter_body_typmod_is_rejected():
    """REWORK S1: `team_promise_candidates.created_at` is bare `TIMESTAMPTZ`
    in the real file; `TIMESTAMPTZ(0)` is syntactically valid PG but rounds
    `now()` to the second — measured to move a row across the digest's own
    day-bucket boundary (23:59:59.6 vs 00:00:00 the next day). Dropping the
    typmod used to hide this; it must be rejected outright instead."""
    sql = _SQL_PATH.read_text().replace(
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();",
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ(0) NOT NULL DEFAULT now();",
    )
    assert "TIMESTAMPTZ(0) NOT NULL" in sql  # the replace actually matched something
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s2_duplicate_column_inside_one_create_body_is_rejected():
    """REWORK S2: a second `promise_text` column inserted right before the
    real one, INSIDE THE SAME `CREATE TABLE` body — PG itself raises
    `DuplicateColumnError` at apply time; the old last-wins overwrite
    silently kept only the second (correct) definition and stayed GREEN
    against the contract, hiding a duplicate name PG would never apply."""
    sql = _SQL_PATH.read_text().replace(
        "    promise_text              TEXT NOT NULL,",
        "    promise_text              INTEGER,\n"
        "    promise_text              TEXT NOT NULL,",
    )
    assert sql.count("promise_text") == 2  # both now inside the CREATE body
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s3_repeated_create_body_syntax_error_is_rejected():
    """REWORK S3: a SECOND, repeated `CREATE TABLE IF NOT EXISTS
    team_promises` is a no-op for its RESULT (the table already exists),
    but PG still PARSES the statement — a double comma is a syntax error at
    apply time regardless of whether the CREATE ever takes effect. The old
    early return skipped validation entirely and stayed silently GREEN;
    this must still raise, naming the repeated body's own bad syntax."""
    sql = _SQL_PATH.read_text() + (
        "\nCREATE TABLE IF NOT EXISTS team_promises (a TEXT,,b TEXT);\n"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s3_repeated_create_body_reserved_word_is_rejected():
    """REWORK S3, second syntax-error shape: a repeated CREATE body whose
    only column is a bare reserved keyword (`select`) — PG errors on this
    at apply time exactly like the double-comma case above, and this file
    must reject it for the same reason: a repeated body's SYNTAX still
    matters even though its semantic RESULT is discarded."""
    sql = _SQL_PATH.read_text() + (
        "\nCREATE TABLE IF NOT EXISTS team_promises (select TEXT);\n"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s3_repeated_create_body_with_null_not_null_conflict_is_rejected():
    """Renamed (carried into the C1-C4 PR per #7413's re-gate "record
    only" note, pull/7413#issuecomment-5847256465): the old name and
    docstring called this a "silent noop" — the INTENT was to prove PG
    skips a repeated body's SEMANTIC errors (a duplicate column, a
    NULL/NOT NULL conflict) without enforcing them, so a parser that
    rejected purely semantic errors here would be MORE strict than PG
    itself. But `NULL NOT NULL` is ALSO a grammar-level conflict this
    file's own column-def grammar rejects independent of S3 (Round-2 R6b),
    so this specific body proves REJECTION, the opposite of what the old
    name claimed — the test's own `pytest.raises` always said so; only the
    name and docstring disagreed with the test's own body."""
    sql = _SQL_PATH.read_text() + (
        "\nCREATE TABLE IF NOT EXISTS team_promises (a TEXT NULL NOT NULL);\n"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        # `NULL NOT NULL` is itself rejected by THIS file's own column-def
        # grammar (Round-2 R6b) independent of S3 — proving the repeated
        # body really is validated, not skipped outright.
        parse_declared_columns(sql)


def test_guilt_s4_alter_redeclares_a_create_body_column_differently_is_rejected():
    """REWORK S4: `team_promise_candidates`'s CREATE body is mutated to
    ALSO declare `cue TEXT NOT NULL DEFAULT ''` (NOT NULL) — the real
    file's own later `ALTER TABLE ... ADD COLUMN IF NOT EXISTS cue TEXT;`
    (nullable) then re-declares the SAME column with a DIFFERENT
    nullability. PG applies the CREATE body's shape (`cue` ends up NOT
    NULL); the old first-wins-always logic silently kept the CREATE body's
    value too, by coincidence — GREEN either way, for the wrong reason
    (i.e. it would just as silently be WRONG had the CREATE body been the
    later, losing statement instead). This must now be rejected outright:
    the file disagrees with itself about `cue`, and first-wins is not a
    resolution to trust silently for a CREATE-body/ALTER split."""
    sql = _SQL_PATH.read_text().replace(
        "    promise_type       TEXT NOT NULL\n);",
        "    promise_type       TEXT NOT NULL,\n"
        "    cue                TEXT NOT NULL DEFAULT ''\n);",
    )
    assert "cue                TEXT NOT NULL DEFAULT ''" in sql
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_s4_alter_redeclares_a_create_body_column_identically_is_accepted():
    """REWORK S4's own boundary: the same mutation as above, but the
    CREATE-body `cue` is declared with the EXACT same `(type, notnull)` the
    real file's own ALTER already gives it (nullable TEXT) — no real
    disagreement exists, so this must stay accepted (first-wins, a
    no-op), not turn into a false positive on every harmless overlap."""
    sql = _SQL_PATH.read_text().replace(
        "    promise_type       TEXT NOT NULL\n);",
        "    promise_type       TEXT NOT NULL,\n"
        "    cue                TEXT\n);",
    )
    assert "    cue                TEXT\n);" in sql
    declared = parse_declared_columns(sql)
    assert ("cue", "text", False) in declared["team_promise_candidates"]


def test_guilt_s6a_index_occupies_relation_namespace_blocks_later_create_table():
    """S6(a), measured against a throwaway PG17 cluster: `CREATE TABLE
    IF NOT EXISTS conflict_slot (...)` after an earlier `CREATE UNIQUE
    INDEX IF NOT EXISTS conflict_slot ON ...` is a PG no-op — table and
    index names share ONE relation namespace per schema, so PG sees
    `conflict_slot` already occupied and skips the table entirely (the
    relation stays an index, `relkind='i'`, never becomes a table). Before
    this fix, `_parse_create_table`'s own private `created_tables` set
    never learned about the index's name, so this parse would silently
    invent columns for a table PG never created."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "CREATE UNIQUE INDEX IF NOT EXISTS conflict_slot ON t (a);\n"
        "CREATE TABLE IF NOT EXISTS conflict_slot (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("a", "text", False)}}
    assert "conflict_slot" not in declared


def test_innocence_s6a_index_after_its_own_table_is_unaffected():
    """The ordinary, non-colliding shape this file actually uses: an index
    created ON a table already declared, no name collision — must stay
    exactly as before."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_t_a ON t (a);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("a", "text", False)}}


_S6B_LONG_NAME = "a" * 64  # 64 bytes, one over PG's NAMEDATALEN-1 limit


def test_guilt_s6b_column_name_over_63_bytes_is_rejected():
    """S6(b), measured: PG doesn't error on a 64-byte column name, it
    silently truncates to 63 bytes at CREATE time. Two different
    over-length names sharing that 63-byte prefix would collide into ONE
    column — a static parser can't reproduce PG's truncation (or the
    collision) faithfully, so it must reject outright instead."""
    sql = f"CREATE TABLE IF NOT EXISTS t ({_S6B_LONG_NAME} TEXT);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s6b_table_name_over_63_bytes_is_rejected():
    sql = f"CREATE TABLE IF NOT EXISTS {_S6B_LONG_NAME} (a TEXT);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_s6b_index_name_over_63_bytes_is_rejected():
    sql = (
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_S6B_LONG_NAME} ON t (a);"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_s6b_identifier_exactly_63_bytes_is_accepted():
    """The boundary itself: exactly 63 bytes is PG's own limit, not
    truncated, and must stay accepted."""
    name_63 = "a" * 63
    sql = f"CREATE TABLE IF NOT EXISTS t ({name_63} TEXT);"
    declared = parse_declared_columns(sql)
    assert declared == {"t": {(name_63, "text", False)}}


def test_guilt_s6c_smallserial_float_char_type_fallback_is_corrected():
    """S6(c), measured against a throwaway PG17 cluster: `format_type()`
    on the real catalog returns `smallint`/`double precision`/`character`
    for `SMALLSERIAL`/`FLOAT`/`CHAR` — none of which
    `_TYPE_ALIASES.get(raw_type, raw_type.lower())`'s old fallback ever
    produced (`smallserial`/`float`/`char`)."""
    sql = "CREATE TABLE IF NOT EXISTS t (a SMALLSERIAL, b FLOAT, c CHAR);"
    declared = parse_declared_columns(sql)
    assert declared == {
        "t": {
            ("a", "smallint", True),
            ("b", "double precision", False),
            ("c", "character", False),
        }
    }


# --- C1-C4 (PR #7439's re-gate, pull/7439#issuecomment-5848724154):
# closing the two MECHANISMS S6 only closed instances of, plus two
# plausible wrong fixes the gate found survived S6's own tests. ---

# C1: 14 single-word type keywords the gate measured as silent-wrong
# against PG17 — none is in `_TYPE_ALIASES`, so the OLD
# `raw_type.lower()` fallback passed each straight through to a spelling
# `format_type()` never returns. SERIAL2/4/8 also lost their implicit NOT
# NULL, since `_IMPLICIT_NOT_NULL_TYPES` only lists the spelled-out serial
# names (SERIAL/BIGSERIAL/SMALLSERIAL).
_C1_SILENT_WRONG_TYPE_KEYWORDS = (
    "INT2", "FLOAT4", "FLOAT8",
    "DECIMAL", "DEC",
    "TIMESTAMP", "TIME", "TIMETZ",
    "SERIAL2", "SERIAL4", "SERIAL8",
    "BPCHAR", "NCHAR", "VARBIT",
)


@pytest.mark.parametrize("raw_type", _C1_SILENT_WRONG_TYPE_KEYWORDS)
def test_guilt_c1_silent_wrong_type_keyword_is_rejected(raw_type):
    sql = f"CREATE TABLE IF NOT EXISTS t (a {raw_type});"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_c1_unrecognized_type_keyword_generic_is_rejected():
    """C1 closes the MECHANISM, not just the 14 measured instances: any
    keyword `_TYPE_ALIASES` has never heard of is rejected outright,
    matching PG17's own `UndefinedObjectError` on a genuinely made-up type
    name (measured: `CREATE TABLE (a FOO)` errors "type \"foo\" does not
    exist")."""
    sql = "CREATE TABLE IF NOT EXISTS t (a FOO);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_c1_every_listed_alias_still_works():
    """Boundary: the fix must not regress anything `_TYPE_ALIASES` DOES
    list — every key still parses to its existing mapped spelling, with
    the existing implicit-NOT-NULL rule for the spelled-out serial names
    untouched."""
    for raw_type, expected_pg_type in _TYPE_ALIASES.items():
        sql = f"CREATE TABLE IF NOT EXISTS t (a {raw_type});"
        declared = parse_declared_columns(sql)
        expected_notnull = raw_type in _IMPLICIT_NOT_NULL_TYPES
        assert declared == {"t": {("a", expected_pg_type, expected_notnull)}}, raw_type


# C2: PG creates a PRIMARY KEY's backing unique index (`<table>_pkey`) and
# a serial column's backing sequence (`<table>_<col>_seq`) in the SAME
# statement as the table itself — both occupy the shared relation
# namespace `occupied_relations` already tracks for S6(a).


def test_guilt_c2_implicit_pkey_blocks_later_create_table():
    """Measured against a throwaway PG17 cluster: `t_pkey` lands
    `relkind='i'` the instant `CREATE TABLE t (id BIGSERIAL PRIMARY KEY,
    ...)` runs. Before this fix, `occupied_relations` never learned the
    implicit name, so a later `CREATE TABLE IF NOT EXISTS t_pkey (...)`
    would invent a phantom table PG never creates (the name is already
    taken by the index, and PG's IF NOT EXISTS skips it)."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (id BIGSERIAL PRIMARY KEY, x TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t_pkey (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("id", "bigint", True), ("x", "text", False)}}
    assert "t_pkey" not in declared


def test_guilt_c2_implicit_seq_blocks_later_create_table():
    """Same mechanism, the serial column's own sequence name."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (id BIGSERIAL, x TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t_id_seq (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("id", "bigint", True), ("x", "text", False)}}
    assert "t_id_seq" not in declared


def test_guilt_c2_implicit_seq_from_alter_added_serial_column():
    """The same mechanism applies to a serial column added via `ALTER
    TABLE ... ADD COLUMN IF NOT EXISTS`, not only one declared in the
    CREATE body."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (x TEXT);\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS n BIGSERIAL;\n"
        "CREATE TABLE IF NOT EXISTS t_n_seq (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("x", "text", False), ("n", "bigint", True)}}
    assert "t_n_seq" not in declared


def test_innocence_c2_table_without_pk_or_serial_claims_no_implicit_names():
    """Boundary: a table with neither a PRIMARY KEY nor a serial column
    claims NOTHING beyond its own name — `t_pkey`/`t_x_seq` stay ordinary,
    independently declarable tables."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (x TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t_pkey (y TEXT NOT NULL);\n"
        "CREATE TABLE IF NOT EXISTS t_x_seq (z TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {
        "t": {("x", "text", False)},
        "t_pkey": {("y", "text", True)},
        "t_x_seq": {("z", "text", True)},
    }


def test_innocence_c2_real_file_implicit_relations_do_not_collide():
    """The real file declares two BIGSERIAL PRIMARY KEY columns
    (`team_promises.promise_id`, `team_promise_candidates.id`) — their
    implicit `_pkey`/`_seq` names must not collide with each other or with
    any other statement in the file, and the file's own columns must still
    match `_REQUIRED_COLUMNS` exactly."""
    declared = parse_declared_columns(_SQL_PATH.read_text())
    assert declared.keys() == _required_as_tuples().keys()
    for table, cols in _required_as_tuples().items():
        assert declared[table] == cols


# C2 follow-up (Gear-3 council round on this PR's own diff, BEFORE the
# gate — codex-gpt-5.6-sol and kimi-code/k3, independently converging on
# the ALTER gap; codex additionally measured the truncation/collision
# residual). Not requested by the original gate comment; found and closed
# in the same PR rather than left for a second round.


def test_guilt_c2_implicit_pkey_from_alter_added_column():
    """Both council seats independently found the SAME gap: the original
    diff destructured `_parse_column_def`'s `primary_key` as `_primary_key`
    in `_parse_alter_table` and never used it. Measured against PG17:
    `ALTER TABLE t ADD COLUMN IF NOT EXISTS id BIGINT PRIMARY KEY` creates
    `t_pkey` exactly as a CREATE-body PRIMARY KEY would."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (x TEXT);\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS id BIGINT PRIMARY KEY;\n"
        "CREATE TABLE IF NOT EXISTS t_pkey (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("x", "text", False), ("id", "bigint", True)}}
    assert "t_pkey" not in declared


def test_guilt_c2_derived_pkey_name_over_63_bytes_is_rejected():
    """codex-gpt-5.6-sol's finding: PG's name allocator truncates the FULL
    derived name (base + `_pkey`/`_id_seq`) to 63 bytes, cutting into the
    base name itself — measured: a 60-byte table name's own `_pkey`/
    `_id_seq` land truncated to exactly 63 bytes, not 65/67. This parser
    cannot reproduce that truncation, so a derived name over 63 bytes is
    rejected outright, matching S6(b)'s precedent for ordinary
    identifiers."""
    long_table = "b" * 60  # + "_pkey" (5) = 65 bytes, over the limit
    sql = f"CREATE TABLE IF NOT EXISTS {long_table} (id BIGSERIAL PRIMARY KEY);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_c2_implicit_pkey_name_collision_is_rejected():
    """codex-gpt-5.6-sol's finding: if the implicit name PG would derive is
    already taken by an unrelated relation, PG does NOT reuse or error on
    that name — it retries with a numeric suffix (measured: `t_pkey`
    already a table -> the real PRIMARY KEY index becomes `t_pkey1`, not
    `t_pkey`). This parser cannot reproduce that disambiguation, so the
    collision is rejected outright rather than silently modeling the WRONG
    (already-taken) name as the real one."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t_pkey (dummy TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t (id BIGSERIAL PRIMARY KEY, x TEXT);"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_two_columns_each_primary_key_is_rejected():
    """codex-gpt-5.6-sol's finding: PG allows only ONE primary key per
    table ("cannot have more than one primary key for table", measured) —
    a hard error, not an IF-NOT-EXISTS no-op. The existing
    R6e-duplicate-primary-key-is-rejected case only covers `PRIMARY KEY
    PRIMARY KEY` repeated on ONE column; this covers two DIFFERENT columns
    each independently marked PRIMARY KEY."""
    sql = "CREATE TABLE IF NOT EXISTS t (a INT PRIMARY KEY, b INT PRIMARY KEY);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_c2_idempotent_recreate_of_pk_bearing_table_does_not_false_positive():
    """kimi-code/k3's delta-round question: `_claim_implicit_relation` is
    NOT idempotent like the old plain `occupied_relations.add` was — does
    a repeated `CREATE TABLE IF NOT EXISTS` of a table that ALREADY has a
    PRIMARY KEY now false-positive on its own second body, since the
    second body would re-derive the SAME `<table>_pkey` name? No:
    `already_created` (checked at the very top, against the table name
    itself) returns BEFORE the implicit-relation claims run at all, so a
    genuine PG no-op never reaches them — confirmed here rather than left
    to the reader to infer from the surrounding code."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (id INT PRIMARY KEY, x TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t (id INT PRIMARY KEY, x TEXT);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("id", "integer", True), ("x", "text", False)}}


# C3: two plausible wrong fixes the gate found SURVIVED S6's own tests —
# both already correct on this head (see `_parse_create_unique_index`'s
# `.lower()` and `_read_qualified_name`'s length check on the POST-prefix
# name), but neither had a test proving it, so a future regression on
# either point would have gone silently green.


def test_guilt_c3_uppercase_index_name_still_claims_lowercase_relation():
    """A mutant that adds the index name to `occupied_relations` WITHOUT
    `.lower()` first survived every existing S6a test, because they all
    used matching case on both sides. PG unquoted identifiers always fold
    to lowercase, so `CONFLICT_SLOT` and `conflict_slot` name the SAME
    relation — a real, case-differing collision must still be caught."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "CREATE UNIQUE INDEX IF NOT EXISTS CONFLICT_SLOT ON t (a);\n"
        "CREATE TABLE IF NOT EXISTS conflict_slot (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("a", "text", False)}}
    assert "conflict_slot" not in declared


def test_guilt_c3_qualified_long_table_name_is_rejected_not_just_schema_part():
    """A mutant that checks identifier length on the SCHEMA token
    (`public`) rather than the bare name after the qualifier is stripped
    survived every existing S6b test, because none of them used a
    `public.`-qualified name. `public.<64 bytes>` must still be rejected."""
    long_name = "a" * 64
    sql = f"CREATE TABLE IF NOT EXISTS public.{long_name} (x TEXT);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_c3_qualified_short_table_name_is_accepted():
    """Boundary: an ordinary `public.`-qualified name well under the limit
    must still parse exactly as its bare equivalent would."""
    sql = "CREATE TABLE IF NOT EXISTS public.t (x TEXT);"
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("x", "text", False)}}


# --- G1-G3 (fresh gate on PR #7478, pull/7478#issuecomment-5851556996):
# three plausible wrong fixes SURVIVED every C2/C3 test above, even though
# the head is already correct on every input they probe — no existing case
# used an upper-case serial column, exercised the ALTER path's own
# collision/second-PK rejection, or measured the exact 63/64-byte
# derived-name boundary. G4 (independent REAL_PG run) was discharged
# separately (pull/7478#issuecomment-5851983749); these three are
# test-only, due before T3 PR-3 merges and no later than 2026-10-04.


def test_guilt_g1_implicit_seq_name_folds_column_case():
    """G1 kills W4: a mutant that derives the sequence name from the
    column's raw token (`element[0].value`) instead of the already-
    lowercased `name` survives every existing C2 seq test, because none of
    them used an upper-case column identifier. PG unquoted identifiers
    always fold to lowercase, so `ID BIGSERIAL` still derives `t_id_seq`,
    not a case-preserved `t_ID_seq` that would leave the real name
    unclaimed and let the phantom `t_id_seq` table through."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (ID BIGSERIAL, x TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t_id_seq (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("id", "bigint", True), ("x", "text", False)}}
    assert "t_id_seq" not in declared


def test_guilt_g1_implicit_pkey_name_folds_table_case():
    """Twin of the above for the table's own PRIMARY KEY name (gate's
    'ideally' twin): an upper-case table identifier `T` already folds to
    `t` in `_read_qualified_name`, so its implicit index is `t_pkey`, not
    `T_pkey` — pinned here alongside G1 even though no mutant of this
    shape survived, for the same reason C3's two cases were pinned
    together."""
    sql = (
        "CREATE TABLE IF NOT EXISTS T (id BIGSERIAL PRIMARY KEY);\n"
        "CREATE TABLE IF NOT EXISTS t_pkey (bogus_col TEXT NOT NULL);"
    )
    declared = parse_declared_columns(sql)
    assert declared == {"t": {("id", "bigint", True)}}
    assert "t_pkey" not in declared


def test_guilt_g2_alter_added_second_primary_key_is_rejected():
    """G2 kills W5: a mutant that claims the ALTER path's implicit
    relations with a plain `occupied_relations.add` instead of
    `_claim_implicit_relation` survives every existing C2 ALTER test,
    because none of them re-claimed a name the CREATE body already
    occupies. PG errors ('multiple primary keys for table ... are not
    allowed', measured) the instant a second ALTER-added PRIMARY KEY
    column lands on a table that already has one — the CREATE-path
    equivalent is `test_guilt_two_columns_each_primary_key_is_rejected`;
    this is its ALTER-path twin."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t (id INT PRIMARY KEY);\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS k BIGINT PRIMARY KEY;"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_guilt_g2_alter_added_serial_seq_name_collision_is_rejected():
    """G2 kills W5's sequence-path twin: an ALTER-added serial column's own
    `<table>_<col>_seq` name, already taken by an unrelated relation, must
    be rejected the same way the CREATE-body serial path already is
    (`test_guilt_c2_implicit_pkey_name_collision_is_rejected`'s pkey
    equivalent), not silently re-claimed via a plain
    `occupied_relations.add`."""
    sql = (
        "CREATE TABLE IF NOT EXISTS t_n_seq (dummy TEXT);\n"
        "CREATE TABLE IF NOT EXISTS t (x TEXT);\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS n BIGSERIAL;"
    )
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


def test_innocence_g3_derived_pkey_name_exactly_63_bytes_is_accepted():
    """G3 kills W6: an off-by-one (`>= 63` instead of `> 63`) in
    `_claim_implicit_relation`'s length check survived every existing C2
    test, because none of them measured the EXACT boundary. A 58-byte
    table name's own `_pkey` (58 + 5 = 63 bytes) is the longest derived
    name PG's real NAMEDATALEN-1 limit still allows untruncated — S6b
    already has this boundary for plain identifiers, C2's implicit names
    never had their own."""
    table_58 = "b" * 58
    assert len(f"{table_58}_pkey") == 63
    # INT, not BIGSERIAL: isolates the `_pkey` boundary from the `_id_seq`
    # one (a serial PK's own `_id_seq` would be 58 + 7 = 65 bytes, over the
    # limit for an unrelated reason and rejected before this case even
    # reaches the boundary this test targets).
    sql = f"CREATE TABLE IF NOT EXISTS {table_58} (id INT PRIMARY KEY);"
    declared = parse_declared_columns(sql)
    assert declared == {table_58: {("id", "integer", True)}}


def test_guilt_g3_derived_pkey_name_64_bytes_is_rejected():
    """One byte over the boundary above: a 59-byte table name's own
    `_pkey` (59 + 5 = 64 bytes) exceeds NAMEDATALEN-1 and must still be
    rejected, pinning the boundary from the other side (an `>= 63` mutant
    would ALSO reject this one, so this case alone cannot kill W6 — it
    only proves the boundary hasn't moved the wrong way)."""
    table_59 = "b" * 59
    assert len(f"{table_59}_pkey") == 64
    sql = f"CREATE TABLE IF NOT EXISTS {table_59} (id INT PRIMARY KEY);"
    with pytest.raises(UnrecognizedSqlShapeError):
        parse_declared_columns(sql)


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


# --- Round 2 (condition C-A, PASS-WITH-CONDITIONS follow-up on PR #7395's
# gate): 8 residuals (R1-R8) the Round-1 tokenizer above was silent-wrong or
# silently accepting on, each judged against PG TRUTH — the SQL applied to a
# throwaway PG17 database, catalog read back — not against the parser's own
# prior expectations. REWORK S5(a): 16 of these 19 cases FAILED against the
# parser as it stood on origin/main (either produced a different column set
# than PG's own catalog, or was accepted where PG itself errors) — the other
# 3 (R5a/R5b before their own REWORK flip, and the R6 non-reserved-word
# control) already passed there and only pin/document a semantics choice or
# an innocence baseline, not a residual; see the PR body's mutation receipt
# for the exact case-by-case before/after. ---

_ROUND2_CA_CASES = [
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT NOT NULL);\n"
        "CREATE TABLE IF NOT EXISTS t (a TEXT NOT NULL, b TEXT);",
        ("t", {("a", "text", True)}),
        id="R1a-repeated-create-table-if-not-exists-is-a-no-op",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS b TEXT;\n"
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS b INTEGER NOT NULL DEFAULT 0;",
        ("t", {("a", "text", False), ("b", "text", False)}),
        id="R1b-repeated-add-column-if-not-exists-keeps-the-first",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT, -- note\rhidden INTEGER NOT NULL,\n d TEXT);",
        ("t", {("c", "text", False), ("d", "text", False), ("hidden", "integer", True)}),
        id="R2a-a-bare-CR-ends-a-dash-dash-comment-like-PG-does",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT -- note\rNOT NULL\n, d TEXT);",
        ("t", {("c", "text", True), ("d", "text", False)}),
        id="R2b-a-bare-CR-ends-a-comment-hiding-not-null",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (\n  c TEXT CHECK (c IN (E'x\\'')),\n"
        "  hidden INTEGER NOT NULL, -- ')),\n  d TEXT\n);",
        None,
        id="R3-e-string-escape-desync-is-rejected-not-silently-hidden",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "ALTER TABLE other.t ADD COLUMN IF NOT EXISTS b TEXT NOT NULL;",
        None,
        id="R4-non-public-schema-qualifier-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TIMESTAMPTZ(3));", None,
        id="R5a-any-typmod-is-rejected-not-dropped",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c VARCHAR(10) NOT NULL);", None,
        id="R5b-any-typmod-is-rejected-not-dropped",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT,);", None,
        id="R6a-trailing-comma-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT NULL NOT NULL);", None,
        id="R6b-null-then-not-null-conflict-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT NOT NULL NULL);", None,
        id="R6c-not-null-then-null-conflict-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c INTEGER DEFAULT 1 DEFAULT 2);", None,
        id="R6d-duplicate-default-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c INTEGER PRIMARY KEY PRIMARY KEY);", None,
        id="R6e-duplicate-primary-key-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT CHECK (1));", None,
        id="R6f-non-boolean-bare-literal-check-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT(3));", None,
        id="R6g-typmod-on-a-type-that-does-not-take-one-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (select TEXT);", None,
        id="R6h-reserved-keyword-as-a-bare-column-name-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (left TEXT);", None,
        id="R6h2-REWORK-S5-catcode-T-keyword-as-a-bare-column-name-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (status TEXT);",
        ("t", {("status", "text", False)}),
        id="R6-control-a-non-reserved-word-is-still-a-valid-column-name",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (thread_Key TEXT);", None,
        id="R7-non-ascii-identifier-kelvin-sign-is-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t ();", None,
        id="R8-empty-parenthesised-body-is-rejected",
    ),
]


@pytest.mark.parametrize("sql, expected", _ROUND2_CA_CASES)
def test_round2_ca_residual_is_parsed_to_pg_truth_or_rejected(sql, expected):
    """Condition C-A: each of these R1-R8 residuals (see this file's module
    docstring) is judged against PG TRUTH — the SQL applied to a throwaway
    PG17 database, catalog read back — never against the parser's own
    prior expectations. See `test_wa_team_promises_real_pg.py` for a subset
    of these re-proven directly against a real cluster, and the PR body for
    the full probe and the before/after mutation receipt."""
    if expected is None:
        with pytest.raises(UnrecognizedSqlShapeError):
            parse_declared_columns(sql)
    else:
        table, columns = expected
        declared = parse_declared_columns(sql)
        assert declared[table] == columns
