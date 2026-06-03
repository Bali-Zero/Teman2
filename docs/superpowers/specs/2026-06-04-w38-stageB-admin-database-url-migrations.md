# W38 Stage B — migration runner privilege fix

> Date: 2026-06-04 · Domain: backend/infra · Severity: P1 (all DB migrations blocked) · Cicatrix: W38
>
> **OUTCOME (2026-06-04): the ADMIN_DATABASE_URL design below was REJECTED by the
> 4-LLM panel (DeepSeek REJECT, Codex REJECT, Gemini APPROVE-WITH-CHANGES) and
> NOT implemented.** Two decisive findings: (1) Codex proved the proposed 3-line
> `MigrationManager.__init__` change is INEFFECTIVE — `BaseMigration.apply()`
> (`migration_base.py:481`) hardcodes `asyncpg.connect(settings.database_url)`,
> bypassing the manager pool, so the failing `CREATE INDEX` would still run as
> `backend_rag_v2`. (2) All three panelists rejected injecting a superuser DSN
> into the app: it reopens the W38 blast-radius win AND creates fresh
> ownership-drift (every future migration object would be owned by the
> superuser, not the app role).
>
> **What was actually shipped instead** (panel-converged, operator-approved):
> a one-time ownership transfer. Empirical audit showed ONLY `schema_migrations`
> was orphaned (owned by `zantara_rag_user`); `_schema_versions` was already
> owned by `backend_rag_v2`, as were 248/258 public tables, and
> `inbound_webhooks` (the FK target of migration 206) too. Single statement,
> run as the `postgres` superuser on the Stolon **primary** machine:
>
> ```sql
> ALTER TABLE schema_migrations OWNER TO backend_rag_v2;
> ```
>
> Zero new credentials, zero code change, zero superuser DSN in the app —
> `backend_rag_v2` stays NOSUPERUSER, W38 preserved. Migration 206 then applied
> cleanly on redeploy; `/api/wa-inbox/threads` verified 200 with the scoped key.
>
> Stolon gotchas captured: real Postgres listens on socket `/run/postgresql`
> port **5433** (5432 is haproxy); the replica returns "read-only transaction";
> `fly machines list` shows the `ROLE` column (primary/replica); use
> `fly ssh console --machine <id>` (the `-s/--select` flag is interactive and
> fails non-interactively).
>
> The original (rejected) design is preserved below as the record of what was
> considered and why it was not taken.

---

## Problem (empirically verified 2026-06-04)

The `release_command` on every Fly deploy runs:

```
python -m backend.db.migrate apply-all && python -m backend.db.schema_audit
```

`MigrationManager` connects with `settings.database_url`, whose role is
`backend_rag_v2`. As of the W38 demotion (Stage C executed at some point
after 2026-05-23), `backend_rag_v2` is **NOSUPERUSER** (verified:
`pg_roles.rolsuper = false`). Meanwhile `schema_migrations` is owned by
`zantara_rag_user` (verified via `pg_get_userbyid(relowner)`).

The deploy of migration 206 (`wa_meta_inbox`) aborted with:

```
asyncpg.exceptions.InsufficientPrivilegeError: must be owner of table schema_migrations
```

Root: `_ensure_migration_log()` issues `CREATE INDEX IF NOT EXISTS` on the
already-existing `schema_migrations`. `CREATE INDEX` requires table-owner
privilege; pre-demotion superuser bypassed ownership, now it cannot. **This
blocks EVERY future migration, not just 206.** W38's own GOTCHA predicted
this exact failure ("new migrations would fail") and prescribed Stage B —
which was never shipped (`grep ADMIN_DATABASE_URL` in `backend/db/` = empty;
no Fly secret of that name). The demotion (Stage C) shipped without its
prerequisite (Stage B): a half-executed scar.

Prod is NOT down: the release_command failure aborted the image swap, so the
previous (healthy, pre-wa_inbox) image is still serving.

## Verified facts

| Fact | Value |
|---|---|
| App DB role (`DATABASE_URL`) | `backend_rag_v2` @ `nuzantara-postgres.flycast/nuzantara_rag` |
| `backend_rag_v2` rolsuper | `false` |
| `schema_migrations` owner | `zantara_rag_user` |
| Superuser roles available | `flypgadmin`, `postgres`, `nuzantara_rag`, `repmgr` |
| Postgres app secrets | `SU_PASSWORD` (superuser), `OPERATOR_PASSWORD`, `REPL_PASSWORD` |
| Max applied migration | 205 (206 not applied) |
| W38 Stage B in code | NOT shipped |

## Design

### Code change (minimal, localized)

`MigrationManager.__init__` prefers an admin DSN when present:

```python
def __init__(self, database_url: str | None = None) -> None:
    self.database_url = (
        database_url
        or settings.admin_database_url   # NEW: superuser DSN for DDL
        or settings.database_url
    )
```

New `config.py` field, mirroring `database_url` (None default, same
postgres:// → postgresql:// normalization validator):

```python
admin_database_url: str | None = None  # superuser DSN for migration DDL only
```

Effect: `MigrationManager()` (no-arg, as called by `migrate.py`) uses the
admin DSN for the migration/audit step; everywhere else the app keeps using
`backend_rag_v2` via `settings.database_url`. The runtime app role stays
NOSUPERUSER — W38's blast-radius reduction is preserved.

### The admin DSN

Construct `ADMIN_DATABASE_URL` pointing at a superuser:

```
postgres://postgres:<SU_PASSWORD>@nuzantara-postgres.flycast:5432/nuzantara_rag?sslmode=disable
```

Set as a Fly secret on `nuzantara-rag`. `SU_PASSWORD` is read from the
postgres app's secrets (`fly ssh`/operator path), never logged.

## Two architectural choices the panel must settle

**Q1 — Where does the admin DSN live: runtime-always, or release-command-only?**
- (A) Plain Fly secret `ADMIN_DATABASE_URL` on nuzantara-rag → present in the
  app runtime env too. Simplest. BUT reintroduces a superuser credential into
  the long-lived app process env — partially reopening the W38 attack surface
  (leaked env / container escape now yields superuser again).
- (B) Inject the admin DSN ONLY for the release_command (ephemeral machine
  that runs migrations then is destroyed), not the runtime api/rag machines.
  Mechanism options: separate process-group env, or a release-command wrapper
  that fetches it. Smaller blast radius (superuser cred only exists during the
  ~30s migration machine lifetime). More complex; Fly release_command shares
  the app secret set, so true scoping may require a wrapper that pulls SU at
  runtime rather than a static secret.

**Q2 — Is the `admin_database_url or database_url` fallback safe, or should
the migrate.py entrypoint require admin explicitly in production?**
- Fallback keeps local/test working (no admin set → uses normal DSN against a
  local DB the dev owns). But in production a silent fallback to the
  non-owner role would just re-fail the same way. Option: in `migrate.py`,
  if `ENVIRONMENT=production` and `admin_database_url` is None, fail loud
  with a clear message rather than attempt-and-InsufficientPrivilege.

## Rollback

Code change is additive (new optional field + preference order). Revert =
unset the Fly secret (manager falls back to `database_url`) + revert the 3-line
diff. No DDL, no data change. The migration runner behavior is identical when
`admin_database_url` is unset.

## Test plan

1. Unit: `MigrationManager(database_url=None)` with `admin_database_url` set →
   uses admin; with both None → MigrationError; with only `database_url` →
   uses it (back-compat).
2. Unit: config field parses + normalizes `postgres://` → `postgresql://`.
3. migrate.py production-guard (if chosen): `ENVIRONMENT=production` +
   no admin → exits with the loud message.
4. Live: set secret → redeploy → release_command applies 206 → verify
   `schema_migrations` max = 206 + endpoint `/api/wa-inbox/threads` returns
   401 (not 503/404).
