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
    r"ADD\s+CONSTRAINT\s+"
    + CONSTRAINT
    + r"\s+CHECK\s*\(\s*policy_scope\s+IN\s*\(([^)]*)\)\s*\)(?!\s*NOT\s+VALID)",
    re.IGNORECASE,
)
#: The guard's opening. Its ELSE and END IF are then resolved by WALKING the
#: text with a balanced IF/END IF counter (Sol O2: a non-nesting regex let a
#: nested IF donate its ELSE, so a rebuild sitting in the guard's THEN arm --
#: executed precisely while own-scope rows exist -- read as guarded).
_GUARD_OPEN_RE = re.compile(
    r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+public\.visa_decision_retention_policies\s+"
    r"WHERE\s+policy_scope\s*=\s*'(?P<scope>[A-Z_]+)'\s*\)\s*THEN",
    re.IGNORECASE,
)
#: A block OPENER is `IF <condition> THEN` -- `DROP CONSTRAINT IF EXISTS ...`
#: has no THEN before its `;` and must not count as one (measured: it made the
#: walker close the guard early on both real files). END IF and ELSIF/ELSE IF
#: are matched before the bare forms so neither is miscounted.
_IF_TOKEN_RE = re.compile(
    r"\b(?P<end>END\s+IF)\b|\b(?P<elsif>ELSIF|ELSE\s+IF)\b[^;]*?\bTHEN\b"
    r"|\b(?P<open>IF)\b[^;]*?\bTHEN\b|\b(?P<els>ELSE)\b",
    re.IGNORECASE | re.DOTALL,
)


def _guard_spans(text: str, scope: str) -> list[tuple[int, int, int]]:
    """`(then_start, else_start, else_end)` for every `IF EXISTS` guard on
    `scope`, with ELSE and END IF taken at the guard's OWN nesting depth. A
    guard whose ELSE belongs to a nested IF, or that has no ELSE of its own,
    yields no span."""
    spans: list[tuple[int, int, int]] = []
    for g in _GUARD_OPEN_RE.finditer(text):
        if g.group("scope") != scope:
            continue
        depth, else_at = 0, None
        for t in _IF_TOKEN_RE.finditer(text, g.end()):
            if t.group("open"):
                depth += 1
            elif t.group("elsif"):
                continue  # same block, not a new one
            elif t.group("els"):
                if depth == 0 and else_at is None:
                    else_at = t.end()
            elif t.group("end"):
                if depth == 0:
                    if else_at is not None:
                        spans.append((g.end(), else_at, t.start()))
                    break
                depth -= 1
    return spans


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
    assert not in_str, (
        "unterminated string literal in the ROLLBACK half: the canary refuses to guess which "
        "half of the text is executable (Sol O2)"
    )
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
    owners = [sp for sp in _guard_spans(text, own_scope) if sp[1] <= alter_at < sp[2]]
    assert owners, (
        f"{name}: the CHECK rebuild at offset {alter_at} is not inside the ELSE branch -- at the "
        f"guard's OWN nesting depth -- of `IF EXISTS (SELECT 1 FROM public."
        f"visa_decision_retention_policies WHERE policy_scope = '{own_scope}') THEN ... ELSE "
        "<rebuild> END IF`. On an append-only table an unconditional narrowing raises "
        "CheckViolationError the moment one row ever used the value (the 2026-08-25 285 bug, the "
        "gate-6287c red); a guard elsewhere, a nested IF's ELSE, a dead branch, or an ALTER after "
        "END IF does not count"
    )
    then_start, else_start, else_end = owners[0]
    assert not _TOUCH_RE.search(text, then_start, else_start), (
        f"{name}: the THEN branch (rows exist) must not touch the CHECK"
    )
    # Inside the guarded ELSE: only the canonical DROP and the canonical
    # rebuild (Sol O2: a second rebuild under another name or `= ANY` beside
    # the canonical one left `len(rebuilds) == 1` and produced no stray).
    allowed = re.compile(
        r"^(?:DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?"
        + CONSTRAINT
        + r"\b|ADD\s+CONSTRAINT\s+"
        + CONSTRAINT
        + r"\b)",  # `_TOUCH_RE` stops at `policy_scope`; the IN-vs-ANY spelling is
        # settled by `_LIST_RE` (exactly one canonical rebuild) and by the count below
        re.IGNORECASE | re.DOTALL,
    )
    inside = [m.group(0) for m in _TOUCH_RE.finditer(text, else_start, else_end)]
    odd = [t[:70] for t in inside if not allowed.match(t)]
    assert not odd, (
        f"{name}: inside the guarded ELSE, only the canonical DROP and rebuild of "
        f"{CONSTRAINT} are a shape this canary can vouch for; found also: {odd}"
    )
    assert len(inside) <= 2, (
        f"{name}: more statements touch the CHECK inside the guarded ELSE than a DROP and an "
        f"ADD: {[t[:70] for t in inside]}"
    )
    # Nothing else in the rollback touches the CHECK outside that ELSE branch.
    strays = [
        m.group(0)[:70]
        for m in _TOUCH_RE.finditer(text)
        if not (else_start <= m.start() < else_end)
    ]
    assert not strays, f"{name}: statements touching the CHECK outside the guarded ELSE: {strays}"
