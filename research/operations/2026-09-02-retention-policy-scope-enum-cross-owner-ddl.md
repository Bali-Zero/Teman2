---
date: 2026-09-02
domain: compliance
client_case: none
sources:
  - apps/backend-rag/backend/db/migrations_v2/281_garuda_voa_retention.sql
  - apps/backend-rag/backend/db/migrations_v2/285_garuda_magic_link.sql
  - apps/backend-rag/backend/db/migrations_v2/304_garuda_documents.sql
  - apps/backend-rag/backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py
  - apps/backend-rag/backend/tests/services/visa_engine/conftest.py
---

# The retention `policy_scope` enum is a CHECK on someone else's table

**Status:** spec, not a change. Written under the rule "cure what the diff introduces,
spec what it inherits" — PR #5526 introduced the third instance and cures its own; the
mechanism that keeps producing instances is older than that diff and is not its to fix.

## The disease, stated once

`visa_decision_retention_policies.policy_scope` is constrained by a CHECK that enumerates
its legal values. The table is owned by `visa_ledger_owner` after the D1 least-privilege
repair. The application role `backend_rag_v2` holds SELECT on it and nothing more.

Therefore **every new GARUDA surface that needs its own retention scope requires a schema
change to a table the application cannot alter**. Adding a value to that enum is
`ALTER TABLE ... DROP CONSTRAINT` + `ADD CONSTRAINT`, and `ALTER TABLE` requires ownership.
No privilege can be granted once to make this legal: ownership is checked per statement,
and Postgres checks it *before* any `IF NOT EXISTS` short-circuit.

The consequence is not theoretical. It has happened three times:

| Migration | Surface | Outcome |
|---|---|---|
| 281 | `garuda_voa_checks` | failed in production 2026-08-26, took four other migrations down with it, aborted the deploy; applied afterwards under a temporary grant |
| 285 | `garuda_magic_link_tokens` | same class, same emergency path; both sit in `GRANDFATHERED` |
| 304 | `garuda_documents` | caught before production by `test_post_d1_migrations_guard_ledger_owned_ddl.py`, the guard written *because* of 281/285 |

The guard works. That is the good news and also the point: it converts a production outage
into a blocked PR, but it does not remove the manual step. Each new surface still costs a
human-held grant on the production database, plus a follow-up commit recording the
application as grandfathered. Three surfaces have paid it. Every future one will.

## What is NOT the problem

The **foreign key** onto the same table looked like a second instance of this and is not.
The repo already solved that one properly: `conftest.py:491` holds
`_GARUDA_VOA_RETENTION_FK_DEPENDENTS`, a registry of every migration that FKs onto
`visa_decision_retention_policies`, walked in reverse by `unwind_garuda_voa_retention_fk()`
so `rollback_264`'s un-CASCADEd `DROP TABLE` succeeds — and
`test_visa_engine_retention_fk_registry.py` fails at authoring time when a new migration
forgets to register. One line per surface, guarded, no human in the loop.

That is the shape the enum lacks, and it is the proof this repo can build it: the FK
problem and the enum problem are the same problem, and one of them already has an antidote.

## Why the obvious repairs do not work

- **Catalog guards.** A catalog guard (`DO $$ IF NOT EXISTS(...) THEN EXECUTE 'ALTER ...'
  END IF $$`) makes the migration a clean no-op where the value is *already* present. That
  is necessary and 304 should have it. It does not help the first time, on any database
  that does not yet have the value — which is every new environment, and production on the
  day the surface ships.
- **Granting `backend_rag_v2` membership in `visa_ledger_owner`.** Legal, and it undoes the
  D1 least-privilege repair wholesale to buy one enum. Rejected.
- **Dropping the CHECK and validating in the application.** Removes a real integrity
  guarantee from the table that carries retention decisions — the one place where a
  silently wrong value has legal consequences under UU PDP. Rejected.

## The repair that removes the class

Replace the CHECK enum with a **lookup table plus a foreign key**:

```
public.visa_retention_policy_scopes (scope TEXT PRIMARY KEY, added_on DATE, note TEXT)
-- owned by visa_ledger_owner
-- GRANT INSERT, SELECT ON it TO backend_rag_v2   -- once, forever

visa_decision_retention_policies.policy_scope  REFERENCES visa_retention_policy_scopes(scope)
```

The asymmetry this exploits is the whole idea: **a schema change needs ownership every
time; a data change needs a privilege that can be granted once.** After the one-time
migration, a new GARUDA surface adds its scope with an `INSERT ... ON CONFLICT DO NOTHING`
— an ordinary statement the application role may execute, in an ordinary migration, with
no grant, no grandfather entry and no human.

The integrity guarantee is not weakened: a foreign key rejects an unknown scope exactly as
the CHECK did. It is strengthened in one respect — the legal values become queryable rows
rather than text inside a constraint definition, so a retention audit can read them instead
of parsing `pg_get_constraintdef`.

**Cost, stated honestly:** one migration that must itself run as `visa_ledger_owner`, i.e.
one more human-held grant. This spec argues that paying once is cheaper than paying per
surface — but it is a real fourth payment, not a free lunch, and it should be scheduled
deliberately rather than smuggled into a feature PR.

## Acceptance, if this is built

1. A migration, applied under the ledger owner, that creates the lookup table, seeds it
   with the values the CHECK currently lists, swaps the CHECK for the FK, and grants
   `INSERT, SELECT` to `backend_rag_v2`.
2. `test_post_d1_migrations_guard_ledger_owned_ddl.py` still passes with `GRANDFATHERED`
   unchanged — the new migration is the last one that needs the grant, and it says so.
3. An authoring-time guard modelled on `test_visa_engine_retention_fk_registry.py`: a
   migration that introduces a new `policy_scope` string without a matching seeding INSERT
   fails CI. Without this the class returns in a new costume.
4. A test proving the FK rejects an unknown scope, and an innocence control proving every
   value the CHECK accepted before is still accepted.

## Until then

304 carries a catalog guard, is applied to production under the same temporary grant as
281 and 285, and is added to `GRANDFATHERED` **after** the application, in a commit citing
the before/after `pg_constraint` observation and its timestamp — never before, or the list
records a state that does not exist.
