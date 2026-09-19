"""The LIVE CHECK allowlists in db/migrations_v2 must agree with the shared
constant `TaxConsultantConstants` (backend/app/core/constants.py).

The defect migration 319 cured (SAETTA-20260915 / W-C, slice R-C) was exactly
this class of drift: four independent Python copies of a 5-address allowlist
and two DB CHECK constraints, all supposed to agree, silently didn't.
Restating a list by hand in a test would just add a SEVENTH copy that could
drift the same way, so this test PARSES the .sql.

TWO THINGS THIS TEST DELIBERATELY DOES NOT DO, both found by adversarial
review 2026-09-16:

1. It does not pin migration 319 BY NAME. The first draft did, which made the
   documented procedure for the next staff change ("edit the constant, add a
   new migration, update team_members") fail this test — the pressure it
   created was to rewrite an already-applied migration, the one thing a
   migration directory must never do. It now resolves the HIGHEST-numbered
   migration that redefines each constraint, so a future 3xx takes over
   automatically.

2. It does not assert list EQUALITY against CANONICAL. During the expand
   phase the live CHECK legitimately also accepts the two retired aliases
   (see 319's EXPAND header), and after the later contract migration it will
   not. Both states must pass, so the invariants asserted are the ones that
   are true in BOTH and that actually protect someone:
     - every canonical address is accepted (no real consultant is ever locked
       out of the portal by the schema), and
     - nothing outside canonical + the known legacy aliases is accepted (a
       ghost cannot re-enter unnoticed).
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.core.constants import TaxConsultantConstants

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"

_EMAIL_RE = re.compile(r"'([\w.+-]+@balizero\.com)'")
_ROLLBACK_MARKER = "-- === ROLLBACK ==="


def _forward_sql(path: Path) -> str:
    """Only the FORWARD section — the rollback section legitimately restores
    the old ghost-laced lists, and must not be mistaken for the live ones."""
    text = path.read_text(encoding="utf-8")
    if _ROLLBACK_MARKER not in text:
        return text
    forward, rollback = text.split(_ROLLBACK_MARKER, 1)
    assert rollback.strip(), f"{path.name}: rollback section must not be empty"
    return forward


def _latest_migration_defining(constraint_name: str) -> Path:
    """The highest-numbered migration whose FORWARD section adds this
    constraint — i.e. the one whose list is actually in force."""
    marker = f"ADD CONSTRAINT {constraint_name}"
    candidates = [
        path
        for path in MIGRATIONS_DIR.glob("*.sql")
        if marker in _forward_sql(path)
    ]
    assert candidates, f"no migration adds {constraint_name}"
    return max(candidates, key=lambda p: int(p.stem.split("_")[0]))


def _constraint_email_list(constraint_name: str) -> list[str]:
    path = _latest_migration_defining(constraint_name)
    forward_sql = _forward_sql(path)
    start = forward_sql.index(f"ADD CONSTRAINT {constraint_name}")
    end = forward_sql.index(");", start)
    return _EMAIL_RE.findall(forward_sql[start:end])


def _legacy() -> set[str]:
    return set(TaxConsultantConstants.LEGACY_ALIASES)


def test_clients_check_accepts_every_canonical_address() -> None:
    accepted = set(_constraint_email_list("clients_tax_consultant_check"))
    missing = set(TaxConsultantConstants.CANONICAL) - accepted
    assert not missing, f"real consultants locked out by the schema: {sorted(missing)}"


def test_clients_check_accepts_nothing_unknown() -> None:
    accepted = set(_constraint_email_list("clients_tax_consultant_check"))
    unexpected = accepted - set(TaxConsultantConstants.CANONICAL) - _legacy()
    assert not unexpected, f"address in the CHECK that is neither real nor a known alias: {sorted(unexpected)}"


def test_lkpm_check_accepts_every_assignee() -> None:
    accepted = set(_constraint_email_list("lkpm_reports_assigned_to_check"))
    missing = set(TaxConsultantConstants.LKPM_ASSIGNEES) - accepted
    assert not missing, f"assignees locked out by the schema: {sorted(missing)}"


def test_lkpm_check_accepts_nothing_unknown() -> None:
    accepted = set(_constraint_email_list("lkpm_reports_assigned_to_check"))
    unexpected = accepted - set(TaxConsultantConstants.LKPM_ASSIGNEES) - _legacy()
    assert not unexpected, f"address in the CHECK that is neither an assignee nor a known alias: {sorted(unexpected)}"


def test_a_dropped_canonical_address_is_caught() -> None:
    """Guilt control: the 'nobody is locked out' assertion must actually break
    when a real address goes missing from the parsed list — otherwise it is a
    test that agrees with itself."""
    accepted = set(_constraint_email_list("clients_tax_consultant_check"))
    accepted.discard("faysha.tax@balizero.com")
    assert set(TaxConsultantConstants.CANONICAL) - accepted


def test_a_stranger_in_the_check_is_caught() -> None:
    """Guilt control for the mirror assertion."""
    accepted = set(_constraint_email_list("clients_tax_consultant_check"))
    accepted.add("stranger@balizero.com")
    assert accepted - set(TaxConsultantConstants.CANONICAL) - _legacy()


def test_the_resolver_picks_the_highest_numbered_migration() -> None:
    """The reason this file no longer names 319: prove the resolver follows
    the number, so the next staff change does not have to edit history."""
    path = _latest_migration_defining("clients_tax_consultant_check")
    numbers = [
        int(p.stem.split("_")[0])
        for p in MIGRATIONS_DIR.glob("*.sql")
        if "ADD CONSTRAINT clients_tax_consultant_check" in _forward_sql(p)
    ]
    assert int(path.stem.split("_")[0]) == max(numbers)
