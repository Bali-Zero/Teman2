"""Read-only Visa Oracle production privilege and privacy preflight."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger("visa_engine.operational_preflight")

PREFLIGHT_DSN_ENV = "VISA_ENGINE_PREFLIGHT_DATABASE_URL"

ACTIVATION_FUNCTION = "public.visa_activate_rule_pack(uuid,text,text)"
ACTIVATION_SET_FUNCTION = "public.visa_replace_activation_set(uuid[],text,text)"
PREPARE_IDEMPOTENCY_FUNCTION = (
    "public.prepare_visa_evaluate_idempotency_reservation(bytea,integer,text)"
)
RETENTION_FUNCTIONS = (
    "public.purge_visa_evaluate_idempotency(integer,text)",
    "public.purge_visa_decisions(integer,text)",
    "public.visa_idempotency_retention_evidence()",
    "public.visa_idempotency_key_usage_evidence()",
    "public.visa_decision_retention_evidence()",
)
PRIVACY_FUNCTIONS = (
    "public.erase_visa_decision_for_dsr(uuid,text,text)",
    "public.set_visa_decision_legal_hold(uuid,boolean,text,text,text,text,"
    "timestamp with time zone)",
)
# The two binders migration 289 re-scopes. Bare `proname` (not the signature
# form above) because this pair is looked up in `pg_proc.proname` to read the
# LIVE body, not passed to `to_regprocedure`.
#
# `bind_visa_decision_payload_retention` is deliberately NOT here: it resolves
# its parent through `visa_decisions.id`, never through
# `visa_decision_retention_policies`, so no scope predicate belongs in it and
# demanding one would make this check permanently red.
SCOPE_BOUND_RETENTION_BINDERS = (
    "bind_visa_decision_retention_policy",
    "bind_visa_evaluate_idempotency_retention_policy",
)
# Matches the WHERE-clause predicate 289 installs, tolerating any whitespace.
# Matching this pattern is NECESSARY but NOT SUFFICIENT — see
# `_active_lookups_are_scoped` for the part that makes it mean something.
_SCOPE_PREDICATE_RE = re.compile(
    r"policy_scope\s*=\s*'VISA_DECISION'", re.IGNORECASE
)
# The active-policy lookup this predicate has to be guarding. `NEW.` excluded:
# `NEW.effective_period` is a column reference on the row being inserted, not a
# containment test against the policy table.
_ACTIVE_LOOKUP_RE = re.compile(r"(?<!NEW\.)(?<!\w)effective_period\s*@>", re.IGNORECASE)
# How far from a lookup the predicate may sit and still plausibly belong to the
# same SELECT. Deliberately generous: this is a smoke alarm, not a SQL parser.
_SCOPE_WINDOW_LINES = 10


def _noise_mask(body: str) -> list[bool]:
    """Mark every character that sits inside a comment or a string literal.

    A MASK, not a deletion — and that distinction is the whole lesson here.
    The first attempt blanked string literals outright, which looked right and
    was self-defeating: the predicate being searched for, `policy_scope =
    'VISA_DECISION'`, ENDS IN A STRING LITERAL, so blanking every literal
    erased the very thing the probe exists to find. It reported a correctly
    scoped body as unscoped. Measured, not reasoned about.

    With a mask the question becomes the right one: is the `policy_scope`
    TOKEN itself real code, or is it text inside a string or a comment? That
    answers both evasions a cross-family refuter reproduced against the earlier
    one-line `re.sub(r"--[^\n]*", "", body)`:

      FALSE GREEN — `RAISE NOTICE $msg$policy_scope = 'VISA_DECISION'$msg$;`
        satisfied the pattern while the real SELECT stayed scope-blind. The
        dangerous direction: a broken database called healthy.
      FALSE RED   — a legitimate line carrying `'range x--y'` was truncated at
        the `--`, taking a real predicate on that line with it. A nightly false
        CRITICAL, which is how a probe gets ignored.

    An UNTERMINATED dollar quote masks only its own tag, never the rest of the
    body. PostgreSQL cannot store such a body, so reaching that branch means the
    input is not what we think it is — and going blind over the remainder would
    make the probe answer "scoped" precisely when it understands least (scar #2:
    the condition that breaks the thing must not also silence the alarm).
    """

    mask = [False] * len(body)
    i, n = 0, len(body)
    while i < n:
        if body.startswith("--", i):
            while i < n and body[i] != "\n":
                mask[i] = True
                i += 1
        elif body.startswith("/*", i):
            while i < n and not body.startswith("*/", i):
                mask[i] = True
                i += 1
            for _ in range(min(2, n - i)):
                mask[i] = True
                i += 1
        elif body[i] == "'":
            mask[i] = True
            i += 1
            while i < n:
                if body.startswith("''", i):
                    mask[i] = mask[i + 1] = True
                    i += 2
                    continue
                closing = body[i] == "'"
                mask[i] = True
                i += 1
                if closing:
                    break
        elif body[i] == "$":
            tag = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", body[i:])
            if tag:
                token = tag.group(0)
                end = body.find(token, i + len(token))
                if end == -1:
                    # Unterminated: mask the tag only, keep reading the tail.
                    for _ in range(len(token)):
                        mask[i] = True
                        i += 1
                else:
                    stop = end + len(token)
                    while i < stop:
                        mask[i] = True
                        i += 1
            else:
                i += 1
        else:
            i += 1
    return mask


def _real_code_spans(body: str) -> tuple[str, list[bool]]:
    return body, _noise_mask(body)


def _active_lookups_are_scoped(body: str) -> bool:
    """True when EVERY active-policy lookup in `body` carries the scope predicate.

    Asserting on the LOOKUPS rather than on the mere presence of the predicate
    is what closes the false-green: a body whose SELECT resolves by environment
    alone fails no matter how many times the phrase appears elsewhere. A body
    with no lookup at all is vacuously fine — it is not the shape 289 repairs.

    Both the lookups and the predicates are counted only where they are real
    code, per `_noise_mask`.
    """

    mask = _noise_mask(body)
    line_start: list[int] = [0]
    for index, char in enumerate(body):
        if char == "\n":
            line_start.append(index + 1)

    def _line_of(offset: int) -> int:
        low, high = 0, len(line_start) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if line_start[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return low

    predicate_offsets = [
        m.start() for m in _SCOPE_PREDICATE_RE.finditer(body) if not mask[m.start()]
    ]
    lookup_offsets = [
        m.start() for m in _ACTIVE_LOOKUP_RE.finditer(body) if not mask[m.start()]
    ]

    # Rule 1 — COUNT. One predicate cannot scope two lookups. A line window
    # alone cannot tell two adjacent SELECTs apart (they sit well inside any
    # window generous enough for the real bodies, where the predicate is one
    # line above its lookup), so proximity is paired with a count: N lookups
    # demand at least N predicates. Both live binders carry exactly one of each.
    if len(predicate_offsets) < len(lookup_offsets):
        return False

    # Rule 2 — PROXIMITY. Every lookup must have a predicate near it, so a
    # predicate parked far away in an unrelated statement cannot vouch for it.
    predicate_lines = {_line_of(offset) for offset in predicate_offsets}
    for offset in lookup_offsets:
        here = _line_of(offset)
        if not any(
            abs(candidate - here) <= _SCOPE_WINDOW_LINES
            for candidate in predicate_lines
        ):
            return False
    return True


# Migration 264's three BEFORE INSERT trigger functions that resolve the
# active Zero-approved retention policy via `SELECT ... FOR SHARE`. Migration
# 268 made all three `SECURITY DEFINER` + owned by `visa_ledger_owner` (see
# that migration's header for the 2026-08-07 incident this closes: `FOR
# SHARE` requires UPDATE, which the least-privilege runtime role no longer
# holds on the locked tables). Unlike every other entry in SENSITIVE_FUNCTIONS,
# no role is expected to hold EXECUTE on these: they are pure trigger
# functions Postgres invokes implicitly on INSERT, never called directly by
# any caller, and migration 268 also REVOKEs the default PUBLIC EXECUTE grant
# as defense-in-depth. Deliberately absent from every `_function_allowlist`
# entry below so every `function:{role}:{signature}` check expects EXECUTE
# False across the board -- only the `owner:{signature}` check applies.
RETENTION_BINDING_TRIGGER_FUNCTIONS = (
    "public.bind_visa_evaluate_idempotency_retention_policy()",
    "public.bind_visa_decision_retention_policy()",
    "public.bind_visa_decision_payload_retention()",
)
SENSITIVE_FUNCTIONS = (
    ACTIVATION_FUNCTION,
    ACTIVATION_SET_FUNCTION,
    PREPARE_IDEMPOTENCY_FUNCTION,
    *RETENTION_FUNCTIONS,
    *PRIVACY_FUNCTIONS,
    *RETENTION_BINDING_TRIGGER_FUNCTIONS,
)

# The role every governed object in this schema must belong to. Named here
# because the class-level census below compares against it; the pre-existing
# per-object checks still spell it inline and are deliberately left alone.
LEDGER_OWNER = "visa_ledger_owner"

# The class-level floor behind `definer:public-security-definer-ledger-owned`.
# Held as a module constant, not inlined, so a real-Postgres test can run the
# SHIPPED text against a real catalog instead of retyping it and drifting from
# the code it is supposed to guard (scar #9 / W114: a fake and the code it
# checks share the same imagination).
#
# It asks the catalog for EVERY SECURITY DEFINER function in `public` and who
# owns it -- no list, no inventory to keep up to date. `prosecdef` is the
# property that makes ownership load-bearing in the first place: a SECURITY
# DEFINER function executes with its OWNER's privileges, so an owner that
# cannot do what the body needs turns the whole construct into a no-op that
# fails only on the first real call.
# Every catalog name is `pg_catalog.`-qualified, and that is load-bearing, not
# housekeeping. An adversarial round (codex gpt-5.6-sol, xhigh) supplied a
# working evasion: the application role can CREATE in `public`, so a
# `public.pg_get_userbyid(oid)` returning a constant plus a `search_path` of
# `public, pg_catalog` makes an unqualified census report a FORGED owner and
# answer ok=True with the ownership still wrong. A privilege check answerable by
# an object the checked role may create is not a check. Qualified names cannot
# be redirected by any search_path.
#
# `prokind` comes back so the remediation names the right statement: a SECURITY
# DEFINER PROCEDURE carries the identical hazard and is censused on purpose, but
# is moved with ALTER PROCEDURE, not ALTER FUNCTION. Cast to `text`: `prokind`
# is Postgres's `"char"` type, which asyncpg decodes to BYTES, so the label
# lookup silently missed and printed `[b'p']`. Found by the real-Postgres test,
# never by the fake -- the fake had been told the answer.
SECURITY_DEFINER_CENSUS_SQL = """
SELECT proc.proname
           || '('
           || pg_catalog.pg_get_function_identity_arguments(proc.oid)
           || ')' AS signature,
       pg_catalog.pg_get_userbyid(proc.proowner) AS owner,
       proc.prokind::text AS kind
  FROM pg_catalog.pg_proc AS proc
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = proc.pronamespace
 WHERE namespace.nspname = 'public'
   AND proc.prosecdef
 ORDER BY signature
"""

# pg_proc.prokind, spelled out for the operator-facing message.
_PROKIND_LABEL = {"f": "function", "p": "procedure", "a": "aggregate", "w": "window"}


def _security_definer_violations(
    rows, *, expected_owner: str = LEDGER_OWNER
) -> list[str]:
    """Every censused routine whose owner is not `expected_owner`.

    Split out from the check so a real-Postgres test can feed it rows read from
    an actual catalog by `SECURITY_DEFINER_CENSUS_SQL`, rather than proving the
    verdict only against a hand-written fake.

    `expected_owner` is a parameter solely so that test can use a
    uuid-suffixed throwaway role: a privilege boundary is cluster-wide, so a
    test may not create a role literally named `visa_ledger_owner`. Nothing in
    production passes it.
    """

    return [
        f"{row['signature']} [{_PROKIND_LABEL.get(row['kind'], row['kind'])}] "
        f"owned by {row['owner']}"
        for row in rows
        if row["owner"] != expected_owner
    ]


SENSITIVE_TABLES = (
    "visa_rule_packs",
    "visa_ruleset_activations",
    "visa_decisions",
    "visa_decision_payloads",
    "visa_source_records",
    "visa_evaluate_idempotency",
    "visa_decision_retention_policies",
    "visa_decision_legal_hold_events",
    "visa_decision_retention_batches",
    "visa_idempotency_retention_batches",
    "visa_decision_dsr_erasure_batches",
)
TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)
PG17_TABLE_PRIVILEGES = ("MAINTAIN",)
ALL_TABLE_PRIVILEGES = (*TABLE_PRIVILEGES, *PG17_TABLE_PRIVILEGES)
CAPABILITY_ROLES = (
    "visa_pack_writer",
    "visa_activation_executor",
    "visa_policy_writer",
    "visa_retention_executor",
    "visa_privacy_operator",
)


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def _function_allowlist(runtime_role: str) -> dict[str, frozenset[str]]:
    return {
        runtime_role: frozenset({PREPARE_IDEMPOTENCY_FUNCTION}),
        "visa_pack_writer": frozenset(),
        "visa_activation_executor": frozenset(
            {ACTIVATION_FUNCTION, ACTIVATION_SET_FUNCTION}
        ),
        "visa_policy_writer": frozenset(),
        "visa_retention_executor": frozenset(RETENTION_FUNCTIONS),
        "visa_privacy_operator": frozenset(PRIVACY_FUNCTIONS),
    }


def _table_privilege_allowlist(
    runtime_role: str,
) -> dict[str, frozenset[tuple[str, str]]]:
    return {
        runtime_role: frozenset(
            {
                ("visa_rule_packs", "SELECT"),
                ("visa_ruleset_activations", "SELECT"),
                ("visa_decisions", "SELECT"),
                ("visa_decision_payloads", "SELECT"),
                ("visa_evaluate_idempotency", "SELECT"),
                ("visa_decision_retention_policies", "SELECT"),
                ("visa_decisions", "INSERT"),
                ("visa_decision_payloads", "INSERT"),
                ("visa_evaluate_idempotency", "INSERT"),
                ("visa_evaluate_idempotency", "UPDATE"),
            }
        ),
        "visa_pack_writer": frozenset(
            {
                ("visa_rule_packs", "SELECT"),
                ("visa_rule_packs", "INSERT"),
            }
        ),
        "visa_activation_executor": frozenset(),
        "visa_policy_writer": frozenset(
            {
                ("visa_decision_retention_policies", "SELECT"),
                ("visa_decision_retention_policies", "INSERT"),
                ("visa_decision_retention_policies", "UPDATE"),
            }
        ),
        # retention_worker._active_policy reads the approved, non-PII policy
        # row directly before invoking the bounded SECURITY DEFINER workers.
        "visa_retention_executor": frozenset(
            {("visa_decision_retention_policies", "SELECT")}
        ),
        "visa_privacy_operator": frozenset(),
    }


async def collect_preflight_checks(
    connection: asyncpg.Connection,
    *,
    runtime_role: str,
) -> tuple[PreflightCheck, ...]:
    """Collect read-only structural and least-privilege assertions."""

    checks: list[PreflightCheck] = []
    server_version_num = int(
        await connection.fetchval("SELECT pg_catalog.current_setting('server_version_num')::integer")
    )
    supported_table_privileges = TABLE_PRIVILEGES
    if server_version_num >= 170000:
        supported_table_privileges = ALL_TABLE_PRIVILEGES
    expected_roles = {
        "visa_ledger_owner": False,
        "visa_pack_writer": False,
        "visa_activation_executor": False,
        "visa_policy_writer": False,
        "visa_retention_executor": False,
        "visa_privacy_operator": False,
        runtime_role: True,
    }
    # Every catalog name in THIS function is `pg_catalog.`-qualified — CALLS and
    # RELATIONS, and as of 2026-08-31 the TYPE CAST below too. That last one was
    # found by the Gear-3 gate, which shadowed `text` on a throwaway PG 17.10:
    # `CREATE DOMAIN public.text AS varchar(1)` makes `$1::text[]` truncate every
    # role name to one character. Note the DIRECTION before reading this as a
    # closed forgery vector — it is not one. A truncated array matches no
    # `rolname`, so `role_rows` comes back empty and every `role:*` check goes
    # ok=False: the attack makes this function fail LOUD, not answer green. It is
    # qualified anyway because the sentence above claimed it already was, and a
    # comment that overstates its own coverage is how the next reader stops
    # checking. What remains genuinely uncovered: casts are a construct class NO
    # guard in this repo can currently see — see
    # docs/specs/2026-08-31-unqualified-catalog-call-lint.md, whose extractor
    # requirement (R1) has to reach them. A second adversarial seat
    # (kimi-code/k3) pointed out the inconsistency and was right: this file now
    # states that "a privilege check answerable by an object the checked role may
    # create is not a check", and then relied on `role:visa_ledger_owner` -- which
    # probed an unqualified `pg_roles` -- to justify migration 300's role guard.
    # A constant-returning `public.pg_roles` view, or a `public.pg_get_userbyid`,
    # forges those green under `search_path = public, pg_catalog`. The doctrine
    # cannot hold for the new code and be waived for the code it leans on.
    role_rows = await connection.fetch(
        "SELECT rolname, rolcanlogin, rolsuper FROM pg_catalog.pg_roles "
        "WHERE rolname = ANY($1::pg_catalog.text[])",
        list(expected_roles),
    )
    roles = {str(row["rolname"]): row for row in role_rows}
    for role, login_expected in expected_roles.items():
        row = roles.get(role)
        ok = (
            row is not None
            and bool(row["rolcanlogin"]) is login_expected
            and not bool(row["rolsuper"])
        )
        checks.append(
            PreflightCheck(
                name=f"role:{role}",
                ok=ok,
                detail="present with expected LOGIN/superuser posture"
                if ok
                else "missing or unsafe",
            )
        )

    table_exists: dict[str, bool] = {}
    for table in SENSITIVE_TABLES:
        owner = await connection.fetchval(
            """
            SELECT pg_catalog.pg_get_userbyid(class.relowner)
              FROM pg_catalog.pg_class AS class
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = class.relnamespace
             WHERE namespace.nspname = 'public' AND class.relname = $1
            """,
            table,
        )
        table_exists[table] = owner is not None
        checks.append(
            PreflightCheck(
                name=f"owner:public.{table}",
                ok=owner == "visa_ledger_owner",
                detail="owned by visa_ledger_owner"
                if owner == "visa_ledger_owner"
                else "wrong/missing owner",
            )
        )

    function_exists: dict[str, bool] = {}
    for signature in SENSITIVE_FUNCTIONS:
        owner = await connection.fetchval(
            "SELECT pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc "
            "WHERE oid = pg_catalog.to_regprocedure($1)",
            signature,
        )
        function_exists[signature] = owner is not None
        checks.append(
            PreflightCheck(
                name=f"owner:{signature}",
                ok=owner == "visa_ledger_owner",
                detail="owned by visa_ledger_owner"
                if owner == "visa_ledger_owner"
                else "wrong/missing owner",
            )
        )

    function_allowlist = _function_allowlist(runtime_role)
    for role, allowed_signatures in function_allowlist.items():
        for signature in SENSITIVE_FUNCTIONS:
            expected = signature in allowed_signatures
            actual = False
            if role in roles and function_exists.get(signature, False):
                actual = bool(
                    await connection.fetchval(
                        "SELECT pg_catalog.has_function_privilege($1, $2, 'EXECUTE')",
                        role,
                        signature,
                    )
                )
            checks.append(
                PreflightCheck(
                    name=f"function:{role}:{signature}",
                    ok=actual is expected,
                    detail=f"EXECUTE={actual} expected={expected}",
                )
            )

    table_privilege_allowlist = _table_privilege_allowlist(runtime_role)
    for role, allowed_privileges in table_privilege_allowlist.items():
        for table in SENSITIVE_TABLES:
            for privilege in supported_table_privileges:
                expected = (table, privilege) in allowed_privileges
                actual = False
                if role in roles and table_exists.get(table, False):
                    actual = bool(
                        await connection.fetchval(
                            "SELECT pg_catalog.has_table_privilege($1, $2, $3)",
                            role,
                            f"public.{table}",
                            privilege,
                        )
                    )
                checks.append(
                    PreflightCheck(
                        name=f"table:{role}:public.{table}:{privilege}",
                        ok=actual is expected,
                        detail=f"{privilege}={actual} expected={expected}",
                    )
                )

    for capability_role in CAPABILITY_ROLES:
        runtime_is_member = False
        if runtime_role in roles and capability_role in roles:
            runtime_is_member = bool(
                await connection.fetchval(
                    "SELECT pg_catalog.pg_has_role($1, $2, 'MEMBER')",
                    runtime_role,
                    capability_role,
                )
            )
        checks.append(
            PreflightCheck(
                name=f"membership:{runtime_role}-not-{capability_role}",
                ok=not runtime_is_member,
                detail=f"runtime_member={runtime_is_member} expected=False",
            )
        )

    dual_capability_login = "roles-missing"
    if "visa_pack_writer" in roles and "visa_activation_executor" in roles:
        dual_capability_login = await connection.fetchval(
            """
            SELECT pg_catalog.string_agg(role.rolname, ', ' ORDER BY role.rolname)
              FROM pg_catalog.pg_roles AS role
             WHERE role.rolcanlogin
               AND pg_catalog.pg_has_role(role.oid, 'visa_pack_writer', 'MEMBER')
               AND pg_catalog.pg_has_role(
                       role.oid, 'visa_activation_executor', 'MEMBER'
                   )
            """
        )
    checks.append(
        PreflightCheck(
            name="membership:no-pack-writer-activation-combination",
            ok=dual_capability_login is None,
            detail="no login combines both capabilities"
            if dual_capability_login is None
            else "one or more logins combine pack-write and activation",
        )
    )

    # ------------------------------------------------------------------
    # binder:retention-policy-scoped
    # ------------------------------------------------------------------
    # This is the LOUD half of migration 289's catalog guard, and it is the
    # only reason that guard is allowed to exist.
    #
    # 289 replaces two SECURITY DEFINER binders so they resolve the retention
    # policy by (environment, policy_scope) instead of environment alone. Both
    # are owned by `visa_ledger_owner`; the migration runner connects with
    # `settings.database_url` -- the runtime role -- which owns neither. So 289
    # wraps each replacement in a `DO $guardN$` block that declines rather than
    # raising, because a raising migration inside `release_command` aborts the
    # WHOLE deploy (measured 2026-08-26 on migrations 281/284-287).
    #
    # A migration that declines is still recorded APPLIED and is therefore
    # never retried -- scar #2, esiste != armato, and on its own strictly worse
    # than a failed deploy because nothing is visible. This check is what makes
    # it visible: it reads the LIVE function body out of the catalog, so it can
    # only go green once the predicate is really in place, whoever put it there
    # and by whatever route.
    #
    # It deliberately does NOT ask whether the phrase `policy_scope =
    # 'VISA_DECISION'` appears anywhere in the body (scar #3, guard-over-match
    # and its under-match twin). It asks whether EVERY active-policy lookup is
    # accompanied by it, on a copy with comments AND string literals blanked —
    # both evasions were reproduced against the earlier one-line version before
    # `_active_lookups_are_scoped` replaced it.
    scoped_binder_rows = await connection.fetch(
        """
        SELECT proname, prosrc
          FROM pg_catalog.pg_proc
         WHERE proname = ANY($1::text[])
        """,
        list(SCOPE_BOUND_RETENTION_BINDERS),
    )
    found_binders = {row["proname"]: row["prosrc"] for row in scoped_binder_rows}
    unscoped_binders: list[str] = []
    for binder in SCOPE_BOUND_RETENTION_BINDERS:
        body = found_binders.get(binder)
        if body is None:
            unscoped_binders.append(f"{binder}(absent)")
            continue
        if not _active_lookups_are_scoped(body):
            unscoped_binders.append(binder)
    checks.append(
        PreflightCheck(
            name="binder:retention-policy-scoped",
            ok=not unscoped_binders,
            detail="both retention binders resolve by (environment, policy_scope)"
            if not unscoped_binders
            else (
                "migration 289 is NOT live in this database: "
                + ", ".join(unscoped_binders)
                + " still resolve(s) the retention policy by environment alone, so a "
                "second active policy in ANY scope makes every visa_decisions / "
                "visa_evaluate_idempotency INSERT fail with the INTO STRICT ambiguity. "
                "289's catalog guard declined (the runtime role does not own these "
                "functions) -- re-apply it as visa_ledger_owner or a superuser."
            ),
        )
    )

    # ------------------------------------------------------------------
    # definer:public-security-definer-ledger-owned
    # ------------------------------------------------------------------
    # A FLOOR, not a replacement for the `owner:{signature}` checks above.
    # Those read a hand-maintained inventory (`SENSITIVE_FUNCTIONS`); this one
    # reads the catalog and needs no list at all.
    #
    # The list is why nothing caught migration 285. That migration created a
    # new SECURITY DEFINER trigger, `bind_garuda_magic_link_token_retention_
    # policy`, left it owned by the runtime role `backend_rag_v2`, and nobody
    # added it to `RETENTION_BINDING_TRIGGER_FUNCTIONS`. Its body takes a
    # `SELECT ... FOR SHARE` on `visa_decision_retention_policies`, which is
    # owned by `visa_ledger_owner` and on which the runtime role holds only
    # SELECT; row locking needs more than SELECT. SECURITY DEFINER bought
    # nothing because the DEFINER could not take the lock either, so
    # `POST /api/visa/voa/auth/magic-links` answered 500 from the day it
    # shipped and no magic link was ever minted. A list-driven check is exactly
    # as good as the memory of whoever last edited the list.
    #
    # Migrations 281 and 286 are the same disease one step earlier: both NAME
    # the ownership transfer, both were recorded APPLIED, and five functions
    # stayed owned by `backend_rag_v2` for four days because their
    # `insufficient_privilege` handler emitted a NOTICE and deferred. Migration
    # 300 makes those two honest; this check is what notices the next one
    # WHENEVER THIS PREFLIGHT IS RUN -- and that qualifier is not decoration.
    #
    # `collect_preflight_checks` has exactly two callers today: this module's
    # own `__main__` and the tests. No workflow, script or deploy step invokes
    # it, so every check in this file -- the pre-existing ones included -- fires
    # when a human runs the CLI (see docs/runbooks/visa-oracle-privacy-enforce-
    # gate.md) and at no other time. A second adversarial seat named this as the
    # decisive limit of the floor and it is recorded rather than glossed:
    # arming it means either calling this from `fullstack_smoke.py` or having a
    # test apply the real migration chain, and BOTH need the sandbox to create a
    # role named `visa_ledger_owner` first, or the census compares against a
    # role that does not exist and reddens on every function in the schema.
    # That is a piece of work with its own design, not a line to smuggle in
    # here.
    #
    # Measured against the production primary on 2026-08-30: 21 SECURITY
    # DEFINER functions in `public`, every one owned by `visa_ledger_owner`,
    # and ZERO of them belonging to an extension (pg_depend deptype='e'), with
    # postgis, pgcrypto, pg_trgm, btree_gist and uuid-ossp all installed into
    # `public`. So there is no legitimate exception in THIS database and none is
    # encoded here.
    #
    # A hypothetical one exists and is named rather than pre-exempted: some
    # contrib extensions do ship SECURITY DEFINER routines (`dblink`'s
    # `dblink_connect_u` is the standard example) which would be owned by
    # whoever installed the extension. If one is ever installed here this check
    # goes red and somebody argues the case in a diff. That is the intended
    # cost: an exemption written before a real case exists is exactly how a
    # floor turns back into the list that let migration 285 through.
    #
    # An empty census is reported in the detail rather than passing silently:
    # zero rows means either a database with no governed functions or a probe
    # reading the wrong catalog, and the two must not look alike in a log. It
    # is deliberately NOT a failure -- the `owner:{signature}` checks above go
    # red on their own the moment those functions are genuinely missing, so an
    # empty schema is already loud without this check inventing a second alarm
    # that would fire on a legitimately fresh database.
    definer_rows = await connection.fetch(SECURITY_DEFINER_CENSUS_SQL)
    violations = _security_definer_violations(definer_rows)
    checks.append(
        PreflightCheck(
            name="definer:public-security-definer-ledger-owned",
            ok=not violations,
            detail=(
                f"all {len(definer_rows)} SECURITY DEFINER function(s) in public "
                f"are owned by {LEDGER_OWNER}"
                if not violations
                else (
                    f"{len(violations)} of {len(definer_rows)} SECURITY DEFINER "
                    f"function(s) in public are NOT owned by {LEDGER_OWNER}: "
                    + ", ".join(violations)
                    + ". A SECURITY DEFINER function runs with its OWNER's "
                    "privileges, so one owned by the runtime role is a no-op "
                    "that fails on its first real call -- the shape that kept "
                    "magic-link issuance answering 500 (migration 285). "
                    "Transfer it with ALTER FUNCTION (or ALTER PROCEDURE, for "
                    f"a routine marked [procedure]) ... OWNER TO {LEDGER_OWNER} "
                    "on a superuser connection."
                )
            ),
        )
    )
    return tuple(checks)


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required")
    connection = await asyncpg.connect(database_url)
    try:
        checks = await collect_preflight_checks(connection, runtime_role=args.runtime_role)
    finally:
        await connection.close()
    for check in checks:
        logger.info("preflight check=%s ok=%s detail=%s", check.name, check.ok, check.detail)
    failed = sum(not check.ok for check in checks)
    logger.info("preflight_summary total=%d failed=%d", len(checks), failed)
    return 0 if failed == 0 else 2


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url-env", default=PREFLIGHT_DSN_ENV)
    parser.add_argument("--runtime-role", default="backend_rag_v2")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
