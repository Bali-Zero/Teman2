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

Every number below was read from the production database on 2026-08-27, not inferred — and they
are a SNAPSHOT, not a constant. Re-measured 2026-09-11: **1011** practices, **137** cancelled,
still **0** with a NULL status, and `practice_status_log` still absent. Any statement about how
many timelines a deploy changes must be re-measured at arming time; the table below is kept at its
original date rather than silently rewritten.

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
| history (after 310)   | `completed=true, is_current=false` → a **green checkmark**                         |

Applying migration 310 would silently flip 124 client-visible practices from "grey" to "green
tick". Neither is obviously right: a cancelled practice is _finished_ but not _achieved_, and the
step model only has two booleans to say so. The honest fix is probably a third state
(`terminal_unsuccessful`) rather than forcing `cancelled` into `completed`.

**Owner: `operator[business]`** — what a client should see when their case was cancelled.

> ⚡ **ANSWERED 2026-09-11 (Zero, M5, asked with the two renderings side by side): a cancelled
> practice is a step that is CLOSED but did not SUCCEED.** `completed=true, is_current=false` —
> nothing is still running, so the client sees no spinner — and it is NOT confused with a
> successful practice because the client colours the step by its STATUS, not by its booleans:
> `apps/mouth/src/components/portal/process/stateColors.ts` already maps `cancelled` to `danger`.
> So the third state this section proposed is not needed: the status field IS the third state, and
> the two booleans only say "closed" and "not running".
>
> This resolves the disagreement in the direction of the history path, which means the cancelled rows do
> change rendering — from a grey empty circle to a filled `danger` marker. That is the intended
> outcome: a cancelled practice reading as "neither done nor active" was the less honest of the two.
> Both paths now compute the pair in `_step_flags()`, and
> `test_both_paths_answer_identically_for_the_same_status` runs one practice through both for every
> terminal status. Removing the helper turns it red on `cancelled` specifically — verified.

### Q3 — Should the timeline show where a practice STARTED?

The trigger is `AFTER UPDATE OF status` only. A practice's **first** status — the one set at
INSERT — is never recorded. So after the first transition the timeline shows only the destination,
and the starting point is gone.

The migration already captures `old_status`, and the reader already **selects it and then ignores
it** (`portal_process_timeline.py:146`, still the only occurrence in the file). So the data to answer
this is being written and thrown away.

Three options: synthesise the baseline from the first row's `old_status`; add an `AFTER INSERT`
arm to the trigger; or declare that the timeline starts at the first _transition_ and drop the
`old_status` column from the query so the code stops implying otherwise.

**Owner: session**, once Q2 is answered — it is a modelling choice, not a business one. Note the
SQL comment on `old_status` was **wrong as written** — for a pre-existing practice the trigger
records `OLD.status`, not `NULL` — and was CORRECTED in this same diff
(`310_practice_status_log.sql:79`, reworded to "NULL only when the PREVIOUS status was itself
NULL"). Kept here because the modelling choice above still stands on its own.

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

## One defect that belonged to nobody here: the migration runner — SINCE FIXED

> ⚡ **STALE AS WRITTEN, corrected 2026-09-11 after a council seat re-measured it.** Everything from
> here to "What is NOT wrong" described the runner as it stood when this spec was drafted. It no
> longer stands: `rollback_migration` (`backend/db/migration_manager.py:318-404`) deletes from
> **BOTH** ledgers inside the rollback transaction, and says so in its own comment — _"Remove from
> BOTH ledgers"_. The cited line numbers were also off: `_is_applied` is at
> `backend/db/migration_base.py:644-648`, not `:365`.
>
> The consequence for THIS PR: 310's three-DROP rollback is correct as written and needs no
> 277-style hand-patch, so the "Blocked on M5" paragraph below is moot — there is nothing left to
> add to it. The text is kept rather than deleted because the reasoning is still the clearest
> record of WHY the two-ledger shape was dangerous, and because a reader meeting a pre-2026-09-01
> database still needs it.

The original finding, as written then — out of scope for any migration PR because it is a property
of the runner:

- rollback deleted from **`_schema_versions`** only
- the applied-check reads **`schema_migrations`**

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

So the workaround existed, was documented, and was applied by a handful of migrations — the rest
were not re-runnable after a rollback, and nothing told you which. The runner fix removed the need
for it; the hand-patches that remain are harmless. Each new migration
is expected to rediscover this and hand-patch its own rollback.

That is the real finding, and it is bigger than this PR: it wants a fix in the **runner** (one
ledger, or the rollback clearing both), plus a test that drives apply → rollback → apply and
asserts the objects exist at the end — never a 171st hand-patched rollback.

**Blocked on M5, recorded not circumvented.** Adding the 277-style two-line workaround to 310 was
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
   — **Q2 ANSWERED 2026-09-11** (above). Q1 remains open and is the reason item 4 is still open.
2. `asyncpg.InterfaceError` no longer escapes the reader (fixed on the branch — see below).
3. Both execution paths give the **same answer for the same practice**, proven by a test that runs
   one practice through both and asserts the payloads are equal.
   — **DONE**: `test_both_paths_answer_identically_for_the_same_status`, parametrised over
   `completed`/`approved`/`cancelled`/`on_process`. Guilt proven: reverting `_step_flags()` turns it
   red on `cancelled` with both renderings printed in the failure message.
4. A test that asserts the backend can never emit a status the frontend enum rejects — the
   contract, not just the code.
   — **STILL OPEN, and deliberately so.** The backend can still emit `"status": null`, which the
   closed `z.enum` in `apps/mouth/src/lib/schemas/process.ts` rejects wholesale. Closing it needs a
   value on BOTH sides of the contract (`unknown` in the enum, or `SET NOT NULL` + backfill — 0 rows
   measured 2026-08-27), i.e. Q1. Both seats of the 2026-09-11 council flagged it; it is recorded
   here rather than half-fixed in the router.
