#!/usr/bin/env python3
"""Derive safe NOLOGIN role creation SQL from a plain pg_dump stream."""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path


_ROLE_NAME = re.compile(r"[a-z_][a-z0-9_]*\Z")
_IDENT = r'"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_$-]*'
_OWNER_RE = re.compile(rf"\bOWNER\s+TO\s+(?P<role>{_IDENT})", re.IGNORECASE)
_FOR_ROLE_RE = re.compile(rf"\bFOR\s+ROLE\s+(?P<role>{_IDENT})", re.IGNORECASE)
_GRANT_RE = re.compile(
    rf"\bGRANT\b[^;]*?\bTO\s+(?P<roles>{_IDENT}(?:\s*,\s*{_IDENT})*)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(_IDENT)
_COPY_START = re.compile(r"COPY\s.*\bFROM\s+stdin;\s*$", re.IGNORECASE)
_DEFAULT_EXCLUDES = frozenset({"postgres", "public"})


class UnsafeRoleName(ValueError):
    """Raised when a dump names a role outside the accepted identifier grammar."""


def _normalise_role(token: str, excluded: set[str]) -> str | None:
    if token.startswith('"'):
        role = token[1:-1].replace('""', '"')
    else:
        role = token.lower()

    if role.lower() in excluded:
        return None
    if not _ROLE_NAME.fullmatch(role):
        # The token is not echoed: a dump line can carry client data.
        raise UnsafeRoleName(f"unsafe role identifier rejected ({len(token)} chars)")
    return role


def scan_roles(lines: Iterable[str], *, exclude: Iterable[str] = ()) -> set[str]:
    """Return validated roles referenced by ownership and privilege statements."""
    excluded = {name.lower() for name in _DEFAULT_EXCLUDES}
    excluded.update(name.lower() for name in exclude)
    roles: set[str] = set()
    in_copy = False

    for line in lines:
        # COPY ... FROM stdin; data rows are client data, never DDL: skip them up to the
        # terminator line, so free text such as "owner to <name>" can neither create a role
        # nor abort the drill.
        if in_copy:
            if line.rstrip("\r\n") == "\\.":
                in_copy = False
            continue
        if _COPY_START.match(line):
            in_copy = True
            continue
        for pattern in (_OWNER_RE, _FOR_ROLE_RE):
            for match in pattern.finditer(line):
                role = _normalise_role(match.group("role"), excluded)
                if role is not None:
                    roles.add(role)

        for match in _GRANT_RE.finditer(line):
            for token in _TOKEN_RE.findall(match.group("roles")):
                role = _normalise_role(token, excluded)
                if role is not None:
                    roles.add(role)

    return roles


def generate_role_sql(roles: Iterable[str]) -> str:
    """Generate deterministic CREATE ROLE statements from validated identifiers."""
    checked: set[str] = set()
    for role in roles:
        if not _ROLE_NAME.fullmatch(role):
            raise UnsafeRoleName(f"unsafe role identifier rejected ({len(role)} chars)")
        checked.add(role)
    return "".join(f'CREATE ROLE "{role}" NOLOGIN;\n' for role in sorted(checked))


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
