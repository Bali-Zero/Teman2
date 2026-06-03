# W38 — Postgres superuser demotion (backend_rag_v2 + sibling app roles)

> Status: **VERIFIED-OPEN, DO-NOT-EXECUTE-AUTONOMOUS**. Generated 2026-06-03 (GENERALE-2 residue).
> Verification: read-only `SELECT … FROM pg_roles WHERE rolsuper=true` on prod via pg-proxy.

## Empirical finding (2026-06-03)
8 roles hold `rolsuper=true` on prod Postgres:

| role | super | justified? |
|---|---|---|
| postgres | t | YES (cluster owner) |
| flypgadmin | t | YES (Fly platform admin) |
| repmgr | t | YES (replication manager) |
| **backend_rag_v2** | t | **NO — app role (W38 target)** |
| **nuzantara_rag** | t | **NO — app role** |
| **zantara_rag_user** | t | **NO — app role** |
| **nuzantara_memory** | t | **NO — app role** |
| **backend_ts_user** | t | **NO — app role** |

W38 originally scoped only `backend_rag_v2`; verification shows **5 app roles** over-privileged (scope-creep — treat as W38-extended).

## Risk / blast radius
- An app role with superuser bypasses ALL RLS / table grants. A compromised app credential = full-cluster read/write/DROP.
- Demotion (`ALTER ROLE <r> NOSUPERUSER`) is **irreversible-class at runtime**: if any code path relies on superuser (e.g. `COPY`, `CREATE EXTENSION`, cross-schema DDL at runtime, bypassing RLS), it breaks until re-granted or redeployed.

## Pre-demotion checklist (per role, MANDATORY before ALTER)
1. Grep app code for runtime DDL / `CREATE EXTENSION` / `COPY FROM PROGRAM` / RLS-bypass reliance using that role's DSN.
2. Confirm the role has explicit GRANTs for everything it does at runtime (SELECT/INSERT/UPDATE/DELETE on its tables) — superuser may have been masking missing grants.
3. Stage in a low-traffic window; have `ALTER ROLE <r> SUPERUSER` rollback ready.
4. Demote ONE role, smoke-test the owning service, then proceed.

## Execution (NEEDS-ANTONELLO — explicit per-role sign-off + window)
```sql
-- run one at a time, smoke-test between each
ALTER ROLE backend_rag_v2  NOSUPERUSER;
ALTER ROLE nuzantara_rag    NOSUPERUSER;
ALTER ROLE zantara_rag_user NOSUPERUSER;
ALTER ROLE nuzantara_memory NOSUPERUSER;
ALTER ROLE backend_ts_user  NOSUPERUSER;
```
Stage B (S2 spec): split `ADMIN_DATABASE_URL` (privileged) from `DATABASE_URL` (app, non-super) so app never connects as super. NOT implemented.
