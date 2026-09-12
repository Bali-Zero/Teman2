"""Parity canary: every rollback that rebuilds the `policy_scope` CHECK on
`visa_decision_retention_policies` must be shape-safe against rows other
files leave behind.

Why this file exists (gate-6287d on PR #6287, mutation (c), 2026-09-12): the
gate put 285's unconditional re-narrowing of the CHECK back into 313's
rollback and every test stayed GREEN -- with the fixture's seed rolled back
there was no committed row for the ALTER to refuse. The migration suite
proves a rollback RUNS; nothing proved a rollback is safe against a row it
did not create. `visa_decision_retention_policies` is append-only (264's
guard trigger), so a scope value, once used, can never be removed to make
room for a narrower CHECK: the only honest rollback is "narrow when no row
carries MY value, otherwise leave it widened" -- the shape 285 and 304 have.

Two levels, text only, no database:

1. Every `migrations_v2/*.sql` whose rollback rebuilds the CHECK must (a)
   guard the ALTER behind `EXISTS (... WHERE policy_scope = '<X>')`, (b)
   with `<X>` being exactly the value its own forward ADDED to the list, and
   (c) rebuild the list as forward's list minus `<X>` -- neither inventing
   nor dropping another value.
2. The set of such files is asserted to be a superset of the two known
   today, so the canary cannot go green by finding nothing.

DECLARED LIMIT (the third row parked in the 313 lane's ledger-rows-held.md):
the guard protects its OWN scope only. 285's rollback with GARUDA_DOCUMENT
rows present and no GARUDA_MAGIC_LINK rows still narrows and raises. That is
a property of the shared mechanism, not of any one file's shape, and this
canary asserts shape, not sufficiency.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.db.migration_base import split_migration_sql

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
CONSTRAINT = "visa_decision_retention_policies_policy_scope_check"
#: Files known to rebuild the CHECK in their rollback as of 2026-09-12. The
#: canary must FIND at least these; a refactor that hides the rebuild from the
#: regex would otherwise read as "nothing to check".
KNOWN_REBUILDERS = {"285_garuda_magic_link.sql", "304_garuda_documents.sql"}

_LIST_RE = re.compile(
    r"ADD\s+CONSTRAINT\s+" + CONSTRAINT + r"\s+CHECK\s*\(\s*policy_scope\s+IN\s*\(([^)]*)\)",
    re.IGNORECASE,
)
#: The full safe shape: the guard, its THEN branch, its ELSE branch, END IF --
#: so the ALTER can be required INSIDE the else of THIS guard (Sol O1: textual
#: precedence alone let a guard in another DO block, a dead branch or a
#: completed IF followed by an unconditional ALTER pass).
_GUARDED_RE = re.compile(
    r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+public\.visa_decision_retention_policies\s+"
    r"WHERE\s+policy_scope\s*=\s*'(?P<scope>[A-Z_]+)'\s*\)\s*THEN(?P<then>.*?)"
    r"ELSE(?P<else>.*?)END\s+IF",
    re.IGNORECASE | re.DOTALL,
)
#: Any executable statement that ADDs a CHECK on policy_scope -- whatever the
#: constraint name, IN vs = ANY, NOT VALID -- or DROPs/VALIDATEs a constraint
#: named as the policy_scope check (Sol O1: discovery by the exact safe
#: spelling was green by omission for a new shape). A rollback that touches
#: and does not match the safe shape is RED. Dropping the COLUMN (281's
#: rollback) is not a touch: no CHECK survives to narrow anything.
_TOUCH_RE = re.compile(
    r"\bADD\s+CONSTRAINT\b[^;]*?\bCHECK\s*\([^;]*?\bpolicy_scope\b"
    r"|\b(?:DROP|VALIDATE)\s+CONSTRAINT\b[^;,]*?policy_scope_check\b",
    re.IGNORECASE | re.DOTALL,
)


def _executable(sql: str) -> str:
    """One pass over the text with a quote-aware state machine (Sol O1: a
    decoy in a block or trailing comment satisfied the regexes, and whole-line
    stripping was the only comment handling). Outside a literal: `-- ...` to
    end of line and `/* ... */` are dropped. Inside a literal: `''` becomes
    `'`, and a literal that ends and is immediately (after whitespace) followed
    by another one is joined -- PL/pgSQL concatenates adjacent literals, which
    is how 304 spells its `EXECUTE 'a ' 'b '`. A `--` inside a literal (the
    NOTICE messages) is text, not a comment."""
    out: list[str] = []
    i, n, in_str = 0, len(sql), False
    while i < n:
        ch = sql[i]
        if in_str:
            if ch == "'":
                if sql.startswith("''", i):
                    out.append("'")
                    i += 2
                    continue
                j = i + 1
                while j < n and sql[j] in " \t\r\n":
                    j += 1
                if j < n and sql[j] == "'":  # 'a ' 'b ' -> 'a b '
                    i = j + 1
                    continue
                in_str = False
            out.append(ch)
            i += 1
            continue
        if sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch == "'":
            in_str = True
        out.append(ch)
        i += 1
    return "".join(out)


def _lists(sql: str) -> list[list[str]]:
    return [re.findall(r"'([A-Z_]+)'", m.group(1)) for m in _LIST_RE.finditer(_executable(sql))]


def _touchers() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        forward, rollback = split_migration_sql(path.read_text())
        if rollback and _TOUCH_RE.search(_executable(rollback)):
            found[path.name] = (forward, rollback)
    return found


TOUCHERS = _touchers()


def test_the_canary_finds_the_rebuilders_it_was_written_against() -> None:
    missing = KNOWN_REBUILDERS - set(TOUCHERS)
    assert not missing, (
        f"{sorted(missing)} rebuild the policy_scope CHECK in their rollback but the canary's "
        "regex no longer sees them -- fix the regex, do not shrink KNOWN_REBUILDERS"
    )


@pytest.mark.parametrize("name", sorted(TOUCHERS), ids=lambda n: n.split("_")[0])
def test_a_rollback_that_touches_the_check_has_the_full_safe_shape(name: str) -> None:
    """Fail-closed: touching the CHECK in any spelling puts a file here; only
    the one safe shape gets it out -- one rebuild under the canonical name,
    with the canonical `IN (...)` list, inside the ELSE of an `IF EXISTS`
    guard on the file's own scope, and nothing else touching the CHECK."""
    forward, rollback = TOUCHERS[name]
    text = _executable(rollback)

    rebuilds = list(_LIST_RE.finditer(text))
    assert len(rebuilds) == 1, (
        f"{name}: the rollback touches the policy_scope CHECK "
        f"({[m.group(0)[:60] for m in _TOUCH_RE.finditer(text)]}) but has {len(rebuilds)} "
        f"rebuild(s) in the one recognised safe spelling -- a different constraint name, "
        "`= ANY`, NOT VALID, VALIDATE or a dynamically built list is not a shape this canary "
        "can vouch for; use the 285/304 spelling"
    )
    forward_lists = _lists(forward)
    assert len(forward_lists) == 1, (
        f"{name}: expected exactly one CHECK rebuild in the forward half"
    )
    forward_list = forward_lists[0]
    rollback_list = re.findall(r"'([A-Z_]+)'", rebuilds[0].group(1))

    added = set(forward_list) - set(rollback_list)
    assert len(added) == 1, (
        f"{name}: the forward must add exactly ONE scope the rollback removes; "
        f"forward={forward_list} rollback={rollback_list}"
    )
    own_scope = added.pop()
    assert rollback_list == [v for v in forward_list if v != own_scope], (
        f"{name}: the rollback list must be the forward list minus {own_scope!r}, in order -- "
        f"got {rollback_list}"
    )

    alter_at = rebuilds[0].start()
    owners = [
        m
        for m in _GUARDED_RE.finditer(text)
        if m.group("scope") == own_scope and m.start("else") <= alter_at < m.end("else")
    ]
    assert owners, (
        f"{name}: the CHECK rebuild at offset {alter_at} is not inside the ELSE branch of "
        f"`IF EXISTS (SELECT 1 FROM public.visa_decision_retention_policies WHERE policy_scope = "
        f"'{own_scope}') THEN ... ELSE <rebuild> END IF` -- on an append-only table an "
        "unconditional narrowing raises CheckViolationError the moment one row ever used the "
        "value (the 2026-08-25 285 bug, the gate-6287c red); a guard elsewhere, in a dead "
        "branch or before an unconditional ALTER does not count"
    )
    assert CONSTRAINT.upper() not in owners[0].group("then").upper(), (
        f"{name}: the THEN branch (rows exist) must not touch the CHECK"
    )
    # Nothing else in the rollback touches the CHECK outside that ELSE branch.
    else_span = (owners[0].start("else"), owners[0].end("else"))
    strays = [
        m.group(0)[:60]
        for m in _TOUCH_RE.finditer(text)
        if not (else_span[0] <= m.start() < else_span[1])
    ]
    assert not strays, f"{name}: statements touching the CHECK outside the guarded ELSE: {strays}"
