"""A SECURITY DEFINER trigger that LOCKS the retention-policy ledger must be
owned by ``visa_ledger_owner``.

This defect has now shipped twice.

* 2026-08-07 -- migration 264's ``bind_visa_evaluate_idempotency_retention_policy``
  ran as its invoker, so the low-privilege application role could not complete
  the ``SELECT ... FOR SHARE`` inside it. Migration 268 cured it, and
  ``backend/tests/scripts/visa_engine/test_retention_binding_security_definer.py``
  reproduces that incident against a throwaway cluster.
* 2026-08-30 -- migration 285's ``bind_garuda_magic_link_token_retention_policy``
  was written ``SECURITY DEFINER`` but was never transferred to
  ``visa_ledger_owner``, so it ran with the privileges of a role that also
  cannot take the lock. Every magic-link issuance answered 500 for weeks and
  ``garuda_magic_link_tokens`` never held a single row. Migration 299 cures it.

Both migrations were reviewed and merged. Neither review caught it, because
nothing about the SQL looks wrong on its own: ``SECURITY DEFINER`` is present,
the lock is deliberate, and the omission is a transfer that lives in a
DIFFERENT part of the file (or, here, in no part of it). Nothing fails at
migration time either -- the privilege is only exercised on the first real
INSERT, which is why it surfaces as a silent runtime 500 long afterwards.

So this is a STATIC test, deliberately: it needs no database, runs on every
PR, and reads the migration text the way the reviewer could not. It fails the
moment a new migration introduces the shape without the transfer.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
assert MIGRATIONS.is_dir(), (
    f"migrations directory not found at {MIGRATIONS} — a glob over a missing "
    "directory returns empty silently, which would make every assertion below "
    "pass for the wrong reason"
)

LEDGER_TABLE = "visa_decision_retention_policies"
LEDGER_OWNER = "visa_ledger_owner"
ROLLBACK_MARKER = re.compile(r"^--\s*===\s*ROLLBACK\s*===", re.MULTILINE)
FUNCTION_START = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?(\w+)\s*\(", re.IGNORECASE
)
DOLLAR_TAG = re.compile(r"\$[A-Za-z_]\w*\$|\$\$")
LOCK_CLAUSE = re.compile(r"\bFOR\s+(?:SHARE|UPDATE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", re.IGNORECASE)


def _forward(sql: str) -> str:
    """Only the forward section: the rollback section is never executed."""
    return ROLLBACK_MARKER.split(sql)[0]


def _definer_functions_locking_the_ledger(sql: str) -> set[str]:
    """Function names in `sql` that are SECURITY DEFINER and lock the ledger.

    The body is delimited by its own dollar-quote tag, not by "text until the
    next CREATE FUNCTION". The coarse version of this helper attributed one
    function's body to its neighbour and reported
    `prepare_visa_evaluate_idempotency_reservation` (migration 264) as an
    offender when production shows it correctly owned by `visa_ledger_owner`
    and it does not read the ledger at all. A lint that cries wolf is a lint
    someone deletes, so it reads the real body.
    """
    found: set[str] = set()
    for match in FUNCTION_START.finditer(sql):
        tag = DOLLAR_TAG.search(sql, match.end())
        if tag is None:
            continue
        closing = sql.find(tag.group(0), tag.end())
        body = sql[tag.end() : closing if closing != -1 else len(sql)]
        header = sql[match.end() : tag.start()]
        if (
            "SECURITY DEFINER" in header.upper()
            and LEDGER_TABLE in body
            and LOCK_CLAUSE.search(body)
        ):
            found.add(match.group(1))
    return found


def _functions_transferred_to_the_ledger_owner() -> set[str]:
    """Every function name named in a migration that transfers to the owner."""
    transferred: set[str] = set()
    for path in MIGRATIONS.glob("*.sql"):
        sql = _forward(path.read_text(encoding="utf-8"))
        if LEDGER_OWNER not in sql or "OWNER TO" not in sql.upper():
            continue
        transferred.update(re.findall(r"public\.(\w+)\s*\(", sql))
    return transferred


def test_every_definer_trigger_that_locks_the_ledger_is_transferred_to_its_owner():
    offenders: dict[str, str] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        for name in _definer_functions_locking_the_ledger(_forward(path.read_text(encoding="utf-8"))):
            offenders.setdefault(name, path.name)

    transferred = _functions_transferred_to_the_ledger_owner()
    missing = {name: origin for name, origin in offenders.items() if name not in transferred}

    assert not missing, (
        "These SECURITY DEFINER functions lock "
        f"{LEDGER_TABLE} but are never transferred to {LEDGER_OWNER}: "
        f"{missing}. SECURITY DEFINER alone buys nothing here -- the function runs "
        "with its OWNER's privileges, and the application role holds only SELECT on "
        "that table, so the lock is denied at runtime with InsufficientPrivilegeError. "
        "Nothing fails at migration time; it surfaces as a silent 500 on the first "
        "real INSERT. Add a role-guarded ownership-transfer DO block, as migrations "
        "281 and 299 do."
    )


def test_the_test_can_actually_see_the_shape_it_guards():
    """Innocence control: a guard that matches nothing would pass forever."""
    seen: set[str] = set()
    for path in MIGRATIONS.glob("*.sql"):
        seen |= _definer_functions_locking_the_ledger(_forward(path.read_text(encoding="utf-8")))
    assert seen, (
        "no SECURITY DEFINER function locking the retention ledger was found at all "
        "— the detector is broken, not the migrations"
    )
    assert _functions_transferred_to_the_ledger_owner(), (
        "no ownership transfer was found in any migration — the second detector is broken"
    )
