# Portal Strategy Brainstorm — my.balizero.com

**Data:** 2026-03-30
**Autore:** Claude Code (Opus 4.6) — analisi codebase reale
**Scope:** Miglioramento strategico del portale clienti Bali Zero

---

## 1. Analisi Stato Attuale

### Cosa Funziona

Il portale è una SPA completa con 15 pagine autenticate, costruita su Next.js App Router con design system Warm Depth coerente. L'analisi del codice reale rivela:

**Architettura solida:**

- Layout autenticato (`portal/(authenticated)/layout.tsx`) con sidebar desktop, bottom nav mobile, overlay mobile sidebar, error boundary globale
- Cross-domain SSO funzionante: `nz_access_token` httpOnly cookie su `.balizero.com`, fallback localStorage → cookie-based auth
- API client tipizzato (`portal.api.ts`, 315 righe) con 14 endpoint, tipi completi (`portal.types.ts`, 360 righe)
- React Query per caching su dashboard principale, polling 30s su chat, 2min su vault/dashboard

**Pagine operative:**

| Pagina                 | Stato       | Qualità | Note                                                                            |
| ---------------------- | ----------- | ------- | ------------------------------------------------------------------------------- |
| Dashboard (/)          | ✅ Completa | Alta    | Traffic-light cards (Visa/Company/Tax), timeline, action items, React Query     |
| Dashboard (/dashboard) | ✅ Completa | Alta    | 3-column: Team Member + Passport OCR + Visa Process (process→electronic→actual) |
| Visa                   | ✅ Completa | Alta    | Current visa, days remaining con alert <60d, history, documents                 |
| Companies              | ✅ Completa | Alta    | Lista con set-primary, navigate to detail, compliance/license status            |
| Company/[id]           | ✅ Completa | Media   | Dettaglio singola company (page esiste, non analizzata in dettaglio)            |
| Taxes                  | ✅ Completa | Alta    | Summary, obligations, history, deadline countdown, IDR formatting               |
| Vault                  | ✅ Completa | Alta    | Upload (10MB max), category filter, search, status badges, download             |
| Chat/Messages          | ✅ Completa | Alta    | Real-time polling 30s, date grouping, read receipts, bubbles, load more         |
| LKPM                   | ✅ Completa | Alta    | Deadlines, history, submit link, quarterly reports                              |
| LKPM/[quarter]         | ✅ Completa | Media   | Dettaglio trimestre (page esiste)                                               |
| LKPM/submit            | ✅ Completa | Media   | Form sottomissione dati investimento                                            |
| Process                | ✅ Completa | Alta    | Grouped by practice, document upload per-process, progress bar, status tracking |
| Profile                | ✅ Completa | Alta    | Read-only, passport validity alerts, birthday detection                         |
| Settings               | ✅ Completa | Media   | Solo toggle email/WhatsApp notifications + readonly language/timezone           |

**Design system:**

- Warm Depth tokens consistenti (`--bz-base`, `--bz-accent-warm`, `--bz-text-1/2/3`)
- Glass-morphism cards (`rgba(30,30,35,0.7)`, `backdrop-blur-xl`)
- Status color system: emerald (ok), amber (warning), rose (critical)
- Skeleton loading per ogni pagina, fade-in animations
- Componenti portal dedicati: `PortalHeader`, `PortalBottomNav`, `PortalErrorBoundary`, `PortalNotifications`

**Navigazione (3 blocchi):**

- Core: Dashboard, Process, Messages
- Services: Companies, Visa, Taxes, LKPM
- Account: Profile, Settings

### Cosa Manca

1. **No Document Vault integrato con Drive** — Vault è flat list, non connesso a Google Drive folders del cliente. Il `TODO` a riga 537 del dashboard dice "Show actual passport image from Google Drive"
2. **Profile read-only** — "To update your profile information, please contact your account manager." Nessun self-service editing.
3. **Settings minimali** — Solo 2 toggle (email/WhatsApp notifications) + readonly language/timezone. Nessun tema, nessuna preferenza di comunicazione avanzata.
4. **Nessun sistema di notifiche push** — Solo polling HTTP. Niente WebSocket, niente push notifications, niente real-time.
5. **Chat è single-thread** — Un unico flusso di messaggi. Nessun concetto di topic/ticket/thread.
6. **Nessun self-service per nuove richieste** — Il cliente non può iniziare un nuovo processo (visa renewal, company setup) dal portale. Deve scrivere in chat.
7. **Nessuna integrazione payments** — Il portale non mostra fatture, pagamenti dovuti, storico transazioni.
8. **Nessun onboarding guidato** — Il portale non guida un nuovo cliente attraverso i primi passi (carica passaporto, compila profilo, ecc.).
9. **Nessuna knowledge base integrata** — Il cliente non ha accesso a FAQ, guide, articoli dal portale.

---

## 2. Pain Points & Gap

### Prospettiva Cliente (5000+ utenti)

**P1 — "Dove sono i miei documenti?"**
Il Vault mostra documenti caricati dal team o dal cliente, ma non è connesso a Google Drive. Il cliente non vede i suoi documenti originali (akta, SK, NPWP scan) che il team ha nel CRM. Risultato: il cliente chiede per email/WhatsApp "puoi mandarmi il mio NPWP?" quando è già nel sistema.

**P2 — "A che punto è la mia pratica?"**
La pagina Process mostra status (inquiry, quotation_sent, payment_pending, in_progress, submitted_to_gov, approved, completed) ma manca: tempo stimato, step successivo, chi sta lavorando, storico delle azioni. Il cliente vede "In Progress" senza context.

**P3 — "Non so cosa devo fare"**
Il dashboard mostra action items ma non c'è un onboarding wizard per nuovi clienti. Un cliente appena registrato vede un portale vuoto senza guidance. La sezione "Actions Required" è data-driven ma non proattiva.

**P4 — "Non riesco ad aggiornare i miei dati"**
Profile è completamente read-only. Per aggiornare telefono, indirizzo o WhatsApp il cliente deve contattare il team. Friction inutile per dati che il cliente conosce meglio di noi.

**P5 — "Quanto devo pagare?"**
Nessuna visibilità su fatture, pagamenti effettuati, saldo dovuto. Il cliente riceve fatture via email/WhatsApp ma non può consultarle nel portale.

**P6 — "La chat è confusa"**
Single-thread messaging mescola topic diversi (visa, company, tax) in un unico flusso. Per un cliente con 3 pratiche attive, trovare il messaggio rilevante richiede scroll.

### Prospettiva Team Interno

**T1 — Sync manuale**: Quando il team aggiorna il CRM, il cliente non lo vede in tempo reale. Il polling a 2 minuti crea lag percepito.
**T2 — Upload duplicato**: Il cliente carica un documento nel portale, il team lo ricarica nel CRM Drive. Due copie, nessuna sync.
**T3 — Comunicazione frammentata**: Il team usa CRM notes, il cliente usa portal chat. Due canali separati per lo stesso cliente.

---

## 3. Miglioramenti Proposti

### P0 — Critici (impatto immediato su retention e trust)

#### P0.1 — Process Tracker Avanzato

**Problema:** "In Progress" non dice nulla.
**Soluzione:** Stepper visuale per ogni pratica con:

- Timeline degli step completati (con date reali da CRM `practices.status_history`)
- Step corrente evidenziato con tempo stimato residuo
- Prossima azione (chi deve fare cosa: "Waiting for government review" vs "You need to upload passport")
- Alert proattivi: "Your KITAS application was submitted to Immigration 3 days ago. Typical processing: 5-10 business days."

**Backend necessario:** Endpoint `GET /api/portal/process/{practice_id}/timeline` che espone `practices.status_log` (già salvato nel CRM).

#### P0.2 — Document Bridge (Portal ↔ Drive)

**Problema:** Vault disconnesso da Google Drive.
**Soluzione:**

- Il Vault mostra documenti dal Google Drive folder del cliente (collegamento `clients.drive_folder_id`)
- Upload nel Vault → salva in Drive → appare nel CRM
- Download dal Vault → file da Drive
- Status sync: team verifica documento in CRM → badge "Verified" nel Vault

**Backend necessario:** Endpoint `GET /api/portal/drive/files` che proxya TeamDriveService con accesso scoped al folder del cliente.

#### P0.3 — Invoice & Payment Visibility

**Problema:** Il cliente non sa quanto deve.
**Soluzione:** Nuova pagina `/portal/billing` con:

- Fatture emesse (da CRM `invoices` table)
- Status pagamento (paid, pending, overdue)
- Download PDF fattura
- Link a pagamento (se integrazione Stripe/Xendit futura)

**Backend necessario:** Endpoint `GET /api/portal/billing` che espone invoices filtrate per `client_id`.

### P1 — Importanti (UX premium, differenziazione competitiva)

#### P1.1 — Profilo Self-Service Editing

Permettere al cliente di modificare: telefono, WhatsApp, indirizzo, lingua preferita. Campi sensibili (nome, passaporto, nazionalità) restano read-only (richiesta team). Ogni modifica → notifica al team member assegnato.

**Backend necessario:** `PATCH /api/portal/profile` con whitelist campi modificabili.

#### P1.2 — Chat Multi-Thread

Sostituire il single-thread con conversazioni per-pratica:

- Thread automatici per ogni pratica attiva
- Thread "General" per domande non legate a una pratica
- Unread count per thread
- Quick-reply suggestions (AI-powered)

**Backend necessario:** Aggiungere `thread_id` (opzionale, default = null per backward compat) ai messaggi portal. Frontend raggruppa per `practice_id`.

#### P1.3 — Onboarding Wizard

Per clienti nuovi (registrati ma senza pratiche):

1. "Welcome! Let's set up your profile" → completa dati mancanti
2. "Upload your passport" → OCR auto-extract
3. "What service do you need?" → avvia prima pratica
4. "Meet your team" → mostra case manager assegnato

**Backend necessario:** Endpoint `GET /api/portal/onboarding-status` che ritorna checklist items con stato completamento.

#### P1.4 — Notification Center

Sostituire polling con:

- SSE (Server-Sent Events) per notifiche real-time
- Centro notifiche in-app (già scaffolded: `PortalNotifications.tsx` esiste)
- Push notifications browser (service worker)
- Digest email giornaliero (opt-in)

**Backend necessario:** Endpoint SSE `GET /api/portal/notifications/stream` + tabella `portal_notifications`.

#### P1.5 — Knowledge Base Integrata

Sezione `/portal/help` con:

- FAQ per categoria (visa, company, tax)
- Guide step-by-step (articoli da blog filtrati per rilevanza)
- Link diretto a Zantara AI chat (zantara.balizero.com)

**Backend necessario:** Nessuno (può usare articoli esistenti con filtro `is_client_facing`).

### P2 — Delight (wow factor, premium feel)

#### P2.1 — Dashboard Analytics Personali

Visualizzazioni per il cliente:

- Timeline dei costi sostenuti (spesa cumulativa Bali Zero)
- Countdown multipli (visa expiry, passport expiry, prossima tax deadline, LKPM deadline)
- "Your Bali Score" — gamification della completezza profilo (% documenti caricati, % profilo completo)

#### P2.2 — Dark/Light Theme Toggle

Il portale è fixed dark theme. Alcuni clienti (specialmente over-50, expat europei) preferiscono light mode. Implementare toggle in Settings.

#### P2.3 — Multi-Language

`PortalPreferences.language` esiste ma è read-only. Attivare i18n con almeno: English, Indonesian, Italian, Russian (top 4 nazionalità clienti).

#### P2.4 — Referral Program

Pagina `/portal/referral` con:

- Codice referral unico
- Tracking referral attivi
- Credit/sconto per ogni referral convertito

#### P2.5 — QR Code Document Sharing

Per ogni documento verificato, generare un QR code che permette sharing temporaneo (es: mostrare KITAS all'hotel senza dare accesso al portale).

---

## 4. Visione UX/UI

### Principi Design

Il portale deve comunicare: **"Tutto è sotto controllo. Noi ci occupiamo di tutto."**

1. **Clarity over density** — Un'informazione importante visibile è meglio di dieci nascoste. Lo stato della pratica deve essere comprensibile in 2 secondi.
2. **Proactive, not reactive** — Il portale deve dire al cliente cosa fare prima che lo chieda. Alert, countdown, next-step suggestions.
3. **Trust signals** — Badge "Verified", timestamp "Updated 2 hours ago", "Your case manager Asya is handling this". Il cliente deve sentire che qualcuno sta lavorando.

### Warm Depth Evolution

Mantenere la palette esistente ma aggiungere:

- **Status gradient bar** su ogni pratica (progress: 0% → 100%)
- **Micro-animations** su state changes (documento verificato → confetti subtile, pratica completata → checkmark animato)
- **Contextual illustrations** — SVG custom per stati vuoti (no visa? → illustrazione aereo; no company? → illustrazione building)
- **Typography hierarchy**: titoli in Geist Sans, dati numerici (countdown, importi) in Geist Mono per leggibilità

### Mobile-First Refinements

Il portale è già responsive (sidebar → bottom nav), ma:

- **Swipe gestures** su Process cards per quick actions
- **Pull-to-refresh** nativo su tutte le pagine
- **Bottom sheet** per document upload (invece di modal)
- **Haptic feedback** su azioni critiche (upload completato, messaggio inviato)

---

## 5. Modifiche Backend Necessarie

### Nuovi Endpoint

| Endpoint                                | Metodo    | Scopo                                    | Priorità |
| --------------------------------------- | --------- | ---------------------------------------- | -------- |
| `GET /api/portal/process/{id}/timeline` | GET       | Stepper con status_log pratica           | P0       |
| `GET /api/portal/drive/files`           | GET       | File dal Google Drive folder del cliente | P0       |
| `POST /api/portal/drive/upload`         | POST      | Upload file → Google Drive client folder | P0       |
| `GET /api/portal/billing`               | GET       | Fatture e pagamenti del cliente          | P0       |
| `GET /api/portal/billing/{id}/pdf`      | GET       | Download PDF fattura                     | P0       |
| `PATCH /api/portal/profile`             | PATCH     | Update campi profilo consentiti          | P1       |
| `GET /api/portal/onboarding-status`     | GET       | Checklist onboarding completamento       | P1       |
| `GET /api/portal/notifications/stream`  | GET (SSE) | Stream notifiche real-time               | P1       |
| `GET /api/portal/help/articles`         | GET       | Articoli knowledge base client-facing    | P1       |

### Schema Changes

```sql
-- Portal notifications table
CREATE TABLE portal_notifications (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    type VARCHAR(50) NOT NULL,  -- 'document_verified', 'status_changed', 'message_received', 'deadline_approaching'
    title TEXT NOT NULL,
    body TEXT,
    data JSONB DEFAULT '{}',
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_portal_notif_client ON portal_notifications(client_id, read_at);

-- Add portal-editable fields tracking
ALTER TABLE clients ADD COLUMN portal_edits_log JSONB DEFAULT '[]';
```

### Service Modifications

- `PortalService`: aggiungere metodi per `get_process_timeline`, `get_billing`, `update_profile_fields`
- `TeamDriveService`: aggiungere metodo `list_client_files(client_id)` con scope al `drive_folder_id` del cliente
- `PortalService`: generare `portal_notifications` entries su eventi CRM (trigger o event-driven)

---

## 6. Punti di Sinergia

### Portal ↔ CRM

| Azione nel CRM (kita.balizero.com)          | Effetto nel Portal (my.balizero.com)             |
| ------------------------------------------- | ------------------------------------------------ |
| Team cambia `practices.status`              | → Status card si aggiorna, notification pushed   |
| Team carica documento in Drive folder       | → Appare nel Vault del cliente                   |
| Team verifica documento (`status=verified`) | → Badge "Verified" nel Vault                     |
| Team scrive nota su pratica                 | → (Opzionale) messaggio nel thread pratica       |
| Team assegna nuovo case manager             | → "Your case manager" si aggiorna nel Dashboard  |
| Team crea nuova pratica per cliente         | → Nuova card nel Process con documenti richiesti |
| Team genera fattura                         | → Appare in /portal/billing                      |

| Azione nel Portal                | Effetto nel CRM                                |
| -------------------------------- | ---------------------------------------------- |
| Cliente carica documento         | → Appare in CRM Drive folder + notifica team   |
| Cliente invia messaggio          | → Notifica al case manager assegnato           |
| Cliente aggiorna profilo         | → Update `clients` table + log + notifica team |
| Cliente approva LKPM draft       | → Status cambia in CRM, team notificato        |
| Cliente completa onboarding step | → Progress tracciato, team vede completamento  |

### Portal ↔ HR

| Dato HR                      | Uso nel Portal                                                                            |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| `team_members.is_on_leave`   | Dashboard mostra "Your case manager Asya is on leave until Apr 5. Damar is covering."     |
| `team_members.working_hours` | Chat mostra "Our team is available Mon-Fri 9:00-17:00 WITA" con indicatore online/offline |
| `team_members.avatar_url`    | Foto case manager nel Dashboard card                                                      |

### Componenti Condivisi

Già condivisi tra Portal e Workspace:

- `AppSidebar` — usato in entrambi con `isPortal={true}` flag e `navigationConfig` diversa
- `Button`, `Input`, `Badge`, `Dialog` — shadcn/ui components
- `useToast` — sistema toast notifiche
- `api` client — stessa libreria API

Da creare come shared:

- `StatusBadge` — attualmente duplicato in 4+ pagine portal con logica identica
- `ProcessStatusConfig` — duplicato tra Process page e CRM workspace
- `PassportValidityChecker` — duplicato tra Dashboard e Profile
- `CountdownChip` — pattern `⏰ ${days}d left` ripetuto in 6+ componenti
- `DocumentCard` — pattern identico in Visa page e Vault

---

## 7. Roadmap Implementazione

### Fase 1 — Foundation (2 settimane)

**Focus:** Risolvere i pain point più urgenti senza rompere nulla.

1. **P0.1 Process Tracker** — Backend: esporre `status_log` da practices. Frontend: stepper component.
2. **P0.2 Document Bridge** — Backend: proxy Drive API scoped. Frontend: integrare Vault con Drive.
3. **Shared components refactor** — Estrarre `StatusBadge`, `CountdownChip`, `DocumentCard`.

**Dipendenze:** Nessuna. `TeamDriveService` e `practices` table già esistono.

### Fase 2 — Communication (2 settimane)

**Focus:** Migliorare comunicazione bidirezionale.

4. **P1.2 Chat Multi-Thread** — Backend: thread_id su messaggi. Frontend: tab per pratica.
5. **P1.4 Notification Center** — Backend: SSE endpoint + notification table. Frontend: bell icon + popover (già scaffolded).
6. **P1.1 Profile Self-Service** — Backend: PATCH endpoint con whitelist. Frontend: edit mode su Profile.

**Dipendenze:** Fase 1 completata per shared components.

### Fase 3 — Business Value (2 settimane)

**Focus:** Funzionalità che generano revenue e retention.

7. **P0.3 Billing Page** — Backend: invoices endpoint. Frontend: nuova pagina /portal/billing.
8. **P1.3 Onboarding Wizard** — Backend: onboarding status endpoint. Frontend: wizard component.
9. **P1.5 Knowledge Base** — Frontend: /portal/help con articoli filtrati.

**Dipendenze:** Billing richiede tabella `invoices` nel CRM (verificare se esiste).

### Fase 4 — Delight (2 settimane)

**Focus:** Differenziazione competitiva e premium feel.

10. **P2.1 Dashboard Analytics** — Frontend: grafici spesa, countdown multipli.
11. **P2.2 Theme Toggle** — Frontend: light/dark switch in Settings.
12. **P2.3 Multi-Language** — Integrare i18n framework (next-intl o similar).

**Dipendenze:** Fasi 1-3 completate. Analytics richiede dati storici sufficienti.

### Milestone di Validazione

| Fase | KPI                                            | Target |
| ---- | ---------------------------------------------- | ------ |
| 1    | Riduzione ticket "dove sono i miei documenti?" | -50%   |
| 2    | Riduzione tempo risposta medio chat            | -30%   |
| 3    | % clienti che consultano fatture nel portale   | >40%   |
| 4    | NPS score portale                              | >70    |

---

## Appendice: File Chiave Analizzati

| File                                        | Righe | Ruolo                                             |
| ------------------------------------------- | ----- | ------------------------------------------------- |
| `portal/(authenticated)/layout.tsx`         | 238   | Layout con SSO, sidebar, mobile nav               |
| `portal/(authenticated)/page.tsx`           | 541   | Dashboard con traffic-light cards + timeline      |
| `portal/(authenticated)/dashboard/page.tsx` | 981   | My Overview (team member, passport, visa process) |
| `portal/(authenticated)/visa/page.tsx`      | 463   | Immigration status con days remaining             |
| `portal/(authenticated)/companies/page.tsx` | 314   | Company list con set-primary                      |
| `portal/(authenticated)/taxes/page.tsx`     | 521   | Tax overview con obligations                      |
| `portal/(authenticated)/vault/page.tsx`     | 444   | Document vault con upload + filter                |
| `portal/(authenticated)/chat/page.tsx`      | 535   | Messaging con polling 30s                         |
| `portal/(authenticated)/lkpm/page.tsx`      | 310   | LKPM reports con deadlines                        |
| `portal/(authenticated)/process/page.tsx`   | 578   | Process tracker con document upload               |
| `portal/(authenticated)/profile/page.tsx`   | 483   | Read-only profile con passport alerts             |
| `portal/(authenticated)/settings/page.tsx`  | 279   | Notification preferences                          |
| `lib/api/portal/portal.api.ts`              | 315   | Client API con 14 endpoint                        |
| `lib/api/portal/portal.types.ts`            | 360   | TypeScript types completi                         |
| `components/portal/index.ts`                | 24    | Portal component exports                          |
| `types/navigation.ts`                       | 155   | Portal navigation config (3 blocchi)              |
| `backend/app/routers/portal.py`             | 80+   | Main portal router con client auth                |

---

## Appendice: Bug P0 Verificati (file:linea)

I seguenti bug sono stati verificati direttamente dal codice sorgente:

### BUG-1: Company Card rotta verso Vault

- **File:** `portal/(authenticated)/page.tsx:142`
- **Codice:** `onClick={() => router.push('/portal/vault')}`
- **Fix:** Cambiare in `router.push('/portal/companies')`
- **Effort:** 5 minuti, 1 riga

### BUG-2: Vault assente dalla sidebar desktop

- **File:** `types/navigation.ts:98-122`
- **Problema:** `portalNavigation` ha 9 item ma manca Vault. Mobile lo ha (PortalBottomNav tab 2).
- **Fix:** Aggiungere `{ title: "Vault", href: "/portal/vault", icon: "FolderOpen" }` alla sezione Main
- **Effort:** 10 minuti

### BUG-3: Upload ignora categoria selezionata

- **File:** `portal/(authenticated)/vault/page.tsx:95`
- **Codice:** `await api.portal.uploadDocument(file, "general")` — hardcoded
- **Fix:** Passare `selectedCategory` invece di `"general"`
- **Effort:** 10 minuti

### BUG-4: Process page chiama CRM API direttamente (security leak)

- **File:** `portal/(authenticated)/process/page.tsx:369,389`
- **Codice:** `api.crm.getClientRequiredDocuments()` e `api.crm.uploadClientDocument()`
- **Problema:** Client con `role='client'` bypassa RBAC del portal e chiama endpoint CRM con regole RBAC diverse
- **Fix:** Creare endpoint portal-scoped `GET /portal/process/documents` e `POST /portal/process/documents/{id}/upload`
- **Effort:** 2-3 ore

### BUG-5: Tax amounts sempre zero

- **File:** `backend/services/portal/portal_service.py:1319,1341`
- **Codice:** `"amount": 0, # No amount stored in practices` e `"totalDue": 0`
- **Problema:** Usa `_get_standard_tax_deadlines()` (riga 2497) — calendario generico uguale per tutti i clienti
- **Fix:** Sostituire con `TaxService.get_obligations_for_client(client_id)` che legge `tax_obligations` table
- **Effort:** 3 ore backend

### BUG-6: Settings blocca editing supportato dal backend

- **File:** `portal/(authenticated)/settings/page.tsx:171-172`
- **Problema:** Language e timezone mostrati come `ReadOnlyField` con "contact support". Ma `portal_service.py` `update_preferences()` li supporta già.
- **Fix:** Sostituire ReadOnlyField con select/dropdown
- **Effort:** 1 ora frontend

### BUG-7: Visa renewal senza CTA

- **File:** `portal/(authenticated)/visa/page.tsx:241`
- **Codice:** Testo "Please contact us immediately to begin renewal" senza bottone
- **Fix:** Aggiungere `POST /portal/visa/renewal-request` + bottone "Request Renewal"
- **Effort:** 4 ore totali

### BUG-8: Chat polling 30s, niente SSE

- **File:** `portal/(authenticated)/chat/page.tsx:15`
- **Codice:** `const POLL_INTERVAL = 30000`
- **Fix:** Migrare a SSE con `GET /portal/messages/stream`
- **Effort:** 6 ore totali

### BUG-9: Due dashboard duplicate

- **File:** `/portal` (React Query) vs `/portal/dashboard` (imperative fetch 2min)
- **Problema:** Overlapping info, `/portal/dashboard` non linkato nella nav primaria
- **Fix:** Consolidare — merge content in `/portal`, redirect `/portal/dashboard` → `/portal`
- **Effort:** 3 ore

### BUG-10: Mobile nav disallineata con desktop

- **Mobile:** 4 tab (Home, Vault, Chat, Profile) — mancano Companies, Visa, Taxes, LKPM, Settings
- **Desktop:** 9 sidebar item — manca Vault
- **Fix:** Aggiungere "More" tab su mobile che apre drawer con le route mancanti
