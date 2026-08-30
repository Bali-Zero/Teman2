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
  ``garuda_magic_link_tokens`` never held a single row. Migration 301 cures it.

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
# NOT used to strip comments -- see _strip_line_comments for why a regex
# cannot do that job. Kept only for ROLLBACK_MARKER's sibling shape below.
ROLLBACK_MARKER = re.compile(r"^--\s*===\s*ROLLBACK\s*===", re.MULTILINE)
FUNCTION_START = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?(\w+)\s*\(", re.IGNORECASE
)
DO_BLOCK = re.compile(r"\bDO\s+(\$[A-Za-z_]\w*\$|\$\$).*?\1", re.IGNORECASE | re.DOTALL)
DOLLAR_TAG = re.compile(r"\$[A-Za-z_]\w*\$|\$\$")
OPAQUE_LANGUAGE = re.compile(r"\bLANGUAGE\s+(?:C|INTERNAL)\b", re.IGNORECASE)
SINGLE_QUOTED_BODY = re.compile(r"\bAS\s+'((?:[^']|'')*)'", re.IGNORECASE)
LOCK_CLAUSE = re.compile(r"\bFOR\s+(?:SHARE|UPDATE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", re.IGNORECASE)


def _strip_line_comments(sql: str) -> str:
    """Blank out `--` line comments WITHOUT touching `--` inside a literal.

    A regex `--[^\n]*` cannot do this, and the difference is not academic:
    Postgres treats `--` inside `'...'` or a dollar-quoted body as ordinary
    data, so the regex deletes real SQL to end-of-line whenever a message
    happens to contain a double hyphen. Measured on this repo's own migration
    299, whose text `'... % is still owned by % -- the SECURITY DEFINER trigger
    cannot take its FOR SHARE lock ...'` loses its `FOR SHARE` to the stripper.
    That is the offender detector's ONE job, and it is the PERMISSIVE one —
    the polarity spec below says a miss here is a silent production 500.

    Concrete defect this closes (kimi-code/k3, adversarial round 2026-08-30):

        CREATE FUNCTION public.evil() RETURNS trigger LANGUAGE plpgsql
        SECURITY DEFINER AS $b$
        BEGIN
            RAISE NOTICE 'see -- docs'; PERFORM 1
              FROM public.visa_decision_retention_policies FOR SHARE;
            RETURN NEW;
        END $b$;

    The old stripper ate `FOR SHARE;` along with the fake comment, so the
    function was not reported and the file passed green with the defect in it.

    Scanned character by character rather than by regex because the state
    (in a single-quoted literal / in a dollar-quoted body / in a comment) is
    not expressible as one pattern. Comments are replaced by a space, never
    deleted, so no two tokens are fused across the removal.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            # Single-quoted literal; '' is an escaped quote, not a terminator.
            out.append(ch)
            i += 1
            while i < n:
                out.append(sql[i])
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        out.append(sql[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$":
            tag = DOLLAR_TAG.match(sql, i)
            if tag is not None:
                closing = sql.find(tag.group(0), tag.end())
                end = (closing + len(tag.group(0))) if closing != -1 else n
                out.append(sql[i:end])
                i = end
                continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            newline = sql.find("\n", i)
            out.append(" ")
            i = n if newline == -1 else newline
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _forward(sql: str) -> str:
    """Only the forward section, with line comments stripped.

    Comments are removed because every detector below matches raw substrings:
    a header reading `-- SECURITY DEFINER is forbidden here` above a function
    that is actually SECURITY INVOKER would otherwise be read as an offender,
    and a commented-out `ALTER ... OWNER TO` would be read as proof of a
    transfer that never happens.

    A `--` inside a string or a dollar-quoted body is DATA, not a comment —
    see `_strip_line_comments`, which is why this is not a one-line regex.
    """
    return _strip_line_comments(ROLLBACK_MARKER.split(sql)[0])


def _definer_functions_locking_the_ledger(sql: str) -> set[str]:
    """Function names in `sql` that are SECURITY DEFINER and lock the ledger.

    SPEC — the two detectors in this file have OPPOSITE polarity, and getting
    that polarity wrong is what produced three rounds of holes (codex
    2026-08-30, then the Gear-3 gate twice). Written down so the next person
    does not rediscover it by being broken again:

    * THIS one, the offender detector, must be PERMISSIVE. Missing an offender
      is a silent production 500. So it reads the whole CREATE FUNCTION
      statement and accepts either body-quoting form, and a SECURITY DEFINER
      function whose body it cannot read AT ALL is reported rather than skipped:
      not reading the body means not being able to rule the lock out, and a
      false accusation is loud and gets fixed while a miss is not. (The gate
      reviewing this file caught the previous version of this paragraph
      promising exactly that while the code still skipped. It was corrected by
      making the code true, not by softening the claim.)
    * `_transfers_in` must be STRICT and FAIL CLOSED, for the mirror reason.

    Concretely here: the body may be dollar-quoted (`$tag$...$tag$`) or, in
    legacy-but-valid PL/pgSQL, an ordinary single-quoted string
    (`AS '...' LANGUAGE plpgsql`). The dollar-tag-only version skipped the
    second form entirely, and `SECURITY DEFINER` may sit on either side of the
    body in both.
    """
    found: set[str] = set()
    for match in FUNCTION_START.finditer(sql):
        name = match.group(1)
        tag = DOLLAR_TAG.search(sql, match.end())
        body_start = body_end = None
        if tag is not None:
            closing = sql.find(tag.group(0), tag.end())
            if closing != -1:
                body_start, body_end = tag.end(), closing
                after_body = closing + len(tag.group(0))
        if body_start is None:
            quoted = SINGLE_QUOTED_BODY.search(sql, match.end())
            if quoted is None:
                # No readable body in either form -- a C-language or externally
                # defined function, say. If it is SECURITY DEFINER we cannot
                # rule the lock out, so report it; if it is not, there is
                # nothing to report.
                terminator = sql.find(";", match.end())
                head = sql[match.end() : terminator if terminator != -1 else len(sql)]
                if "SECURITY DEFINER" in head.upper():
                    found.add(name)
                continue
            body_start, body_end = quoted.start(1), quoted.end(1)
            after_body = quoted.end()
        body = sql[body_start:body_end]
        terminator = sql.find(";", after_body)
        attributes = (
            sql[match.end() : body_start]
            + " "
            + sql[after_body : terminator if terminator != -1 else len(sql)]
        ).upper()
        if "SECURITY DEFINER" not in attributes:
            continue
        if OPAQUE_LANGUAGE.search(attributes):
            # `LANGUAGE c` / `internal`: what looks like a body is an object
            # file and a link symbol, not SQL. The lock cannot be ruled out, so
            # the permissive direction reports it. Nothing in this repo is
            # written that way today, which is exactly the argument for not
            # letting the detector depend on that staying true.
            found.add(name)
            continue
        if LEDGER_TABLE in body and LOCK_CLAUSE.search(body):
            found.add(name)
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


def ASSIGNMENT(var: str) -> re.Pattern[str]:
    """`var` assigned at the START of its own statement, nothing before it.

    The anchor is the whole point: the previous version matched
    `\\b<var>\\b[^;]*?:=`, which walked from a MENTION of the variable into an
    assignment to a different one, because nothing in between was a semicolon.
    """
    return re.compile(
        rf"^[ \t]*{re.escape(var)}\b[^;:=]*:=\s*(ARRAY\s*\[[^\]]*\]|'[^']*')",
        re.IGNORECASE | re.MULTILINE,
    )


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

    SPEC — this detector FAILS CLOSED (see the polarity note on
    `_definer_functions_locking_the_ledger`). Recognising a transfer that did
    not happen is how an offender gets laundered into silence; refusing to
    recognise one that did happen only produces a loud false accusation. So
    anything it cannot bind with certainty yields the EMPTY set.

    Three rounds of adversarial review all broke the permissive direction, each
    time by a different proximity trick on the same regex:

    * collecting every ``public.<name>(`` in a file that mentions the role;
    * collecting every quoted signature inside the DO block, so a signature
      merely NAMED by ``to_regprocedure()`` counted;
    * matching ``<var> ... := '<sig>'`` across intervening text, so an
      assignment to a DIFFERENT variable on the next line counted, and so did a
      variable reassigned between its declaration and the ALTER.

    Hence the contract, deliberately narrow: the block must contain EXACTLY ONE
    ``format('ALTER FUNCTION %s OWNER TO %I', <var>, <role>)``; ``<role>`` must
    resolve to ``visa_ledger_owner``; and the variable it formats -- or the
    array that variable iterates via FOREACH or subscripts -- must have EXACTLY
    ONE assignment, anchored at the start of its own statement. More than one
    assignment, or none, means this helper cannot say what reaches the ALTER,
    so it says nothing.
    """
    alters = ALTER_FORMAT.findall(body)
    if len(alters) != 1:
        return set()
    var, role_var = alters[0]
    if not _resolves_to_ledger_owner(body, role_var):
        return set()

    sources = {var}
    for loop_var, array_var in FOREACH.findall(body):
        if loop_var == var:
            sources.add(array_var)

    names: set[str] = set()
    for source in sources:
        literals = _sole_assignment(body, source)
        if literals is None:
            continue
        names |= set(TRANSFER_ARRAY_ENTRY.findall(literals))
    return names


def _sole_assignment(body: str, var: str) -> str | None:
    """The one literal assigned to `var` at statement start, or None.

    None means "cannot say" -- zero assignments, or more than one. Both are
    treated as no-transfer, which is the fail-closed direction.
    """
    matches = ASSIGNMENT(var).findall(body)
    return matches[0] if len(matches) == 1 else None


def _resolves_to_ledger_owner(body: str, role_var: str) -> bool:
    """`role_var` is either the role name itself or a variable holding it."""
    if role_var == LEDGER_OWNER:
        return True
    literal = _sole_assignment(body, role_var)
    return literal is not None and LEDGER_OWNER in literal


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

    `to_regprocedure('public.<name>()')` is migration 301's own idiom, so a
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


# ============================================================
# Round three (2026-08-30) — the gate broke the fixes above too
# ============================================================
#
# Same class every time: regex proximity. These closed it by changing the
# POLARITY of the two detectors rather than by patching the patterns again —
# see the SPEC notes on `_definer_functions_locking_the_ledger` and
# `_do_block_transfers`. That reframing is the fix; these are its proof.

def test_a_body_with_no_dollar_quoting_is_still_read():
    """`AS '...' LANGUAGE plpgsql` is legacy but valid, and used to vanish.

    `DOLLAR_TAG.search` found nothing, so the loop skipped the statement before
    any attribute was read — the offender was invisible whatever else was true.
    """
    sql = """
CREATE FUNCTION public.old_style()
RETURNS trigger
AS 'BEGIN PERFORM 1 FROM public.visa_decision_retention_policies FOR SHARE; RETURN NEW; END'
LANGUAGE plpgsql SECURITY DEFINER;
"""
    assert "old_style" in _definer_functions_locking_the_ledger(sql)


def test_an_assignment_to_a_different_variable_is_not_the_altered_signature():
    """The killer shape: nothing between the two is a semicolon.

    The old pattern walked from a MENTION of the ALTER variable, inside an IF
    condition, straight into the next line's assignment to `probe` — so a file
    carrying a live offender reported it transferred and passed green.
    """
    sql = _BAD_TRIGGER + """
DO $z$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.some_other_helper()';
    probe text;
BEGIN
    IF to_regprocedure(signature) IS NULL THEN
        probe := 'public.bad_trigger()';
    END IF;
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
END;
$z$;
"""
    transferred = _transfers_in(_forward(sql))
    assert "some_other_helper" in transferred, "the real transfer must still count"
    assert "bad_trigger" not in transferred, (
        "an assignment to a DIFFERENT variable never reaches the ALTER"
    )


def test_a_reassigned_variable_fails_closed():
    """Two assignments to the ALTER's variable: the helper cannot say which one
    reaches it, so it says nothing rather than counting both."""
    sql = """
DO $r$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature text;
BEGIN
    signature := 'public.never_transferred()';
    signature := 'public.actually_transferred()';
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
END;
$r$;
"""
    assert _transfers_in(sql) == set(), (
        "ambiguous dataflow must yield NO transfers — a false accusation is loud, "
        "a laundered offender is silent"
    )


def test_two_alters_in_one_block_fail_closed():
    """More than one ALTER means the single-binding contract does not hold."""
    sql = """
DO $m$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    a constant text := 'public.one()';
    b constant text := 'public.two()';
BEGIN
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', a, ledger_owner);
    EXECUTE format('ALTER FUNCTION %s OWNER TO %I', b, ledger_owner);
END;
$m$;
"""
    assert _transfers_in(sql) == set()


def test_a_definer_function_whose_body_cannot_be_read_is_reported_anyway():
    """The permissive direction, made true rather than merely claimed.

    An unreadable body means the lock cannot be ruled out. A C-language or
    externally-defined SECURITY DEFINER function has no readable body at all;
    reporting it costs one loud false accusation, skipping it costs a silent
    production 500. The gate caught the docstring promising this while the code
    skipped — this test is what stops the promise drifting from the code again.
    """
    sql = """
CREATE FUNCTION public.opaque_definer()
RETURNS trigger
LANGUAGE c
SECURITY DEFINER
AS 'MODULE_PATHNAME', 'opaque_definer';
"""
    assert "opaque_definer" in _definer_functions_locking_the_ledger(sql)


def test_a_non_definer_function_with_no_readable_body_is_not_reported():
    """Innocence control for the clause above: unreadable is not, by itself,
    an accusation — only unreadable AND SECURITY DEFINER is."""
    sql = """
CREATE FUNCTION public.opaque_invoker()
RETURNS trigger
LANGUAGE c
AS 'MODULE_PATHNAME', 'opaque_invoker';
"""
    assert "opaque_invoker" not in _definer_functions_locking_the_ledger(sql)


def test_a_double_hyphen_inside_a_literal_does_not_hide_the_lock():
    """GUILT. The offender detector is the PERMISSIVE one, so the thing that
    must never happen is a real SECURITY DEFINER ledger-locker going
    unreported. A `--` inside a string literal is DATA; a regex stripper reads
    it as a comment and deletes the rest of the line, `FOR SHARE` included.

    Found by kimi-code/k3 on 2026-08-30 as a synthetic repro, then confirmed
    to fire on this repo's own migration 301, whose exception message contains
    `-- the SECURITY DEFINER trigger cannot take its FOR SHARE lock`.
    """
    sql = """
CREATE FUNCTION public.evil() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $b$
BEGIN
    RAISE NOTICE 'see -- docs'; PERFORM 1 FROM public.visa_decision_retention_policies FOR SHARE;
    RETURN NEW;
END $b$;
"""
    assert "evil" in _definer_functions_locking_the_ledger(_forward(sql))


def test_a_double_hyphen_inside_a_dollar_quoted_body_does_not_hide_the_lock():
    """GUILT, second quoting form. A dollar-quoted body is equally literal."""
    sql = """
CREATE FUNCTION public.evil2() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $x$
BEGIN
    RAISE EXCEPTION 'a -- b';
    PERFORM 1 FROM public.visa_decision_retention_policies FOR UPDATE;
    RETURN NEW;
END $x$;
"""
    assert "evil2" in _definer_functions_locking_the_ledger(_forward(sql))


def test_a_real_comment_is_still_stripped():
    """INNOCENCE. Teaching the stripper about literals must not stop it
    stripping actual comments -- that is the false-accusation half, and
    test_security_definer_written_only_in_a_comment_is_not_an_offender above
    depends on it. Asserted directly here so the property is named."""
    stripped = _strip_line_comments(
        "SELECT 1; -- SECURITY DEFINER ... FOR SHARE\nSELECT 2;"
    )
    assert "SECURITY DEFINER" not in stripped
    assert "FOR SHARE" not in stripped
    assert "SELECT 1;" in stripped and "SELECT 2;" in stripped


def test_an_escaped_quote_inside_a_literal_does_not_end_it():
    """INNOCENCE. `''` is an escaped quote, not a terminator. Getting this
    wrong flips the scanner's state and makes the REST of the file look like
    a literal, which would silence every detector after it."""
    stripped = _strip_line_comments(
        "SELECT 'it''s -- fine'; -- a real comment\nSELECT 'x' FOR SHARE;"
    )
    assert "it''s -- fine" in stripped
    assert "a real comment" not in stripped
    assert "FOR SHARE" in stripped


def test_the_stripper_does_not_maul_migration_299_itself():
    """The live case. 299's own exception text carries a double hyphen ahead
    of the words FOR SHARE; before this fix the stripper deleted them."""
    sql = (MIGRATIONS / "301_garuda_magic_link_binding_owner.sql").read_text()
    forward = _forward(sql)
    assert "the SECURITY DEFINER trigger cannot take its FOR SHARE lock" in forward
