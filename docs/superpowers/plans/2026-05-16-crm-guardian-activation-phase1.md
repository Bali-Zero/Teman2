# CRM-Guardian Activation Phase 1 — Cross-folder L1 Summary

**Date**: 2026-05-16
**Owner**: Antonello (Zero)
**Status**: APPROVED — ready to execute
**Branch**: `feat/crm-guardian-phase1-activation` (TBD)

---

## Goal in plain Italian

Accendere il sistema CRM-Guardian dormiente per generare summary AI di ogni cliente, leggendo **cross-folder** la cartella Drive del cliente + le cartelle Drive delle sue companies linkate via `client_company_links`. Trigger: solo on-change (file modificati in Drive). Costo aggiuntivo: €0/mese (Workspace AI add-on già pagato).

Phase 1 copre **cliente + sue companies**, non ancora Drive globale non-cliente (Phase 4).

---

## Scope IN

- Worker Playwright che consuma `crm_guardian_summary_queue` e produce `clients.ai_summary` JSONB
- Trigger on-change in `drive_poll_service.py` con cascading enqueue (file in cartella company → enqueue tutti i clienti linkati)
- Prompt L1 esteso v2 con sezione `tax_records` + `lkpm_history` + `source_company_folders[]`
- Endpoint `GET /api/crm/clients/{id}/ai-summary` con RBAC
- 8 card AI Summary nei tab kita.balizero.com (Overview + 7 tab specifici)
- Pilot 5 clienti VIP `dry_run=true`, validazione, poi flip `dry_run=false` su rolling subset
- Test integration end-to-end su pilot

## Scope OUT (rinviato a Phase 2-5)

- Portal cliente my.balizero.com (Phase 3)
- Cartelle Drive globali non-cliente: `/Tax/2026/`, `/Legal/`, `/KBLI/`, `/Marketing/` (Phase 4)
- File `_AI_BRIEF.md` scritto dentro Drive cliente (Phase 5, attivazione `I11_summary_l2_markdown`)
- NotebookLM per-cliente VIP (Phase futura, `I12_summary_l3_notebooklm`)
- Properties/villas linkage (tabella non esiste, fuori scope)

---

## Architettura

### Modello dati

| Tabella                                       | Stato                              | Ruolo                                            |
| --------------------------------------------- | ---------------------------------- | ------------------------------------------------ |
| `clients.ai_summary` JSONB                    | ESISTE (migration 129)             | Storage finale summary L1                        |
| `clients.ai_summary_file_hash` TEXT           | ESISTE (migration 129)             | SHA256 fingerprint per skip                      |
| `clients.ai_summary_generated_at` TIMESTAMPTZ | ESISTE (migration 129)             | Freshness badge                                  |
| `crm_guardian_summary_queue`                  | ESISTE (migration 130)             | Work queue                                       |
| `crm_guardian_events`                         | ESISTE (migration 129)             | Audit trail                                      |
| `crm_guardian_state`                          | ESISTE (migration 129)             | Runtime config + enable flags                    |
| `companies`                                   | ESISTE (modulo crm.company_models) | Entity con `google_drive_folder_id`              |
| `client_company_links`                        | ESISTE (idem)                      | Join cliente ↔ company con `role` + `is_primary` |
| `tax_records`                                 | ESISTE (citata in docstring)       | Storico SPT/PPN per company                      |
| `lkpm_reports`                                | ESISTE (migration 132)             | LKPM history                                     |

**Nessuna nuova tabella in Phase 1.** Tutto il modello dati c'è.

### Schema L1 estensione

File: `apps/backend-rag/backend/services/crm_guardian/schemas.py`

Bump `SCHEMA_VERSION = "v2.0"`, aggiungere a `Company`:

```python
class TaxRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str  # "2024", "Q1-2025", etc.
    spt_type: Literal["SPT_Tahunan", "SPT_Masa_PPN", "SPT_Masa_PPh21", "Other"] | None
    filed_at: date | None
    amount_idr: int | None
    status: Literal["filed", "pending", "overdue", "audited", "unknown"] = "unknown"
    source_file_id: str | None

class LkpmRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str  # "Q1-2025"
    reported_at: date | None
    realization_idr: int | None
    employment_count: int | None
    status: Literal["submitted", "draft", "rejected", "unknown"] = "unknown"
```

Estendere `Company` con:

```python
tax_records: list[TaxRecord] = Field(default_factory=list)
lkpm_history: list[LkpmRecord] = Field(default_factory=list)
source_company_folders: list[str] = Field(
    default_factory=list,
    description="Drive folder IDs delle cartelle company che hanno contribuito a questo summary."
)
```

Bump `prompt_version` da `L1_extraction_v1` a `L1_extraction_v2`.

### Trigger on-change cascading

File: `apps/backend-rag/backend/services/crm/drive_poll_service.py:240+`

Logica nuova dopo che file viene risolto a `client_id`:

```
1. File in subfolder cliente (00_Profile, 01_Immigration, ...) → enqueue client_id
2. File in cartella company.google_drive_folder_id → query client_company_links →
   enqueue TUTTI i clienti collegati a quella company
3. Computa fingerprint SHA256 della cartella + cartelle linked company al tempo enqueue
4. Insert in crm_guardian_summary_queue con priority:
   - VIP (clients.ai_summary->profile->>'tier' = 'VIP') → priority=1
   - standard → priority=50
   - archive → priority=100
5. UNIQUE INDEX ux_crm_guardian_queue_client_pending già garantisce no-duplicate
```

### Worker Playwright

File nuovo: `apps/backend-rag/scripts/crm_guardian_gemini_worker.py`

Stack: usa `packages/browser-core` (stealth manager esistente, già usato da nuzantara-mcp-browser).

Flow per ogni job:

````
1. Poll prossimo job da crm_guardian_summary_queue WHERE status='pending'
   ORDER BY priority ASC, enqueued_at ASC LIMIT 1
2. UPDATE status='running', attempts=attempts+1, started_at=NOW(), run_id=gen_random_uuid()
3. Risolvi client_id → cartella cliente Drive + lista companies linkate via JOIN
4. Lancia Chrome stealth con profilo Workspace Antonello (sessione persistente)
5. Naviga a drive.google.com/drive/folders/{client_folder_id}
6. Apri Gemini Panel Side (selector data-testid="gemini-panel-toggle" o equivalente)
7. Inietta prompt L1_extraction_v2 con substitution {{drive_folder_ids}} =
   [cliente_root, company1_root, company2_root, ...]
8. Aspetta risposta Gemini (timeout 180s, max 3 retry con exponential backoff 30/60/120s)
9. Cattura DOM response, estrae JSON fenced block ```json ... ```
10. Parse + valida con L1ClientSummary (Pydantic)
11. UPDATE clients SET ai_summary=$1, ai_summary_file_hash=$2, ai_summary_generated_at=NOW()
12. UPDATE crm_guardian_summary_queue SET status='success', completed_at=NOW(), duration_ms=$
13. INSERT crm_guardian_events (audit trail con run_id)
14. Su error: UPDATE status='error', last_error, next_retry_at=NOW()+15min*2^attempts
15. Su max_retries (3): status='error' permanente, alert Telegram a Zero (chat_id 1125336968)
````

Concurrency: max 3 Chrome stealth in parallelo (semaphore Python). Throttle 30s tra job per safety rate-limit Workspace AI add-on.

Fallback se Playwright Panel Side fallisce 3 volte di fila (DOM Google cambiato): switch automatico a `gemini --print` CLI con OAuth free (multimodal via file download). Documentato in cicatrix scar pre-emptive.

### Endpoint backend

File nuovo: aggiungere in `apps/backend-rag/backend/app/routers/crm_clients.py` dopo riga 1200 (sezione AI/metrics):

```python
@router.get("/{client_id}/ai-summary")
async def get_client_ai_summary(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Ritorna L1 summary AI cross-folder per il cliente."""
    rbac_filter = get_crm_user_filter(current_user)
    async with db_pool.acquire() as conn:
        # ... query con rbac_filter ...
        row = await conn.fetchrow(
            """SELECT ai_summary, ai_summary_generated_at, ai_summary_schema_version,
                      ai_summary_file_hash
               FROM clients WHERE id=$1""",
            client_id,
        )
    if not row or not row["ai_summary"]:
        raise HTTPException(404, "AI summary not yet generated for this client")
    return {
        "client_id": client_id,
        "summary": row["ai_summary"],  # JSONB
        "generated_at": row["ai_summary_generated_at"].isoformat(),
        "schema_version": row["ai_summary_schema_version"],
        "fingerprint": row["ai_summary_file_hash"],
    }
```

Path: `GET /api/crm/clients/{client_id}/ai-summary`
Auth: `get_current_user` + RBAC filter via `get_crm_user_filter`
Cache: response header `Cache-Control: private, max-age=60` (1 minuto)

### Frontend kita.balizero.com

File da modificare in `apps/mouth/src/app/(workspace)/clients/[id]/components/`:

**Nuovo componente condiviso**: `AiSummaryCard.tsx`

```tsx
interface AiSummaryCardProps {
  clientId: number;
  section:
    | "overview"
    | "company"
    | "tax"
    | "immigration"
    | "family"
    | "documents"
    | "process"
    | "timeline";
}

// Fetch GET /api/crm/clients/{id}/ai-summary (SWR cache 60s)
// Estrae sezione corretta da summary JSONB
// Mostra:
//   - Headline 2-3 bullet (extraction da Gemini narrative)
//   - Highlights data-driven (es. Company tab: KBLI + capital + KBLI risk class)
//   - Badge freshness: 🟢 < 24h, 🟡 1-7gg, 🔴 > 7gg o mai
//   - Confidence indicator: progress bar 0-100% da extraction_confidence
```

Inserire in:

- `OverviewTab.tsx`: card grande in alto con sezione `profile` + `narrative_en` + 3 scadenze critiche da `compliance`
- `CompanyTab.tsx`: card con `company.legal_name`, `kbli_primary`, `paid_up_capital_idr`, lista `tax_records` + `lkpm_history`
- `TaxTab.tsx`: card con `compliance.spt_tahunan_last`, `compliance.lkpm_next_due` + tabella `tax_records`
- `ImmigrationTab.tsx`: card con `visa.visa_type`, `visa.valid_until`, `compliance.visa_days_until_expiry`, `compliance.passport_days_until_expiry`
- `FamilyTab.tsx`: card con dipendenti visa derivati da `shareholders` o `compliance.red_flags`
- `DocumentsTab.tsx`: card con `documents[]` strutturato per `doc_type`
- `ProcessTab.tsx`: card con `compliance.red_flags` + scadenze pratiche derivate
- `TimelineTab.tsx`: card con `timeline[]` Gemini-extracted come overlay sopra timeline DB

### Activation sequence

| Step                          | Comando                                                                                                                                                                          | Verifica                                                  |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 1. Crea branch                | `git checkout -b feat/crm-guardian-phase1-activation`                                                                                                                            | branch attivo                                             |
| 2. Estendi schema L1 v2       | edit `schemas.py` + new `prompts/L1_extraction_v2.md`                                                                                                                            | pytest schemas                                            |
| 3. Worker Playwright          | new `scripts/crm_guardian_gemini_worker.py` + test smoke su 1 cliente                                                                                                            | output JSON valido in DB                                  |
| 4. Cascading enqueue          | edit `drive_poll_service.py` + test integration                                                                                                                                  | enqueue su file change cartella company propaga a clienti |
| 5. Endpoint API               | edit `crm_clients.py` + test unit                                                                                                                                                | curl `/api/crm/clients/1/ai-summary` ritorna 200 + RBAC   |
| 6. Migration 180 enable flags | new `migrations_v2/180_crm_guardian_phase1_enable.sql` UPDATE crm_guardian_state SET enabled=true WHERE invariant_id IN ('I10_summary_l1','I10b_summary_queue') AND dry_run=true | rows updated 2                                            |
| 7. Pilot 5 VIP dry_run=true   | Antonello sceglie 5 clienti VIP, enqueue manuale                                                                                                                                 | worker processa, ispeziona output JSON                    |
| 8. Flip dry_run=false su VIP  | UPDATE crm_guardian_state SET dry_run=false WHERE ...                                                                                                                            | worker scrive in `clients.ai_summary` real                |
| 9. Componente AiSummaryCard   | edit 8 file tab mouth + new component                                                                                                                                            | UI mostra card su `localhost:3000/clients/{id}`           |
| 10. Rollout graduale          | UPDATE enabled+dry_run su tier='standard', poi 'archive'                                                                                                                         | tutti clienti coperti                                     |
| 11. LaunchAgent worker H24    | new plist `com.nuzantara.crm-guardian-worker.plist` su Pro                                                                                                                       | `launchctl list \| grep crm-guardian` shows running       |
| 12. Telegram alert errori     | hook in worker su status='error' max_retries                                                                                                                                     | test forcing failure → alert ricevuto                     |

---

## Vincoli zero-costo (HARD)

| Risorsa                      | Modalità gratuita scelta                                              |
| ---------------------------- | --------------------------------------------------------------------- |
| Gemini 3 Pro multimodale     | Workspace Business Plus AI add-on via Panel Side (Playwright stealth) |
| Fallback se Playwright rotto | `gemini --print` CLI OAuth free (1M context, NO API key)              |
| Drive API                    | Service Account esistente `ServiceAccountDriveService`                |
| Storage                      | Postgres Fly esistente (`nuzantara-postgres`)                         |
| Frontend                     | Mouth Next.js + Vercel esistenti                                      |
| Compute worker               | LaunchAgent Pro 48GB (sovranità locale Symbiosis Law 6)               |
| **TOTALE incremental cost**  | **€0/mese**                                                           |

**HARD BAN**: nessun `GEMINI_API_KEY`, nessun `OPENAI_API_KEY`, nessun `ANTHROPIC_API_KEY` per questo sistema. Solo OAuth flow Workspace o CLI subprocess.

---

## Rischi & mitigazioni

| Rischio                                                   | Probabilità                          | Impatto           | Mitigazione                                                                                                                                                                      |
| --------------------------------------------------------- | ------------------------------------ | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DOM drive.google.com cambia → Playwright Panel Side rotto | Media (Google cambia ~ogni 3-6 mesi) | Alto              | Smoke test daily 06:00 WITA su 1 cliente canary; fallback CLI `gemini --print` automatico dopo 3 fail consecutivi                                                                |
| Workspace AI rate limit non documentato                   | Media                                | Medio             | Throttle 30s tra job, max 3 concorrenti; monitoring via `crm_guardian_events.duration_ms` percentile                                                                             |
| 5000 clienti × prima generazione = 50h Playwright         | Certa                                | Medio             | Priorità: VIP first (priority=1), standard (50), archive (100). Backfill notturno 22:00-06:00 WITA. Stima: VIP+standard ~500 clienti × 30s × 3 concurrent = ~83 minuti           |
| Gemini hallucina dati (KBLI sbagliato, capital errato)    | Media                                | Alto (regulatory) | `extraction_confidence < 0.6` → flag `manual_review_required=true`, NON scrive in `ai_summary` finché Antonello/team conferma. Audit trail su `crm_guardian_events` con `run_id` |
| Drift schema L1 v2 ↔ frontend                             | Bassa                                | Medio             | `schema_version` in JSONB, frontend valida con type guard, fallback `unknown`                                                                                                    |
| Worker crash mid-job → riga 'running' orfana              | Media                                | Basso             | Watchdog cron 5min: UPDATE status='error' WHERE status='running' AND started_at < NOW() - INTERVAL '15 min'                                                                      |
| Cliente vede dato sbagliato in portal                     | N/A Phase 1 (portal Phase 3)         | —                 | Phase 3 avrà filtro whitelist campi + manual review obbligatoria pre-published                                                                                                   |

---

## Pilot 5 clienti VIP — criteri di selezione

Antonello sceglie 5 clienti rappresentativi con questi requisiti:

- 1 expat solo (no company) → testa archetype `individual_expat`
- 2 expat con PT PMA → testa cross-folder cliente+company
- 1 PT PMA-only (no individuo) → testa archetype `business_only`
- 1 cliente family (con dipendenti visa) → testa archetype `family_member`

Per ognuno verificare manualmente:

- [ ] `ai_summary.identity` corretto (passport, NPWP)
- [ ] `ai_summary.company.tax_records` popolato se ha company
- [ ] `ai_summary.company.lkpm_history` popolato se ha PT PMA
- [ ] `ai_summary.profile.archetype` plausibile
- [ ] `ai_summary.extraction_confidence` ≥ 0.6
- [ ] `ai_summary.narrative_en` legge bene (non hallucina)

Sign-off Antonello richiesto prima di flip `dry_run=false`.

---

## Acceptance criteria Phase 1

- [ ] 5 clienti VIP hanno `clients.ai_summary` popolato e validato manualmente
- [ ] Worker LaunchAgent H24 stabile (uptime > 95% in 1 settimana di pilot)
- [ ] Endpoint `/api/crm/clients/{id}/ai-summary` risponde 200 con RBAC funzionante
- [ ] 8 tab kita.balizero.com mostrano AI Summary card senza errori UI
- [ ] Smoke daily test verde per 7 giorni consecutivi
- [ ] Zero spese API aggiuntive (verificato su billing Google Cloud + Anthropic Console)
- [ ] Telegram alert ricevuto per error simulato
- [ ] Documentazione cicatrix-scars aggiornata con eventuali workaround

## Timeline

| Giorno     | Lavoro                                               |
| ---------- | ---------------------------------------------------- |
| Giorno 1   | Branch + schema L1 v2 + prompt v2 + migration 180    |
| Giorno 2-3 | Worker Playwright completo + smoke test 1 cliente    |
| Giorno 3-4 | Cascading enqueue + integration test                 |
| Giorno 4   | Endpoint API + test RBAC                             |
| Giorno 5   | Pilot 5 VIP dry_run=true + validation Antonello      |
| Giorno 5-6 | 8 tab frontend mouth + AiSummaryCard                 |
| Giorno 7   | LaunchAgent + rollout standard tier + Telegram alert |

**Phase 1 complete: 7 giorni di lavoro effettivo.**

---

## Decisioni acquisite (2026-05-16)

1. **Selezione 5 VIP per pilot**: Antonello indica `client_id` al Giorno 5 (sign-off prima di flip `dry_run=false`)
2. **Chrome profile**: profilo Workspace `zero@balizero.com`, PIN sessione `010719` (auth persistente in `~/.config/google-chrome/CRM-Guardian/`). PIN gestito via macOS Keychain (`security find-generic-password -s "crm-guardian-chrome-pin"`), MAI in env vars o repo.
3. **Re-extraction tax_records**: AGGRESSIVA — quando qualunque file in cartella company cambia, re-estraggo `tax_records` + `lkpm_history` from scratch. No cache 7gg. Trade-off accettato: più Playwright calls vs freschezza garantita
4. **Narrative**: SOLO `narrative_en` (inglese). Rimuovere `narrative_id` dallo schema L1 v2 — inglese sempre, anche per UI italiana

---

**Next action**: creare branch `feat/crm-guardian-phase1-activation`, partire da Giorno 1 (schema L1 v2 + prompt v2).
