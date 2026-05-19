---
date: 2026-05-20
domain: operations
client_case: Intel Lake + WR2 perfect-production plan Phase C
sources: 3
---

# Probe Sandbox Setup — Phase C 2026-05-20

Hard-isolated sandbox for Intel Lake + WR2 end-to-end synthetic probes.
Panel critique (Gemini + Codex 2/2 convergent) rejected flag-only isolation
as insufficient — propagation to NotebookLM/Canva/dashboards/embeddings is
not guaranteed by a single boolean. Phase C uses tenant separation at every
storage layer.

## Sandbox tenants

| Layer            | Tenant identifier                      | Notes                                                                                             |
| ---------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------- |
| NotebookLM       | NB-PROBE-SANDBOX-2026-05               | UUID `7e6ae978-136c-4c96-bed5-9fab6f39176f` (created via `mcp__notebooklm-mcp__notebook_create`). |
| PG `intel_items` | `producer_name LIKE 'probe-sandbox-%'` | Migration 187 adds `is_probe_sandbox BOOLEAN` + CHECK constraint hard barrier.                    |
| Canva            | Folder `wr2-probe-sandbox` (TBD)       | Separate from production folder `FAHEwkTYduI`. `canva-apply --target-folder` flag.                |
| Telegram         | `TELEGRAM_PROBE_CHAT_ID` (TBD)         | Probe failures route here — never owner chat (`TELEGRAM_OWNER_CHAT_ID=1125336968`).               |

## Cleanup invariants

Post-probe, all tenants must be empty:

```sql
-- intel_items
SELECT count(*) FROM intel_items
WHERE producer_name LIKE 'probe-sandbox-%' AND first_seen_at < now() - interval '24h';
-- expected: 0

-- war_room_drafts
SELECT count(*) FROM war_room_drafts
WHERE topic LIKE '[PROBE-SANDBOX-%' AND created_at < now() - interval '24h';
-- expected: 0
```

NotebookLM sandbox NB can be deleted wholesale via
`mcp__notebooklm-mcp__notebook_delete(notebook_id='7e6ae978-...')` if state
drifts. Canva sandbox folder: trash all designs in folder via Canva UI.

## Verification (read-only)

```bash
# NB sandbox exists + 0 sources (fresh)
mcp__notebooklm-mcp__notebook_describe(notebook_id='7e6ae978-136c-4c96-bed5-9fab6f39176f')
# Expected: source_count=0
```

## Why hard barrier vs flag-only

`is_probe_sandbox=true` boolean alone fails:

- Dashboard aggregation queries that forget `WHERE NOT is_probe_sandbox` count probes as real data.
- Embedding pipelines index sandbox content into production Qdrant collections.
- Audit log queries pick up sandbox rows.

Migration 187 enforces:

- CHECK: `is_probe_sandbox = true OR producer_name NOT LIKE 'probe-sandbox-%'` (sandbox rows MUST have flag set).
- Inverse CHECK: rows with `is_probe_sandbox=true` MUST have `producer_name LIKE 'probe-sandbox-%'`.
- Partial index `idx_intel_items_production` ON `(first_seen_at)` WHERE `is_probe_sandbox = false` — production queries use this; sandbox rows are physically excluded from the index plan.

## Risk register

| Risk                                                 | Likelihood               | Impact | Mitigation                                                                                                         |
| ---------------------------------------------------- | ------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------ |
| Producer code forgets to set `is_probe_sandbox`      | LOW (probe-only writers) | HIGH   | CHECK constraint catches at INSERT time, asyncpg raises error.                                                     |
| Dashboard query forgets `WHERE NOT is_probe_sandbox` | MED                      | LOW    | Partial index makes sandbox rows physically slow to scan; partial-index review checklist in dashboard PR template. |
| Probe crashes mid-flight, leaves dangling state      | MED                      | LOW    | `docs/runbooks/synthetic-probe-cleanup.md` emergency teardown.                                                     |

## References

- Plan: `~/.claude/plans/vectorized-tinkering-moon.md` (Phase C section)
- Migration: `apps/backend-rag/backend/db/migrations_v2/187_probe_sandbox_isolation.sql`
- Probe scripts: `scripts/probes/intel_lake_e2e_probe.py`, `scripts/probes/wr2_e2e_probe.py`
