# Runbook — Synthetic probe cleanup emergency

> Da usare SOLO quando un probe e2e si è schiantato a metà e ha lasciato dati nel sandbox tenant. Versione 2026-05-20 (Phase C+D).

## Quando serve

Sintomi che indicano probe dangling:

- Dashboard mostra "probe last pass: 5 days ago"
- `~/logs/intel-lake-probe-cron.log` ha `PROBE CRASHED` ma cleanup hop5/hop6 non si vede
- Errore Telegram con `defensive cleanup failed`
- `psql -c "SELECT count(*) FROM intel_items WHERE is_probe_sandbox = true"` ritorna > 0

## Sandbox tenants

| Tenant                 | Identificatore                                   | Cleanup query                                                                                           |
| ---------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `intel_items`          | `is_probe_sandbox = true`                        | `DELETE FROM intel_items WHERE is_probe_sandbox = true`                                                 |
| `intel_observations`   | cascade da intel_items (FK ON DELETE CASCADE)    | Automatico — non serve query separata                                                                   |
| `intel_item_nb_pushes` | cascade da intel_items                           | Automatico                                                                                              |
| `events_outbox`        | `channel = 'intel_lake_event'` con payload probe | `DELETE FROM events_outbox WHERE channel = 'intel_lake_event' AND payload::text LIKE '%probe-sandbox%'` |
| `war_room_drafts`      | `topic LIKE '[PROBE-SANDBOX-%'`                  | `DELETE FROM war_room_drafts WHERE topic LIKE '[PROBE-SANDBOX-%'`                                       |
| NotebookLM sandbox     | NB UUID `7e6ae978-136c-4c96-bed5-9fab6f39176f`   | Manuale via Canva UI o MCP `notebook_delete` (poi `notebook_create` per ricreare)                       |
| Canva sandbox          | Folder `wr2-probe-sandbox` (TBD UUID)            | Manuale: Canva UI → Trash folder content                                                                |

## Cleanup procedure

```bash
# 1. Verifica scope contaminazione
psql "${DATABASE_URL}" -c "
    SELECT 'intel_items' AS tenant, count(*) FROM intel_items WHERE is_probe_sandbox = true
    UNION ALL
    SELECT 'war_room_drafts', count(*) FROM war_room_drafts WHERE topic LIKE '[PROBE-SANDBOX-%'
    UNION ALL
    SELECT 'events_outbox', count(*) FROM events_outbox WHERE channel='intel_lake_event' AND payload::text LIKE '%probe-sandbox%' AND consumed_at IS NULL;
"

# 2. Cleanup SQL (idempotente, sicuro)
psql "${DATABASE_URL}" -c "
    BEGIN;
    DELETE FROM intel_items WHERE is_probe_sandbox = true;
    DELETE FROM war_room_drafts WHERE topic LIKE '[PROBE-SANDBOX-%';
    DELETE FROM events_outbox
        WHERE channel = 'intel_lake_event'
          AND payload::text LIKE '%probe-sandbox%'
          AND consumed_at IS NULL;
    COMMIT;
"

# 3. Verifica 0 residue
psql "${DATABASE_URL}" -c "
    SELECT count(*) AS leftover FROM intel_items WHERE is_probe_sandbox = true;
"
# Atteso: leftover = 0
```

## NotebookLM sandbox reset (raro)

Se il NB sandbox `NB-PROBE-SANDBOX-2026-05` è corrotto (es: source orfane, troppi push falliti):

```bash
# Antonello-only — usa MCP
# Step 1: cancella NB sandbox
mcp__notebooklm-mcp__notebook_delete \
    --notebook-id 7e6ae978-136c-4c96-bed5-9fab6f39176f

# Step 2: ricrea
mcp__notebooklm-mcp__notebook_create --title "NB-PROBE-SANDBOX-2026-05"

# Step 3: aggiorna UUID nel probe script e nel runbook
# Edit: scripts/probes/intel_lake_e2e_probe.py — costante NB_SANDBOX_UUID
# Edit: research/operations/2026-05-20-probe-sandbox-setup.md — sezione tenants
```

## Rollback migration 187 (super-raro)

Se serve davvero rimuovere `is_probe_sandbox`:

```bash
# CLEANUP FIRST (impossibile dopo drop column)
psql "${DATABASE_URL}" -c "DELETE FROM intel_items WHERE is_probe_sandbox = true"

# Poi applica rollback section di 187
sed -n '/-- === ROLLBACK ===/,$p' \
    apps/backend-rag/backend/db/migrations_v2/187_probe_sandbox_isolation.sql \
    | psql "${DATABASE_URL}"
```

Dopo il rollback, registra in `schema_migrations` come rolled-back.

## Postmortem

Dopo ogni cleanup, scrivi 2 righe in `.claude/rules/cicatrix-scars.md`:

- data
- cosa è andato storto (crash di Python? rete? NB ban?)
- antibody (è una mitigazione possibile?)

Senza postmortem → la cicatrix non si forma e ripete l'errore.
