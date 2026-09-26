# W38b — Residual superuser role demotion: `nuzantara_rag` + `backend_ts_user`

> **Status: SPEC READY — NOT EXECUTED.** Requires Antonello's explicit go + a
> supervised execution window. The read-only Postgres MCP cannot run `ALTER
> ROLE`; execution path is `fly ssh console -a nuzantara-rag` as a platform
> superuser.
>
> Date: 2026-06-12 · Parent: W38 (`W38-backend-rag-v2-nosuperuser.md`) ·
> Audit source: guardian-of-guardians 2026-06-11.

## 1. Context

W38 (the big one) demoted the **primary application role** `backend_rag_v2`
from `rolsuper=t` to NOSUPERUSER — **DONE** (verified 2026-06-12: it is no
longer in the superuser list, yet still serves 21 live sessions and owns 263
tables / 173 sequences via OWNER grants, exactly as designed).

Two **residual** app roles were left superuser and are the subject of this
spec:

| Role | superuser (2026-06-12) | active sessions | owned tables | owned sequences |
|---|---|---|---|---|
| `nuzantara_rag` | **YES** | 0 | 0 | 0 |
| `backend_ts_user` | **YES** | 0 | 0 | 0 |

The other superuser roles — `flypgadmin`, `postgres`, `repmgr` — are
Fly/Stolon platform roles and are **out of scope** (do not touch).

## 2. Why this is LOW risk (much simpler than W38 for `backend_rag_v2`)

`backend_rag_v2` needed a 3-stage plan precisely because it owns 263 tables
(OWNER grants had to be proven sufficient post-demotion). These two residuals:

- **Own nothing** (0 tables, 0 sequences) → there are **no OWNER grants to
  preserve**, no privilege cliff after demotion.
- **Have zero active sessions** → no live connection to break.
- **No live use in the codebase** (verified 2026-06-12 by repo-wide audit):
  - `nuzantara_rag` — legacy DB-owner naming; appears only in W38 spec
    (`:49` "legacy") + cicatrix + structural-debt FROZEN ("legacy/Fly-platform,
    NOT used by app code"). No DSN / Fly secret / wrapper connects as it.
  - `backend_ts_user` — annotated `:46` "timescale? not used by app"; a
    TimescaleDB remnant never wired. No DSN / Fly secret / wrapper connects.
- They are NOT reachable via a leakable application secret (only
  `backend_rag_v2` was, via `DATABASE_URL`). So the blast-radius reduction is
  smaller than W38's — but the change itself is near-trivial and reversible in
  one command.

## 3. Execution (SUPERVISED — do NOT run autonomously)

Window: low-traffic (Sunday 03:00–05:00 WITA, same discipline as W38 stage C),
though the zero-session/zero-ownership state means any low-traffic moment is
acceptable.

Path: `fly ssh console -a nuzantara-rag` → `psql` as a platform superuser
(`flypgadmin`).

```sql
-- forward
ALTER ROLE nuzantara_rag   NOSUPERUSER;
ALTER ROLE backend_ts_user NOSUPERUSER;
```

## 4. Verification (immediately after)

```sql
-- expect: rolsuper = f for both
SELECT rolname, rolsuper, rolcanlogin
FROM pg_roles
WHERE rolname IN ('nuzantara_rag', 'backend_ts_user')
ORDER BY rolname;
```

Then confirm the organism is healthy (nothing connects as these roles, so this
should be a no-op, but verify anyway):

- `GET /health` on `nuzantara-rag` → 200
- `mcp__nuzantara-mcp__check_health`
- `mcp__nuzantara-mcp__list_clients limit=1` (exercises the live
  `backend_rag_v2` path — must stay green)
- 24h: watch the Cell organism Telegram + `audit-launchd-daily` delta for any
  new auth failure mentioning either role (expected: none).

## 5. Rollback (one command, fully reversible)

```sql
ALTER ROLE nuzantara_rag   SUPERUSER;
ALTER ROLE backend_ts_user SUPERUSER;
```

## 6. Guardrails

- **Do NOT execute without Antonello's explicit go.** Operator decision
  2026-06-12 was "schedule the demotion" with "I'll update you before
  executing" — this spec is the schedule, not the execution.
- If, against expectation, a session for either role appears in
  `pg_stat_activity` at execution time, ABORT and re-audit (something started
  using a role this spec assumed dead).
- `postgres` / `flypgadmin` / `repmgr` stay superuser — platform roles.

## 7. Open follow-up (separate, not this spec)

The remaining legacy superuser roles `nuzantara_memory` and `zantara_rag_user`
(flagged in the W38 cicatrix as "legacy attack surface for any rogue script
that hardcodes them") were NOT in the 2026-06-12 superuser snapshot — confirm
whether they were already demoted or dropped before drafting any further
demotion. (Snapshot 2026-06-12 superuser set: `backend_ts_user`, `flypgadmin`,
`nuzantara_rag`, `postgres`, `repmgr` — five, not the eight the original W38
audit listed.)
