#!/usr/bin/env python3
"""Derive safe NOLOGIN role creation SQL from a plain pg_dump stream.

The dump is read as SQL, not as text: single-quoted strings (including E'' escapes),
dollar-quoted bodies and comments are blanked before any keyword is looked for, and
COPY ... FROM stdin data rows are skipped until the ``\\.`` terminator. A role is
collected from the statement forms that make a restore abort when it is missing:
OWNER TO, FOR ROLE / FOR USER, GRANT ... TO a, b [GRANTED BY c], REVOKE ... FROM,
CREATE POLICY ... TO, SET ROLE, ALTER ROLE, and GRANT role TO role.
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

# Never created: PUBLIC and the pseudo-roles are not roles; pg_* names are predefined, and
# creating one would abort the pre-create under ON_ERROR_STOP=1. "postgres" is NOT excluded:
# the drill container's superuser is the caller's POSTGRES_USER, so a dump that says
# "OWNER TO postgres" needs that role created (pass the drill user through --exclude).
_PSEUDO = frozenset({"public", "current_user", "session_user", "current_role", "none"})
_MAX_ROLE_BYTES = 63

_DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_\x80-\U0010ffff][A-Za-z0-9_\x80-\U0010ffff]*)?\$")
_WORD = re.compile(r"[A-Za-z_\x80-\U0010ffff][A-Za-z0-9_$\x80-\U0010ffff]*")


class UnsafeRoleName(ValueError):
    """Raised when a dump names a role that cannot be created safely."""


class _Lexer:
    """Streaming SQL tokenizer: yields ('w', word) / ('q', ident) / ('p', punct) tokens."""

    def __init__(self) -> None:
        self.in_single = False
        self.single_escapes = False
        self.dollar_tag: str | None = None
        self.block_depth = 0  # PostgreSQL block comments nest

    def tokens(self, line: str) -> Iterator[tuple[str, str]]:
        i, n = 0, len(line)
        while i < n:
            if self.block_depth:
                close, opener = line.find("*/", i), line.find("/*", i)
                if opener >= 0 and (close < 0 or opener < close):
                    self.block_depth, i = self.block_depth + 1, opener + 2
                elif close >= 0:
                    self.block_depth, i = self.block_depth - 1, close + 2
                else:
                    return
                continue
            if self.dollar_tag is not None:
                end = line.find(self.dollar_tag, i)
                if end < 0:
                    return
                self.dollar_tag, i = None, end + len(self.dollar_tag)
                continue
            if self.in_single:
                ch = line[i]
                if self.single_escapes and ch == "\\":
                    i += 2
                elif ch == "'":
                    if line[i + 1 : i + 2] == "'":
                        i += 2
                    else:
                        self.in_single = False
                        i += 1
                else:
                    i += 1
                continue
            ch = line[i]
            if ch.isspace():
                i += 1
            elif line.startswith("--", i):
                return
            elif line.startswith("/*", i):
                self.block_depth, i = 1, i + 2
            elif ch == "'":
                prev = line[i - 1 : i]
                self.single_escapes = prev in ("E", "e") and (i < 2 or not line[i - 2].isalnum())
                self.in_single, i = True, i + 1
            elif ch == '"':
                j, parts = i + 1, []
                while True:
                    end = line.find('"', j)
                    if end < 0:  # an identifier never spans lines in pg_dump output
                        parts.append(line[j:])
                        j = n
                        break
                    parts.append(line[j:end])
                    if line[end + 1 : end + 2] == '"':
                        parts.append('"')
                        j = end + 2
                    else:
                        j = end + 1
                        break
                yield ("q", "".join(parts))
                i = j
            elif ch == "$":
                m = _DOLLAR_TAG.match(line, i)
                if m:
                    self.dollar_tag, i = m.group(0), m.end()
                else:
                    i += 1
            else:
                m = _WORD.match(line, i)
                if m:
                    yield ("w", m.group(0))
                    i = m.end()
                else:
                    yield ("p", ch)
                    i += 1


def _name(token: tuple[str, str], excluded: set[str]) -> str | None:
    kind, text = token
    role = text.lower() if kind == "w" else text
    # An unquoted name folds to lower case; a quoted one is exact ("Drill" is not drill).
    if kind == "w" and role in _PSEUDO:
        return None
    if role in excluded or role.startswith("pg_"):
        return None
    _check_name(role)
    return role


def _check_name(role: str) -> None:
    # The value is never echoed: a dump line can carry client data.
    if not role or len(role.encode("utf-8")) > _MAX_ROLE_BYTES:
        raise UnsafeRoleName(f"role identifier rejected (length {len(role)})")
    if any(ord(c) < 32 or ord(c) == 127 for c in role):
        raise UnsafeRoleName("role identifier rejected (control character)")


def _ident_list(tokens: list[tuple[str, str]], start: int) -> tuple[list[tuple[str, str]], int]:
    """Read ident (',' ident)* from tokens[start:]; return (idents, next index)."""
    found: list[tuple[str, str]] = []
    i = start
    while i < len(tokens) and tokens[i][0] in ("w", "q"):
        found.append(tokens[i])
        if i + 1 < len(tokens) and tokens[i + 1] == ("p", ","):
            i += 2
        else:
            i += 1
            break
    return found, i


def _statement_roles(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
    words = [(k, t.lower()) if k == "w" else (k, t) for k, t in tokens]
    first = words[0][1] if words and words[0][0] == "w" else ""
    roles: list[tuple[str, str]] = []
    # TO introduces grantees only in GRANT, CREATE POLICY and ALTER DEFAULT PRIVILEGES; elsewhere
    # (RENAME TO, OWNER TO handled apart) it must not mint roles.
    grantish = first == "grant" or (first == "create" and len(words) > 1 and words[1][1] == "policy") or (
        first == "alter" and len(words) > 2 and words[1][1] == "default" and words[2][1] == "privileges"
    )

    def kw(idx: int, *names: str) -> bool:
        return idx < len(words) and words[idx][0] == "w" and words[idx][1] in names

    for idx in range(len(words)):
        nxt = idx + 1
        if kw(idx, "owner") and kw(nxt, "to"):
            roles += _ident_list(tokens, idx + 2)[0][:1]
        elif kw(idx, "for") and kw(nxt, "role", "user"):
            roles += _ident_list(tokens, idx + 2)[0]
        elif kw(idx, "to") and grantish:
            found, after = _ident_list(tokens, idx + 1)
            roles += found
            if kw(after, "granted") and kw(after + 1, "by"):
                roles += _ident_list(tokens, after + 2)[0][:1]
        elif kw(idx, "from") and (first == "revoke" or (grantish and first == "alter")):
            found, after = _ident_list(tokens, idx + 1)
            roles += found
            if kw(after, "granted") and kw(after + 1, "by"):
                roles += _ident_list(tokens, after + 2)[0][:1]
        elif kw(idx, "granted") and kw(nxt, "by") and first in ("grant", "revoke"):
            roles += _ident_list(tokens, idx + 2)[0][:1]
    if first == "set" and (kw(1, "role") or (kw(1, "session", "local") and kw(2, "role"))):
        roles += _ident_list(tokens, 2 if kw(1, "role") else 3)[0][:1]
    if first == "alter" and kw(1, "role", "user", "group"):
        roles += _ident_list(tokens, 2)[0][:1]
    # GRANT role_a [, role_b] TO role_c: a membership grant has no ON; the granted names are roles.
    if first in ("grant", "revoke") and not any(kw(i, "on") for i in range(len(words))):
        idx_to = next((i for i in range(len(words)) if kw(i, "to", "from")), len(words))
        roles += [t for t in tokens[1:idx_to] if (t[0] == "q" or t[1].lower() not in ("option", "admin", "grant", "for", "inherit", "set", "true", "false", "with"))]
    return roles


def scan_roles(lines: Iterable[str], *, exclude: Iterable[str] = ()) -> set[str]:
    """Return validated roles referenced by ownership and privilege statements."""
    excluded = set(exclude)  # exact names: the drill user is a plain lower-case identifier
    roles: set[str] = set()
    lexer = _Lexer()
    statement: list[tuple[str, str]] = []
    in_copy = False

    for line in lines:
        # COPY ... FROM stdin; data rows are client data, never DDL: skip them up to the
        # terminator line, so free text can neither create a role nor abort the drill.
        if in_copy:
            if line.rstrip("\r\n") == "\\.":
                in_copy = False
            continue
        for token in lexer.tokens(line):
            if token == ("p", ";"):
                if statement:
                    first = statement[0][1].lower() if statement[0][0] == "w" else ""
                    tail = [t[1].lower() for t in statement[-2:] if t[0] == "w"]
                    if first == "copy" and tail == ["from", "stdin"]:
                        in_copy = True
                    else:
                        for found in _statement_roles(statement):
                            role = _name(found, excluded)
                            if role is not None:
                                roles.add(role)
                statement = []
            else:
                statement.append(token)
        if in_copy:
            continue
    return roles


def quote_ident(role: str) -> str:
    _check_name(role)
    return '"' + role.replace('"', '""') + '"'


def generate_role_sql(roles: Iterable[str]) -> str:
    """Generate deterministic CREATE ROLE statements; every name is quoted."""
    return "".join(f"CREATE ROLE {quote_ident(role)} NOLOGIN;\n" for role in sorted(set(roles)))


def _dump_lines(path: Path) -> Iterator[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        yield from handle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path, help="plain-SQL pg_dump compressed with gzip")
    parser.add_argument("--exclude", action="append", default=[], help="additional role to omit")
    parser.add_argument("--output", type=Path, required=True, help="destination SQL file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        roles = scan_roles(_dump_lines(args.dump), exclude=args.exclude)
        args.output.write_text(generate_role_sql(roles), encoding="utf-8")
    except (OSError, EOFError, UnsafeRoleName) as exc:
        print(f"role scan failed: {exc}", file=sys.stderr)
        return 2
    print(f"role pre-create SQL: {len(roles)} role(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
