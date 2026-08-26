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
Measured over all 169 migration files: 47 top-level `ALTER TABLE` statements
target a table that production no longer lets the app role own. 37 of them live
in migrations <= 268 and applied without incident, because at the time they ran
the runtime role still WAS the owner — the D1 repair came afterwards. The
remaining 10 live in migrations > 268, and they are exactly the two files that
failed in production. The boundary at 268 separates "applied fine, forever
frozen" from "the live hazard" with zero false positives and zero false
negatives against the observed incident, which is why it is drawn there rather
than at some rounder number. Retro-fitting the 37 historical statements would
change nothing in any database and would bury the ten that matter.

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
_TABLE_REF = {t: re.compile(rf"\b(?:public\.)?{t}\b") for t in NON_APP_OWNED_TABLES}


def find_unguarded_alters(sql: str) -> list[tuple[int, str, str]]:
    """Return (line_no, table, statement) for each top-level ALTER TABLE.

    "Top-level" means: not inside a dollar-quoted body. A line is inside one
    when an odd number of ``$$`` tokens has been seen before it — which covers
    both ``DO $$ ... $$;`` blocks and ``CREATE FUNCTION ... $$ ... $$;`` bodies.
    Statements inside such a body are exempt because that is where a catalog
    guard lives: the block can inspect ``information_schema`` and decline to
    ``EXECUTE`` the ALTER at all, which is the only construction that survives
    the ownership check.

    Comment-only lines are skipped before matching. Migration headers in this
    repository legitimately DISCUSS statements like
    ``ALTER TABLE public.visa_decision_retention_policies`` in prose — this
    file's own docstring does it repeatedly — and a scanner that matched raw
    text would convict the documentation instead of the code.
    """
    findings: list[tuple[int, str, str]] = []
    lines = sql.splitlines()
    dollars = 0
    for lineno, raw in enumerate(lines, start=1):
        inside_body = (dollars % 2) == 1
        dollars += raw.count("$$")

        stripped = raw.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if inside_body or not _ALTER_TABLE.match(stripped):
            continue

        # The target table may trail onto the next lines of a multi-line ALTER.
        window = " ".join(lines[lineno - 1 : lineno + 2])
        for table, pattern in _TABLE_REF.items():
            if pattern.search(window):
                findings.append((lineno, table, stripped[:100]))
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
        for lineno, table, statement in find_unguarded_alters(path.read_text()):
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
]


@pytest.mark.parametrize("sql", GUILTY)
def test_detector_convicts(sql: str) -> None:
    assert find_unguarded_alters(sql), "detector missed an unguarded ALTER"


@pytest.mark.parametrize("sql", INNOCENT)
def test_detector_acquits(sql: str) -> None:
    assert not find_unguarded_alters(sql), f"detector produced a false positive on:\n{sql}"


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
