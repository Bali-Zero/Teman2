# Option D: owner provisioning and release preconditions

Zero selected D on 2026-09-11. This file prepares the one-time operations reserved
to the owner by `docs/runbooks/prod-db-writes.md`; none were executed by this seat.
At last read-back: no migrator role, no document table, no active document policy.

## Role and password: owner-run on Pro

Open the established interactive owner connection:

```bash
fly postgres connect -a nuzantara-postgres -d nuzantara_rag
```

Then paste the following into psql. Expected effect: one new role and two role
memberships, zero customer rows. This deliberately fails if the role already exists;
inspect an existing role rather than changing it blindly. No superuser, role-creation,
database-creation, replication or row-security-bypass capability is granted.

```sql
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF current_database() <> 'nuzantara_rag' THEN
        RAISE EXCEPTION 'Wrong database for option D provisioning';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backend_rag_migrator') THEN
        RAISE EXCEPTION 'Migrator already exists: inspect before changing it';
    END IF;
END;
$$;
CREATE ROLE backend_rag_migrator LOGIN INHERIT
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT backend_rag_v2, visa_ledger_owner TO backend_rag_migrator
    WITH INHERIT TRUE, SET TRUE;
COMMIT;
\password backend_rag_migrator
```

The password is entered at psql's hidden prompt, never a command argument, chat
message, file in the repository or SQL literal. Until it is set, the newly created
role has no password usable for password authentication. Runtime gets no membership
in the ledger owner. The migrator needs both memberships with SET and inherited
privileges; the measured CREATE privileges of both owners on public already exist.

## Dedicated DSN: owner-run, hidden input, stage only

Use the existing internal database destination and database name, replacing only the
login/password with the new migrator's credentials. Keep DATABASE_URL unchanged.
The following asks for the complete migration DSN with terminal echo disabled and
sends it over stdin to Fly. It rejects newlines and stages the secret without a
deployment. `fly secrets import --help` was checked on Pro in this session.

```bash
python3 - <<'PY'
import getpass
import subprocess
from urllib.parse import urlsplit

dsn = getpass.getpass('MIGRATION_DATABASE_URL (hidden): ')
parsed = urlsplit(dsn)
if ('\n' in dsn or '\r' in dsn or parsed.scheme not in ('postgres', 'postgresql')
        or parsed.username != 'backend_rag_migrator' or not parsed.password
        or parsed.path != '/nuzantara_rag'):
    raise SystemExit('Rejected: expected the dedicated migrator DSN for nuzantara_rag')
result = subprocess.run(
    ['/opt/homebrew/bin/fly', 'secrets', 'import', '--app', 'nuzantara-rag', '--stage'],
    input='MIGRATION_DATABASE_URL=' + dsn + '\n', text=True, capture_output=True,
)
print('Migration secret staged' if result.returncode == 0 else 'Secret staging failed')
raise SystemExit(result.returncode)
PY
```

Staged does not mean active in the current release. Secret metadata and a later
release's catalog provenance are separate proofs. This design separates DB roles;
an application process able to read all secrets of the same Fly app may also read
MIGRATION_DATABASE_URL. It is not credential isolation from a compromised process.

## Read-back: agent-readable, SELECT only

Through `ssh pro` and `scripts/pg.sh`, verify:

```sql
SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_roles WHERE rolname = 'backend_rag_migrator';
-- Expected: true, false, false, false, false, false.

SELECT pg_has_role('backend_rag_migrator', 'backend_rag_v2', 'SET'),
       pg_has_role('backend_rag_migrator', 'backend_rag_v2', 'USAGE'),
       pg_has_role('backend_rag_migrator', 'visa_ledger_owner', 'SET'),
       pg_has_role('backend_rag_migrator', 'visa_ledger_owner', 'USAGE'),
       pg_has_role('backend_rag_v2', 'visa_ledger_owner', 'MEMBER');
-- Expected: true, true, true, true, false.
```

After the reviewed release applies 304 through its Python runner:

```sql
SELECT relname, pg_get_userbyid(relowner)
FROM pg_class WHERE oid IN (
    'public.garuda_documents'::regclass,
    'public.garuda_document_review_fields'::regclass
);
-- Both backend_rag_v2.

SELECT pg_get_userbyid(proowner)
FROM pg_proc WHERE oid = 'public.bind_garuda_document_retention_policy()'::regprocedure;
-- visa_ledger_owner.

SELECT migration_number, applied_as, applied_via
FROM _schema_versions WHERE migration_number = 304;
-- 304, backend_rag_v2 (session_user=backend_rag_migrator), release_command.
SELECT count(*) FROM schema_migrations WHERE migration_number = 304;
-- 1.
```

No real document should be used to manufacture a proof while the signed production
GARUDA_DOCUMENT policy is absent. Once provisioned, reviewed, released, wired and
policy-covered, prove the local-OCR upload and review journey under its own contract.

## Provisioning rollback, not migration rollback

Before removing a role or its memberships, drain migration sessions and coordinate
with the release owner so no pending privileged migration depends on it. Remove the
staged secret through the owner workflow; do not invoke a deployment as a side effect.
Then owner-run:

```sql
BEGIN;
ALTER ROLE backend_rag_migrator NOLOGIN;
REVOKE backend_rag_v2, visa_ledger_owner FROM backend_rag_migrator;
COMMIT;
```

This disables new logins and removes two memberships without touching schema or
customer rows; repeat is safe while the role exists. NOLOGIN does not terminate an
existing session. DROP ROLE is optional only after a catalog check confirms no owned
objects, grants or active sessions depend on it. A failure during the initial CREATE
transaction rolls that transaction back. This is not permission to hand-apply or
hand-undo 304; its own split-ownership rollback remains unproved.
