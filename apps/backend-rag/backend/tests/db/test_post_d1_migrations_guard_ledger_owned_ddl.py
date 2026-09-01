"""A migration authored after the D1 repair may not ALTER a table it no longer owns.

WHAT HAPPENED (2026-08-26, production, `nuzantara-rag`)
-------------------------------------------------------
Fly's `release_command` ran `python -m backend.db.migrate apply-all` on the new
image and failed all five pending GARUDA migrations, aborting the deploy before
any machine was replaced:

    281_garuda_voa_retention      must be owner of table visa_decision_retention_policies
    284_garuda_orders             column "policy_scope" does not exist          (cascade of 281)
    285_garuda_magic_link         could not locate the policy_scope enum CHECK  (cascade of 281)
    286_garuda_voa_check_results  permission denied for table visa_decision_retention_policies
    287_garuda_practices          relation "public.garuda_orders" does not exist (cascade of 284)

One root cause. Migrations connect with `settings.database_url`
(`migration_manager.py:96`) — the SAME DSN the runtime uses, with no `SET ROLE`
anywhere in the chain. The "D1" least-privilege repair had moved ownership of
the Visa Oracle ledger tables to `visa_ledger_owner`, leaving the runtime role
`backend_rag_v2` holding only SELECT. `ALTER TABLE` requires ownership (or
membership in the owning role); a foreign key requires REFERENCES. 281 had
neither.

The repository had ALREADY written this trap down, in migration 268's own
header:

    "The D1 least-privilege repair moved ownership of the Visa Oracle ... to
     `visa_ledger_owner`, leaving the runtime role (`backend_rag_v2`) ...
     When [264] was written, the runtime role WAS the table owner and the gap
     was invisible."

268 applied the cure to FUNCTIONS (role-guarded, idempotent, best-effort
`ALTER FUNCTION ... OWNER TO`). Nobody applied it to TABLES. The knowledge
existed as prose and existed in no executable guard — which is the whole
difference between a document and an antidote. This file is the antidote.

WHY CI COULD NOT CATCH IT, AND STILL CANNOT
--------------------------------------------
`fly-deploy.yml:50` validates migrations against
`postgresql://test:test@localhost:5432/nuzantara_test` — an ephemeral Postgres
where the role `test` creates every table from scratch and therefore OWNS them
all. In that world `ALTER TABLE` cannot fail. The pre-deploy gate is green by
construction for this entire class, and will stay green no matter what cure is
written, because the condition that breaks the thing does not exist in the
environment the probe runs in. That is precisely why this guard is a static
check over the migration TEXT and not an integration test: an integration test
would have to reproduce the ownership split to mean anything, and would then be
testing its own fixture.

THE TRAP INSIDE THE TRAP: `IF NOT EXISTS` DOES NOT SAVE YOU
------------------------------------------------------------
The obvious repair — make the statements idempotent with
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — looks right and is not. PostgreSQL
performs the ownership check BEFORE the IF-NOT-EXISTS short-circuit, so the
statement fails even when the column already exists and there is nothing to do.
Reproduced locally on a twelve-line fixture that reproduces both production
errors verbatim::

    SET ROLE t_ledger_owner;
    CREATE TABLE public.ledger (id int primary key, policy_scope text);
    GRANT SELECT ON public.ledger TO t_runtime;   -- what 268 says the runtime role has
    RESET ROLE; SET ROLE t_runtime;

    ALTER TABLE public.ledger ADD COLUMN IF NOT EXISTS policy_scope text;
    -->  ERROR:  must be owner of table ledger          (column ALREADY present)

    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                     WHERE table_schema='public' AND table_name='ledger'
                       AND column_name='policy_scope') THEN
        EXECUTE 'ALTER TABLE public.ledger ADD COLUMN policy_scope text';
      END IF;
    END $$;
    -->  clean no-op, the ALTER is never attempted

    CREATE TABLE public.child (id int primary key, pid int REFERENCES public.ledger(id));
    -->  ERROR:  permission denied for table ledger

So the guard this file enforces is specifically a CATALOG guard — the statement
must sit inside a dollar-quoted block that can decline to run it — not an
SQL-level `IF NOT EXISTS`.

WHY THE RULE STARTS AT 269 AND NOT AT 1
----------------------------------------
Measured over all 169 migration files: 45 top-level `ALTER TABLE` statements
touch a table that production no longer lets the app role own — 44 by ALTERing
it (an OWNERSHIP problem) and 1 by naming it in a REFERENCES clause (a
PRIVILEGE problem, cured by a GRANT rather than by a guard). The two are
reported under different labels because they need different fixes; the single
REFERENCES case lives inside migration 281 itself. 37 of them live
in migrations <= 268 and applied without incident, because at the time they ran
the runtime role still WAS the owner — the D1 repair came afterwards. The
remaining 8 live in migrations > 268, and they are exactly the two files that
failed in production. The boundary at 268 separates "applied fine, forever
frozen" from "the live hazard" with zero false positives and zero false
negatives against the observed incident, which is why it is drawn there rather
than at some rounder number. Retro-fitting the 37 historical statements would
change nothing in any database and would bury the eight that matter.

SCOPE, DELIBERATELY NARROW
---------------------------
`ALTER TABLE` and function DDL (`CREATE OR REPLACE FUNCTION` / `DROP FUNCTION` /
bare `ALTER FUNCTION`) are checked — see the "FUNCTION DDL" section further down
this file for the function side, added once production confirmed `visa_ledger_owner`
also owns a set of trigger/utility functions, not only tables. `CREATE TRIGGER`
needs the TRIGGER privilege and `CREATE INDEX` needs ownership too, and post-D1
migrations that do either against these tables would very likely fail as well —
but no such statement exists today, so including them would be a rule asserted
rather than measured. A guard that invents a target is as bad as one that misses
it. Widen this when there is an observation to widen it with.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_MIG_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"

# The migration that documents the D1 ownership split. Anything authored after
# it is expected to know about it.
D1_BOUNDARY = 268

# Tables production does NOT let `backend_rag_v2` own.
#
# PROVENANCE: measured on the production leader on 2026-08-26, read-only, with
#
#   SELECT c.relname, pg_get_userbyid(c.relowner) AS owner
#     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
#    WHERE n.nspname = 'public' AND c.relkind = 'r'
#      AND pg_get_userbyid(c.relowner) <> 'backend_rag_v2'
#    ORDER BY 2, 1;
#
# This is a SNAPSHOT and can drift: a table added to a non-app role later would
# not be listed here and this guard would not see it. Re-run the query above
# when ownership changes, and treat this set as a floor rather than a ceiling.
# `visa_decision_retention_policies` is the only member independently PROVEN by
# a production error; the rest come from that single measurement.
NON_APP_OWNED_TABLES: frozenset[str] = frozenset(
    {
        # owner: visa_ledger_owner (the D1 least-privilege repair)
        "visa_decision_dsr_erasure_batches",
        "visa_decision_legal_hold_events",
        "visa_decision_payloads",
        "visa_decision_retention_batches",
        "visa_decision_retention_policies",
        "visa_decisions",
        "visa_evaluate_idempotency",
        "visa_idempotency_retention_batches",
        "visa_rule_packs",
        "visa_ruleset_activations",
        "visa_source_records",
        # owner: zantara_rag_user
        "collective_memory",
        "conversations",
        "memory_facts",
        "persistent_sessions",
        "query_clusters",
        "team_employees",
        "team_timesheet",
        "team_work_sessions",
        "user_stats",
        # owner: postgres
        "x_monitored_tweets",
        # owner: repmgr — an anomaly, almost certainly a historical accident
        # rather than a design decision; listed because the app role still
        # cannot ALTER it.
        "attendance_late_incidents",
    }
)

# Migrations that violate the rule and are FROZEN that way on purpose.
#
# Both were applied to production on 2026-08-26 under a temporary
# `GRANT visa_ledger_owner TO backend_rag_v2`, immediately revoked afterwards
# (the revocation was re-measured with pg_has_role(...) = f). Editing them now
# would buy nothing anywhere and would cost something: production will never
# re-run them, a rollback would use the `rollback_sql` stored in
# `_schema_versions` at apply time rather than the file, and a fresh
# environment never hits the wall at all because there the runtime role creates
# and therefore owns the table. The edit would only diverge the file from the
# checksum recorded alongside it.
GRANDFATHERED: dict[int, str] = {
    281: "applied 2026-08-26 under temporary visa_ledger_owner membership, since revoked",
    285: "applied 2026-08-26 under temporary visa_ledger_owner membership, since revoked",
}

_ALTER_TABLE = re.compile(r"^ALTER\s+TABLE\b", re.IGNORECASE)
# The table an ALTER actually alters: the first name after the keyword, past
# the optional IF EXISTS / ONLY modifiers. Needed because a listed table can
# also appear LATER in the same statement — in a REFERENCES clause — and the
# two cases fail in production for different reasons and need different cures.
_ALTER_TARGET = re.compile(
    r"^ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?"
    r'(?:public\s*\.\s*)?"?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"?',
    re.IGNORECASE,
)
# `"foo"` and `foo` and `public.foo` and `public . "foo"` all name the same table.
_TABLE_REF = {
    t: re.compile(rf'(?:\bpublic\s*\.\s*)?"?\b{t}\b"?', re.IGNORECASE)
    for t in NON_APP_OWNED_TABLES
}
# Every dollar-quote delimiter form PostgreSQL accepts: bare `$$` and tagged
# `$tag$`. The corpus uses tagged ones heavily — $func$ (18), $grant_block$
# (18), $revoke_block$ (14), $function$, $visa_268_owner_transfer$ and more —
# so a scanner that counted only `$$` would treat the inside of a $func$ body
# as top level and convict statements that are already guarded.
_DOLLAR_TAG = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")

# An ALTER anywhere in a string, not just at the front of a statement: inside a
# DO block the statement lives inside a quoted `EXECUTE '...'`, so the anchored
# pattern above never sees it.
_ALTER_ANYWHERE = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?"
    r'(?:public\s*\.\s*)?"?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"?',
    re.IGNORECASE,
)
# What makes a DO block a GUARD rather than a wrapper: it can DECLINE to run.
# The test is deliberately the coarsest coherent one — does the body contain a
# conditional at all — rather than "does it read the catalog". The first draft
# of this rule keyed on catalog reads and was incoherent: a body that
# interrogates `information_schema` and then EXECUTEs unconditionally fails in
# production exactly like a bare statement, so that predicate acquitted one
# broken shape while convicting another for no principled reason. Keying on
# `END IF` cannot produce a false positive, because a body with no conditional
# anywhere always runs its ALTER.
#
# NOT verified, and deliberately so: that the ALTER sits INSIDE that
# conditional. Deciding that needs PL/pgSQL control-flow analysis, which does
# not belong in a test file. So a body carrying an unrelated `IF ... END IF`
# plus an unconditional ALTER still passes — 285's DROP CONSTRAINT is exactly
# that shape. Written down because a limit on paper can be closed later; an
# implied one is discovered in production.
_HAS_CONDITIONAL = re.compile(r"\bEND\s+IF\b", re.IGNORECASE)
# `DO` as the last token before the opening delimiter, allowing the optional
# `LANGUAGE <name>` that PostgreSQL permits between them.
_DO_KEYWORD = re.compile(r"\bDO\s*(?:LANGUAGE\s+[A-Za-z_][A-Za-z0-9_]*\s*)?$", re.IGNORECASE)


def _executable_text(
    sql: str,
) -> tuple[list[str], list[int], list[tuple[int, str, bool]]]:
    """Reduce SQL to the characters PostgreSQL would actually execute.

    A single left-to-right lexer, written once, instead of a pile of regex
    patches — because every patch so far uncovered another case the previous
    one had not considered. It tracks the five states that matter and emits
    only what is in the NORMAL one:

    ``--`` line comment · ``/* */`` block comment · ``'...'`` string literal
    (with the ``''`` escape) · ``$tag$...$tag$`` dollar-quoted body · normal.

    Every one of these can contain the others' delimiters, which is exactly
    why order-of-stripping cannot work and a state machine can. Measured
    failures of the regex versions this replaces, each now a fixture:

    * ``-- a comment containing $$ once`` flipped dollar parity and hid every
      statement after it;
    * ``INSERT INTO t(c) VALUES ('a -- x');`` had its statement terminator
      eaten by naive comment stripping, swallowing the next statement;
    * ``/* ... */`` on its own line pushed the ALTER off the start of the
      statement;
    * a ``$func$`` body was not recognised as a body at all.

    Dollar-quoted bodies are dropped because that is where a catalog guard
    lives; string and comment contents are dropped because they are not
    executed. Returns (characters, line-number-per-character) so a finding can
    name the line it came from.
    """
    chars: list[str] = []
    origin: list[int] = []
    bodies: list[tuple[int, str, bool]] = []
    i, lineno, n = 0, 1, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "\n":
            chars.append("\n")
            origin.append(lineno)
            lineno += 1
            i += 1
        elif sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):
            i += 2
            while i < n and not sql.startswith("*/", i):
                lineno += sql[i] == "\n"
                i += 1
            i += 2
        elif ch == "'":
            i += 1
            while i < n:
                if sql[i] == "'" and sql.startswith("''", i):
                    i += 2
                    continue
                if sql[i] == "'":
                    i += 1
                    break
                lineno += sql[i] == "\n"
                i += 1
            # A consumed literal still separates tokens.
            chars.append(" ")
            origin.append(lineno)
        elif (m := _DOLLAR_TAG.match(sql, i)) is not None:
            tag = m.group(0)
            j = sql.find(tag, m.end())
            if j == -1:
                # UNTERMINATED body. Suppressing the rest of the file would
                # blind the guard from here on — measured: an unclosed
                # `DO $blk$` hid a real unguarded ALTER two lines below. Treat
                # the delimiter as ordinary text so the tail stays visible.
                # A guard that goes quiet on malformed input is worse than none.
                chars.extend(tag)
                origin.extend([lineno] * len(tag))
                i = m.end()
                continue
            # WHOSE body is this? `DO $$ ... $$` runs at apply time, so an
            # ALTER inside it hits the ownership check now. A routine body
            # (`CREATE FUNCTION ... AS $$ ... $$`) is only stored — it runs
            # when something CALLS it, under whatever role calls it, which is
            # exactly the shape 268 used to deliver its cure. Convicting a
            # function body would convict 268's own remedy.
            preceding = " ".join("".join(chars[-160:]).split())
            is_do = _DO_KEYWORD.search(preceding) is not None
            bodies.append((lineno, sql[m.end() : j], is_do))
            lineno += sql.count("\n", i, j + len(tag))
            i = j + len(tag)
            chars.append(" ")
            origin.append(lineno)
        else:
            chars.append(ch)
            origin.append(lineno)
            i += 1
    return chars, origin, bodies


def find_unguarded_alters(sql: str) -> list[tuple[int, str, str]]:
    """Return (line_no, table, statement) for each top-level ALTER TABLE.

    "Top-level" means: not inside a dollar-quoted body. Statements inside such
    a body are exempt because that is exactly where a catalog guard lives — the
    block can inspect ``information_schema`` and decline to ``EXECUTE`` the
    ALTER at all, which is the only construction that survives the ownership
    check.

    Statements are split on ``;`` over the lexer's output rather than read
    line-by-line: anchoring on ``^ALTER TABLE`` missed
    ``SELECT 1; ALTER TABLE ...`` written on one line, and a fixed line window
    missed an ALTER whose table name sat further below the keyword. Comment
    contents never reach here, so the scanner cannot convict documentation —
    migration headers legitimately DISCUSS statements like
    ``ALTER TABLE public.visa_decision_retention_policies`` in prose, as this
    file's own docstring does repeatedly.
    """
    chars, origin, bodies = _executable_text(sql)
    findings: list[tuple[int, str, str]] = []

    start = 0
    for end in [idx for idx, c in enumerate(chars) if c == ";"] + [len(chars)]:
        segment = "".join(chars[start:end])
        head = len(segment) - len(segment.lstrip())
        collapsed = " ".join(segment.split())
        at = start + head
        start = end + 1
        if not collapsed or not _ALTER_TABLE.match(collapsed):
            continue
        lineno = origin[at] if at < len(origin) else (origin[-1] if origin else 1)

        target_match = _ALTER_TARGET.match(collapsed)
        target = target_match.group("name").lower() if target_match else None
        if target in NON_APP_OWNED_TABLES:
            findings.append((lineno, target, "owner", collapsed[:110]))
            continue
        # The altered table is fine, but a listed one may still be named in a
        # REFERENCES clause — which needs the REFERENCES privilege, not
        # ownership. That is precisely how migration 286 died in production
        # ("permission denied for table visa_decision_retention_policies"),
        # and its cure is a GRANT by the owner, NOT a catalog guard. Reporting
        # it under the ownership label would send the author to fix the wrong
        # thing — a true finding with a false diagnosis.
        for table, pattern in _TABLE_REF.items():
            if pattern.search(collapsed):
                findings.append((lineno, table, "references", collapsed[:110]))
                break

    # A dollar-quoted body is exempt only if it is actually a GUARD. Being
    # inside `$$` proves the author typed two dollar signs, nothing more:
    #     DO $$ BEGIN EXECUTE 'ALTER TABLE public.visa_decisions ADD ...'; END $$;
    # fails in production identically to the bare statement, and the earlier
    # version of this scanner acquitted it — a false negative in the exact
    # class the file exists to catch. Someone copying the remediation template
    # below and dropping the IF would have shipped the incident again.
    for body_lineno, body, is_do in bodies:
        if not is_do or _HAS_CONDITIONAL.search(body):
            continue
        for m in _ALTER_ANYWHERE.finditer(body):
            target = m.group("name").lower()
            if target not in NON_APP_OWNED_TABLES:
                continue
            findings.append((
                body_lineno + body.count("\n", 0, m.start()),
                target,
                "unguarded-do",
                " ".join(body[m.start() : m.start() + 110].split()),
            ))
            break

    return sorted(findings)


def _migration_number(path: Path) -> int:
    """A filename with no leading number is a defect, not a reason to crash.

    `int()` on it raised ValueError, which pytest reports as a suite ERROR
    with a traceback into this helper — the reader is sent to debug the guard
    instead of to the misnamed file. -1 keeps such a file out of the post-D1
    window, and the test below names it plainly instead.
    """
    head = path.name.split("_", 1)[0]
    return int(head) if head.isdigit() else -1


def test_every_migration_filename_carries_a_number() -> None:
    """Because -1 above would otherwise hide a file from the scan in silence."""
    unnumbered = [p.name for p in sorted(_MIG_DIR.glob("*.sql")) if _migration_number(p) < 0]
    assert not unnumbered, (
        f"migration files with no leading number: {unnumbered}. The D1 boundary is "
        f"drawn on that number, so an unnumbered file is invisible to this guard."
    )


def test_every_snapshot_table_is_still_named_somewhere_in_the_repository() -> None:
    """The snapshot can rot in BOTH directions; this catches one of them.

    A table renamed or dropped since 2026-08-26 leaves a name here that the
    guard watches forever and that can never match — dead weight that reads
    like coverage.

    The corpus is the whole tracked tree, NOT `migrations_v2/`. Measured while
    writing this: scanning only that directory reported `collective_memory`,
    `team_employees` and `user_stats` as dead, and all three are alive —
    `user_stats` is created by the OLDER migration system under
    `backend/migrations/`, and a table can exist in production having never
    passed through any migration directory at all (CLAUDE.md records
    `kbli_documents` as seeded out-of-band with no migration and no ORM model).
    "Absent from migrations_v2" and "does not exist" are different claims.

    The OTHER direction — a table transferred to a non-app role AFTER the
    snapshot — is not detectable from the repository at any scope: it lives in
    `pg_class.relowner` on the production leader, and only re-running the
    provenance query at the top of this file can see it. Deliberately not
    faked with a date-based expiry, because a test that turns red on a
    calendar day, on a commit nobody touched, ejects innocent PRs from the
    merge queue (cicatrix `W129`). What would close it is a scheduled job that
    re-runs the query and diffs it against this list.
    """
    repo_root = Path(__file__).resolve().parents[5]
    # ONE invocation: `git grep -o` prints the matched text itself, so the
    # union of its output is exactly the set of names present. Asking per name
    # instead cost 10s on this repo (22 index scans) for the same answer.
    names = sorted(NON_APP_OWNED_TABLES)
    patterns: list[str] = []
    for table in names:
        patterns += ["-e", table]
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "grep", "-h", "-o", "-w", "-F", *patterns,
         "--", ":!*test_post_d1_migrations_guard_ledger_owned_ddl.py"],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise AssertionError(
            f"git grep failed ({proc.returncode}): {proc.stderr.strip()[:200]}. Failing "
            f"closed rather than reporting a clean snapshot on a broken instrument."
        )
    seen = {line.strip() for line in proc.stdout.splitlines()}
    ghosts = [t for t in names if t not in seen]
    assert not ghosts, (
        f"tables in the NON_APP_OWNED_TABLES snapshot named nowhere in the tracked "
        f"tree: {ghosts}. Either they were renamed/dropped and the entry is dead, or "
        f"the snapshot names something this repository never created. Re-run the "
        f"provenance query in this file's header against the production leader."
    )


def test_no_post_d1_migration_alters_a_table_the_app_role_cannot_own() -> None:
    """The real assertion, over the real migration corpus."""
    offenders: list[str] = []
    for path in sorted(_MIG_DIR.glob("*.sql")):
        number = _migration_number(path)
        if number <= D1_BOUNDARY or number in GRANDFATHERED:
            continue
        for lineno, table, kind, statement in find_unguarded_alters(path.read_text()):
            if kind == "references":
                offenders.append(
                    f"{path.name}:{lineno} does not ALTER `{table}`, but NAMES it in a "
                    f"REFERENCES clause — which needs the REFERENCES privilege that "
                    f"`backend_rag_v2` does not hold. This is how migration 286 died in "
                    f"production. A catalog guard does NOT fix it: the cure is a one-time "
                    f"`GRANT REFERENCES ON public.{table} TO backend_rag_v2;` run by the "
                    f"table's owner.\n    {statement}"
                )
                continue
            if kind == "unguarded-do":
                offenders.append(
                    f"{path.name}:{lineno} runs an ALTER on `{table}` inside a `DO` block "
                    f"that contains no conditional at all — so it EXECUTEs unconditionally "
                    f"and fails in production exactly like a bare statement. Being inside "
                    f"`$$` is not a guard; being able to DECLINE is.\n    {statement}\n"
                    f"    Wrap the EXECUTE in the existence test:\n"
                    f"        IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
                    f"                       WHERE table_schema='public' "
                    f"AND table_name='{table}'\n"
                    f"                         AND column_name='<the column>') THEN\n"
                    f"          EXECUTE 'ALTER TABLE public.{table} ...';\n"
                    f"        END IF;"
                )
                continue
            offenders.append(
                f"{path.name}:{lineno} ALTERs `{table}`, which production does not let "
                f"`backend_rag_v2` own — this fails in prod and passes in CI.\n"
                f"    {statement}\n"
                f"    Wrap it in a catalog guard:\n"
                f"        DO $$ BEGIN\n"
                f"          IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
                f"                         WHERE table_schema='public' AND table_name='{table}'\n"
                f"                           AND column_name='<the column>') THEN\n"
                f"            EXECUTE 'ALTER TABLE public.{table} ...';\n"
                f"          END IF;\n"
                f"        END $$;\n"
                f"    `ADD COLUMN IF NOT EXISTS` does NOT work here: the ownership check\n"
                f"    runs before the short-circuit. See this file's docstring."
            )
    assert not offenders, "\n\n".join(offenders)


def test_the_grandfathered_pair_really_does_still_violate_the_rule() -> None:
    """An exemption for something that stopped violating is a lie in the config.

    If 281/285 are ever rewritten to be guarded, this fails and tells whoever
    did it to delete their entry from GRANDFATHERED — so the allowlist cannot
    quietly outlive its reason.
    """
    for number in GRANDFATHERED:
        matches = list(_MIG_DIR.glob(f"{number}_*.sql"))
        assert len(matches) == 1, f"expected exactly one migration {number}, got {matches}"
        findings = find_unguarded_alters(matches[0].read_text())
        assert findings, (
            f"migration {number} is on the GRANDFATHERED list but no longer contains an "
            f"unguarded ALTER TABLE. Remove its entry."
        )


def test_the_incident_files_are_exactly_the_post_d1_violations() -> None:
    """Anchor the boundary to the observed incident rather than to a round number.

    Every top-level offender after 268 must be one of the two files production
    actually rejected. If a third file appears here, either a new migration
    slipped past the guard above or the D1 boundary is drawn in the wrong place
    — both worth failing on.
    """
    post_d1 = {
        _migration_number(p)
        for p in sorted(_MIG_DIR.glob("*.sql"))
        if _migration_number(p) > D1_BOUNDARY and find_unguarded_alters(p.read_text())
    }
    new = sorted(post_d1 - set(GRANDFATHERED))
    healed = sorted(set(GRANDFATHERED) - post_d1)
    assert post_d1 == set(GRANDFATHERED), (
        (
            f"NEW violation(s) after the D1 boundary: {new}. Either the migration is "
            f"genuinely unguarded — the test above says how to fix it — or it was applied "
            f"to production under a temporary `GRANT visa_ledger_owner`, the same "
            f"emergency path 281/285 took. In THAT case the fix is not to weaken this "
            f"test: add the number to GRANDFATHERED with the date and the reason, exactly "
            f"as its two existing entries do.\n"
            if new else ""
        )
        + (
            f"Grandfathered file(s) that no longer violate: {healed}. Delete their "
            f"GRANDFATHERED entries — an exemption that outlives its reason is a lie.\n"
            if healed else ""
        )
        + f"observed={sorted(post_d1)} grandfathered={sorted(GRANDFATHERED)}"
    )


# --------------------------------------------------------------------------
# guilt and innocence for the detector itself
#
# The guard-conformance rule this repository runs requires that a guard prove
# BOTH that it convicts what it should and that it acquits what it should. A
# detector with only guilt tests can be a function that returns True.
# --------------------------------------------------------------------------

_LEDGER = "visa_decision_retention_policies"

GUILTY = [
    pytest.param(
        f"ALTER TABLE public.{_LEDGER}\n    ADD COLUMN policy_scope TEXT;\n",
        id="bare-alter-add-column",
    ),
    pytest.param(
        f"ALTER TABLE public.{_LEDGER} ADD COLUMN IF NOT EXISTS policy_scope TEXT;\n",
        id="if-not-exists-does-not-save-you",
    ),
    pytest.param(
        f"alter table {_LEDGER}\n    drop constraint foo;\n",
        id="lowercase-and-unqualified",
    ),
    pytest.param(
        f"-- prose mentioning ALTER TABLE {_LEDGER} harmlessly\n"
        f"ALTER TABLE public.{_LEDGER}\n"
        f"    ADD CONSTRAINT c CHECK (true);\n",
        id="real-statement-below-a-comment-that-mentions-it",
    ),
    pytest.param(
        f"DO $blk$ BEGIN NULL;\nALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\n",
        id="unterminated-body-must-not-blind-the-tail",
    ),
    pytest.param(
        f"SELECT 1; ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\n",
        id="two-statements-on-one-line",
    ),
    pytest.param(
        f"INSERT INTO t(c) VALUES ('a -- x');\nALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\n",
        id="double-dash-inside-a-string-literal-is-not-a-comment",
    ),
    pytest.param(
        f"INSERT INTO t VALUES ('it''s -- fine');\nALTER TABLE public.{_LEDGER} ADD COLUMN x;\n",
        id="escaped-quote-inside-a-literal",
    ),
    pytest.param(
        f"/* line one\n   ALTER TABLE public.{_LEDGER} in prose\n*/\n"
        f"ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\n",
        id="multi-line-block-comment-then-a-real-alter",
    ),
    pytest.param(
        f"ALTER TABLE public.{_LEDGER}\n    ADD COLUMN x TEXT\n",
        id="no-terminating-semicolon-at-eof",
    ),
    pytest.param(
        f"ALTER TABLE IF EXISTS public.{_LEDGER} DROP CONSTRAINT c;\n",
        id="alter-table-if-exists",
    ),
    pytest.param(
        f"DO $blk$ BEGIN\nALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\nEND\n$blk$;\n",
        id="bare-alter-inside-a-TAGGED-do-block",
    ),
    pytest.param(
        "DO $$ BEGIN\n"
        f"  EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT';\n"
        "END $$;\n",
        id="unconditional-EXECUTE-in-a-DO-block-is-not-a-guard",
    ),
    pytest.param(
        f"ALTER TABLE ONLY public.{_LEDGER} ADD COLUMN x TEXT;\n",
        id="alter-table-only",
    ),
    pytest.param(
        f"DO $a$ BEGIN NULL; END $a$;\nDO $b$ BEGIN NULL; END $b$;\n"
        f"ALTER TABLE public.{_LEDGER} ADD COLUMN x;\n",
        id="consecutive-tagged-blocks-then-a-real-alter",
    ),
]

INNOCENT = [
    pytest.param(
        "DO $$ BEGIN\n"
        "  IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
        f"                 WHERE table_name='{_LEDGER}' AND column_name='policy_scope') THEN\n"
        f"    EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN policy_scope TEXT';\n"
        "  END IF;\n"
        "END $$;\n",
        id="catalog-guarded-inside-a-DO-block",
    ),
    pytest.param(
        f"-- ALTER TABLE public.{_LEDGER} ADD COLUMN policy_scope TEXT;\n"
        f"-- (discussed in prose, never executed)\n",
        id="comment-only",
    ),
    pytest.param(
        "ALTER TABLE public.garuda_orders ADD COLUMN status TEXT;\n",
        id="app-owned-table-is-none-of-our-business",
    ),
    pytest.param(
        "CREATE FUNCTION f() RETURNS void AS $$\n"
        "BEGIN\n"
        f"  EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT';\n"
        "END;\n"
        "$$ LANGUAGE plpgsql;\n",
        id="inside-a-function-body",
    ),
    pytest.param(
        f"CREATE TRIGGER t AFTER INSERT ON public.{_LEDGER} EXECUTE FUNCTION f();\n",
        id="create-trigger-is-out-of-scope-on-purpose",
    ),
    pytest.param(
        f"CREATE FUNCTION g() RETURNS void AS $func$\nBEGIN\n"
        f"  EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN x';\nEND;\n"
        f"$func$ LANGUAGE plpgsql;\n",
        id="inside-a-TAGGED-function-body",
    ),
    pytest.param(
        "DO $g$ BEGIN\n"
        f"  IF to_regclass('public.{_LEDGER}') IS NOT NULL THEN\n"
        f"    EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT';\n"
        "  END IF;\n"
        "END $g$;\n",
        id="conditional-EXECUTE-in-a-TAGGED-do-block",
    ),
    pytest.param(
        f"SELECT 'ALTER TABLE public.{_LEDGER} ADD COLUMN x';\n",
        id="named-only-inside-a-string-literal",
    ),
    pytest.param(
        f"ALTER TABLE public.garuda_orders ADD COLUMN src TEXT DEFAULT '{_LEDGER}';\n",
        id="listed-name-only-inside-a-DEFAULT-literal",
    ),
    pytest.param(
        "ALTER TABLE public.visa_decisions_archive ADD COLUMN x TEXT;\n",
        id="a-different-table-whose-name-contains-a-listed-one",
    ),
]


@pytest.mark.parametrize("sql", GUILTY)
def test_detector_convicts(sql: str) -> None:
    assert find_unguarded_alters(sql), "detector missed an unguarded ALTER"


@pytest.mark.parametrize("sql", INNOCENT)
def test_detector_acquits(sql: str) -> None:
    assert not find_unguarded_alters(sql), f"detector produced a false positive on:\n{sql}"


def test_an_fk_reference_is_reported_as_a_privilege_problem_not_an_ownership_one() -> None:
    """A true finding with a false diagnosis sends the author to the wrong fix.

    `ALTER TABLE <app-owned> ... REFERENCES <ledger-owned>` DOES fail in
    production — that is exactly how migration 286 died — but the cure is a
    one-time GRANT by the table's owner, not a catalog guard. Reporting it as
    "ALTERs the ledger table" would be right about there being a problem and
    wrong about every actionable detail.
    """
    owner_case = find_unguarded_alters(
        f"ALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\n"
    )
    assert [(t, k) for _, t, k, _ in owner_case] == [(_LEDGER, "owner")]

    reference_case = find_unguarded_alters(
        "ALTER TABLE public.garuda_orders ADD CONSTRAINT fk "
        f"FOREIGN KEY (pid) REFERENCES public.{_LEDGER}(id);\n"
    )
    assert [(t, k) for _, t, k, _ in reference_case] == [(_LEDGER, "references")]


def test_the_corpus_is_actually_being_scanned() -> None:
    """A glob that matches nothing makes every assertion above vacuously true.

    Measured 2026-08-26: 169 migration files. Asserting a floor rather than the
    exact count keeps this from becoming a chore on every new migration, while
    still going red if the directory moves or the pattern rots.
    """
    files = list(_MIG_DIR.glob("*.sql"))
    assert len(files) >= 160, f"only {len(files)} migration files found at {_MIG_DIR}"
    post_d1 = [p for p in files if _migration_number(p) > D1_BOUNDARY]
    assert post_d1, "no post-D1 migrations found — the rule above would test nothing"


# ==============================================================================
# FUNCTION DDL: the same hazard, past ALTER TABLE
# ==============================================================================
#
# WHY THIS EXTENSION EXISTS
# ------------------------------------------------------------------------------
# Everything above guards `ALTER TABLE`. Postgres applies the identical
# ownership check -- the session must be the object's owner, or hold membership
# in the owning role -- to `CREATE OR REPLACE FUNCTION`, `DROP FUNCTION`, and a
# bare `ALTER FUNCTION` on a function that already exists. The D1
# least-privilege repair did not stop at tables: 268's own header already
# records that it moved ownership of several FUNCTIONS to `visa_ledger_owner`
# too ("...moved ownership of the Visa Oracle ledger tables (and several
# already-`SECURITY DEFINER` functions)..."). Measured directly against the
# production leader (2026-08-27, read-only, `pg_get_userbyid(proowner)` over
# `pg_proc` joined to `pg_namespace`), `visa_ledger_owner` owns every function
# named in NON_APP_OWNED_FUNCTIONS below -- `backend_rag_v2` can no more
# `CREATE OR REPLACE` or `DROP` one of them than it can `ALTER TABLE` one of
# the tables above, for the identical reason.
#
# Migration 289 (`289_visa_retention_binders_scope_to_visa_decision.sql`, this
# branch) is the first migration written after this specific gap -- function
# DDL, not table DDL -- was understood: both its `CREATE OR REPLACE FUNCTION`
# statements sit inside a `DO $guardN$` block that checks
# `pg_has_role(current_user, proowner, 'USAGE')` against the LIVE catalog and
# `RETURN`s before attempting the replace if the connecting role cannot. That
# is the function-DDL equivalent of the `information_schema.columns` catalog
# guard the table section documents above for `ALTER TABLE ... ADD COLUMN` --
# same shape, same reason: a guard must be able to DECLINE to run the
# statement, not merely sit inside a pair of `$$`.
#
# THE SAME TRAP INSIDE THE TRAP
# ------------------------------------------------------------------------------
# `DROP FUNCTION IF EXISTS <owned-elsewhere>` looks safe -- IF EXISTS should
# make a missing function a clean no-op -- and fails exactly like
# `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` already does above: Postgres
# checks ownership BEFORE the existence short-circuit, so a function that
# already exists and is owned by someone else still raises
# `must be owner of function`, `IF EXISTS` or not. The two ROLLBACK sections
# this rule newly convicts (281, 286 -- see FUNCTION_GRANDFATHERED below) are
# exactly that shape.
#
# SCOPE
# ------------------------------------------------------------------------------
# Bare `CREATE FUNCTION` (no `OR REPLACE`) is deliberately NOT convicted: it
# only succeeds when the function does not yet exist, which needs CREATE
# privilege on the schema, never ownership of the function -- it is how every
# one of these functions was born in the first place (281's own forward
# section creates seven of them exactly this way, immediately before its own
# best-effort `ALTER FUNCTION ... OWNER TO visa_ledger_owner` transfer at the
# end of that same migration). Convicting a bare `CREATE FUNCTION` would be a
# rule invented, not measured -- the same discipline the table section already
# applies to `CREATE TRIGGER` / `CREATE INDEX`.

# Functions production does NOT let `backend_rag_v2` own.
#
# PROVENANCE: measured on the production leader on 2026-08-27, read-only, with
#
#   SELECT p.proname, pg_get_userbyid(p.proowner) AS owner
#     FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
#    WHERE n.nspname = 'public'
#      AND pg_get_userbyid(p.proowner) <> 'backend_rag_v2'
#    ORDER BY 1;
#
# Every function below came back owned by `visa_ledger_owner`. Same caveat as
# NON_APP_OWNED_TABLES above: this is a snapshot, not a live query -- a floor,
# not a ceiling.
NON_APP_OWNED_FUNCTIONS: frozenset[str] = frozenset(
    {
        # owner: visa_ledger_owner (the D1 least-privilege repair; 268's own
        # header names this same role for functions, not only tables)
        "bind_visa_decision_retention_policy",
        "bind_visa_evaluate_idempotency_retention_policy",
        "bind_visa_decision_payload_retention",
        "bind_garuda_voa_check_retention_policy",
        "bind_garuda_voa_check_result_retention_policy",
        "bind_legacy_garuda_voa_checks_retention_policy",
        "purge_visa_decisions",
        "purge_visa_evaluate_idempotency",
        "purge_garuda_voa_checks",
        "purge_garuda_voa_check_results",
        "erase_visa_decision_for_dsr",
        "visa_activate_rule_pack",
        "visa_replace_activation_set",
        "prepare_visa_evaluate_idempotency_reservation",
        "set_visa_decision_legal_hold",
        "set_garuda_voa_check_legal_hold",
        "reject_visa_activation_insert",
        "reject_visa_activation_mutation",
        "reject_visa_immutable_mutation",
        "reject_visa_pack_payload_mismatch",
        "guard_garuda_voa_check_legal_hold_events_mutation",
        "guard_garuda_voa_checks_retention_mutation",
        "visa_decision_retention_evidence",
        "visa_idempotency_retention_evidence",
        "visa_idempotency_key_usage_evidence",
        "garuda_voa_check_retention_evidence",
    }
)

# Migrations whose ROLLBACK section drops one of the functions above without a
# catalog guard, and are FROZEN that way on purpose -- same rationale as
# GRANDFATHERED for tables above: the file's on-disk text is a checksummed,
# already-applied record, and editing it now would only diverge the file from
# that checksum for a codepath nothing exercises (`migration_base.py`'s runner
# extracts only the FORWARD section at apply time; a real rollback reads
# `rollback_sql` captured in `_schema_versions` at apply time, per 289's own
# header, not this file).
#
# Kept as a SEPARATE dict from the table GRANDFATHERED above, deliberately:
# the two convict for independently-true reasons on different statements, and
# 285 -- grandfathered above for an ALTER TABLE finding -- has NO function-DDL
# finding at all (none of the functions its rollback drops appear in
# NON_APP_OWNED_FUNCTIONS). Folding it into one shared dict would either
# grandfather 285 here for nothing, or force this file to explain an entry
# that never actually violates the function rule.
FUNCTION_GRANDFATHERED: dict[int, str] = {
    281: (
        "rollback section (after `-- === ROLLBACK ===`) bare-DROPs the seven "
        "functions 281's own forward section creates and then best-effort "
        "transfers to visa_ledger_owner (lines ~820-859) -- same shape and "
        "root cause as 281's ALTER TABLE entry in GRANDFATHERED above, just "
        "on the function side of the same migration"
    ),
    286: (
        "rollback section bare-DROPs purge_garuda_voa_check_results and "
        "bind_garuda_voa_check_result_retention_policy, both transferred to "
        "visa_ledger_owner by 286's own forward-section best-effort transfer "
        "(lines ~394-427) -- identical shape to 281's, on a migration that "
        "has no ALTER TABLE finding of its own and so is not already in the "
        "table GRANDFATHERED dict above"
    ),
}

# Statement types that need FUNCTION ownership. Bare `CREATE FUNCTION` (no
# `OR REPLACE`) is deliberately absent -- see SCOPE above.
_FUNCTION_DDL_TOP = re.compile(
    r"^(?:CREATE\s+OR\s+REPLACE\s+FUNCTION|DROP\s+FUNCTION(?:\s+IF\s+EXISTS)?|ALTER\s+FUNCTION)\b",
    re.IGNORECASE,
)
# The function actually targeted: its name immediately followed by its
# argument-list opening paren (every function signature has one, even a
# zero-arg function -- `f()`).
_FUNCTION_TARGET = re.compile(
    r"^(?:CREATE\s+OR\s+REPLACE\s+FUNCTION|DROP\s+FUNCTION(?:\s+IF\s+EXISTS)?|ALTER\s+FUNCTION)\s+"
    r'(?:public\s*\.\s*)?"?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"?\s*\(',
    re.IGNORECASE,
)
# Same statement, matched anywhere rather than anchored at the front -- for
# the `EXECUTE 'CREATE OR REPLACE FUNCTION ...'` shape inside a DO block, same
# reason `_ALTER_ANYWHERE` exists above.
_FUNCTION_ANYWHERE = re.compile(
    r"(?:CREATE\s+OR\s+REPLACE\s+FUNCTION|DROP\s+FUNCTION(?:\s+IF\s+EXISTS)?|ALTER\s+FUNCTION)\s+"
    r'(?:public\s*\.\s*)?"?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"?\s*\(',
    re.IGNORECASE,
)


def find_unguarded_function_ddl(sql: str) -> list[tuple[int, str, str, str]]:
    """Return (line_no, function_name, kind, statement) for each top-level
    CREATE OR REPLACE FUNCTION / DROP FUNCTION / ALTER FUNCTION naming a
    ledger-owned function.

    Deliberately reuses the exact lexer (`_executable_text`) and the exact
    DO-block discipline `find_unguarded_alters` above uses for tables: a
    dollar-quoted body is exempt from scanning unless it is a `DO` block (a
    routine's own `AS $$ ... $$` body is never convicted -- that is precisely
    where 268/281/286's ownership-transfer cure and 289's guard live) AND
    contains no conditional at all (`END IF` anywhere is read as "this block
    CAN decline" -- the same coarse, false-positive-free heuristic the table
    detector already uses, for the same reason: proving the ALTER/DROP/REPLACE
    sits *inside* that conditional needs real PL/pgSQL control-flow analysis,
    which does not belong in a test file).

    This is what acquits migration 289 with NO special case written for it:
    each of its `DO $guardN$` bodies contains
    `IF NOT pg_has_role(...) THEN RAISE NOTICE ...; RETURN; END IF;` before
    the `EXECUTE $ddl$ CREATE OR REPLACE FUNCTION ...`, so `_HAS_CONDITIONAL`
    matches and the body is never scanned for a function-DDL finding at all --
    same mechanism, not a carve-out.
    """
    chars, origin, bodies = _executable_text(sql)
    findings: list[tuple[int, str, str, str]] = []

    start = 0
    for end in [idx for idx, c in enumerate(chars) if c == ";"] + [len(chars)]:
        segment = "".join(chars[start:end])
        head = len(segment) - len(segment.lstrip())
        collapsed = " ".join(segment.split())
        at = start + head
        start = end + 1
        if not collapsed or not _FUNCTION_DDL_TOP.match(collapsed):
            continue
        lineno = origin[at] if at < len(origin) else (origin[-1] if origin else 1)
        target_match = _FUNCTION_TARGET.match(collapsed)
        target = target_match.group("name").lower() if target_match else None
        if target in NON_APP_OWNED_FUNCTIONS:
            findings.append((lineno, target, "owner", collapsed[:110]))

    # A dollar-quoted body is exempt only if it is actually a GUARD -- same
    # rule, same reasoning as the table detector's identical block above.
    for body_lineno, body, is_do in bodies:
        if not is_do or _HAS_CONDITIONAL.search(body):
            continue
        for m in _FUNCTION_ANYWHERE.finditer(body):
            target = m.group("name").lower()
            if target not in NON_APP_OWNED_FUNCTIONS:
                continue
            findings.append((
                body_lineno + body.count("\n", 0, m.start()),
                target,
                "unguarded-do",
                " ".join(body[m.start() : m.start() + 110].split()),
            ))
            break

    return sorted(findings)


def test_no_post_d1_migration_replaces_a_function_the_app_role_cannot_own() -> None:
    """The function-DDL analogue of the real ALTER TABLE assertion above."""
    offenders: list[str] = []
    for path in sorted(_MIG_DIR.glob("*.sql")):
        number = _migration_number(path)
        if number <= D1_BOUNDARY or number in FUNCTION_GRANDFATHERED:
            continue
        for lineno, name, kind, statement in find_unguarded_function_ddl(path.read_text()):
            if kind == "unguarded-do":
                offenders.append(
                    f"{path.name}:{lineno} runs function DDL on `{name}` inside a `DO` block "
                    f"that contains no conditional at all -- so it EXECUTEs unconditionally and "
                    f"fails in production exactly like a bare statement. Being inside `$$` is not "
                    f"a guard; being able to DECLINE is.\n    {statement}\n"
                    f"    Wrap it the way migration 289 does -- see the fix below."
                )
                continue
            offenders.append(
                f"{path.name}:{lineno} runs unguarded function DDL on `{name}`, which production "
                f"does not let `backend_rag_v2` own -- this fails in prod "
                f"(`must be owner of function`) and passes in CI.\n"
                f"    {statement}\n"
                f"    Wrap it in a catalog guard, the way migration 289 does:\n"
                f"        DO $guardN$ BEGIN\n"
                f"          IF NOT pg_catalog.pg_has_role(current_user,\n"
                f"                 (SELECT proowner FROM pg_catalog.pg_proc\n"
                f"                   WHERE oid = 'public.{name}(...)'::regprocedure), 'USAGE') THEN\n"
                f"            RAISE NOTICE 'cannot replace {name} -- % is neither owner nor "
                f"member', current_user;\n"
                f"            RETURN;\n"
                f"          END IF;\n"
                f"          EXECUTE $ddl$ ... $ddl$;\n"
                f"        END $guardN$;\n"
                f"    `DROP FUNCTION IF EXISTS` does NOT save you either: the ownership check\n"
                f"    runs before the IF-EXISTS short-circuit, same trap as ALTER TABLE above."
            )
    assert not offenders, "\n\n".join(offenders)


def test_the_function_grandfathered_entries_really_do_still_violate_the_rule() -> None:
    """An exemption for something that stopped violating is a lie in the config.

    Mirrors `test_the_grandfathered_pair_really_does_still_violate_the_rule`
    above, for FUNCTION_GRANDFATHERED instead of GRANDFATHERED.
    """
    for number in FUNCTION_GRANDFATHERED:
        matches = list(_MIG_DIR.glob(f"{number}_*.sql"))
        assert len(matches) == 1, f"expected exactly one migration {number}, got {matches}"
        findings = find_unguarded_function_ddl(matches[0].read_text())
        assert findings, (
            f"migration {number} is on FUNCTION_GRANDFATHERED but no longer contains an "
            f"unguarded function DDL statement. Remove its entry."
        )


def test_migration_289_is_acquitted_by_the_function_detector() -> None:
    """289 is the migration that INTRODUCED the catalog-guard shape this
    detector enforces -- both its `CREATE OR REPLACE FUNCTION` statements
    replace ledger-owned functions from inside a `DO $guardN$` block that
    checks `pg_has_role` and can decline. If the detector convicts 289, the
    detector is wrong, not 289: do not "fix" 289 to satisfy a broken rule.
    """
    matches = list(_MIG_DIR.glob("289_*.sql"))
    assert len(matches) == 1, f"expected exactly one migration 289, got {matches}"
    findings = find_unguarded_function_ddl(matches[0].read_text())
    assert not findings, f"289 should be catalog-guarded and innocent, got: {findings}"


# --------------------------------------------------------------------------
# guilt and innocence for the function detector itself
# --------------------------------------------------------------------------

_LEDGER_FN = "purge_visa_decisions"

FUNCTION_GUILTY = [
    pytest.param(
        f"CREATE OR REPLACE FUNCTION public.{_LEDGER_FN}(p_limit INTEGER, p_requested_by TEXT)\n"
        f"RETURNS INTEGER LANGUAGE plpgsql AS $$\nBEGIN\n  RETURN 0;\nEND;\n$$;\n",
        id="bare-create-or-replace",
    ),
    pytest.param(
        f"DROP FUNCTION IF EXISTS public.{_LEDGER_FN}(INTEGER, TEXT);\n",
        id="drop-function-if-exists-does-not-save-you",
    ),
    pytest.param(
        f"ALTER FUNCTION public.{_LEDGER_FN}(INTEGER, TEXT) SECURITY DEFINER;\n",
        id="bare-alter-function",
    ),
    pytest.param(
        f"drop function {_LEDGER_FN}(integer, text);\n",
        id="lowercase-and-unqualified",
    ),
    pytest.param(
        "DO $$ BEGIN\n"
        f"  EXECUTE 'CREATE OR REPLACE FUNCTION public.{_LEDGER_FN}(p_limit INTEGER, "
        f"p_requested_by TEXT) RETURNS INTEGER LANGUAGE sql AS $body$ SELECT 0 $body$';\n"
        "END $$;\n",
        id="unconditional-EXECUTE-in-a-DO-block-is-not-a-guard",
    ),
    pytest.param(
        f"DO $blk$ BEGIN NULL;\nDROP FUNCTION IF EXISTS public.{_LEDGER_FN}(INTEGER, TEXT);\n",
        id="unterminated-body-must-not-blind-the-tail",
    ),
]

FUNCTION_INNOCENT = [
    pytest.param(
        f"CREATE FUNCTION public.{_LEDGER_FN}(p_limit INTEGER, p_requested_by TEXT)\n"
        f"RETURNS INTEGER LANGUAGE plpgsql AS $$\nBEGIN\n  RETURN 0;\nEND;\n$$;\n",
        id="bare-create-no-or-replace-is-how-they-are-all-born",
    ),
    pytest.param(
        "DO $guard1$\nBEGIN\n"
        "  IF NOT pg_catalog.pg_has_role(current_user,\n"
        f"         (SELECT proowner FROM pg_catalog.pg_proc WHERE oid = "
        f"'public.{_LEDGER_FN}(integer, text)'::regprocedure), 'USAGE') THEN\n"
        f"    RAISE NOTICE 'cannot replace {_LEDGER_FN} -- % is neither owner nor member', "
        "current_user;\n"
        "    RETURN;\n"
        "  END IF;\n"
        "  EXECUTE $ddl$\n"
        f"CREATE OR REPLACE FUNCTION public.{_LEDGER_FN}(p_limit INTEGER, p_requested_by TEXT)\n"
        "RETURNS INTEGER LANGUAGE plpgsql AS $fn$\nBEGIN\n  RETURN 0;\nEND;\n$fn$;\n"
        "    $ddl$;\n"
        "END;\n"
        "$guard1$;\n",
        id="catalog-guarded-like-migration-289",
    ),
    pytest.param(
        f"-- DROP FUNCTION IF EXISTS public.{_LEDGER_FN}(INTEGER, TEXT); (discussed in prose)\n",
        id="comment-only",
    ),
    pytest.param(
        "CREATE OR REPLACE FUNCTION public.guard_garuda_order_state_transition()\n"
        "RETURNS trigger LANGUAGE plpgsql AS $$\nBEGIN\n  RETURN NEW;\nEND;\n$$;\n",
        id="app-owned-function-is-none-of-our-business",
    ),
    pytest.param(
        f"CREATE FUNCTION f() RETURNS void AS $$\nBEGIN\n"
        f"  EXECUTE 'DROP FUNCTION IF EXISTS public.{_LEDGER_FN}(integer, text)';\n"
        "END;\n$$ LANGUAGE plpgsql;\n",
        id="inside-a-function-body-is-not-a-DO-block",
    ),
    pytest.param(
        "DO $g$ BEGIN\n"
        f"  IF to_regclass('public.some_marker') IS NOT NULL THEN\n"
        f"    EXECUTE 'DROP FUNCTION IF EXISTS public.{_LEDGER_FN}(integer, text)';\n"
        "  END IF;\n"
        "END $g$;\n",
        id="conditional-EXECUTE-in-a-TAGGED-do-block",
    ),
    pytest.param(
        f"SELECT 'DROP FUNCTION IF EXISTS public.{_LEDGER_FN}(integer, text)';\n",
        id="named-only-inside-a-string-literal",
    ),
]


@pytest.mark.parametrize("sql", FUNCTION_GUILTY)
def test_function_detector_convicts(sql: str) -> None:
    assert find_unguarded_function_ddl(sql), "detector missed an unguarded function DDL statement"


@pytest.mark.parametrize("sql", FUNCTION_INNOCENT)
def test_function_detector_acquits(sql: str) -> None:
    assert not find_unguarded_function_ddl(sql), f"detector produced a false positive on:\n{sql}"
