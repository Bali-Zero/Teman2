# Step 5 — the privilege decision, measured (2026-09-02)

> One question for the codeowner, with the costs measured first. This closes the "measure before
> asking" instruction in `NEXT-SESSION.md` §Step 5. The spec that frames the problem is
> `research/operations/2026-09-02-retention-policy-scope-enum-cross-owner-ddl.md` (PR #5548, merged
> 2026-09-01 23:45Z). Nothing below was recalled: every value was read from production or from the
> tree in the session that wrote this file.

## What blocks #5526, in one sentence

Migration `304_garuda_documents.sql` must end with
`ALTER FUNCTION bind_garuda_document_retention_policy() OWNER TO visa_ledger_owner`, and the role
that runs every migration in production cannot perform that statement.

## Production, read-only, 2026-09-02 (via `scripts/pg.sh`, role `nuzantara_readonly`)

| measurement                                                          | value                                                                                                                 |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| roles matching `%migrat%` / `%ddl%`                                  | **none** — no migration role exists                                                                                   |
| `backend_rag_v2`                                                     | login=true, super=false                                                                                               |
| `visa_ledger_owner`                                                  | login=false, super=false                                                                                              |
| `pg_has_role('backend_rag_v2','visa_ledger_owner','MEMBER')`         | false                                                                                                                 |
| `has_schema_privilege('visa_ledger_owner','public','CREATE')`        | **true** (the "new owner needs CREATE on the schema" precondition is already met)                                     |
| `has_schema_privilege('backend_rag_v2','public','CREATE')`           | true                                                                                                                  |
| owner of every `garuda_*` table (15 tables)                          | `backend_rag_v2`, all of them                                                                                         |
| functions owned by `visa_ledger_owner`                               | 27                                                                                                                    |
| `pg_default_acl` rows                                                | 4 — only read grants to `nuzantara_readonly` (from `repmgr` and `backend_rag_v2`); nothing grants to `backend_rag_v2` |
| `_schema_versions.applied_as / applied_via` for 300, 301, 302, 303   | `backend_rag_v2 / release_command` — the ledger already records who applied what (migration 299 provenance columns)   |
| rows in `garuda_practices` / `garuda_orders`                         | 0 / 0 — the funnel is dark; no customer data is at stake in any option                                                |
| login roles that ARE members of `visa_ledger_owner` (measured 08-27) | `flypgadmin`, `postgres`, `repmgr` — all superusers                                                                   |

## The runner, on disk (`apps/backend-rag/backend/db/`)

- One DSN for everything: `migration_manager.py:96` (`self.database_url = database_url or settings.database_url`),
  `migration_base.py:626-655` (`asyncpg.connect(settings.database_url)`), `migrate.py:150`. No
  `SET ROLE` anywhere in the chain. Three touch points, not thirty.
- Each migration file runs in its own transaction; a failure is appended to `failed` and the loop
  **continues** to the next file (`migration_manager.py::_apply_all_pending_locked`).
- Both ledgers (`schema_migrations`, `_schema_versions`) are written only by
  `BaseMigration._log_migration` from Python. A hand-run `psql -f` writes neither, so the deploy
  retries the file and dies on the bare `CREATE TABLE public.garuda_documents` (304 line 140 — no
  `IF NOT EXISTS`; only its two `DO` blocks are catalog-guarded).
- Six shipped migrations already contain `OWNER TO visa_ledger_owner`
  (253, 268, 281, 286, 300, 301). 301's header documents how they landed: **a manual superuser
  transaction**, never a role grant. This will happen again: every future GARUDA table that binds a
  retention policy through a `SECURITY DEFINER` trigger needs the same transfer.

## Option D — a dedicated migration role

**Shape.** `CREATE ROLE backend_rag_migrator LOGIN IN ROLE backend_rag_v2, visa_ledger_owner`
(PG17: both memberships `WITH INHERIT TRUE, SET TRUE`). The runner connects as the migrator through a
NEW DSN (`MIGRATION_DATABASE_URL`, Fly secret) and immediately executes `SET ROLE backend_rag_v2`, so
every object a migration creates is owned by `backend_rag_v2` exactly as today. A migration that
needs the ledger transfer does `RESET ROLE` before its `DO $..._owner_transfer$` block and
`SET ROLE backend_rag_v2` after it: at that point `current_user` is the migrator, which is a member
of the function's owner (may `ALTER` it) and a member of `visa_ledger_owner` with `SET` (may
transfer to it). Under the old single-DSN runtime the same two statements are no-ops for
`backend_rag_v2`, so the file stays valid in CI and on a fresh clone.

| cost item                         | measured                                                                                                                                                                                                                                                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| operator superuser session (once) | 1 session, 2 statements (`CREATE ROLE … IN ROLE …`, `ALTER ROLE … PASSWORD`) — `operator[secret]`                                                                                                                                                                                                        |
| Fly secret (once)                 | 1 (`MIGRATION_DATABASE_URL`) — `operator[secret]`; today the app holds exactly one DB secret, `DATABASE_URL`                                                                                                                                                                                             |
| code                              | 3 connect sites → one `settings.migration_database_url or settings.database_url`; one `SET ROLE` after connect (guarded: only when `current_user <> 'backend_rag_v2'`); `resolve_applied_as` unchanged (Postgres answers `session_user`, so the ledger shows `backend_rag_migrator` — honest provenance) |
| migration 304                     | +2 lines (`RESET ROLE` / `SET ROLE backend_rag_v2` around the transfer block)                                                                                                                                                                                                                            |
| tests                             | extend `test_retention_binder_scope_survives_a_non_owner_runner.py` with the migrator identity; one guilt test that the runner refuses to run DDL as a superuser DSN                                                                                                                                     |
| what it leaves owned by whom      | unchanged: tables `backend_rag_v2`, retention functions `visa_ledger_owner`; the migrator owns nothing                                                                                                                                                                                                   |
| reusable for 305+                 | **yes** — the next `OWNER TO` migration needs no human                                                                                                                                                                                                                                                   |
| provable read-only afterwards     | **yes** — `pg_has_role('backend_rag_migrator', …)` ×2, `rolcanlogin`, `pg_get_userbyid(proowner)` on the transferred function, `_schema_versions.applied_as` for 304                                                                                                                                     |
| standing exposure                 | one more login role holding ledger-owner membership, used only by `release_command`; the runtime DSN is untouched. A compromised runtime role gains nothing it does not have today                                                                                                                       |

## Option E — a fully specified superuser transaction

**Shape.** Before the merge, an operator applies 304 from the PR checkout with
`DATABASE_URL=<superuser DSN> python -m backend.db.migrate apply-all` (so `_log_migration` writes both
ledgers atomically, `applied_via=manual`, `applied_as=postgres`), after editing 304 to wrap its
ordinary DDL in `SET LOCAL ROLE backend_rag_v2` … `RESET ROLE` so tables and functions come out owned
by `backend_rag_v2`, and asserting every final owner inside the transaction. On merge the runner
finds 304 applied and skips it.

| cost item                     | measured                                                                                                                                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| operator action               | **one per privileged migration**, forever (six so far, 304 is the seventh): a superuser DSN on a laptop, `operator[secret]` each time                                                                       |
| code                          | 0 in the runner; 304 +4 lines; a runbook                                                                                                                                                                    |
| ordering hazard               | the manual apply must be byte-identical to the file that later merges — the ledger stores a checksum but `_is_applied` keys on `migration_name` only, so a drift is **not** detected                        |
| ordering hazard 2             | applying before merge means production carries a table the running image does not know for the whole merge-queue transit (15-min batches); harmless for 304 (nothing reads it yet), not a general property  |
| reusable for 305+             | as a recipe only — every future transfer repeats the human step                                                                                                                                             |
| provable read-only afterwards | yes, same catalog reads as D                                                                                                                                                                                |
| standing exposure             | none new — but each execution is a superuser session driven from a developer machine, the exact class the 2026-08-27 lesson (`ssh console` picks a random machine, `pg connect` likewise) was written about |

## Rejected, for the record

- **(A) temporary `GRANT visa_ledger_owner TO backend_rag_v2`** — elevates the live runtime role
  for the whole window; the runner does not stop the batch; a session that already did `SET ROLE`
  survives the `REVOKE`; a forgotten revoke is a permanent least-privilege regression. Enumerated in
  the spec; superseded here.
- **(C) lookup table with standing `INSERT` to the runtime role** — trades the enum problem for a
  weaker integrity property (any runtime write can mint a legal scope). Solves requirement 1 only,
  never the transfer.
- **Dropping `SECURITY DEFINER`** from the new trigger — a seventh surface on a second privilege
  model.

## The one question

> **Do we create a dedicated migration role (D), or keep applying privileged migrations by hand
> under a superuser (E)?**

**Recommendation: D.** It costs one superuser session and one Fly secret once, three code lines in
the runner, and it removes the human from every future `OWNER TO` migration — 304 is the seventh in
five months. E is cheaper only for the next single migration and keeps a superuser credential in
the loop for each one after it.

Either answer unblocks #5526 the same way: 304 gets its two `SET ROLE` lines, the wiring branch
`garuda-voa-store-wiring` is re-based on it, and the PR is armed only after the chosen precondition
is verified read-only in production.

## Solo-operatore (what only the codeowner can do)

- the D/E decision (business risk);
- under D: the one superuser session that creates `backend_rag_migrator` and sets its password,
  and `fly secrets set MIGRATION_DATABASE_URL=…` — both `operator[secret]`;
- under E: the superuser DSN on the machine that runs the manual apply — `operator[secret]`.

Everything else — runner change, tests, 304 edit, wiring rebase, arming, post-merge catalog proof —
is the session's.
