# SOLIDIFICATION 07 — Database Layer Audit

**Date:** 2026-04-06
**Component:** PostgreSQL, asyncpg pool, repositories, migrations

## Findings: 3 MEDIUM, 4 LOW, 1 INFO

## Fixes Applied (4)

| Fix | Severity | What |
|-----|----------|------|
| F1 | MEDIUM | Light-init pool: added statement_timeout=30s + max_inactive_connection_lifetime=30s |
| F3 | MEDIUM | conversation save_messages: wrapped in conn.transaction() (TOCTOU race fix) |
| F4 | LOW-MED | query/workflow_analytics: added granularity allowlist at repo boundary |

## Deferred

- F2: Migration pool JSONB codec (LOW — admin-only path)
- F5: httpx per-email in CRM services (LOW — background path)
- F6: Three divergent migration tracking tables (LOW — needs design decision)
- F7: Pool acquire timeout (LOW — add monitoring first)
