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
LINE_COMMENT = re.compile(r"--[^\n]*")
ROLLBACK_MARKER = re.compile(r"^--\s*===\s*ROLLBACK\s*===", re.MULTILINE)
FUNCTION_START = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?(\w+)\s*\(", re.IGNORECASE
)
DO_BLOCK = re.compile(r"\bDO\s+(\$[A-Za-z_]\w*\$|\$\$).*?\1", re.IGNORECASE | re.DOTALL)
DOLLAR_TAG = re.compile(r"\$[A-Za-z_]\w*\$|\$\$")
LOCK_CLAUSE = re.compile(r"\bFOR\s+(?:SHARE|UPDATE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", re.IGNORECASE)


def _forward(sql: str) -> str:
    """Only the forward section, with line comments stripped.

    Comments are removed because every detector below matches raw substrings:
    a header reading `-- SECURITY DEFINER is forbidden here` above a function
    that is actually SECURITY INVOKER would otherwise be read as an offender,
    and a commented-out `ALTER ... OWNER TO` would be read as proof of a
    transfer that never happens.
    """
    return LINE_COMMENT.sub(" ", ROLLBACK_MARKER.split(sql)[0])


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
        if closing == -1:
            body, after = sql[tag.end() :], ""
        else:
            body = sql[tag.end() : closing]
            end = sql.find(";", closing + len(tag.group(0)))
            after = sql[closing + len(tag.group(0)) : end if end != -1 else len(sql)]
        header = sql[match.end() : tag.start()]
        # The attribute may sit on EITHER side of the body -- Postgres accepts
        # `... SECURITY DEFINER AS $b$...$b$;` and `... AS $b$...$b$ LANGUAGE
        # plpgsql SECURITY DEFINER;` alike. Reading only the pre-body header
        # made the second ordering invisible: the gate wrote that migration and
        # the lint stayed green with the defect present. Zero of the twelve
        # migrations on disk use it, which is exactly why nothing caught it.
        attributes = (header + " " + after).upper()
        if (
            "SECURITY DEFINER" in attributes
            and LEDGER_TABLE in body
            and LOCK_CLAUSE.search(body)
        ):
            found.add(match.group(1))
    return found


ALTER_OWNER = re.compile(
    r"ALTER\s+FUNCTION\s+(?:public\.)?(\w+)\s*\([^)]*\)\s*OWNER\s+TO\s+(\w+)",
    re.IGNORECASE,
)
TRANSFER_ARRAY_ENTRY = re.compile(r"'(?:public\.)?(\w+)\s*\([^)]*\)'")
ALTER_FORMAT = re.compile(
    # the first argument may be a scalar variable (299), a loop variable (281)
    # or a subscript into the array itself -- all three reach the ALTER
    r"format\s*\(\s*'ALTER\s+FUNCTION\s+%s\s+OWNER\s+TO\s+%I'\s*,\s*(\w+)(?:\[[^\]]*\])?\s*,\s*(\w+)",
    re.IGNORECASE,
)
FOREACH = re.compile(r"FOREACH\s+(\w+)\s+IN\s+ARRAY\s+(\w+)", re.IGNORECASE)


def _transfers_in(sql: str) -> set[str]:
    """Functions a migration actually transfers to `visa_ledger_owner`.

    Two shapes count, and nothing else:

    * a literal ``ALTER FUNCTION <sig> OWNER TO visa_ledger_owner``;
    * a name inside the quoted signature array of a ``DO`` block whose body
      performs ``ALTER FUNCTION %s OWNER TO %I`` with that role, which is how
      migrations 281 and 299 do it (the ALTER is built by `format()`, so no
      literal statement exists to match).

    The first version of this helper collected EVERY ``public.<name>(``
    occurrence in any file mentioning the role, which the adversarial review
    broke in one line: a migration containing a real transfer of some unrelated
    function marks every other function in the same file as transferred, and a
    mere ``COMMENT ON FUNCTION`` or ``EXECUTE FUNCTION`` reference is enough. It
    also mislabelled `guard_visa_decision_retention_policy_mutation`, which
    migration 281 mentions but never transfers.
    """
    transferred: set[str] = set()
    for name, role in ALTER_OWNER.findall(sql):
        if role == LEDGER_OWNER:
            transferred.add(name)
    for block in DO_BLOCK.finditer(sql):
        body = block.group(0)
        if LEDGER_OWNER not in body:
            continue
        transferred |= _do_block_transfers(body)
    return transferred


def _do_block_transfers(body: str) -> set[str]:
    """Signatures a DO block actually feeds to its ``ALTER ... OWNER TO``.

    Collecting every quoted signature in the block was the same laundering
    codex rejected at file level, fixed only one level down: a block that
    transfers one function while merely naming another -- `to_regprocedure(
    'public.other()')` is migration 299's own idiom -- marked the second one
    transferred too. So the signature must reach the ALTER: it is read from the
    variable that `format('ALTER FUNCTION %s OWNER TO %I', <var>, ...)` passes,
    either assigned to it directly (299) or held in the array it iterates with
    FOREACH (281).
    """
    names: set[str] = set()
    for var, _role in ALTER_FORMAT.findall(body):
        sources = {var}
        for loop_var, array_var in FOREACH.findall(body):
            if loop_var == var:
                sources.add(array_var)
        for source in sources:
            for literal in re.finditer(
                rf"\b{re.escape(source)}\b[^;]*?:=\s*(ARRAY\s*\[[^]]*\]|'[^']*')",
                body,
                re.IGNORECASE,
            ):
                names |= set(TRANSFER_ARRAY_ENTRY.findall(literal.group(1)))
    return names


def _functions_transferred_to_the_ledger_owner() -> set[str]:
    transferred: set[str] = set()
    for path in MIGRATIONS.glob("*.sql"):
        transferred |= _transfers_in(_forward(path.read_text(encoding="utf-8")))
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


# ============================================================
# The adversarial review's own counterexamples, kept as tests
# ============================================================
#
# codex gpt-5.6-sol broke the first version of this lint in one line and was
# right. Each case below is the exact shape it produced; they live here so the
# hole cannot quietly reopen when someone "simplifies" the detectors.

_BAD_TRIGGER = """
CREATE FUNCTION public.bad_trigger()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $body$
BEGIN
    PERFORM 1 FROM public.visa_decision_retention_policies FOR SHARE;
    RETURN NEW;
END
$body$;
"""


def test_an_unrelated_transfer_in_the_same_file_does_not_launder_an_offender():
    sql = _BAD_TRIGGER + """
ALTER FUNCTION public.unrelated_function() OWNER TO visa_ledger_owner;
"""
    assert "bad_trigger" in _definer_functions_locking_the_ledger(sql)
    assert "bad_trigger" not in _transfers_in(sql), (
        "a real transfer of some OTHER function must never mark this one transferred"
    )
    assert "unrelated_function" in _transfers_in(sql)


def test_a_commented_out_transfer_is_not_a_transfer():
    sql = _BAD_TRIGGER + """
-- ALTER FUNCTION public.bad_trigger() OWNER TO visa_ledger_owner;
"""
    assert "bad_trigger" not in _transfers_in(_forward(sql))


def test_a_mere_mention_of_the_function_is_not_a_transfer():
    sql = _BAD_TRIGGER + """
COMMENT ON FUNCTION public.bad_trigger() IS 'nothing to see here';
DROP FUNCTION IF EXISTS public.something_else();
ALTER FUNCTION public.something_else() OWNER TO visa_ledger_owner;
"""
    assert "bad_trigger" not in _transfers_in(sql)


def test_security_definer_written_only_in_a_comment_is_not_an_offender():
    sql = """
-- SECURITY DEFINER is forbidden here
CREATE FUNCTION public.harmless()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
AS $body$
BEGIN
    PERFORM 1 FROM public.visa_decision_retention_policies FOR SHARE;
    RETURN NEW;
END
$body$;
"""
    assert not _definer_functions_locking_the_ledger(_forward(sql)), (
        "a comment must never make a SECURITY INVOKER function read as a definer"
    )


def test_a_do_block_transfer_array_still_counts():
    """Migrations 281 and 299 build the ALTER with format(), so no literal
    ``ALTER FUNCTION ... OWNER TO visa_ledger_owner`` statement exists to match."""
    sql = _BAD_TRIGGER + """
DO $t$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY['public.bad_trigger()'];
BEGIN
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', target_function[1], ledger_owner);
END;
$t$;
"""
    assert "bad_trigger" in _transfers_in(sql)


# ============================================================
# The Gear-3 gate's counterexamples (2026-08-30)
# ============================================================
#
# An independent on-disk gate broke the version above with two shapes the
# adversarial round had not reached. Both were real: the lint stayed green with
# the defect present. They are kept here for the same reason as the block above.

def test_security_definer_declared_after_the_body_is_still_an_offender():
    """Postgres accepts the attribute on either side of the body.

    Reading only the text BEFORE the dollar-tag made this ordering invisible.
    No migration on disk uses it, which is precisely why nothing caught it —
    a corpus that happens to be uniform is not a guarantee about the next file.
    """
    sql = """
CREATE FUNCTION public.late_definer()
RETURNS trigger
AS $body$
BEGIN
    PERFORM 1 FROM public.visa_decision_retention_policies FOR SHARE;
    RETURN NEW;
END
$body$ LANGUAGE plpgsql SECURITY DEFINER;
"""
    assert "late_definer" in _definer_functions_locking_the_ledger(sql)


def test_a_do_block_does_not_launder_a_signature_it_merely_names():
    """The signature must REACH the ALTER, not just appear in the same block.

    `to_regprocedure('public.<name>()')` is migration 299's own idiom, so a
    block that transfers one function while checking another marked both.
    """
    sql = _BAD_TRIGGER + """
DO $x$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.some_other_helper()';
    probe oid;
BEGIN
    probe := to_regprocedure('public.bad_trigger()');
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
END;
$x$;
"""
    transferred = _transfers_in(_forward(sql))
    assert "some_other_helper" in transferred, "the real transfer must still count"
    assert "bad_trigger" not in transferred, (
        "a signature the block merely names never reaches the ALTER"
    )


def test_the_two_real_migration_shapes_still_count_as_transfers():
    """Innocence control for the fix above: 299's scalar and 281's FOREACH."""
    scalar = """
DO $x$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.scalar_shape()';
BEGIN
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
END;
$x$;
"""
    loop = """
DO $y$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.loop_shape_one()',
        'public.loop_shape_two(integer, text)'
    ];
    signature text;
BEGIN
    FOREACH signature IN ARRAY target_function
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
    END LOOP;
END;
$y$;
"""
    assert "scalar_shape" in _transfers_in(scalar)
    assert {"loop_shape_one", "loop_shape_two"} <= _transfers_in(loop)
