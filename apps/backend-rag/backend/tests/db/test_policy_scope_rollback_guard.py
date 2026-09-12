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
_GUARD_RE = re.compile(
    r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+public\.visa_decision_retention_policies\s+"
    r"WHERE\s+policy_scope\s*=\s*'([A-Z_]+)'\s*\)",
    re.IGNORECASE,
)


def _executable(sql: str) -> str:
    """Comment-free text normalised so the inline form (285) and the dynamic
    `EXECUTE 'a ' 'b '` form (304) read the same: adjacent string literals
    are joined first (PL/pgSQL concatenates them), THEN the `''` doubling
    inside a literal is undone. Order matters -- undoing first would turn a
    literal boundary `' '` into a lone quote and hide the CHECK from the
    regex, which is exactly the "green by finding nothing" this file's
    superset assertion guards against."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    text = "\n".join(lines)
    text = re.sub(r"'\s*\n\s*'", "", text)  # 'a '\n'b ' -> 'a b '
    return text.replace("''", "'")


def _lists(sql: str) -> list[list[str]]:
    return [re.findall(r"'([A-Z_]+)'", m.group(1)) for m in _LIST_RE.finditer(_executable(sql))]


def _rebuilders() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        forward, rollback = split_migration_sql(path.read_text())
        if rollback and _LIST_RE.search(_executable(rollback)):
            found[path.name] = (forward, rollback)
    return found


REBUILDERS = _rebuilders()


def test_the_canary_finds_the_rebuilders_it_was_written_against() -> None:
    missing = KNOWN_REBUILDERS - set(REBUILDERS)
    assert not missing, (
        f"{sorted(missing)} rebuild the policy_scope CHECK in their rollback but the canary's "
        "regex no longer sees them -- fix the regex, do not shrink KNOWN_REBUILDERS"
    )


@pytest.mark.parametrize("name", sorted(REBUILDERS), ids=lambda n: n.split("_")[0])
def test_a_rollback_that_rebuilds_the_check_is_guarded_on_its_own_scope(name: str) -> None:
    forward, rollback = REBUILDERS[name]
    forward_lists = _lists(forward)
    assert len(forward_lists) == 1, (
        f"{name}: expected exactly one CHECK rebuild in the forward half"
    )
    rollback_lists = _lists(rollback)
    assert len(rollback_lists) == 1, f"{name}: expected exactly one CHECK rebuild in the rollback"
    forward_list, rollback_list = forward_lists[0], rollback_lists[0]

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

    text = _executable(rollback)
    alter_at = _LIST_RE.search(text).start()  # type: ignore[union-attr]
    guards = [(m.start(), m.group(1)) for m in _GUARD_RE.finditer(text)]
    own_guards = [pos for pos, scope in guards if scope == own_scope and pos < alter_at]
    assert own_guards, (
        f"{name}: the CHECK rebuild at offset {alter_at} is not preceded by "
        f"`IF EXISTS (SELECT 1 FROM public.visa_decision_retention_policies WHERE policy_scope = "
        f"'{own_scope}')` -- on an append-only table an unconditional narrowing raises "
        "CheckViolationError the moment one row ever used the value (the 2026-08-25 285 bug, "
        f"the gate-6287c red); guards found: {guards}"
    )
