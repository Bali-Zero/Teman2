---
date: 2026-09-02
domain: compliance
client_case: none
adversarial_review: codex
sources:
  - apps/backend-rag/backend/db/migrations_v2/281_garuda_voa_retention.sql
  - apps/backend-rag/backend/db/migrations_v2/285_garuda_magic_link.sql
  - apps/backend-rag/backend/db/migrations_v2/301_garuda_magic_link_binding_owner.sql
  - apps/backend-rag/backend/db/migrations_v2/304_garuda_documents.sql
  - apps/backend-rag/backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py
  - apps/backend-rag/backend/tests/services/visa_engine/conftest.py
  - evidence/2026-09/agent-air-m5-ops-garuda-voa-documents-57f48f6b/journal.jsonl
  - docs/specs/2026-08-31-security-definer-ledger-lock-lint.md
---

# The retention `policy_scope` enum is a CHECK on someone else's table

**Status:** spec, not a change. Written under the rule "cure what the diff introduces,
spec what it inherits" — PR #5526 introduced the third instance and cures its own; the
mechanism that keeps producing instances is older than that diff and is not its to fix.

**Update 2026-09-02:** the cross-family adversarial gate on #5526 BLOCKED three rounds
running, on the same underlying cause, and what it found widens the scope of this spec.
The recurring cost documented below is not one CHECK — it is a **privilege protocol** with
three distinct requirements, and 304 needed all three of them. Two are now satisfied in
production; the third is not, and the PR is suspended on it (ledger row at the bottom of
this repo's `.claude/skills/modus/PENDING-ARMS.md`). See "The privilege protocol is three
requirements, not one" below.

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
| 304 | `garuda_documents` | caught before production by `test_post_d1_migrations_guard_ledger_owned_ddl.py`, the guard written *because* of 281/285 — but the round-2/3 adversarial gate found the catch was partial (see below) |

The guard works, partially. That is the good news and also the point: it converts a
production outage into a blocked PR, but it does not remove the manual step, and — per the
finding below — it cannot see every shape the manual step can take. Each new surface still
costs a human-held grant on the production database. 281 and 285 both needed a follow-up
commit recording the application as `GRANDFATHERED`; 304 will not need one, for a reason
that is itself a finding (see "A guard that cannot see this" below) — but it still needed
two human-held grants before it could be caught as fixed rather than caught as broken, and
a third grant is still outstanding.

## The privilege protocol is three requirements, not one

The thesis above understated the disease: "a schema change to a table the application
cannot alter" is exactly one of *three* distinct privilege requirements 304 turned out to
need, each with a different remedy shape.

| # | Requirement | What it needs | Status on `visa_decision_retention_policies` for 304 |
|---|---|---|---|
| 1 | Widen the `policy_scope` CHECK to add `GARUDA_DOCUMENT` | table ownership (`ALTER TABLE`) | **Done in production**, verified read-only 2026-09-01T22:05:43Z: the CHECK's `ARRAY` now includes `GARUDA_DOCUMENT` (before: four values without it) |
| 2 | `garuda_documents.retention_policy_id` FK REFERENCES the table | the `REFERENCES` privilege (a `GRANT`, not ownership) | **Done**, same verification pass: `has_table_privilege('backend_rag_v2', 'public.visa_decision_retention_policies', 'REFERENCES')` went `false` → `true` |
| 3 | `bind_garuda_document_retention_policy()` (the `BEFORE INSERT` trigger function) must be owned by `visa_ledger_owner`, not `backend_rag_v2`, so its `SECURITY DEFINER` body can take the `FOR SHARE` lock the table owner already holds | role membership in `visa_ledger_owner` **with the schema's CREATE privilege also held by that role and the membership's `SET` option granted** (see correction below), or a superuser connection, at `ALTER FUNCTION ... OWNER TO` time | **Not done.** `pg_has_role('backend_rag_v2', 'visa_ledger_owner', 'MEMBER')` is `false`; the migration-runner role's `rolsuper` is `false`. `304_garuda_documents.sql`'s `DO $garuda_304_owner_transfer$` block (lines 266-304) attempts `ALTER FUNCTION public.bind_garuda_document_retention_policy() OWNER TO visa_ledger_owner` (line 289), catches the resulting `insufficient_privilege` and converts it to a `RAISE NOTICE` (lines 290-293), re-reads the owner, and then, finding it still `backend_rag_v2`, `RAISE EXCEPTION`s at line 299 — a raise that is conditional on three things holding at once (the role existing, the function resolving, and the transfer not having landed on the re-check), not unconditional, though in the stated production configuration it is deterministic. Because `migration_base.py` applies the whole file in one transaction, that abort rolls back the `CREATE FUNCTION` earlier in the same block — the remedy the error message itself names ("run the ALTER on a superuser connection, then re-apply") has nothing left to `ALTER` once the transaction unwinds. **A fourth branch exists and is untested**: lines 273-277 `RETURN` early — recording 304 as cleanly applied — if `visa_ledger_owner` does not exist in the target database at all, leaving the trigger owned by `backend_rag_v2` with no exception raised. Every environment this repo runs in today has the role, so the branch is dormant, not live — but nothing in `test_post_d1_migrations_guard_ledger_owned_ddl.py` or elsewhere asserts the migration refuses to record itself as applied on a database that lacks the role, and a database that reached this state would silently reproduce 285's original pre-301 defect (a `SECURITY DEFINER` function that 500s on its first real INSERT) with a green migration log. |

**Correction against PostgreSQL's own ownership-transfer rule, found by adversarial review
(below):** `ALTER FUNCTION ... OWNER TO` does not accept role membership as the whole
precondition. The session must additionally be able to `SET ROLE` to the new owner — which
requires the membership to carry the `SET` option, a thing distinct from the `INHERIT` option
that governs automatic privilege inheritance — and the new owner role must hold `CREATE` on
the function's containing schema (`public`). A plain `GRANT visa_ledger_owner TO
backend_rag_v2` with neither `SET` nor confirmed schema `CREATE` would still fail the same
`insufficient_privilege` branch the table row above describes. Whichever option below is
chosen, these two facts must be proven true of the target database before the grant is
treated as sufficient — this spec does not assert they are currently false, only that no
evidence on file established they are true.

Requirement 3 is not a corner case this repo has never handled — it is the norm. Six
sibling trigger functions already do, in production, exactly what 304's cannot yet do:
`bind_garuda_magic_link_token_retention_policy`, `bind_garuda_voa_check_result_retention_policy`,
`bind_garuda_voa_check_retention_policy`, `bind_legacy_garuda_voa_checks_retention_policy`,
`bind_visa_decision_retention_policy`, and `bind_visa_evaluate_idempotency_retention_policy`
are all `SECURITY DEFINER` and all owned by `visa_ledger_owner`.

**Correction against the disk** (an earlier draft of this section said this protocol was
"never written down anywhere" — false, and worth stating plainly rather than quietly fixed):
migration `301_garuda_magic_link_binding_owner.sql`'s own header documents the exact
sequence at length — measured 2026-08-30, nobody was a member of `visa_ledger_owner`, so
301's copy of this block was *expected* to `RAISE EXCEPTION` on first attempt (its own words:
"it fails loudly until an operator runs the ALTER, which is the honest state: the cure is
not in force"), and only after an operator ran `ALTER FUNCTION ... OWNER TO` on a superuser
connection and 301 was re-applied did the postcondition hold and the migration record as
applied. 304's header explicitly inherits this ("replicated from 301's shape verbatim...
301's own honest caveat carries over unchanged"). So the actual gap is narrower than "tribal
knowledge": the protocol is written down, repeatedly, **inside each migration's own header**
(251/253/268/281/301/304, each pointing back to the last) — but never distilled into one
operator-facing runbook a future author is sent to instead of re-deriving it from a chain of
SQL comments. That is what "the apply protocol" below actually is: not a discovery of a
hidden step, but the first attempt to write the six-times-repeated narrative down as a
checklist instead of a comment thread.

**Also on the disk, and distinct from this spec's findings**: the general version of
requirement 3 — "no CI guard exists to catch a *future* SECURITY DEFINER ledger-locker that
omits the transfer" — already has its own spec, suspended under rule 8 after four
withdrawn implementation rounds:
`docs/specs/2026-08-31-security-definer-ledger-lock-lint.md`, tracked by its own
`PENDING-ARMS.md` row (opened 2026-08-31, PR #5302). That spec's lexer-based lint targets
a *different* test (`test_retention_lock_triggers_are_ledger_owned.py`, never shipped) than
the one this spec's "guard-over-match" finding below concerns
(`test_post_d1_migrations_guard_ledger_owned_ddl.py`, which does exist and does run) — the
two are adjacent instances of the same underlying disease, not the same open item. This
spec does not attempt to resolve that other one; R6 there (whether a hand-written SQL lexer
should exist at all, given the catalog-driven `SECURITY_DEFINER_CENSUS_SQL` from PR #5309)
is still open and is not this document's to close.

Writing the apply protocol down, and giving the codeowner an explicit choice for closing
requirement 3 on 304, is what the rest of this update does — it does not replace the
lookup-table repair below, which addresses requirement 1 only.

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

**Second cost, found by adversarial review, that the "integrity guarantee is not weakened"
claim above overstated:** the standing `GRANT INSERT ... TO backend_rag_v2` on the lookup
table is *permanent*, not scoped to the one-time migration, and it changes who can mint a
legal scope value. Under the CHECK, `backend_rag_v2` could never add a new value to the
enum by itself — that required `ALTER TABLE`, which is ownership-gated, so a compromised
application role was structurally unable to legalize an arbitrary `policy_scope` string.
Under the lookup table, that same compromised role holds standing `INSERT` and can insert an
arbitrary new row into `visa_retention_policy_scopes`, then reference it from a
`visa_decision_retention_policies` row the FK will accept without complaint — the FK rejects
an *unregistered* scope exactly as claimed, but it cannot reject a scope the attacker just
registered. This is not a reason to reject the repair (the enum-registration win for
requirement 1 is real and the FK still catches a typo or an unregistered surface), but the
integrity property changes shape: from "no application-role write can create a new legal
value" to "an application-role write can, but it lands in an audit-visible row rather than a
silent constraint edit." The acceptance criteria below should require whichever
implementation follows this spec to either scope the `INSERT` narrower than the bare
runtime role (a dedicated migration role, or a `SECURITY DEFINER` function the runtime role
may call but not the bare table) or to accept and document this shape change explicitly
rather than carry forward the stronger claim made above.

The lookup-table repair above closes requirement 1 for good. It says nothing about
requirements 2 and 3 — a FK REFERENCES grant and a trigger-function ownership transfer are
not schema changes to the enum's own CHECK, so a future GARUDA surface that needs its own
retention-bound trigger still needs requirement 3 solved, lookup table or not. The rest of
this update is about requirement 3, which is the one blocking #5526 today.

## The apply protocol (the actual missing artifact)

304's `DO $garuda_304_owner_transfer$` block is not defective SQL — it is a faithful copy of
a pattern this repo has shipped at least six times. What was missing is that **the repo has
never written down what a human must do, and when, before a migration using that pattern is
merged.** On this repo, merging `apps/backend-rag/**` *is* the deploy: `fly-deploy.yml`
fires on push to `main`, and its `release_command` applies pending migrations forward,
automatically, before the new release serves traffic. There is no separate "apply" step for
a human to interpose between merge and production — so any privileged precondition has to
be true *before the merge*, not "during a deploy window":

1. **Before the merge**: every privileged step the migration's forward section cannot
   perform as `backend_rag_v2` must already be true in production. For 304, requirements 1
   and 2 were satisfied this way — the codeowner ran the CHECK-widen and the `GRANT
   REFERENCES` directly over a superuser `psql` session, and the session verified the result
   read-only afterward (`pg_get_constraintdef`, `has_table_privilege`).
2. **The migration's own catalog guards are what make step 1 safe to do out of band.**
   304's `DO $garuda_304_widen_scope_check$` block reads `pg_constraint` first and no-ops
   the `ALTER` entirely once the value is already present, so establishing the CHECK ahead
   of the merge does not create a second competing writer — the migration, when it runs,
   finds nothing left to do for that requirement and moves on.
3. **Requirement 3 cannot be pre-satisfied the same way**, and this is the actual gap in the
   protocol, not a flaw in 304: `to_regprocedure('public.bind_garuda_document_retention_policy()')`
   can only resolve *after* the `CREATE FUNCTION` earlier in the same file, and that
   `CREATE` lives inside this migration's own transaction. The ownership-transfer attempt
   therefore necessarily happens *inside* the merge-triggered apply, never before it. What
   must exist before the merge fires the deploy is not the transfer itself but the
   *privilege that lets the transfer succeed* — see the two options below.
4. **After the merge**, verify against production the way round 2 did: read the actual
   catalog state (`pg_get_constraintdef`, `has_table_privilege`,
   `pg_get_userbyid(proowner)`), not the migration's exit code. A green `release_command`
   proves the transaction committed — it does not say which branch of a `DO` block it took.

## Two ways to close requirement 3 — undecided by design

Both named routes below clear the block on #5526 (one of them, checked against the disk,
turns out to have a precedented variant worth naming separately — see (A′)). Neither is
chosen here: the choice trades an operational risk window against a functional gap, and
that is a business-risk call for the codeowner, not this spec.

**(A) Temporary membership.** `GRANT visa_ledger_owner TO backend_rag_v2` immediately
before the merge; `REVOKE` immediately after the post-merge verification in step 4 above
confirms the transfer landed. **Correction against the disk**: an earlier draft of this
paragraph claimed this "matches what the six sibling migrations relied on" — checked against
301's own header and found wrong. What 301 actually documents is a *different* mechanism:
"the ALTER lands on a superuser connection (CI, a fresh clone, or the operator's provisioning
step)... the cure was applied to production in one manual superuser transaction." That is an
operator's own already-privileged session executing the transfer (or the whole migration)
directly — never a grant that elevates `backend_rag_v2` itself. So (A) as stated here is a
genuinely different proposal from precedent, not a restatement of it, and should be judged on
its own cost: for the length of the window, `backend_rag_v2` — the application's own runtime
role, reachable from ordinary request-handling code — can do anything `visa_ledger_owner` can,
against a live production database, not a sandbox. That is a broader blast radius than an
operator's own session doing one `ALTER FUNCTION` by hand, which is the precedented
alternative — call it **(A′) manual superuser application** (corrected below).

**(A) is worse than "a broader blast radius" — adversarial review named concrete failure
modes this spec had not enumerated, and they change (A) from a bounded-window trick into an
operationally live hazard**, none of them requiring anything to go wrong beyond ordinary
concurrent traffic:

- The grant elevates the *live application role* — every runtime request-handling session,
  not just the migration process, inherits `visa_ledger_owner`'s privileges over every
  ledger-owned object for the length of the window, not only the one function 304 needs.
- A session that has already run `SET ROLE visa_ledger_owner` before the `REVOKE` commits is
  not neutralized by the revoke: PostgreSQL does not force a running session back off a role
  it already switched into. That session must be individually reset or terminated, and
  nothing in this repo's runtime currently enumerates or does that.
- Objects created, altered, or granted while a session holds the elevated role survive the
  revoke — a persistent side effect from what was meant to be a transient window.
- `backend_rag_v2` acquiring `SET ROLE` ability at all depends on the membership carrying the
  `SET` option (and automatic inheritance separately on `INHERIT`) — a plain `GRANT ROLE`
  without specifying these does not necessarily grant what (A) assumes it grants.
- **The migration runner does not treat the pending batch as one transaction**
  (`migration_manager.py::_apply_all_pending_locked`, verified by reading the loop at
  lines 507-528): each pending migration gets its own `try`/`except`, and a failure is
  appended to a `failed` list — the `for` loop continues to the *next* migration_info
  regardless. So if 304 is not the only pending migration at merge time, other migrations can
  commit while the elevated membership is still live, extending the exposure window in a way
  the "REVOKE immediately after verification" framing does not account for.
- Revoke timing is exact and easy to get wrong in both directions: revoking before the
  *new* image's `release_command` actually reaches 304 reproduces the RAISE EXCEPTION failure
  this spec already describes (304 only exists in the new image, so an old-image pre-deploy
  revoke is simply too early); revoking too late leaves the window open longer than intended.
- The one existing advisory lock in the runner (`_APPLY_ALL_LOCK_ID`, `migration_manager.py`)
  serializes concurrent *migration runs* against each other — it does nothing to prevent
  ordinary application traffic from using the elevated role while the grant is active.
- A revoke that fails or is forgotten converts a "temporary" workaround into a permanent
  least-privilege regression on `backend_rag_v2` — silently, unless something checks for it.

Minimum controls a real implementation of (A) would need, none of which exist today: 304
must be the sole pending migration at grant time; the grant must specify `WITH SET` (and
confirm `INHERIT` as needed) rather than a bare `GRANT ROLE`; `visa_ledger_owner`'s `CREATE`
privilege on `public` must be confirmed before the grant is trusted to work at all (see the
correction on Requirement 3 above); the grant should be issued as close as possible to the
actual `release_command` invocation, not at an arbitrary point in the deploy window; the
revoke must be followed by an explicit sweep for sessions that already ran `SET ROLE` and
still hold it; and the revoke's success must itself be verified, not assumed. Adversarial
review's own conclusion: "a dedicated migration role would be substantially cleaner than
elevating the runtime role" — worth naming as a fourth option a future revision of this spec
could specify, not something this one adopts, since inventing the mechanism is exactly the
kind of decision this spec has deliberately left to the codeowner.

Also note (A) and (A′) below are not the *permanent* membership already rejected under "Why
the obvious repairs do not work" above (which was rejected as an indefinite workaround for
the enum specifically): both here are meant to be bounded and verified, not indefinite — the
earlier rejection does not settle either of these on its own, and the danger list above is
about how hard "bounded and verified" actually is to make true, not a claim that bounded
membership is as bad as permanent membership.

**(A′) manual superuser application, corrected.** The operator runs 304's full SQL directly
against production over a superuser connection, before the automated `fly-deploy.yml` release
path ever attempts it. **This spec previously claimed "the migration-tracking table records
it as applied so the automated runner skips it on merge" — that claim is FALSE, found by
adversarial review and confirmed by reading the runner: both tracking tables
(`schema_migrations`, read by `BaseMigration._is_applied`, and `_schema_versions`, read by
`MigrationManager.get_applied_migrations`) are written by `BaseMigration._log_migration`
(`migration_base.py:521-585`), a Python method invoked from inside `BaseMigration.apply()`'s
own transaction (`:665-701`) — migration 304's own SQL file never touches either table.**
Running `psql -f 304_garuda_documents.sql` against a superuser connection applies the DDL and
leaves BOTH ledgers exactly as they were: 304 still reads as pending, so the very next
`apply_all_pending()` (i.e. the next `release_command`) tries it again — and fails immediately
on the bare `CREATE TABLE public.garuda_documents` (no `IF NOT EXISTS`; only the two `DO`
blocks in 304 are catalog-guarded) with a duplicate-object error, aborting that release the
same way 281/285 originally aborted production. (A′) as a bare "run the file by hand" is
therefore not a fix at all unless something ALSO writes the two ledger rows — and a
hand-fabricated `INSERT INTO schema_migrations / _schema_versions` reintroduces exactly the
provenance risk the spec's own migration-299 checksum/`applied_via`/`applied_as` columns
exist to prevent (see `migration_base.py`'s provenance helpers).

A second defect, independent of the ledger one: applying the **entire** migration file as
superuser makes every object it creates superuser-owned by default *except* the one function
304's own `DO $garuda_304_owner_transfer$` block explicitly transfers — that is, both new
tables (`garuda_documents`, `garuda_document_review_fields`) and the other two functions
(`active_garuda_document_policy_available`, `guard_garuda_document_mutation`) would end up
owned by the superuser, not `backend_rag_v2`. In normal operation these are owned by
`backend_rag_v2` implicitly, because that is the role that runs the migration — 304 contains
no explicit `GRANT` to `backend_rag_v2` on any of them because it has never needed one. Under
(A′) as a bare superuser apply, runtime code's `SELECT`/`INSERT` against these tables
(`postgres_store.py`) would fail on ordinary permission grounds the day this ships, a defect
this spec did not previously name.

**A properly specified (A′)** — the shape adversarial review recommends in place of either
the bare-`psql` variant above or a bare superuser DSN through the Python runner (which fixes
the ledger problem but not the ownership one) — would need, inside one superuser transaction:
(1) `SET LOCAL ROLE backend_rag_v2` for the ordinary `CREATE TABLE`/`CREATE FUNCTION`
statements, so those objects are owned the same way they would be under a normal deploy;
(2) `RESET ROLE` (back to the privileged connection) for the one `ALTER FUNCTION ... OWNER
TO` transfer; (3) assertion of every final owner and privilege against the catalog before
committing; and (4) driving the whole thing through `BaseMigration.apply()` (with
`settings.database_url` pointed at the superuser DSN for this one invocation) rather than raw
`psql`, so `_log_migration` still runs and both ledgers are written atomically with the DDL.
That is no longer "apply the migration file exactly as committed" — it is a distinct,
operator-sensitive procedure this spec has not fully written out, and it would need its own
proof before being trusted as a fixed recipe rather than a sketch.

**(C) Split forward.** 304 creates `garuda_documents` and `garuda_document_review_fields`
without the ownership transfer and without the trigger depending on it — ship the tables
now, bind the retention policy in a follow-up migration once requirement 3 is closed by
whichever means. No escalation of any kind. Cost, stated honestly: a declared window, from
this migration's merge to the follow-up, in which `postgres_store.py::commit()` has no
active `GARUDA_DOCUMENT` policy to bind against. The module's own docstring already names
`PERSISTENCE_POLICY_UNAVAILABLE` as the fail-closed behavior when no policy is active for a
scope; for the length of the window that extends to "no scope wired at all," so document
intake answers a clean 5xx on every write rather than persisting an unretained row — no
data-integrity risk, a functional gap instead. How long that window is acceptable depends
on how soon requirement 3 is actually closed, which this spec cannot settle either.

A third option was considered — raised by the gate during round 2/3 — and rejected here:
**changing what the trigger function requires**, i.e. dropping `SECURITY DEFINER` from
`bind_garuda_document_retention_policy()` so it runs as the caller (`backend_rag_v2`)
instead of the table owner, which needs no ownership transfer at all. Rejected by the
session on one ground: it would leave this seventh surface on a different privilege model
from the six that already exist, and two coexisting models for how a
`visa_decision_retention_policies`-adjacent trigger acquires its lock is worse than the
problem it removes — the next author has to know which model applies to which table before
writing a guard, an ownership audit, or a guilt/innocence test pair. Kept here for the
record, not as a live third option.

## A guard that cannot see this: guard-over-match on `END IF` (scar family #3)

`test_post_d1_migrations_guard_ledger_owned_ddl.py` is the repo's antidote for exactly this
failure class — a DDL statement against a ledger-owned object the app role cannot execute.
Its rule for exempting a `DO` block from scanning is `_HAS_CONDITIONAL = re.compile(r"\bEND
\s+IF\b", re.IGNORECASE)` (`:236`), applied at `:396` for table ALTERs
(`find_unguarded_alters`) and `:975` for function DDL (`find_unguarded_function_ddl`): *any*
`END IF` anywhere in a `DO` body exempts the whole block from every finding, independent of
what the condition actually tests. The guard's own comment (`:229-234`) names this as a
deliberate, known limit — "a body carrying an unrelated `IF ... END IF` plus an
unconditional ALTER still passes... written down because a limit on paper can be closed
later" — citing 285's rollback `DROP CONSTRAINT` as the first live instance. 304 supplies a
second, and a cleaner one, because the same file shows both the correct case and the false
one side by side:

- `304`'s `DO $garuda_304_owner_transfer$` (lines 266-304) genuinely tests the thing an
  ownership guard needs to test — `pg_get_userbyid(proowner)` against `ledger_owner` — before
  attempting the `ALTER FUNCTION ... OWNER TO` at line 289. This is the shape the exemption
  exists *for*.
- `304`'s rollback, `DO $garuda_304_narrow_policy_scope$` (lines 373-388), reads `IF EXISTS
  (SELECT 1 FROM ... WHERE policy_scope = 'GARUDA_DOCUMENT') ... ELSE <unconditional ALTER
  TABLE DROP CONSTRAINT / ADD CONSTRAINT> END IF` (lines 375-386). Its conditional tests
  whether a row exists — never who owns `visa_decision_retention_policies` — and the `ALTER
  TABLE` in the `ELSE` branch runs exactly when that is false, with no ownership check
  anywhere on that path. Because the block contains `END IF` at all, `_HAS_CONDITIONAL`
  matches and `find_unguarded_alters` never scans it — even though the scanner does reach
  rollback sections in general (that is why `FUNCTION_GRANDFATHERED` exists at all: both its
  entries, 281 and 286, are rollback-section findings, `:889-905`). The blindness here is
  the exemption's coarseness, not the scanner's reach.

The practical consequence is narrow but real: rolling back 304 against a database where
`backend_rag_v2` does not own `visa_decision_retention_policies` and no `GARUDA_DOCUMENT`
row has ever been inserted hits the exact "must be owner of table" failure that started
this whole class on 2026-08-26 — and the guard built specifically to catch that failure
shape says nothing about it, for a reason unrelated to whether the rollback path is
actually safe.

**Acceptance criterion for fixing this** (guard-conformance rule: a guard needs a guilt case
and an innocence case on the entity/intent it actually claims to test, never a bare
substring/shape proxy):

- **Guilt case**: a `DO` block containing `END IF` whose conditional does not read the
  ownership catalog (`pg_proc` / `pg_roles` / `pg_get_userbyid` / `pg_has_role`) — row
  existence, like 304's rollback, is the concrete example on file — wrapped around an
  unconditional `ALTER TABLE` or `ALTER FUNCTION ... OWNER TO` against a
  `NON_APP_OWNED_TABLES` / `NON_APP_OWNED_FUNCTIONS` target must FAIL the guard.
- **Innocence case**: a `DO` block whose conditional does read the ownership catalog before
  attempting the ALTER — 304's own `$garuda_304_owner_transfer$`, or 289's `pg_has_role`
  pre-check — must continue to PASS.

The distinction the current regex cannot draw is exactly the one that separates these two
cases: not "is there a conditional anywhere in this body" but "does the conditional test the
thing the ALTER needs to be safe."

## The missing proof: first application as the real role

The 11/11-green integration suite cited in round 1 (`test_postgres_store.py`) proves 304's
schema and store logic once the schema already exists — it applies the forward migration
through `_ADMIN_URL`, which that fixture itself requires to be a superuser connection. It
never exercises the one path that actually failed in production on 2026-08-26: the
migration applied by the real, low-privilege migration-runner role while
`visa_ledger_owner` exists and holds no membership from it. A test that would actually
prove first-application safety needs to create both roles with production's real privilege
split (SELECT-only for the app role, full ownership for the ledger role), apply the
migration as the app role with no membership grant in place, and assert on the *specific*
failure the current code produces — a `RAISE EXCEPTION` naming the still-wrong owner
(line 299-301), not a generic Postgres `insufficient_privilege` — so a future regression
that turns this explicit message back into an opaque failure is caught too. No such test
exists today under any name in `apps/backend-rag/backend/tests/`.

## Acceptance, if this is built

This list covers requirement 1 (the enum CHECK) only — it was written before the round-2/3
findings above, and requirements 2 (the REFERENCES grant) and 3 (trigger-function
ownership) need their own acceptance criteria, not these four items. Requirement 2 has no
open acceptance criterion yet — a single `GRANT` is not a class the way the enum is.
Requirement 3's are the guard-conformance guilt/innocence pair and the missing first-
application test, both specified above; deliberately, this spec does not turn "which of
option A or C" into an acceptance criterion, since that choice is the codeowner's.

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
5. Added by adversarial review: either the standing `GRANT INSERT` on
   `visa_retention_policy_scopes` is scoped narrower than the bare runtime role (a dedicated
   migration role, or a `SECURITY DEFINER` registration function `backend_rag_v2` may call
   but not the table directly), or the integrity-guarantee claim in "The repair that removes
   the class" is rewritten to state the weaker, honest shape ("rejects unregistered scopes,
   does not prevent an application-role write from registering a new one") rather than the
   stronger claim made today.

## Adversarial review

Seat: **codex**, model `gpt-5.6-sol` at `model_reasoning_effort=xhigh`, `--sandbox
read-only`, invoked 2026-09-02 against this file at branch sha `57e745cc47`. **Verdict:
BLOCK** — not softened here; the review named concrete, checkable defects in both named
options for closing requirement 3, and this section records what was verified against the
actual migration files (`304_garuda_documents.sql`, `301_garuda_magic_link_binding_owner.sql`)
and the migration runner (`migration_base.py`, `migration_manager.py`) rather than accepted on
the reviewer's word.

**Confirmed and folded into the text above:**

- The `ALTER FUNCTION ... OWNER TO` precondition is incomplete as stated — role membership
  alone is not sufficient; the session also needs the membership's `SET` option and the new
  owner needs `CREATE` on the target schema. Folded into the Requirement 3 table row.
- `304`'s `RAISE EXCEPTION` at line 299 is conditional (role exists, function resolves,
  transfer still hasn't landed), not unconditional. Folded into the same row. The exact
  phrase "RAISEs unconditionally" that the review corrects does not appear verbatim anywhere
  in this spec at the reviewed sha — it is not clear what text the reviewer was quoting from,
  and this is named here rather than silently accepted, per this repo's anti-hallucination
  discipline. The underlying substance (the raise is conditional) is independently confirmed
  by reading `304_garuda_documents.sql:266-304` directly, so the correction is folded in on
  its own merits, not on trust in the quote.
- Temporary role membership (Option A) elevates the *live application role*, not merely the
  migration process — `backend_rag_v2` is the same role runtime request-handling code uses
  (this spec's own "disease" section already says so). Confirmed and folded in as the
  danger-list under Option A.
- A revoked `SET ROLE` does not retroactively neutralize a session that already switched into
  the elevated role; the membership's `SET`/`INHERIT` options are distinct and both matter.
  Standard PostgreSQL role-membership semantics (this repo runs Postgres 17.7), folded in.
- The migration runner does **not** treat the pending batch as one transaction and does
  **not** stop on a single migration's failure — verified by reading
  `migration_manager.py::_apply_all_pending_locked` (`:507-528`): the `for` loop over
  `pending` migrations wraps each `apply_migration` call in its own `try`/`except`, appends
  failures to a list, and continues to the next migration regardless. Confirmed, folded into
  Option A's danger list.
- The advisory lock (`_APPLY_ALL_LOCK_ID`, `migration_manager.py`) serializes concurrent
  migration *runs* only — it does nothing to stop ordinary application sessions from using an
  elevated role. Confirmed by reading the lock's scope (acquired on one dedicated connection
  around `_apply_all_pending_locked` only) and folded in.
- Option A′ ("manual superuser application") as this spec previously described it was
  **factually wrong**, not merely risky: the claim that "the migration-tracking table records
  it as applied so the automated runner skips it on merge" is false. Both migration ledgers
  (`schema_migrations`, `_schema_versions`) are written by `BaseMigration._log_migration`, a
  Python method called from inside `BaseMigration.apply()`'s own transaction
  (`migration_base.py:521-701`) — migration 304's SQL file itself never touches either table.
  Running the file via raw `psql` leaves both ledgers unchanged, so the very next automated
  `release_command` would try 304 again and fail on the bare (non-catalog-guarded)
  `CREATE TABLE public.garuda_documents`. This is the most consequential finding in the
  review: it directly contradicts a claim this spec made with confidence, and it is corrected
  in place above rather than left standing next to the correction.
- Applying the whole migration as superuser leaves every object it creates
  superuser-owned except the one function 304 explicitly transfers — both new tables and the
  other two functions would end up owned by the wrong role, breaking runtime
  `SELECT`/`INSERT` the moment traffic hits them, since 304 contains no explicit `GRANT` to
  `backend_rag_v2` (it has never needed one — normal application means `backend_rag_v2` is
  the creating role by default). Confirmed by reading 304's DDL in full (two `CREATE TABLE`,
  three `CREATE FUNCTION`, one explicit `OWNER TO`) and folded in as a second, independent
  defect in the bare-(A′) shape.
- The `visa_ledger_owner`-absent branch (`304_garuda_documents.sql:273-277`) `RETURN`s early
  rather than enforcing the owner postcondition, so a database lacking that role would record
  304 as cleanly applied with the trigger function still owned by `backend_rag_v2`. Confirmed
  by reading the branch; folded into the Requirement 3 row as a fourth, currently-dormant
  branch. Every environment this repo runs today has the role, so this is a latent gap, not a
  live one — stated exactly that way rather than escalated.
- The lookup-table repair's standing `GRANT INSERT` on `visa_retention_policy_scopes` weakens
  the stated integrity guarantee: a compromised `backend_rag_v2` could register a new scope
  and then reference it, which the CHECK design structurally prevented. Confirmed as a real
  design gap (the FK still rejects an *unregistered* scope, so the finding narrows rather than
  voids the repair's value) and folded into that section's cost paragraph plus a fifth
  acceptance criterion above.

**Accepted as a well-founded recommendation, not adopted as this spec's choice:** the
review's proposed "properly specified (A′)" (`SET LOCAL ROLE` for ordinary object creation,
`RESET ROLE` for the transfer, catalog assertion, driven through the Python runner so both
ledgers are written) is folded in above as a sketch of what a correct (A′) would need — it is
not fully specified here and this spec does not adopt it as the answer, consistent with
leaving the A/A′/C choice to the codeowner. Likewise "a dedicated migration role would be
substantially cleaner than elevating the runtime role" is recorded as a fourth option a
future revision could specify, not adopted here.

**Not independently verified (outside what this session can check from a read-only repo
checkout):** whether `visa_ledger_owner` currently holds `CREATE` on `public` in the live
production database. The review treats this as a precondition to prove before trusting either
option, not as an assertion that it is currently false, and this spec keeps it in that form —
naming it as a gap in the evidence, not manufacturing a verdict this session has no DB access
to support.

**No findings were rejected.** Every substantive finding in the review's four numbered
sections was either independently confirmed against the actual files (above) or is a
recommendation this spec explicitly declines to adopt while still recording it. The one
imprecision found in the review itself — attributing the phrase "RAISEs unconditionally" to
this spec when that exact phrase does not appear in it — does not change any disposition
above, since the substance behind it is independently true.

## Until then

Corrected 2026-09-02, after three rounds of adversarial gate on #5526: the paragraph this
replaces predicted a single temporary-grant application of 304 followed by a
`GRANDFATHERED` entry. Neither happened, and the reason why is itself part of the record.

**Requirements 1 and 2 are done, and done differently than predicted.** Not by applying
304 itself under a temporary grant, but by the codeowner establishing the target state
directly over a superuser `psql` session — widen the CHECK, `GRANT REFERENCES` — verified
read-only by the session afterward against `pg_get_constraintdef` and
`has_table_privilege` (2026-09-01T22:05:43Z; before/after values recorded in "three
requirements, not one" above). Because 304's own catalog guard for the CHECK reads the
constraint definition before touching it, this out-of-band preparation makes 304's forward
section a no-op for requirement 1 the moment the migration runs. It is also why **304 is
not going into `GRANDFATHERED`**: that list exists to excuse a bare, ungated ALTER the
static guard cannot help but convict — 281's and 285's shape. 304's ALTER is gated, the
static guard passes on its own once the CHECK is pre-widened, and adding an unneeded entry
would misrepresent 304 as the same shape as its two predecessors when it deliberately is
not.

**Requirement 3 is not done, and #5526 does not merge while it is not**: on this repo the
merge IS the deploy, so an armed PR would apply the migration before any privileged step
could run, reproducing 2026-08-26 a third time — precisely what round 2 refused to let
through on a PASS-WITH-CONDITIONS. Closing it needs a codeowner decision between the two
options above (temporary membership, or a split-forward migration), made and executed
*before* the merge, per "the apply protocol." Until that decision is made, #5526 is
suspended per Agent PR Contract rule 8 — not retried a fourth time on the same cause, and
not merged on an assumption about which option will be chosen.

**Updated 2026-09-02, after the cross-family adversarial review above (verdict BLOCK):**
neither named option is ready to execute as originally specified. (A) needs its minimum
controls list satisfied (sole-pending-migration, `SET`/`INHERIT` confirmed, a session sweep
after revoke) before "temporary membership" is actually temporary in practice, not just in
intent. (A′) needs the ledger-population defect fixed — the bare "run the file by hand"
shape this spec described does not, on its own, stop the automated runner from retrying 304
and failing — so any execution of (A′) must go through a corrected procedure (drive
`BaseMigration.apply()` itself against a privileged DSN with `SET LOCAL ROLE` scoping
ordinary object creation, per the review's sketch above), not the plain superuser `psql`
session this spec originally described. (C) is unaffected by the review's findings, since it
avoids the privileged-transfer question entirely by deferring it. The codeowner decision this
section already calls for is therefore now a decision among a corrected (A), a corrected
(A′), or (C) — not among the three options as this spec first wrote them.
