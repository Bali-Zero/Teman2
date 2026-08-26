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
Only `ALTER TABLE` is checked. `CREATE TRIGGER` needs the TRIGGER privilege and
`CREATE INDEX` needs ownership too, and post-D1 migrations that do either against
these tables would very likely fail as well — but no such statement exists today,
so including them would be a rule asserted rather than measured. A guard that
invents a target is as bad as one that misses it. Widen this when there is an
observation to widen it with.
"""

from __future__ import annotations

import re
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


def _executable_text(sql: str) -> tuple[list[str], list[int]]:
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
            lineno += sql.count("\n", i, j + len(tag))
            i = j + len(tag)
            chars.append(" ")
            origin.append(lineno)
        else:
            chars.append(ch)
            origin.append(lineno)
            i += 1
    return chars, origin


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
    chars, origin = _executable_text(sql)
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
    return findings


def _migration_number(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


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
    assert post_d1 == set(GRANDFATHERED), (
        f"post-D1 files with a top-level ALTER on a non-app-owned table: {sorted(post_d1)}; "
        f"grandfathered: {sorted(GRANDFATHERED)}"
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
        f"DO $blk$ BEGIN\nALTER TABLE public.{_LEDGER} ADD COLUMN x TEXT;\nEND\n$blk$;\n",
        id="bare-alter-inside-a-TAGGED-do-block",
    ),
    pytest.param(
        f"CREATE FUNCTION g() RETURNS void AS $func$\nBEGIN\n"
        f"  EXECUTE 'ALTER TABLE public.{_LEDGER} ADD COLUMN x';\nEND;\n"
        f"$func$ LANGUAGE plpgsql;\n",
        id="inside-a-TAGGED-function-body",
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
