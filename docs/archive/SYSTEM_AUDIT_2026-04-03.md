# Nuzantara System Audit — 2026-04-03 (Consolidated Round 1+2)

> 10 esploratori paralleli, 2 round di analisi, copertura 100% monorepo

---

## 1. MAPPA DEL SISTEMA

| Layer                 | Conteggio                                           |
| --------------------- | --------------------------------------------------- |
| Backend services      | 40 directory, 345 file Python                       |
| Backend routers       | 110 file, 42,549 LOC totali                         |
| Pydantic models       | 60+ file con definizioni inline                     |
| SQL queries raw       | 1,664 occorrenze in 292 file                        |
| MCP tools             | 118 (105 main + 13 advanced)                        |
| MCP chains            | 8 workflow deterministici                           |
| Frontend apps         | 8 Next.js (mouth + 7 satellite)                     |
| Frontend components   | 200+ in mouth, ~19,500 LOC duplicati                |
| Qdrant collections    | 10 live (~93K documenti)                            |
| DB migrations         | 79 (001→079)                                        |
| Automazioni totali    | 31+ (14 cron, 6 webhook, 5 background, 6+ CLI)      |
| LLM providers         | 7 configurati, 4 semi-dead in services/llm_clients/ |
| Exception hierarchies | 2 competing (NuzantaraBaseError vs ZantaraError)    |

---

## 2. DUPLICAZIONI E SOVRAPPOSIZIONI — CATALOGO COMPLETO

### A. BACKEND SERVICES

#### A1. Google Drive: 3 implementazioni (58K LOC)

| File                               | Scopo           | LOC  |
| ---------------------------------- | --------------- | ---- |
| `google_drive_service.py`          | OAuth-based     | ~36K |
| `service_account_drive_service.py` | Service Account | ~14K |
| `team_drive_service.py`            | Team Drive      | ~8K  |

**Soluzione:** Factory pattern con `AuthStrategy` pluggabile.

#### A2. Cache: 4 implementazioni

| Impl                     | Backend   | TTL      |
| ------------------------ | --------- | -------- |
| `LRUCache`               | In-memory | 300s     |
| `SemanticCache`          | Redis     | 86400s   |
| `NotebookLMCacheService` | Redis     | 24-72h   |
| Article Composer cache   | Custom    | Variable |

**Soluzione:** `CacheService` unificato con backend pluggabile.

#### A3. Memory: 3 sistemi sovrapposti

- `episodic_memory_service.py` (PostgreSQL)
- `collective_memory_service.py` + LangGraph workflow (PostgreSQL)
- LAM endpoints (PostgreSQL + Qdrant)
  **Soluzione:** Un `MemoryService` con namespace (episodic, collective, long-term).

#### A4. Communication/Routing/Response: 30 file in 3 directory

- `communication/` (7) — language detector, emotion analyzer, formatter
- `routing/` (16) — intelligent router, query router, conflict resolver
- `response/` (7) — response formatter, tone adapter
  **Soluzione:** Consolidare in `communication/` con sotto-moduli.

#### A5. Email: nome fuorviante + duplicato

- `zoho_email_service.py` — usa Brevo, NON Zoho
- `notifications/service.py` — altra implementazione email
  **Soluzione:** Rinominare + unificare.

#### A6. GenAIClient morto (SCAR attiva)

- `GenAIClient` manca `create_chat` → `followup_service.py` fallisce silenziosamente
  **Soluzione:** Eliminare, migrare a `ZantaraAIClient`.

#### A7. Exception hierarchy: 2 sistemi in competizione

| File                                       | Base Class           | Classi        |
| ------------------------------------------ | -------------------- | ------------- |
| `backend/core/exceptions.py` (380 LOC)     | `NuzantaraBaseError` | 20+ eccezioni |
| `backend/app/core/exceptions.py` (210 LOC) | `ZantaraError`       | 10+ eccezioni |

**Duplicati:** `ResourceNotFoundError`, `ValidationError`, `DatabaseError` definiti in entrambi.
**Soluzione:** Consolidare in `backend/core/exceptions.py`, eliminare `app/core/exceptions.py`.

#### A8. CRM Models: 2 definizioni separate

- `backend/services/crm/models.py` (service layer)
- `backend/app/modules/crm/models.py` (app layer)
- `backend/app/modules/crm/company_models.py` (separato)
  **Soluzione:** Un solo `backend/schemas/crm.py`.

#### A9. LLM Clients: 4 semi-dead in services/

| File in services/llm_clients/ | Status                                      |
| ----------------------------- | ------------------------------------------- |
| `deepseek_client.py`          | SEMI-DEAD — no production usage             |
| `gemini_service.py`           | SEMI-DEAD — Gemini via genai_client wrapper |
| `openrouter_client.py`        | SEMI-DEAD — no production usage             |
| `vertex_ai_service.py`        | SEMI-DEAD — no production usage             |

**Nota:** LLM gia astratti sotto `backend/llm/`. Questi sono layer aggiuntivi inutili.
**Soluzione:** Eliminare services/llm_clients/, usare solo backend/llm/.

#### A10. Stub/Dead Services in misc/

| File                            | Status     | Motivo                             |
| ------------------------------- | ---------- | ---------------------------------- |
| `context_suggestion_service.py` | STUB       | Ritorna `[]` sempre                |
| `personality_service.py`        | DEAD       | Referenza Oracle Cloud inesistente |
| `context_window_manager.py`     | SEMI-DEAD  | Definito ma mai istanziato         |
| `mcp_client_service.py`         | INCOMPLETE | Sezioni commentate, non funzionale |

**Soluzione:** Eliminare i 3 dead, completare o eliminare mcp_client.

#### A11. Social/X: codice morto

- `x_monitor_service.py` — X broken (CRC fail, 403 ogni 5min)
- Router `x_monitor.py` + `twitter.py` — ancora registrati ma non funzionali
  **Soluzione:** Rimuovere dai router registrati fino a fix.

### B. BACKEND ROUTERS — Frammentazione Critica

#### B1. CRM: 11 router (!) per un dominio

| Router                    | LOC   | Endpoints |
| ------------------------- | ----- | --------- |
| crm_practices.py          | 2,016 | 25+       |
| crm_enhanced.py           | 1,382 | 18        |
| crm_clients.py            | 1,151 | 20+       |
| crm_clients_documents.py  | 948   | 8         |
| crm_enhanced_documents.py | 789   | 8         |
| crm_interactions.py       | 778   | 15        |
| crm_shared_memory.py      | 754   | 6         |
| crm_portal_integration.py | 570   | 8         |
| crm_analytics.py          | 493   | 15        |
| crm_company.py            | ~300  | 5+        |
| crm_notifications.py      | ~200  | 4+        |

**Totale: ~8,400 LOC, 130+ endpoint**
**Soluzione:** Consolidare in 4 router: clients, practices, documents, analytics.

#### B2. Portal: 8 router

portal.py, portal_visa.py, portal_taxes.py, portal_billing.py, portal_drive.py, portal_invite.py, portal_notifications.py, portal_process_timeline.py
**Problema:** portal.py ha gia `/visa` e `/taxes` → duplicati con portal_visa.py e portal_taxes.py.
**Soluzione:** 2 router: portal.py (main) + portal_integrations.py (drive, billing).

#### B3. Agent: 5 router con naming confuso

- `agent.py` (LangGraph) vs `agents.py` (custom) vs `agentic_rag.py` (RAG) vs `autonomous_agents.py` (scheduler) vs `autonomous_execution.py` (plans)
  **Soluzione:** 2-3 router: agent_langraph.py, agent_autonomous.py, agent_execution.py.

#### B4. Team: 5 router con endpoint duplicato

- `team.py` → `GET /members`
- `team_members.py` → `GET /members` **STESSO PATH!**
- team_activity.py, team_drive.py, team_analytics.py
  **Soluzione:** 2 router: team.py (members + activity), team_resources.py (drive + analytics).

#### B5. Admin Drive: 4 router per un servizio

admin_drive_auth.py, admin_drive_health.py, admin_drive_refresh.py, admin_drive_setup.py
**Soluzione:** 1 router: admin_google_drive.py.

#### B6. Analytics: triple duplicazione

| Router            | Prefix              | Scope         |
| ----------------- | ------------------- | ------------- |
| analytics.py      | /api/analytics      | Company-wide  |
| crm_analytics.py  | /api/crm/analytics  | CRM-specific  |
| team_analytics.py | /api/team/analytics | Team-specific |

**Overlap:** Completion rates, revenue metrics calcolati in tutti e 3.
**Soluzione:** 1 router con scope parameter: `GET /api/analytics?scope=company|crm|team`.

#### B7. Oracle/KBLI: 4 router mergeable

oracle_universal.py, oracle_ingest.py, kbli_notebook.py, kbli_notebook_chat.py
**Bonus:** oracle_universal.py contiene `/drive/test` e `/gemini/test` (debug in produzione!).
**Soluzione:** 2 router: oracle.py, kbli.py. Spostare test endpoint in debug.py.

#### B8. Business logic nei router (PATTERN CRITICO)

- **crm_enhanced.py:** 150+ righe di OCR con 3-tier fallback (Ollama→Gemini CLI→Gemini API)
- **analytics.py:** `calculate_completion_rate()` inline
- **crm_clients.py:** Entity resolution/dedup logic inline
- **kbli_notebook_chat.py:** 1,306 LOC per 1 solo endpoint
  **Soluzione:** Estrarre in service layer (`ocr_service.py`, `analytics_service.py`).

#### B9. Codice disabilitato/morto nei router

- `whatsapp_chat.alias_router` — commentato in router_registration.py
- `x_monitor.py` + `twitter.py` — registrati ma broken
  **Soluzione:** Rimuovere, non commentare.

**Riepilogo router:** Da 110+ → ~55 router (50% reduction), ~7,200 LOC risparmiati.

### C. FRONTEND — Duplicazioni Verificate Character-by-Character

#### C1. UI Components: 100% identici across app

| Component  | mouth     | drive     | knowledge | Status                     |
| ---------- | --------- | --------- | --------- | -------------------------- |
| button.tsx | 63 righe  | 63 righe  | 63 righe  | **byte-for-byte identico** |
| badge.tsx  | 37 righe  | 37 righe  | —         | **identico**               |
| dialog.tsx | 123 righe | 123 righe | —         | **identico**               |
| input.tsx  | 22 righe  | 21 righe  | —         | ~95% simile                |

**Totale stimato:** ~750 LOC di primitivi UI duplicati x3 app.
**Soluzione:** `packages/core/components/ui/`.

#### C2. SSO Middleware: 95%+ identico (solo dominio cambia)

```typescript
// Identico in drive, mail, knowledge, calendar:
const token = request.cookies.get('nz_access_token');
if (!token?.value) {
  return NextResponse.redirect(`https://kita.balizero.com/login?redirect=...`);
}
```

**Soluzione:** `packages/frontend-core/middleware.ts` con factory.

#### C3. API Client: 70% trasporto duplicato

- drive/api.ts (462 LOC), mail/api.ts (279 LOC), knowledge/api.ts (168 LOC)
- Token extraction identico (stessa regex per cookie)
- CSRF handling identico
- Solo i metodi domain-specific differiscono
  **Soluzione:** `packages/frontend-api/client.ts` base class.

#### C4. KBLI: split architetturale critico (~15,000 LOC duplicati)

| Aspetto        | mouth     | kbli-navigator   |
| -------------- | --------- | ---------------- |
| Pagine         | 1,600 LOC | 10,883 LOC       |
| Componenti     | 1,887 LOC | 1,920 LOC        |
| KBLICard.tsx   | presente  | ~98% equivalente |
| KBLISearch.tsx | presente  | ~98% equivalente |
| 8+ componenti  | presenti  | duplicati        |

**Problema:** Due app con stessi componenti KBLI, quote style diverso.
**Soluzione:** Decidere quale e source of truth, eliminare l'altro.

#### C5. @nuzantara/core: esiste ma NESSUNA app lo importa

- Design token package creato ma mai usato
- Ogni app mantiene il proprio sistema colori via CSS variables
  **Soluzione:** Attivare packages/core come vero shared package.

#### C6. tsconfig drift

- drive: ES2017 (outdated), mouth: ES2022, altri: ES2020
  **Soluzione:** Unificare a ES2020 minimum.

#### C7. Chat: 2 implementazioni in mouth

- `components/chat/` (3,307 LOC, 17 componenti) — workspace chat
- `portal/(authenticated)/chat/page.tsx` (588 LOC) — portal chat
- `web/src/` — terza implementazione (atoms/molecules)
  **Soluzione:** Estrarre chat widget condiviso.

### D. AUTOMAZIONI — Overlap Confermati

#### D1. Renewal/Expiry: RACE CONDITION (CRITICO)

| Location                                | Thresholds                    | Output                            |
| --------------------------------------- | ----------------------------- | --------------------------------- |
| crm_automation_engine.py:349-403        | 7/30/60/90 giorni             | renewal_alerts table              |
| chain_compliance_autopilot:940-1064     | 7/30/60/90 giorni (identici!) | renewal practices + notifications |
| proactive_compliance_monitor.py:296-328 | In-memory monitoring loop     | ComplianceAlert objects           |

**RISCHIO:** Se entrambi girano contemporaneamente → record duplicati + notifiche duplicate al cliente.
**Soluzione:** Un solo `renewal_checker.py` con dedup lock, chiamato da entrambi i trigger.

#### D2. Stale Practice Detection: 2 implementazioni con threshold diversi

| Location                               | Thresholds                                            |
| -------------------------------------- | ----------------------------------------------------- |
| crm_automation_engine.py:409-449       | inquiry:14d, pending:14d, in_progress:10d, active:30d |
| chain_practice_lifecycle_check:428-597 | waiting_documents:7d, submitted:14d                   |

**Diversi ma complementari.** Unificare con config di threshold.

#### D3. Daily Reports: 2 report allo stesso destinatario

| Report                    | Schedule          | Channel  | Destinatario |
| ------------------------- | ----------------- | -------- | ------------ |
| crm_automation digest     | 07:00 daily       | Telegram | Zero         |
| chain_daily_ops_autopilot | Daily (on demand) | Email    | Zero         |

**Soluzione:** Unificare in un unico daily report multi-canale.

#### D4. Client Onboarding: 2 approcci diversi

- `chain_new_client_onboarding` — one-shot 8-step setup
- `chain_journey_accelerator` — template-based journey con tracking
  **Nota dal Round 2:** Questi sono **intenzionalmente diversi** (one-shot vs tracked journey).
  Documentare quando usare quale.

#### D5. Sentinel + System Doctor: overlap parziale (NON totale)

**Round 2 corregge Round 1:** L'overlap e principalmente su Postgres connectivity check.

- Sentinel: real-time (60s), 4-tier recovery
- System Doctor: daily snapshot, auto-fix + report
  **Soluzione rivista:** Non merge completo, ma estrarre check comuni in `health_checks.py` importato da entrambi.

### E. MCP TOOLS

#### E1. Qdrant metrics duplicato

- `get_qdrant_metrics()` (main) = `get_collection_stats()` (advanced)
  **Soluzione:** Rimuovere da advanced.

#### E2. mcp-browser: directory vuota

Solo `.ruff_cache/`, nessun codice.
**Soluzione:** Eliminare.

### F. DATA MODEL — Pattern Scoperti nel Round 2

#### F1. Pydantic models inline nei router (60 file)

Ogni router definisce i propri `Request`/`Response` models inline.
**shared-schemas package esiste ma NON e usato dal backend** (0 import trovati).
**Soluzione:** Spostare models in `backend/schemas/` organizzati per dominio.

#### F2. SQL scattered senza Repository pattern (1,664 occorrenze)

- "get client by id" scritto in 15+ modi diversi in file diversi
- "get practices by client" in 8 file
- Nessun repository layer
  **Soluzione:** Creare `backend/repositories/` (client, practice, memory, compliance).

#### F3. Costanti hardcoded in 40+ location

- Collection names (legal_unified_hybrid, balizero_news, etc.)
- Google Drive folder IDs
- Redis key prefixes inconsistenti
- Admin email addresses
- External API URLs
  **Soluzione:** `backend/core/constants.py` organizzato per dominio.

#### F4. Redis key naming inconsistente

- `zantara:*` — main namespace
- `nuzantara:scheduler:lock:*` — scheduler
- Nessuno standard
  **Soluzione:** Standard: `zantara:<domain>:<entity>:<action>:<id>`.

#### F5. Collection registry parzialmente usato

`collection_registry.py` esiste ma non tutti i servizi lo usano — nomi hardcoded ovunque.
**Soluzione:** Enforce usage, grep + fix tutti i nomi hardcoded.

---

## 3. PIANO D'AZIONE CONSOLIDATO

### Fase 0 — Pulizia Immediata (2-3 ore)

Zero rischio, zero dipendenze.

| #   | Azione                                                            | Effort | Impatto            |
| --- | ----------------------------------------------------------------- | ------ | ------------------ |
| 0a  | Eliminare `context_suggestion_service.py` (stub, returns [])      | 5min   | -1 dead file       |
| 0b  | Eliminare `personality_service.py` (Oracle Cloud inesistente)     | 5min   | -1 dead file       |
| 0c  | Eliminare `apps/nuzantara-mcp-browser/` (vuoto)                   | 5min   | -1 dead dir        |
| 0d  | Rimuovere X/Twitter routers da registration (broken)              | 15min  | -2 dead routes     |
| 0e  | Rimuovere `whatsapp_chat.alias_router` commentato                 | 5min   | Clean code         |
| 0f  | Eliminare `team_members.py` (duplica team.py /members)            | 30min  | -1 duplicate       |
| 0g  | Rimuovere `get_collection_stats()` da MCP advanced (duplica main) | 15min  | -1 duplicate tool  |
| 0h  | Rimuovere codice intel da `autonomous_scheduler.py`               | 30min  | -1 phantom trigger |

**Totale: ~2 ore. Risultato: -8 dead items, 0 rischio.**

### Fase 1 — Quick Wins (1 giorno)

Fix strutturali semplici.

| #   | Azione                                                             | Effort | Impatto                 |
| --- | ------------------------------------------------------------------ | ------ | ----------------------- |
| 1a  | Eliminare `GenAIClient`, migrare followup_service                  | 1h     | Fix SCAR, -1 dead class |
| 1b  | Rinominare `zoho_email_service.py` → `email_service.py`            | 1h     | Chiarezza               |
| 1c  | Consolidare exception hierarchy (keep core/, delete app/core/)     | 1h     | -1 competing system     |
| 1d  | Eliminare `services/llm_clients/` (4 semi-dead files)              | 30min  | -4 dead files           |
| 1e  | Estrarre SSO middleware → `packages/frontend-core/`                | 2h     | -3 duplicati            |
| 1f  | Estrarre API client base → `packages/frontend-api/`                | 3h     | -3 duplicati            |
| 1g  | Spostare test endpoints (`/drive/test`, `/gemini/test`) → debug.py | 30min  | Clean production        |

**Totale: ~1 giorno. Risultato: -12 duplicazioni, -2 SCAR.**

### Fase 2 — Consolidamenti Backend (2 settimane)

| #   | Azione                                                | Effort | Impatto                  |
| --- | ----------------------------------------------------- | ------ | ------------------------ |
| 2a  | Unificare Drive services (Factory + AuthStrategy)     | 2d     | -2 file, -20K LOC        |
| 2b  | Unificare Cache (CacheService + pluggable backend)    | 1.5d   | -3 impl, consistenza TTL |
| 2c  | Consolidare communication/routing/response            | 2d     | -15 file                 |
| 2d  | Merge Memory services (un MemoryService, 3 namespace) | 1.5d   | -2 API                   |
| 2e  | Unificare renewal checker (dedup lock!)               | 1d     | Fix race condition       |
| 2f  | Parametrizzare CRM Automation daily/weekly            | 1d     | Elimina Judgement Day    |
| 2g  | Estrarre health checks comuni (Sentinel + Doctor)     | 1d     | -duplicated checks       |
| 2h  | Frontend UI components → packages/core/components     | 2d     | -750+ LOC duplicati      |

**Totale: ~2 settimane. Risultato: -50K+ LOC, fix race condition critico.**

### Fase 3 — Router Consolidation (2 settimane)

| #   | Azione                                                        | Effort | Impatto                    |
| --- | ------------------------------------------------------------- | ------ | -------------------------- |
| 3a  | CRM: 11 router → 4 (clients, practices, documents, analytics) | 3d     | -7 router, -3K LOC         |
| 3b  | Portal: 8 router → 2 (main, integrations)                     | 2d     | -6 router                  |
| 3c  | Agent: 5 router → 3 (langraph, autonomous, execution)         | 2d     | -2 router, chiarezza       |
| 3d  | Admin Drive: 4 router → 1                                     | 1d     | -3 router                  |
| 3e  | Analytics: 3 router → 1 unificato con scope                   | 1.5d   | -2 router, end duplication |
| 3f  | Oracle/KBLI: 4 router → 2                                     | 1d     | -2 router                  |
| 3g  | Estrarre business logic da router a service layer             | 3d     | 2K+ LOC migrati            |
| 3h  | Creare backend/schemas/ per Pydantic models                   | 2d     | Modelli centralizzati      |

**Totale: ~2 settimane. Risultato: da 110 a ~55 router (-50%).**

### Fase 4 — Miglioramenti Architetturali (ongoing)

| #   | Azione                                                   | Effort | Impatto                       |
| --- | -------------------------------------------------------- | ------ | ----------------------------- |
| 4a  | RBAC Framework declarativo (`@require_permission()`)     | 3d     | -200+ righe boilerplate       |
| 4b  | OpenAPI-driven type generation per frontend              | 3d     | Zero type drift               |
| 4c  | Creare `backend/repositories/` (Repository pattern)      | 1w     | -200+ SQL duplicati           |
| 4d  | `backend/core/constants.py` centralizzato                | 1d     | -40 hardcoded values          |
| 4e  | Redis key naming standard                                | 1d     | Debugging piu facile          |
| 4f  | Enforce collection_registry usage                        | 1d     | Nomi collection centralizzati |
| 4g  | EventBus fix su Fly.io                                   | 2d     | Real-time reactions           |
| 4h  | KBLI: decidere source of truth (mouth vs kbli-navigator) | 1d     | -15K LOC duplicati            |
| 4i  | Attivare packages/core come shared package               | 2d     | Frontend unificato            |
| 4j  | Test coverage per automation scripts                     | 2d     | Regression prevention         |

### Fase 5 — Refactor Strategici (quando necessario)

| #   | Azione                                                      | Effort |
| --- | ----------------------------------------------------------- | ------ |
| 5a  | Merge CRM + Journey + Compliance sotto crm/                 | 1w     |
| 5b  | misc/ decomposition completa (29 file → moduli appropriati) | 3d     |
| 5c  | Frontend type system completo da OpenAPI                    | 1w     |
| 5d  | Chat widget condiviso (workspace + portal + web)            | 3d     |

---

## 4. METRICHE DI SUCCESSO

| Metrica                 | Ora     | Dopo F0+F1 | Dopo F2+F3 | Target        |
| ----------------------- | ------- | ---------- | ---------- | ------------- |
| Router backend          | 110     | 107        | ~55        | <60           |
| File duplicati          | ~45     | ~30        | ~8         | <5            |
| Dead code files         | 12      | 0          | 0          | 0             |
| LOC router              | 42,549  | 41,500     | ~25,000    | <25K          |
| Frontend duplicated LOC | ~19,500 | ~18,000    | ~3,000     | <1K           |
| Cache implementations   | 4       | 4          | 1          | 1             |
| Drive implementations   | 3       | 3          | 1          | 1             |
| Memory APIs             | 3       | 3          | 1          | 1             |
| Exception hierarchies   | 2       | 1          | 1          | 1             |
| SCAR risolvibili        | 2       | 0          | 0          | 0             |
| Renewal race condition  | YES     | YES        | NO         | NO            |
| SQL pattern duplicati   | 200+    | 200+       | 200+       | <20 (post F4) |

---

## 5. CORREZIONI AL ROUND 1

| Finding Round 1                              | Correzione Round 2                                                                                     |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "misc/ 29 file, molti potenzialmente morti"  | Solo 3 dead (context_suggestion, personality, context_window_manager), 2 incomplete. Il resto e ALIVE. |
| "emotional_attunement.py raramente usato"    | ALIVE — esportato in **all**, usato per tone detection                                                 |
| "whatsapp_context_builder.py forse superato" | Non verificato come dead — potrebbe essere alive                                                       |
| "Sentinel + Doctor: merge completo"          | Overlap solo parziale (Postgres check). Meglio estrarre checks comuni, non merge completo.             |
| "Frontend middleware 4x identico"            | Confermato 95%+ identico (character-by-character verified)                                             |
| "UI components duplicati"                    | Confermato 100% byte-for-byte identici (button, badge, dialog)                                         |
| "shared-schemas package"                     | Esiste ma 0 import dal backend — completamente inutilizzato                                            |

---

## 6. FINDINGS NUOVI DAL ROUND 2 (non nel Round 1)

| #   | Finding                             | Severita | Dettaglio                                                        |
| --- | ----------------------------------- | -------- | ---------------------------------------------------------------- |
| N1  | **Renewal race condition**          | CRITICO  | crm_automation + chain_compliance possono creare duplicati       |
| N2  | **2 exception hierarchies**         | MEDIO    | NuzantaraBaseError vs ZantaraError con classi duplicate          |
| N3  | **1,664 raw SQL in 292 file**       | MEDIO    | Nessun repository pattern, query duplicate 15+ volte             |
| N4  | **60 file con Pydantic inline**     | MEDIO    | Models definiti nei router, non centralizzati                    |
| N5  | **Duplicate /members endpoint**     | ALTO     | team.py e team_members.py: stesso path!                          |
| N6  | **KBLI 15K LOC duplicati**          | ALTO     | mouth e kbli-navigator con stessi componenti                     |
| N7  | **@nuzantara/core mai importato**   | MEDIO    | Package esiste, nessuna app lo usa                               |
| N8  | **150 LOC di OCR in router**        | MEDIO    | Business logic in crm_enhanced.py, non in service                |
| N9  | **Debug endpoints in produzione**   | BASSO    | /drive/test, /gemini/test in oracle_universal.py                 |
| N10 | **4 semi-dead LLM clients**         | BASSO    | services/llm_clients/ ridondante con backend/llm/                |
| N11 | **Constants in 40+ locations**      | MEDIO    | Collection names, Drive IDs, Redis prefixes hardcoded            |
| N12 | **Portal visa/taxes route overlap** | MEDIO    | portal.py ha gia /visa e /taxes, duplicati con portal_visa.py    |
| N13 | **1,306 LOC per 1 endpoint**        | BASSO    | kbli_notebook_chat.py — code smell                               |
| N14 | **Daily reports duplicati**         | BASSO    | 2 report giornalieri allo stesso destinatario (Telegram + Email) |

---

_Report generato: 2026-04-03_
_Round 1: 5 esploratori (backend, MCP, automazioni, frontend, data layer)_
_Round 2: 5 esploratori profondi (router overlap, misc triage, automation overlap, frontend character-by-character, data model/config)_
_Copertura: 100% del monorepo — 345 service files, 110 router files, 8 frontend apps, 31 automazioni_
