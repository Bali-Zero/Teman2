# Practice timeline semantics — the spec that was missing (v1, 2026-08-27)

> **Why this file exists.** PR #5072 (create `practice_status_log`, repoint the client tracker at
> it) went through **three adversarial review rounds and was rejected three times**. Round 1 and 2
> findings were real and were fixed. Round 3 rejected the _fixes_. At that point the Agent PR
> Contract rule 8 applies verbatim — _"a fix-of-a-fix chain stops at depth 1: if the correction is
> itself wrong, the surface is under-specified — write the spec, do not open the third PR."_
>
> This is that spec. Every remaining blocker resolves to **a product question nobody has ever
> written an answer to**, and the code has been guessing a different answer in each of its two
> execution paths. No amount of further review closes that; only a decision does.
>
> PR #5072 is SUSPENDED, branch alive: `agent/air-m5/ops/practice-status-log-0827`.

## The ground truth, measured 2026-08-27 against production

Every number below was read from the production database this turn, not inferred.

| Fact                          | Value                                                                                                            | Consequence                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `practices` rows              | 893                                                                                                              |                                                                              |
| `practices.status` type       | `character varying(50)`, **NULLABLE**                                                                            | audit columns at `VARCHAR(64)` are WIDER — the trigger cannot abort on width |
| rows with `status IS NULL`    | **0**                                                                                                            | the NULL crash is **LATENT, not live**                                       |
| distinct live statuses        | `completed` 669 · `cancelled` 124 · `on_process` 68 · `sending_invoice` 17 · `inquiry` 8 · `waiting_documents` 7 | all six are inside the frontend enum                                         |
| `practice_status_log` in prod | **does not exist**                                                                                               | 100% of traffic runs the fallback path today                                 |

**A correction this spec exists to record.** An earlier session statement said the NULL crash was
"already live in production today". That is **false**: zero rows carry a NULL status. The path is
_reachable_ — the column is nullable and carries no CHECK constraint — but nothing exercises it.
The distinction changes the priority from incident to hygiene, which is why it is written here
rather than quietly corrected.

## The frontend contract is CLOSED, and the backend does not know it

`apps/mouth/src/lib/schemas/process.ts` declares `ProcessStepState` as a **`z.enum`** — a closed
set — and both `ProcessStep.status` and `ProcessTimelineData.current_status` are non-nullable
members of it. So:

- a `null` status → Zod rejects the **entire response** → the portal renders
  _"Unable to load the timeline"_;
- any status outside the enum → same outcome.

This is the finding that makes the round-2 fix insufficient rather than wrong. Making
`_status_label()` NULL-safe stops the backend raising `AttributeError`, but the user sees the same
broken screen, because the failure simply moves from a 500 to a schema rejection. **A backend-only
NULL fix cannot succeed**; the contract has to be settled at both ends or the column has to stop
being nullable.

---

## The four open questions

Each is a decision, not a bug. Each names who can answer and what changes once it is answered.

### Q1 — What does a NULL `practices.status` MEAN?

Three coherent answers exist and the codebase currently implies all three at once:

1. **It is impossible** → then say so in the schema: `SET NOT NULL` with a backfill, or a CHECK
   against the known vocabulary. The frontend enum becomes honest, and the whole NULL branch (and
   its tests) disappears from the reader.
2. **It means "not yet classified"** → then it needs a name in the enum (`unknown`), on both sides,
   and a label. The reader stops special-casing and the client stops rejecting.
3. **It is a data defect to be surfaced** → then the endpoint should fail loudly for staff and
   degrade for clients, which is a different shape than either path has today.

**Recommendation: (1).** Zero rows use it, the frontend already refuses it, and a nullable status
column with no CHECK is what let four surfaces be typed against a vocabulary the database never
enforced. **Owner: `operator[business]`** — it is a product statement about what a practice is.

### Q2 — Is a CANCELLED practice "completed"?

This is the one that touches real rows today: **124 of 893**.

The two paths already disagree, and the disagreement is currently invisible only because the
history path never runs:

| Path                  | `cancelled` renders as                                                             |
| --------------------- | ---------------------------------------------------------------------------------- |
| fallback (live today) | `completed=false, is_current=false` → a grey empty circle: neither done nor active |
| history (after 289)   | `completed=true, is_current=false` → a **green checkmark**                         |

Applying migration 289 would silently flip 124 client-visible practices from "grey" to "green
tick". Neither is obviously right: a cancelled practice is _finished_ but not _achieved_, and the
step model only has two booleans to say so. The honest fix is probably a third state
(`terminal_unsuccessful`) rather than forcing `cancelled` into `completed`.

**Owner: `operator[business]`** — what a client should see when their case was cancelled.

### Q3 — Should the timeline show where a practice STARTED?

The trigger is `AFTER UPDATE OF status` only. A practice's **first** status — the one set at
INSERT — is never recorded. So after the first transition the timeline shows only the destination,
and the starting point is gone.

The migration already captures `old_status`, and the reader already **selects it and then ignores
it** (`portal_process_timeline.py:119` is the only occurrence in the file). So the data to answer
this is being written and thrown away.

Three options: synthesise the baseline from the first row's `old_status`; add an `AFTER INSERT`
arm to the trigger; or declare that the timeline starts at the first _transition_ and drop the
`old_status` column from the query so the code stops implying otherwise.

**Owner: session**, once Q2 is answered — it is a modelling choice, not a business one. Note the
SQL comment at `289_practice_status_log.sql:75` is **wrong as written**: for a pre-existing
practice the trigger records `OLD.status`, not `NULL`.

### Q4 — Ordering and snapshot

Two smaller defects, both real, both cheap, both blocked behind the above because they change the
same lines:

- `ORDER BY changed_at ASC` alone is **non-deterministic on ties**. With `clock_timestamp()` ties
  are unlikely but not impossible, and any row written before the `DEFAULT` converged carries
  transaction-start time, where ties are ordinary. Needs `ORDER BY changed_at, id`.
- The current status and the history are read in **two separate statements with no shared
  snapshot**. A commit in between yields a payload whose `current_status` matches no step, and the
  reader then marks every step complete and none current.

**Owner: session.** No decision required — these are corrections, and they land with whatever
shape Q1–Q3 settle on.

---

## One defect that belongs to nobody here: the migration runner

Independently verified at the cited lines, and **out of scope for any migration PR** because it is
a property of the runner:

- rollback deletes from **`_schema_versions`** (`backend/db/migration_manager.py:257`)
- the applied-check reads **`schema_migrations`** (`backend/db/migration_base.py:365`)

They ARE reachable from the same run, and it is one chain, not two runners that never meet:
`apply_all_pending()` filters pending work using `_schema_versions`, then constructs a
`BaseMigration` whose own `apply()` guard consults `schema_migrations`. A successful apply INSERTs
into **both**. So a rollback deletes the `_schema_versions` row, the next apply finds the surviving
`schema_migrations` row, **skips the SQL entirely**, and silently re-inserts the row it had
deleted: the objects are gone and both ledgers report success.

**This is not a new discovery, and that is the part that matters.** The repo already knows:

- `migrations_v2/277_correct_ari_email_typo.sql` documents this defect **verbatim** in its own
  rollback section — _"a rollback that only clears `_schema_versions` … leaves the runner believing
  277 is still applied"_ — and closes it with an explicit `DELETE FROM schema_migrations`.
- `165_reconcile_schema_migrations_duplicates.sql` and `278_reassign_orphaned_clients_setup_team.sql`
  do the same.
- `schema_audit.py` was built to detect the two ledgers diverging, and its own header calls them
  _"two tables in flight … during the migration-runner consolidation"_.

So the workaround exists, is documented, and is applied by **3 migrations out of 171** — which
means **168 are not re-runnable after a rollback**, and nothing tells you which. Each new migration
is expected to rediscover this and hand-patch its own rollback.

That is the real finding, and it is bigger than this PR: it wants a fix in the **runner** (one
ledger, or the rollback clearing both), plus a test that drives apply → rollback → apply and
asserts the objects exist at the end — never a 171st hand-patched rollback.

**Blocked on M5, recorded not circumvented.** Adding the 277-style two-line workaround to 289 was
attempted and **refused by the guardrails static fallback** (`SQL destructive introduced in Edit`)
— the tier-1 daemon is absent on this machine, so the fallback blocks all DML in a migration file
without being able to judge that these two DELETEs target the migration's own ledger rows inside a
rollback section. The block is correct behaviour for a machine that cannot make the finer call, and
was not routed around. Owner: `operator[control-plane]`.

## What is NOT wrong (recorded so it is not re-litigated)

- **`VARCHAR(64)` is safe.** A round-3 finding claimed the audit columns could abort an UPDATE by
  being too narrow, citing a QA fixture that permits 100 characters. Production's
  `practices.status` is `varchar(50)` — narrower than 64. The reviewer flagged that it could not
  reach production; the measurement above closes it. It is still worth deriving the audit width
  from the source width rather than leaving the margin to coincidence.
- **`TERMINAL_STATUSES` is complete** against the six statuses production actually holds.
- **The exception ORDER is correct** — `UndefinedTableError` is a subclass of `PostgresError`, so
  the narrow handler must come first, and it does.

## Definition of done for the resumed PR

1. Q1 and Q2 answered by the owner; Q3 chosen; Q4 folded in.
2. `asyncpg.InterfaceError` no longer escapes the reader (fixed on the branch — see below).
3. Both execution paths give the **same answer for the same practice**, proven by a test that runs
   one practice through both and asserts the payloads are equal.
4. A test that asserts the backend can never emit a status the frontend enum rejects — the
   contract, not just the code.
