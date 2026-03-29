# CRM Strategy Brainstorm — Bali Zero

> **Data:** 2026-03-30
> **Autore:** Claude Code (Opus 4.6) — 4 agenti di esplorazione paralleli
> **Scope:** Frontend CRM (`kita.balizero.com/clients`), sinergia Portal + HR
> **Codebase:** 42+ file CRM frontend, 11 backend routers, 90+ endpoint, 5000+ clienti

---

## 1. Analisi Stato Attuale

### Cosa Funziona Bene

**Architettura solida.** Il CRM è un sistema maturo con 4 route principali (`/clients`, `/clients/new`, `/clients/[id]`, `/clients/analytics`), 8 tab nel dettaglio client, un layer API completo (`CrmApi` — 1231 righe, 65+ metodi), e pattern consistenti per CRUD, modali e feedback visivo.

**Client list performante.** La pagina lista usa React Query (`useCrmClients`) con infinite scroll virtualizzato (`@tanstack/react-virtual`), `React.memo` con comparator custom su `ClientCard`, e debounced search (300ms). Regge bene i 5000+ record.

**OCR pipeline sofisticato.** 3 livelli di fallback (Ollama qwen2.5vl:7b → Gemini CLI → Gemini API) per passaporti, NPWP, NIB, visti. Auto-trigger su upload documento via `_dispatch_ocr_by_folder()`.

**Status-driven automation.** Ogni transizione di stato practice scatena automazioni: email clienti (`WaitingDocumentsService`), generazione fattura PDF (`InvoiceAutomationService`), alert rinnovo, bonus HR. Pattern `asyncio.create_task()` non-bloccante.

**Warm Depth design coerente.** Token CSS custom (`--bz-base: #0c0c0e`, `--bz-accent: #d4845a`, `--bz-surface`, `--bz-card`). Empty states con dashed-border + icona + CTA. Sonner toast per conferma azioni distruttive.

**CompanyTab editoriale.** Layout magazine-style con `EditorialHero`, `LegalTimeline`, `KBLIEditorial`, `FactBoxes` — la migliore UX del CRM, benchmark per le altre tab.

**Google Drive integration.** Struttura cartelle standardizzata (00_Profile → 99_Misc), upload diretto, folder stats, bulk population completata per 984 clienti.

**Lead Assignment Agent.** LangGraph 3-step: entity resolution (dedup email/phone/passport) → specialty + workload-based assignment → Telegram notification con inline keyboard.

### Cosa Non Funziona

**Detail page monolitica.** `[id]/page.tsx` è 977 righe con state management manuale (`useState` + `Promise.all`), nessun React Query, nessun refetch automatico su window focus. Ogni tab riceve `refreshProfile()` come prop — accoppiamento forte.

**Team members hardcoded in 3 posti.** Array `TEAM_MEMBERS` duplicato in `new/page.tsx:44`, `constants.ts:63`, e `EditClientModal.tsx`. Ogni cambio team richiede modifica manuale + deploy.

**RBAC inconsistente.** Backend: `is_crm_admin()` ritorna `true` per TUTTI i team member (`role != "client"`), vanificando la distinzione. Frontend: hardcoded email sets. Endpoint documents e interactions hanno commento `// RBAC REMOVED`. `GET /expiry-alerts/summary` non ha auth.

**TaxTab è scaffold vuoto.** Definisce tipi locali (`PersonalTaxData`, `AnnualCompanyTaxData`) ma zero integrazione API. I `TaxRecord` e `TaxDocument` nel backend non hanno router CRM dedicato — solo portal.

**Table view non implementata.** Il pulsante Table2 nel toolbar lista cambia `viewMode` state ma non renderizza nulla. Feature visibile ma rotta.

---

## 2. Pain Points & Gap

### P0 — Bug e Rischi di Sicurezza

| #   | Problema                                                                                                                                      | File                                  | Impatto                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ---------------------------------------- |
| 1   | `GET /expiry-alerts/summary` **senza autenticazione** — espone conteggi alert                                                                 | `crm_enhanced_alerts.py:71`           | Leak dati aggregati                      |
| 2   | Soft delete client imposta `status='inactive'` ma **non scrive `deleted_at`** — il filtro `WHERE deleted_at IS NULL` non esclude i cancellati | `crm_clients.py:739-748`              | Clienti "cancellati" riappaiono in lista |
| 3   | OCR background tasks **creano pool asyncpg transienti** (min=1, max=2, poi chiudono) — viola Golden Rule #11, connection churn sotto carico   | `crm_enhanced.py:230-235`             | Pool exhaustion su Fly.io 2GB            |
| 4   | `company_name` su `clients` e `companies` **non sincronizzato** — display inconsistente                                                       | `crm_clients.py`, `company_router.py` | Confusione utente                        |
| 5   | **Vault route mancante dalla portal navigation** — `/portal/vault` esiste ma non appare nella sidebar                                         | `navigation.ts:98`                    | Feature invisibile al cliente            |
| 6   | Company detail back button **routes a `/portal/vault`** su errore — dovrebbe essere `/portal/companies`                                       | `company/[id]/page.tsx:120`           | UX rotta                                 |

### P1 — Gap Funzionali

| #   | Gap                                                                                                           | Dettaglio                                                                 | File di riferimento                              |
| --- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------ |
| 7   | **Tab URL non sincronizzati** — switch tab non aggiorna `?tab=`, deep link funziona solo al primo caricamento | `[id]/page.tsx` — useState senza router.replace                           | Non si possono condividere link a tab specifiche |
| 8   | **Nessun table view** nella lista client — pulsante presente, rendering assente                               | `clients/page.tsx` — no branch per `viewMode === 'table'`                 | Feature promessa ma non consegnata               |
| 9   | **TaxTab vuota** — scaffold frontend senza API                                                                | `TaxTab.tsx` + assenza router CRM per tax_records                         | Intero dominio fiscale mancante dal CRM          |
| 10  | **Nessuna operazione bulk** — no bulk update, bulk assignment, bulk export                                    | Assenza endpoint `/api/crm/clients/bulk`                                  | Operazioni su 5000+ clienti impossibili          |
| 11  | **Nessun export CSV/Excel** per revenue, client list, analytics                                               | Assenza endpoint export                                                   | Team operativo deve screenshottare analytics     |
| 12  | **Duplicate detection solo a constraint SQL** — no fuzzy pre-check                                            | `client_identity_resolver.py` esiste ma non è chiamato da create endpoint | Duplicati creati e scoperti tardi                |
| 13  | **Portal messaging senza push** — polling 30s sia CRM che Portal, nessun WebSocket/SSE                        | `PortalMessages.tsx`, `chat/page.tsx`                                     | Latenza fino a 30s su messaggi urgenti           |
| 14  | **N+1 team performance** — 4 query × N team member nel loop Python                                            | `crm_analytics.py:214-270`                                                | Endpoint lento con team crescente                |
| 15  | **N+1 company associates** — COUNT separato per ogni company                                                  | `company_router.py:93-98`                                                 | Lento su lista companies                         |

### P2 — Debito Tecnico

| #   | Debito                                                                                                         | File                                                           |
| --- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| 16  | Detail page non usa React Query — no cache condivisa, no refetch automatico, prop drilling di `refreshProfile` | `[id]/page.tsx`                                                |
| 17  | Logica expiry duplicata in 4 componenti con threshold diversi (≤30 vs ≤90 per "warning")                       | `PassportCard`, `ImmigrationTab`, `ProcessTab`, `DocumentsTab` |
| 18  | `formatDate`/`formatTime` passati come props a 8 tab — dovrebbero essere hook o utility                        | `[id]/page.tsx:211-230`                                        |
| 19  | Analytics types definiti localmente invece che in `crm.types.ts`                                               | `analytics/page.tsx`                                           |
| 20  | `onRefresh` tipo inconsistente (`() => void` vs `() => Promise<void>`) tra tab                                 | Vari tab components                                            |
| 21  | OCR auto-trigger su PassportCard si riattiva al remount (ref non persistente)                                  | `PassportCard.tsx`                                             |
| 22  | Portal passport/birthday logic duplicata identica in dashboard e profile                                       | `portal/dashboard/page.tsx`, `portal/profile/page.tsx`         |
| 23  | `audit_logger.py` importa `unittest.mock.MagicMock` in produzione                                              | `audit_logger.py:12`                                           |
| 24  | Month arithmetic con `timedelta(days=i*30)` — boundary errate                                                  | `crm_analytics.py:322-327`                                     |
| 25  | LKPM submit manda `client_id: 0` come sentinel — nessuna safety compile-time                                   | `lkpm/submit/page.tsx:151`                                     |

---

## 3. Miglioramenti Proposti

### P0 — Critici (settimana 1-2)

**P0.1 — Fix security: auth su expiry-alerts/summary**
Aggiungere `current_user: dict = Depends(get_current_user)` all'endpoint. Una riga.

**P0.2 — Fix soft delete: scrivere deleted_at**
In `DELETE /clients/{client_id}`, aggiungere `deleted_at = NOW()` al UPDATE. Allineare il filtro.

**P0.3 — Migrare OCR tasks al pool condiviso**
Passare `db_pool` come argomento ai background task OCR invece di creare pool transienti. Pattern: `asyncio.create_task(_auto_ocr_passport(pool, ...))`.

**P0.4 — Fix portal navigation: aggiungere Vault + fix company back button**
Due edit puntuali in `navigation.ts` e `company/[id]/page.tsx`.

**P0.5 — Tab URL sync**
In `[id]/page.tsx`, quando `setActiveTab(tab)` → `router.replace(\`?tab=${tab}\`, { scroll: false })`. Mantiene deep link funzionante.

### P1 — Importanti (settimane 3-6)

**P1.1 — Table view per client list**
Implementare `DataTable` con colonne: nome, email, nazionalità, status, assigned_to, passport expiry, last interaction. Sorting server-side, selezione righe per bulk actions.

**P1.2 — Bulk operations backend + frontend**

- `POST /api/crm/clients/bulk-update` — status change, re-assignment
- `POST /api/crm/clients/bulk-export` — CSV/Excel via streaming
- Frontend: checkbox su DataTable, action bar sticky

**P1.3 — TaxTab: wiring completo**

- Nuovo router `crm_tax.py` che espone `tax_records` e `tax_documents` per client/company
- Frontend: collegare i tipi già definiti in TaxTab alle nuove API
- Sincronizzare con portal tax view per coerenza dati

**P1.4 — Detail page su React Query**
Migrare `[id]/page.tsx` da `Promise.all` + `refreshProfile()` a:

- `useQuery(['client', id], () => api.crm.getClientProfile(id))`
- `queryClient.invalidateQueries(['client', id])` nelle mutazioni
- Rimuovere prop drilling di `onRefresh` — ogni tab chiama `invalidateQueries` direttamente

**P1.5 — Team members da API**

- Endpoint `GET /api/team/members` (già presente come `GET /api/hr/employees` per admin)
- Rimuovere array `TEAM_MEMBERS` hardcoded dai 3 file
- Dropdown "assigned to" carica da API con cache 5min

**P1.6 — RBAC database-driven**
Migrare da email hardcoded a tabella `team_permissions`:

```sql
CREATE TABLE team_permissions (
    team_member_id VARCHAR(36) REFERENCES team_members(id),
    permission VARCHAR(50), -- 'crm_admin', 'crm_view_all', 'hr_admin', etc.
    granted_by VARCHAR(255),
    granted_at TIMESTAMPTZ DEFAULT NOW()
);
```

Ri-abilitare RBAC sugli endpoint documents/interactions dove è stato rimosso.

**P1.7 — Duplicate detection pre-create**
Chiamare `client_identity_resolver.py` in `POST /clients/` prima dell'inserimento. Se match fuzzy >0.85 → warning con opzione merge. Frontend: modal di conferma "Possibile duplicato trovato: [nome, email]".

**P1.8 — Fix N+1 queries**

- Team performance: singola query `GROUP BY assigned_to` con `SUM`, `COUNT`, `CASE WHEN`
- Company associates: `LEFT JOIN client_company_links` con `COUNT` nella query lista

**P1.9 — Export CSV/Excel**

- `GET /api/crm/clients/export?format=csv&filters=...` — streaming response
- `GET /api/crm/analytics/revenue/export?format=xlsx` — openpyxl
- Frontend: pulsante "Export" nella toolbar analytics e client list

### P2 — Nice-to-Have (settimane 7-12)

**P2.1 — Shared expiry utility**
Estrarre `getExpiryStatus(date, thresholds)` in `utils.ts` condiviso tra CRM e Portal. Threshold unificati: expired, critical (≤30d), warning (≤90d), ok.

**P2.2 — Real-time messaging con SSE**
Sostituire polling 30s con SSE per Portal messages. Backend: endpoint `GET /api/portal/messages/stream` con `StreamingResponse`. Frontend: `EventSource` in `PortalMessages.tsx` e `chat/page.tsx`.

**P2.3 — Client self-service update requests**
Portal: form strutturato "Request profile update" che crea un portal message con tipo `update_request` + payload JSON dei campi da modificare. CRM: widget "Pending update requests" nell'OverviewTab con approve/reject.

**P2.4 — Drive document preview nel Portal vault**
Esporre `GET /api/portal/drive-files` (subset read-only del Drive folder del client). Vault page mostra file reali oltre ai metadata. Risolvere il TODO in `dashboard/page.tsx:536`.

**P2.5 — Usare hook `useDateFormat` invece di prop drilling**
Creare `hooks/useDateFormat.ts` che gestisce hydration check internamente. Rimuovere `formatDate`/`formatTime` props da tutti i tab.

**P2.6 — AI-powered client insights**
Card nell'OverviewTab: "AI Summary" che chiama backend per un riassunto generato (ultimo contatto, prossime scadenze, sentiment trend, azioni suggerite). Usa Gemini Flash via AI Gateway. `<MessageResponse>` per rendering markdown.

**P2.7 — Kanban per practices (cross-client)**
Vista kanban globale delle practices per status (non per client). Già esiste `ClientKanban` per status client — pattern replicabile per practices. Drag & drop per cambio stato.

---

## 4. Visione UX/UI

### Principi di Design

Il CRM deve evolvere da "database con UI" a **workspace operativo** che anticipa le azioni del team. Il linguaggio visivo Warm Depth è già il fondamento — va esteso con coerenza.

### Palette & Token

```css
/* Già in uso — mantenere */
--bz-base: #0c0c0e; /* sfondo principale */
--bz-accent: #d4845a; /* terracotta — CTA, highlight */
--bz-surface: var(--bz-surface); /* card background */
--bz-card: var(--bz-card); /* card elevated */
--bz-text-1: ...; /* testo primario */
--bz-text-2: ...; /* testo secondario */
--bz-border: ...; /* bordi sottili */

/* Da aggiungere per status semantici */
--bz-status-active: #22c55e; /* green-500 — active, completed */
--bz-status-warning: #f59e0b; /* amber-500 — expiring, pending */
--bz-status-critical: #ef4444; /* red-500 — expired, overdue */
--bz-status-info: #3b82f6; /* blue-500 — in progress */
--bz-status-muted: #71717a; /* zinc-500 — cancelled, archived */
```

### Client List — 3 View Modes (oggi: 2.5)

1. **Grid (esistente)** — `ClientCard` con sentiment ring, passport alert badge. Funziona bene per browsing visuale.

2. **Table (da implementare)** — `DataTable` con:
   - Colonne: avatar+nome, email, nazionalità (flag emoji), status (chip colorato), assigned_to, passport expiry (chip con countdown), last interaction (relative time), active practices count
   - Sorting server-side su tutte le colonne
   - Row selection con checkbox per bulk actions
   - Action bar sticky in basso: "X selected — Assign to... | Change status... | Export"
   - Font: Geist Sans per nomi, Geist Mono per date e ID

3. **Kanban (esistente)** — per status client. Aggiungere count nel header colonna.

### Client Detail — Redesign Tab Experience

**Header fisso** con:

- Avatar + nome + nazionalità flag
- Status chip (con dropdown per cambio rapido)
- "Assigned to" con avatar piccolo + dropdown per re-assegnazione
- Quick actions: Call, WhatsApp, Email, Note (icon buttons)
- Breadcrumb: `Clients / {client_name}`

**Tab bar** con:

- Badge count su tab (es. Documents (12), Messages (3 unread))
- URL sync (`?tab=company`)
- Animazione slide orizzontale tra tab

**OverviewTab redesign:**

- Top row: PassportCard (compatto, non 621 righe) + VisaCard + Quick Stats
- Center: "Recent Activity" timeline (ultime 5 interazioni) + "Upcoming" (prossime scadenze)
- Bottom: AI Insights card (opzionale, P2.6)
- Pattern: card grid 2-3 colonne, responsive a 1 colonna su mobile

**ProcessTab migliorato:**

- Mini-kanban inline per practices del client (drag disabled, solo visual)
- Revenue summary con sparkline per trend
- "Add Practice" button prominente

### Portal — Coerenza Visiva

Il Portal usa gli stessi token Warm Depth. Le aree di miglioramento:

- Dashboard page è 981 righe — estrarre `TeamMemberCard`, `PassportCard`, `VisaProcessCard` in `components/portal/dashboard/`
- Unificare la logica passport/birthday con il CRM via shared utility

---

## 5. Modifiche Backend Necessarie

### Nuovi Endpoint

| Endpoint                                | Metodo | Scopo                                            | Priorità |
| --------------------------------------- | ------ | ------------------------------------------------ | -------- |
| `GET /api/team/members`                 | GET    | Lista team members per dropdown (non-admin safe) | P1       |
| `GET /api/crm/tax/{client_id}`          | GET    | Tax records e documents per client               | P1       |
| `POST /api/crm/tax/{client_id}/records` | POST   | Crea tax record                                  | P1       |
| `POST /api/crm/clients/bulk-update`     | POST   | Bulk status change, re-assignment                | P1       |
| `GET /api/crm/clients/export`           | GET    | CSV/Excel export con filtri                      | P1       |
| `GET /api/crm/analytics/revenue/export` | GET    | Revenue report export                            | P1       |
| `GET /api/crm/practices/kanban`         | GET    | Practices raggruppate per status (cross-client)  | P2       |
| `GET /api/portal/messages/stream`       | GET    | SSE stream per real-time messaging               | P2       |
| `GET /api/portal/drive-files`           | GET    | File Drive del client (read-only)                | P2       |
| `POST /api/portal/update-requests`      | POST   | Richiesta modifica profilo strutturata           | P2       |
| `GET /api/crm/clients/{id}/ai-summary`  | GET    | AI-generated client summary                      | P2       |

### Schema Changes

```sql
-- P1.6: RBAC database-driven
CREATE TABLE team_permissions (
    id SERIAL PRIMARY KEY,
    team_member_id VARCHAR(36) REFERENCES team_members(id) ON DELETE CASCADE,
    permission VARCHAR(50) NOT NULL,
    granted_by VARCHAR(255),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_member_id, permission)
);

-- Permissions: 'crm_admin', 'crm_view_all_practices', 'crm_view_all_clients',
--              'hr_admin', 'portal_manage', 'analytics_export'

-- P2.3: Update requests
ALTER TABLE portal_messages ADD COLUMN message_type VARCHAR(20) DEFAULT 'message';
-- Values: 'message', 'update_request', 'system_notification'
ALTER TABLE portal_messages ADD COLUMN payload JSONB;
-- Per update_request: {"fields": {"passport_expiry": "2027-06-15", "address": "..."}}
```

### Fix Backend Esistente

| Fix                                                   | File                           | Effort             |
| ----------------------------------------------------- | ------------------------------ | ------------------ |
| Aggiungere auth a `expiry-alerts/summary`             | `crm_enhanced_alerts.py:71`    | 1 riga             |
| Scrivere `deleted_at` in soft delete                  | `crm_clients.py:739-748`       | 3 righe            |
| Passare pool condiviso a OCR tasks                    | `crm_enhanced.py:230-235`      | ~20 righe refactor |
| Fix `timedelta(days=i*30)` → `dateutil.relativedelta` | `crm_analytics.py:322-327`     | 5 righe            |
| Rimuovere `import MagicMock` da produzione            | `audit_logger.py:12`           | 1 riga             |
| N+1 team performance → GROUP BY                       | `crm_analytics.py:214-270`     | ~30 righe rewrite  |
| N+1 company associates → LEFT JOIN COUNT              | `company_router.py:93-98`      | ~10 righe          |
| company_name sync client↔company                      | `crm_clients.py` create/update | ~15 righe trigger  |

---

## 6. Punti di Sinergia

### 6.1 CRM ↔ Portal

| Sinergia                                   | Direzione          | Stato                                         | Proposta                                                                                 |
| ------------------------------------------ | ------------------ | --------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Status push in tempo reale**             | CRM → Portal       | Polling 30s/2min                              | SSE stream da mutation endpoint CRM                                                      |
| **Notifiche automatiche su status change** | CRM → Portal       | Assente                                       | Auto-create portal message quando practice → `submitted_to_gov`, `approved`, `completed` |
| **Client update requests**                 | Portal → CRM       | Assente (solo "contact your manager")         | Form strutturato → portal message tipo `update_request` → widget CRM approve/reject      |
| **Drive preview nel Vault**                | CRM → Portal       | CRM ha Drive integration, Portal no           | `GET /api/portal/drive-files` read-only                                                  |
| **Expiry alerts condivisi**                | Backend → entrambi | Logic duplicata in 6 componenti               | Singolo endpoint + utility condivisa                                                     |
| **LKPM approval loop**                     | Portal → CRM       | API esiste (`approveLKPMDraft`) ma nessuna UI | Bottone approve nel portal quarter detail                                                |
| **Required document status feedback**      | CRM → Portal       | Polling                                       | Push notification quando document → `verified`/`rejected`                                |

**Componenti condivisibili CRM↔Portal:**

| Componente           | Attuale                                          | Proposta                                                                      |
| -------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| Passport expiry chip | Duplicato in 6 file con threshold diversi        | `<ExpiryChip date={date} entity="passport" />` in `packages/core/components/` |
| Birthday detection   | Duplicato in 2 file portal + usato in CRM        | `isBirthdayToday(date)` in `packages/core/utils/`                             |
| Status chip practice | 13 stati mirrored tra CRM e Portal               | `<PracticeStatusChip status={status} />` in `packages/core/components/`       |
| Currency formatter   | `formatCurrency` in CRM utils, inline nel Portal | `formatIDR(amount)` in `packages/core/utils/`                                 |

### 6.2 CRM ↔ HR

| Sinergia                         | Direzione                | Stato                                                         | Proposta                                                                |
| -------------------------------- | ------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Bonus automatico**             | CRM → HR                 | ✅ Funzionante (practice completed → bonus ledger)            | Aggiungere alert quando bonus viene skippato (missing config)           |
| **Workload visibility**          | CRM → HR                 | Dati esistono in `dashboard_summary.py` ma non mostrati in HR | Card "Team Workload" in HR admin dashboard                              |
| **Leave impact on CRM**          | HR → CRM                 | Assente                                                       | Mostrare count practices attive quando si approva una leave request     |
| **My CRM performance**           | CRM → HR                 | Assente                                                       | Sezione in `/hr` personal: quali practices hanno generato i miei bonus  |
| **Team capacity per assignment** | CRM+HR → CRM             | Solo nel Lead Assignment Agent (non UI)                       | Widget `/hr/team-capacity` o sidebar CRM con practice count per persona |
| **Employee profile page**        | HR backend → HR frontend | Backend ha CRUD completo, frontend non ha `/hr/employees`     | Implementare pagina gestione dipendenti                                 |
| **Clock-in ↔ Leave**             | Team API → HR            | Sistemi paralleli non connessi                                | Bridge `clock_in/out` con `hr_leave_requests` per coerenza presenze     |

**Componenti condivisibili CRM↔HR:**

| Componente                                     | Proposta                                            |
| ---------------------------------------------- | --------------------------------------------------- |
| `<TeamMemberAvatar email={email} />`           | Avatar + nome da `team_members`, usabile ovunque    |
| `<WorkloadBadge email={email} />`              | Badge con count practices attive, colore per carico |
| `<PracticeMiniKanban practices={practices} />` | Mini kanban read-only, usabile in HR e CRM          |

### 6.3 Componenti Condivisi tra i 3 Domini

```
packages/core/components/
├── ExpiryChip.tsx           — chip con countdown, colore semantico
├── PracticeStatusChip.tsx   — 13 stati con colore + icona
├── TeamMemberAvatar.tsx     — avatar + nome + ruolo da API
├── WorkloadBadge.tsx        — count practices attive
├── CurrencyDisplay.tsx      — formattazione IDR/USD
├── DateDisplay.tsx          — formattazione date con hydration-safe
├── EmptyState.tsx           — dashed-border + icon + CTA (pattern già usato)
└── DataExportButton.tsx     — trigger export CSV/Excel

packages/core/utils/
├── expiry.ts                — getExpiryStatus(date, thresholds)
├── birthday.ts              — isBirthdayToday(date)
├── currency.ts              — formatIDR, formatUSD
└── date.ts                  — formatDate, formatTime, formatRelative
```

---

## 7. Roadmap Implementazione

### Fase 0 — Security & Bug Fix (settimana 1)

_Nessuna dipendenza. Può iniziare subito._

- [ ] Fix auth su `expiry-alerts/summary`
- [ ] Fix soft delete `deleted_at`
- [ ] Fix portal vault navigation + company back button
- [ ] Rimuovere `import MagicMock` da audit_logger
- [ ] Fix `timedelta(days=i*30)`

**Effort:** ~2 ore, 0 rischio, deploy immediato.

### Fase 1 — Foundation (settimane 2-3)

_Blocca Fase 2 (table view dipende da React Query migration)._

- [ ] Migrare OCR tasks al pool condiviso
- [ ] Tab URL sync (`router.replace`)
- [ ] Estrarre shared utilities in `packages/core/utils/` (expiry, birthday, currency, date)
- [ ] Estrarre componenti condivisi in `packages/core/components/` (ExpiryChip, PracticeStatusChip)
- [ ] Team members da API (endpoint + rimuovere hardcoded arrays)
- [ ] Migrare detail page a React Query
- [ ] Fix N+1 queries (team performance + company associates)

**Effort:** ~2 settimane, rischio medio (React Query migration è il pezzo più grande).

### Fase 2 — Core Features (settimane 4-6)

_Dipende da Fase 1 per React Query e shared components._

- [ ] Table view per client list con sorting e selezione
- [ ] Bulk operations (backend + frontend)
- [ ] Export CSV/Excel (backend + frontend)
- [ ] TaxTab wiring (nuovo router + collegamento frontend)
- [ ] Duplicate detection pre-create
- [ ] RBAC database-driven (schema + migration + refactor utils)

**Effort:** ~3 settimane, rischio medio-alto (RBAC migration è il pezzo più delicato).

### Fase 3 — Synergy (settimane 7-9)

_Dipende da Fase 2 per RBAC e shared components._

- [ ] Real-time messaging SSE (Portal + CRM)
- [ ] Auto-notifiche su status change practice
- [ ] Client update requests (Portal → CRM)
- [ ] HR workload visibility (card in HR dashboard)
- [ ] Leave impact display (count practices in leave approval)
- [ ] Employee profile page in HR frontend

**Effort:** ~3 settimane, rischio medio.

### Fase 4 — Polish & Intelligence (settimane 10-12)

_Nessuna hard dependency, può essere parallela a Fase 3._

- [ ] Drive preview nel Portal vault
- [ ] AI client insights card (OverviewTab)
- [ ] Practices kanban cross-client
- [ ] My CRM Performance view in HR
- [ ] Team capacity widget
- [ ] LKPM approval loop UI

**Effort:** ~3 settimane, rischio basso (feature additive).

### Dipendenze Visualizzate

```
Fase 0 (security)
    │
    ▼
Fase 1 (foundation)
    │
    ├──────────────────┐
    ▼                  ▼
Fase 2 (features)  Fase 4 (polish) ← può iniziare in parallelo
    │
    ▼
Fase 3 (synergy)
```

---

## Appendice A — File Chiave per Implementazione

### CRM Frontend

| File                                                   | Righe | Ruolo                            |
| ------------------------------------------------------ | ----- | -------------------------------- |
| `apps/mouth/src/app/(workspace)/clients/page.tsx`      | ~550  | Lista client (grid/kanban/table) |
| `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` | 977   | Detail page orchestrator         |
| `apps/mouth/src/app/(workspace)/clients/new/page.tsx`  | 807   | Wizard creazione                 |
| `apps/mouth/src/lib/api/crm/crm.api.ts`                | 1231  | Layer API completo               |
| `apps/mouth/src/lib/api/crm/crm.types.ts`              | 614   | Type definitions                 |
| `apps/mouth/src/hooks/useCrmClients.ts`                | —     | React Query hooks lista          |
| `apps/mouth/src/components/crm/ClientCard.tsx`         | 432   | Card con memo + sentiment        |

### Portal Frontend

| File                                                         | Righe | Ruolo                       |
| ------------------------------------------------------------ | ----- | --------------------------- |
| `apps/mouth/src/app/portal/(authenticated)/layout.tsx`       | —     | Auth gate + SSO             |
| `apps/mouth/src/lib/api/portal/portal.api.ts`                | —     | API surface portal          |
| `apps/mouth/src/app/portal/(authenticated)/process/page.tsx` | —     | Cross-boundary CRM API call |
| `apps/mouth/src/app/portal/(authenticated)/chat/page.tsx`    | —     | Messaging (polling 30s)     |

### HR Frontend + Backend

| File                                                     | Righe | Ruolo                       |
| -------------------------------------------------------- | ----- | --------------------------- |
| `apps/mouth/src/app/(workspace)/hr/page.tsx`             | —     | Dashboard dual-mode         |
| `apps/mouth/src/lib/api/hr/hr.ts`                        | —     | API client (20 funzioni)    |
| `apps/backend-rag/backend/app/routers/hr.py`             | —     | 18 endpoint                 |
| `apps/backend-rag/backend/app/services/hr/hr_service.py` | —     | Payroll engine + BPJS/PPh21 |

### CRM Backend

| File                                                             | Righe | Ruolo                            |
| ---------------------------------------------------------------- | ----- | -------------------------------- |
| `apps/backend-rag/backend/app/routers/crm_clients.py`            | —     | Client CRUD + stats              |
| `apps/backend-rag/backend/app/routers/crm_practices.py`          | —     | Practice lifecycle + automation  |
| `apps/backend-rag/backend/app/routers/crm_analytics.py`          | —     | Reporting (N+1 da fixare)        |
| `apps/backend-rag/backend/app/routers/crm_enhanced.py`           | —     | OCR pipeline + family            |
| `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py` | —     | Documents + Drive upload         |
| `apps/backend-rag/backend/app/utils/crm_utils.py`                | —     | RBAC (hardcoded → da migrare)    |
| `apps/backend-rag/backend/services/crm/enhanced_crm_service.py`  | —     | Bonus hook (unico bridge CRM→HR) |

---

## Appendice B — Metriche di Successo

| Metrica                      | Baseline attuale                        | Target post-roadmap          |
| ---------------------------- | --------------------------------------- | ---------------------------- |
| Tempo per trovare un client  | ~5s (scroll grid)                       | <2s (table search + sort)    |
| Deep link a tab specifica    | Solo primo load                         | Sempre (URL sync)            |
| Bulk re-assignment           | Impossibile                             | <30s per 100 clienti         |
| Latenza messaggi portal      | Fino a 30s                              | <2s (SSE)                    |
| Export analytics             | Screenshot manuale                      | 1-click CSV/Excel            |
| Onboarding nuovo team member | Modifica codice + deploy                | Toggle permission in UI      |
| RBAC endpoint coverage       | ~60% (documenti/interazioni senza auth) | 100%                         |
| Duplicate detection          | Solo constraint SQL post-insert         | Fuzzy pre-check con merge UI |
| TaxTab completeness          | 0% (scaffold vuoto)                     | 100% (read/write/upload)     |
| HR workload visibility       | Assente da HR UI                        | Card con practices/persona   |

---

## Appendice C — Bug P0 Verificati (Agent 2, file:linea)

Trovati dall'agente CRM Strategy indipendente, verificati su codice sorgente:

### BUG-01: TaxTab POST a endpoint inesistente

- **File:** `TaxTab.tsx:493`
- **Codice:** `api.post('/api/crm/clients/${clientId}/tax-documents', ...)`
- **Verifica:** Grep su 13 router CRM = 0 match. Genera 404 su ogni upload.
- **Fix:** Creare router `crm_tax_documents.py` con POST/GET/DELETE

### BUG-02: Status enum client disallineato (frontend 5, backend 4)

- **File backend:** `crm_clients.py:42` — `{"active", "inactive", "prospect", "lead"}`
- **File frontend:** `crm.types.ts:97` — aggiunge `"completed"` e `"lost"`
- **Impatto:** UPDATE client con status "completed"/"lost" → 422 dal backend

### BUG-03: Practice status disallineato (frontend 12, backend 5)

- **File backend:** `crm_practices.py:60-66` — 5 stati
- **File frontend:** `constants.ts:17-30` — 12 stati (7 fantasma: approved, rejected, cancelled, on_hold, waiting_payment, archived, ...)
- **Impatto:** Practice in stati fantasma non possono essere salvate

### BUG-04: Portal integration — 5 endpoint pronti, zero UI

- **File:** `crm_portal_integration.py` — 571 righe, 5+ endpoint
- **Endpoint disponibili:** status, invite, preview, unread-count, message
- **Problema:** Nessuno surfacato nell'UI CRM. Infrastruttura pronta dal 2025-12.

### BUG-05: PortalMessages senza badge unread

- **File:** `PortalMessages.tsx:42` — polling 30s, renderizzato nel body overview (`:837`)
- **Backend:** `GET /api/crm/portal/messages/unread-count` esiste (`:335`) ma non consumato
- **Fix:** Badge nel tab nav + consumare unread-count endpoint

### BUG-06: AddDocumentModal — solo URL, no upload

- **File:** `AddDocumentModal.tsx:172-184` — solo input URL Google Drive
- **Problema:** Portal vault ha upload diretto, CRM no. Pattern da backportare.

### BUG-07: CompanyTab refetch ad ogni tab switch

- **File:** `CompanyTab.tsx:81` — useEffect raw, no React Query
- **Impatto:** Ogni switch al tab Company = refetch completo. 8 tab × N switch = sprechi.

### BUG-08: KBLI lookup — 7 hardcoded su 1563 disponibili

- **File:** `KBLIEditorial.tsx:16` — mappa con 7 codici
- **Fix:** Chiamata live `GET /api/kbli/{code}` con React Query staleTime: Infinity

### BUG-09: Timeline cappata a 50 senza paginazione

- **File:** `clients/[id]/page.tsx:168` — `getClientTimeline(clientId, 50)` hardcoded
- **Impatto:** Clienti con 200+ interazioni vedono solo ultime 50, no load-more

### BUG-10: TEAM_MEMBERS hardcoded in 2 file

- **File 1:** `constants.ts:64` — "Should fetch from API but hardcoded for now"
- **File 2:** `new/page.tsx:45` — "// Team members - ideally fetch from API"
- **Fix:** `GET /api/crm/team/members` + React Query

### BUG-11: Design token frammentazione

- `ClientCard.tsx:22-35` — token `--neon-*` (non Warm Depth)
- `TimelineTab.tsx:7-14` — Tailwind raw (bg-green-500/20)
- `hr/page.tsx:25` — zinc palette (bg-zinc-900)
- **Fix:** Migrare tutto a `--bz-*` token

### BUG-12: RBAC rimosso esplicitamente su 2 router

- `crm_enhanced_documents.py:49` — RBAC removed
- `crm_enhanced_alerts.py:34` — RBAC removed
- **Rischio:** Qualsiasi utente autenticato (anche client role) potrebbe accedere
