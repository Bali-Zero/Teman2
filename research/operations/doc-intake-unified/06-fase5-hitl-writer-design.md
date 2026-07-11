---
date: 2026-06-04
domain: compliance
study: doc-intake-unified
phase: 5 — HITL & CRM WRITER (GO-LIVE)
client_case: false
sources:
  - research/operations/doc-intake-unified/04-4-entity-routing.md          # proposal schema + commit_gate (FASE 4)
  - research/operations/doc-intake-unified/04-5-hitl-evolver.md            # HITL gate + intake_corrections + evolver (pre-design)
  - research/operations/doc-intake-unified/04-2-queue-orchestrator.md      # intake_queue state-machine + FOR UPDATE SKIP LOCKED
  - research/operations/doc-intake-unified/04-1-ingestion-dedup.md         # intake_queue status enum + content_hash dedup
  - apps/backend-rag/backend/app/routers/crm_enhanced_documents.py:107     # create_document — CANONICAL CRM document writer (REUSE)
  - apps/backend-rag/backend/app/routers/crm_enhanced.py:922               # DocumentCreate model + _dispatch_ocr_by_folder
  - apps/backend-rag/backend/services/crm/drive_poll_service.py:446        # automated-intake writer precedent (content_hash dedup + INSERT)
  - apps/backend-rag/backend/app/routers/crm_practices.py:1604             # add_document_to_practice (practices.documents JSON append)
  - apps/backend-rag/backend/app/utils/crm_utils.py:108                    # verify_client_access RBAC + is_crm_admin
  - apps/backend-rag/backend/app/core/config.py:828                        # admin_emails_set (zero@/asya@/antonellosiano@)
---

# FASE 5 — HITL & CRM WRITER (GO-LIVE)

> FASE 5 e lUNICO punto del sistema document-intake che scrive sul CRM reale
> (clients / practices / documents). Tutto a monte (FASE 1-4) e read-only sul CRM:
> produce una document_routing_proposal e si ferma. FASE 5 la approva (HITL) e committa.
> Questo documento e DESIGN, non codice. Ogni claim sul writer esistente e da grep/read live 2026-06-04.

---

## 0. SINTESI ESECUTIVA (TL;DR)

- **Writer CRM esistente TROVATO e RIUSABILE**: `create_document` (`crm_enhanced_documents.py:107`,
  endpoint `POST /api/crm/clients/{client_id}/documents`) + il suo gemello batch `create_documents_bulk`.
  Fa: `INSERT INTO documents(...)`, RBAC `verify_client_access`, OCR auto-dispatch, portal-notify,
  `invalidate_cache("zantara:crm_clients_stats:*")`. FASE 5 NON inventa un writer: chiama questa logica.
- **Precedente di intake automatico**: `drive_poll_service` (`drive_poll_service.py:446-575`) e gia oggi
  un writer non-HTTP che inserisce in `documents` con `content_hash` (dedup advisory SELECT-then-skip),
  tocca `clients.updated_at`, enqueue guardian, dispatch OCR. E il template architetturale per lauto-commit.
- **Policy auto-commit**: SOLO `AUTO_ATTACH` (entity score >= 0.92, >=1 strong-key, >=2 segnali concordi)
  E `needs_field_review=false` E nessun `phone_owner_risk` → auto-commit con audit. TUTTO il resto → HITL.
- **HITL UI riusa il CRM web esistente** (apps/mouth, pattern workspace_inbox + RBAC) via 2-3 endpoint nuovi.
  Nessuna UI nuova costruita ora.
- **Go-live dietro 5 guardrail**: feature-flag default OFF, dry-run mode, rate-limit/circuit-breaker,
  audit log per ogni commit, rollback di un attach errato.
- **Piano in 4 sotto-parti** committabili: 5A review-queue API (read-only) · 5B writer dry-run · 5C writer
  reale dietro flag · 5D corrections + audit + rollback.

---

## 1. STUDIO REUSE-FIRST DEL CRM WRITER ESISTENTE (CRITICO)

### 1.1 Come si attacca OGGI un documento a un cliente

Due path di scrittura coesistono gia in produzione (entrambi scrivono la STESSA tabella `documents`):

| Path | Dove | Tipo | Idempotenza | Note |
|---|---|---|---|---|
| **A. HTTP create_document** | `crm_enhanced_documents.py:107` | endpoint REST | NESSUNA (insert puro) | il writer canonico usato dalla UI CRM |
| **B. drive_poll_service** | `drive_poll_service.py:446` | servizio async (cron) | content_hash advisory (SELECT-then-skip, 30gg) | il precedente di intake automatico piu vicino a FASE 5 |

Esistono altri INSERT in `documents` (`portal/_mixins/documents.py`, `admin_drive_health.py`,
`crm_enhanced_documents.py:276/776` per bulk/upload) ma sono varianti dello stesso pattern.

### 1.2 Il writer canonico — `create_document` (REUSE TARGET)

```
POST /api/crm/clients/{client_id}/documents     # body = DocumentCreate
```

INSERT reale (verbatim dal codice):

```sql
INSERT INTO documents (
    client_id, document_type, document_category,
    file_name, file_id, file_url, google_drive_file_url,
    expiry_date, notes, family_member_id, practice_id,
    status, storage_type
) VALUES (.., 'google_drive', 'google_drive')
RETURNING id
```

Model `DocumentCreate` (crm_enhanced.py:922): `document_type` (obblig.), `document_category`,
`file_name`, `file_id` (Drive ID), `file_url`, `google_drive_file_url`, `expiry_date` (str→date),
`notes`, `family_member_id`, `practice_id`.

Side-effect del writer canonico (TUTTI da preservare in FASE 5):
1. `verify_client_access(client_id, current_user, conn, allow_assigned=True)` — RBAC gate.
2. Auto OCR: `background_tasks.add_task(_dispatch_ocr_by_folder, ...)` + `UPDATE documents SET ocr_status='pending'`.
3. Portal notify: `PortalNotificationService.notify_document_uploaded(...)`.
4. **Cache invalidation (INVARIANTE CLAUDE.md §9)**: `await invalidate_cache("zantara:crm_clients_stats:*")`.

### 1.3 Invarianti del writer (da NON violare)

- **INV-1 cache**: dopo OGNI mutazione su clients/documents → `invalidate_cache("zantara:crm_clients_stats:*")`.
  Per practices → `invalidate_cache("zantara:crm_practices_stats:*")` (vedi crm_practices.py:1604). FASE 5
  committa su entrambi → DEVE invalidare entrambi i namespace.
- **INV-2 RBAC**: ogni write passa per `verify_client_access`. FASE 5 (writer di servizio, no HTTP user)
  DEVE replicare il check con lidentita del committer (vedi §6e).
- **INV-3 storage_type**: `'google_drive'` di default — coerente con D2 Drive routing.
- **INV-4 OCR re-trigger**: il writer ri-dispatcha OCR. FASE 5 commetta documenti GIA OCRd da FASE 3 →
  DEVE evitare doppio-OCR (passare `ocr_status='completed'` + non add_task, vedi §6 GOTCHA).
- **INV-5 practices.documents**: e una colonna JSON (array), append via `add_document_to_practice`
  (crm_practices.py:1604), NON una FK. Il link practice↔document e doppio: `documents.practice_id` (FK)
  + `practices.documents[]` (JSON snapshot). FASE 5 che risolve una practice DEVE aggiornare entrambi.

### 1.4 Verdetto reuse

**RIUSABILE: SI.** FASE 5 non scrive un nuovo writer CRM. Estrae la logica di `create_document` in una
funzione di servizio chiamabile sia da HTTP sia dal commit-worker (oggi e inline nel router — va fattorizzata
in `services/crm/document_writer.py` cosi i due path NON divergono). Lauto-commit segue il pattern di
`drive_poll_service` (servizio async, content_hash, no HTTP). Vedi §4 per la transazionalita.

> **FINDING reuse**: la logica di `create_document` e oggi *inline nel router* (accoppiata a FastAPI
> Depends + BackgroundTasks). Per riusarla dal commit-worker va estratta in un servizio puro
> (`async def write_client_document(conn, client_id, payload, committed_by) -> int`). Senza questa
> estrazione, FASE 5 sarebbe tentata di duplicare lINSERT → due path divergenti (anti-pattern esplicito del task).

---

## 2. DECISION-MATRIX → AZIONE

La `document_routing_proposal` (FASE 4) porta `entity_resolution.decision` + `commit_gate`.
FASE 5 mappa ogni esito a unazione:

| decision (C4) | commit_gate.requires_human | Azione FASE 5 | Razionale |
|---|---|---|---|
| **AUTO_ATTACH** | false (score>=0.92, >=2 signals, no field-review, no phone_risk) | **AUTO-COMMIT** con audit, no umano | strong-key exact + soglia altissima = rischio false-merge minimo; lHITL su questi sarebbe rumore che erode la fiducia nellHITL sui casi veri |
| **AUTO_ATTACH** ma needs_field_review=true | true | **HITL** (verifica campi, poi commit) | un campo PII/legale incerto richiede occhio umano anche se il cliente e certo |
| **LINK_CANDIDATE** | true | **HITL** — umano conferma/sceglie il cliente | 0.70<=score<0.92 o singolo segnale o solo-phone/solo-nome: ambiguita reale |
| **AMBIGUOUS** | true | **HITL** — umano sceglie tra top-N candidati | omonimi entro Δ0.08: auto-merge = corruzione dati |
| **NO_MATCH** | true | **HITL** — umano: crea nuovo cliente / lega a esistente / rigetta | nessun candidato: mai creare clienti automaticamente |

### 2.1 Policy auto-commit (RACCOMANDATA, giustificata)

**Auto-commit SOLO se TUTTE vere:**
1. `entity_resolution.decision == AUTO_ATTACH`
2. `commit_gate.auto_commit_eligible == true` (gia calcolato in FASE 4: AUTO_ATTACH ∧ no field-review)
3. `entity_resolution.phone_owner_risk == false`
4. il documento ha **almeno una strong-key exact** (passport/kitas/npwp/nik) — il phone da solo NON basta (C4)
5. feature-flag `INTAKE_AUTOCOMMIT_ENABLED == true` (default OFF — vedi §6a; lauto-commit si accende
   DOPO che lHITL ha girato settimane e si ha confidenza empirica sulle soglie)

**Tutto il resto → HITL.** Anche AUTO_ATTACH, finche il flag autocommit e OFF, passa per HITL (review
che sara quasi sempre un "approva" secco: addestra il team e raccoglie baseline `outcome=auto_committed`
per validare le soglie PRIMA di togliere lumano).

**Giustificazione**: lasimmetria del costo. Un falso auto-commit corrompe il fascicolo di un cliente reale
(documento legato al cliente sbagliato = leak PII cross-cliente + decisione legale su dati errati). Un HITL
di troppo costa 5 secondi a un umano. Il sistema parte **conservativo** (HITL ovunque), e solo dopo evidenza
empirica (correction_rate bassa sugli AUTO_ATTACH) si abilita lauto-commit per la fascia piu sicura. Questo
e anche cio che FASE 4.5 §1.2 chiama "registra comunque outcome=auto_committed come baseline".

---

## 3. INTERFACCIA HITL (REUSE-FIRST)

### 3.1 Cosa esiste gia
- **CRM web** (apps/mouth, kita.balizero.com) con auth team + RBAC `assigned_to` — pattern `workspace_inbox`.
- **paperless-gpt** (citato in 05): pattern di review-UI per doc-intake, GPL → STUDIA-PATTERN, non copiare.
- **wa-mirror :7790**: localhost-only sul Pro → il team su Windows/telefono NON la raggiunge. Scartata come editor.

### 3.2 Scelta (conferma FASE 4.5 §2): **vista "Intake review" dentro il CRM web esistente** + endpoint API.
NON si costruisce la UI ora. Si progetta l**interfaccia** (endpoint) che una vista del CRM consumera.

### 3.3 Endpoint API (contratto)

```
GET    /api/crm/intake-review                      # lista proposte status=review_pending, filtrata RBAC
GET    /api/crm/intake-review/{proposal_id}        # dettaglio: campi incerti + candidati + anteprima doc
POST   /api/crm/intake-review/{proposal_id}/claim  # lease atomico (FOR UPDATE SKIP LOCKED) → review_claimed
POST   /api/crm/intake-review/{proposal_id}/approve # body: {client_id, final_fields, practice_id?} → commit
POST   /api/crm/intake-review/{proposal_id}/reject  # body: {reason} → rejected (dead-state tracciato)
PATCH  /api/crm/intake-review/{proposal_id}/fields  # edit campi estratti (registra in intake_corrections)
```

- **list/detail**: RBAC `verify_client_access` sul `client_id` candidato; item NO_MATCH/AMBIGUOUS senza
  cliente risolto → visibili solo agli admin (`is_crm_admin`: zero@/asya@/antonellosiano@).
- **claim**: lease con TTL (riuso pattern `FOR UPDATE SKIP LOCKED` gia in repo, replay_outbox) → due
  reviewer non lavorano lo stesso item; timeout → torna review_pending.
- **approve**: e lUNICO trigger del write CRM per gli item in coda. Idempotente su `proposal_id` (vedi §4).
- **Telegram = NOTIFIER, non editor** (FASE 4.5 §2): ping con deep-link + soli nomi-campo (NO valori PII, Law 2).

---

## 4. WRITER TRANSAZIONALE + IDEMPOTENZA

### 4.1 Macchina a stati (estende intake_queue FASE 1/2)

`intake_queue.status` enum esistente (04-1:134): `pending|ocr|classified|extracted|review|routed|done|dead|duplicate`.
`document_routing_proposal.status` (04-4): `proposed|approved|committed|done|rejected|dead`.

FASE 5 opera sulla proposal e sincronizza la queue:

```
proposal: proposed ──(gate)──► review_pending ──claim──► review_claimed
                                     │                        │
                                     │ auto-commit            │ approve
                                     ▼                        ▼
                                  approved ───── COMMIT TX ──► committed ──► done
                                     │                        │
                                  reject                   TX fail → rollback → review_pending
                                     ▼
                                 rejected (dead-state, motivo tracciato)

intake_queue: extracted ──► review ──(approve/auto)──► routed ──(post-commit ok)──► done
                                  └──(reject)──► dead
```

### 4.2 La transazione di commit (atomica, idempotente)

Tutto in **UNA `async with conn.transaction()`** (asyncpg), un solo commit-worker serializzato (C2):

```
BEGIN
  1. SELECT proposal FOR UPDATE  -- lock; se status gia 'committed'/'done' → no-op (idempotenza)
  2. (idempotency guard) SELECT 1 FROM documents WHERE intake_idempotency_key =   -- se esiste → skip insert, riusa doc_id
  3. doc_id = write_client_document(conn, client_id, payload, committed_by)   -- INSERT documents (riuso §1.4)
  4. if practice_id: UPDATE documents SET practice_id=; append practices.documents[] (riuso add_document_to_practice logic)
  5. INSERT interactions (provenance: channel, doc_type, blob_sha256, proposal_id)
  6. INSERT intake_corrections (per ogni campo toccato + audit)   -- §5
  7. INSERT intake_commit_audit (chi/quando/proposal/client/doc_id/dry_run=false)   -- §6d
  8. UPDATE document_routing_proposal SET status='committed'
  9. UPDATE intake_queue SET status='routed'
COMMIT
-- post-commit (FUORI dalla TX, best-effort, idempotenti):
  10. invalidate_cache("zantara:crm_clients_stats:*") + ("zantara:crm_practices_stats:*")   -- INV-1
  11. UPDATE intake_queue SET status='done' ; proposal status='done'
  12. enqueue D3 auditor (solo company docs) ; portal notify (best-effort)
```

### 4.3 Idempotenza (3 livelli, recepisce C1/C2)
1. **idempotency_key** = `<blob_sha256>:<doc_index>:<pipeline_version>` (gia in proposal, FASE 4 §5).
   Va PERSISTITO sulla riga `documents` (colonna nuova `intake_idempotency_key` UNIQUE) → re-commit = no-op.
2. **proposal status guard**: SELECT FOR UPDATE; se gia committed/done → return doc_id esistente, niente insert.
3. **content_hash advisory** (riuso drive_poll): se stesso content_hash sullo stesso client_id <30gg → flagga
   duplicato in review invece di committare (semantic dedup, non blocca riprocessamento legittimo C1).

> **GOTCHA idempotenza (da drive_poll)**: il dedup di drive_poll e SELECT-then-INSERT **senza unique
> constraint** → TOCTOU race se due worker concorrono. FASE 5 chiude il buco con `intake_idempotency_key
> UNIQUE` + ON CONFLICT DO NOTHING, NON solo la SELECT. Il commit-worker e comunque single-flight (un solo
> consumer della coda approved, claim atomico) ma la unique e la cintura di sicurezza.

### 4.4 Commit fallisce a meta?
Tutta la TX (passi 1-9) e atomica → un fallimento a qualunque punto fa **ROLLBACK completo**: nessun
documento orfano, nessuna practice aggiornata a meta. Il worker:
- riporta `proposal.status` a `review_pending` (o `approved` per retry automatico con backoff, max N),
- logga lerrore in `intake_commit_audit` con `outcome='failed'`,
- dopo max retry → `dead` + alert Telegram (DLQ pattern FASE 2).
I passi 10-12 (post-commit) sono best-effort e idempotenti: se crasha tra COMMIT e invalidate_cache, un
reconcile-tick ri-esegue cache-invalidation e D3 (la TX e gia durable, lo stato e `committed`).

---

## 5. intake_corrections (SEME EVOLVER)

Riuso integrale dello schema gia progettato in FASE 4.5 §3 (`intake_corrections`). FASE 5 e il PRODUTTORE:
una riga per ogni campo toccato O esplicitamente approvato, su ogni `approve`/`auto-commit`/`reject`.

Cosa registrare per riga (campi chiave): `intake_id`, `content_hash`, `doc_type`, `field_name`, `source`,
`ai_value`, `human_value`, `ai_confidence`, `outcome` (approved|corrected|rejected|auto_committed),
`stage` (classify|extract|validate), `rule_passed`, `model_id/version`, `verified_by`, `verified_at`.

Inoltre, **decision-level correction**: se lumano cambia il `client_id` rispetto al candidato AI
(es. AI propose 412, umano sceglie 889) → riga con `field_name='__entity__'`, `ai_value=412`,
`human_value=889`, `outcome=corrected`. E il segnale piu prezioso per migliorare lentity-resolution.

PII discipline (FASE 4.5 §3): la tabella vive SOLO su Postgres locale del Pro; levolver legge un digest
aggregato+redatto, mai i valori grezzi. Retention: hash/troncamento dei valori PII dopo 90gg.

---

## 6. GUARDRAIL GO-LIVE

### 6a. Feature-flag (default OFF)
Due flag distinti:
- `INTAKE_WRITER_ENABLED` (default **false**): se false, FASE 5 gira in dry-run (logga, non scrive). Si
  accende solo quando il team e pronto.
- `INTAKE_AUTOCOMMIT_ENABLED` (default **false**): anche con writer ON, lauto-commit resta OFF finche le
  soglie non sono validate empiricamente. Con writer ON + autocommit OFF → TUTTO passa per HITL.

### 6b. Dry-run mode
Con `INTAKE_WRITER_ENABLED=false`, il commit-worker esegue lINTERA logica (risolve payload, calcola TX)
ma sostituisce gli INSERT/UPDATE con un log strutturato `intake_commit_audit(dry_run=true)`: "AVREI scritto
documents(client=412, type=passport, file=...); AVREI aggiornato practice 98". Permette di validare il
routing su traffico reale senza toccare il CRM. Lapprove via UI in dry-run ritorna 200 con `{dry_run:true}`.

### 6c. Rate-limit / circuit-breaker
- Rate-limit sul commit-worker: max N commit/min (config, default conservativo es. 20/min) → un bug a monte
  non puo riversare 10k documenti nel CRM in pochi secondi.
- Circuit-breaker: se >K commit consecutivi falliscono (es. K=5) → il worker si APRE (stop auto-commit),
  mette tutto in review_pending, alert Telegram. Riuso del pattern alerter/DLQ gia in repo.

### 6d. Audit log (intake_commit_audit, tabella nuova)
Una riga per OGNI tentativo di commit (riuscito, dry-run, o fallito):
`proposal_id`, `intake_id`, `client_id`, `doc_id` (null se dry/fail), `committed_by` (umano o
`'system:autocommit'`), `decision` (AUTO_ATTACH/...), `dry_run` bool, `outcome`
(committed|dry_run|failed|rolled_back), `error`, `committed_at`. E la traccia forense: chi ha legato
quale documento a quale cliente, quando, e con che autorita.

### 6e. RBAC (CLAUDE.md §13)
- HITL approve: `verify_client_access(client_id, committer, conn)` con lidentita del reviewer; item senza
  cliente risolto (NO_MATCH/AMBIGUOUS) → solo `is_crm_admin` (zero@/asya@/antonellosiano@).
- Auto-commit (no umano): committer = `'system:autocommit'`; bypassa il check user-level MA registra
  in audit + e gated dal flag + applica solo ad AUTO_ATTACH (cliente gia certo via strong-key).

### 6f. Rollback di un attach errato
Un commit sbagliato (umano lega al cliente errato, o auto-commit su falso match) deve essere reversibile:
- endpoint `POST /api/crm/intake-review/{proposal_id}/rollback` (admin-only): soft-delete del documento
  (`UPDATE documents SET is_archived=true, status='rolled_back'` — NON hard delete, traccia forense),
  rimuove la voce da `practices.documents[]`, riporta proposal a `review_pending`, scrive
  `intake_corrections(field='__entity__', outcome='corrected')` + audit `outcome='rolled_back'`,
  invalida le cache. Il documento Drive NON si cancella (resta nel Drive del cliente errato fino a spostamento
  manuale — segnalare nellaudit). Reuse: il soft-delete esiste gia (`delete_client_document`, crm_enhanced_documents.py:403).

---

## 7. PIANO DI IMPLEMENTAZIONE (4 sotto-parti)

| Parte | Scope | Test | Rischio | Scrive CRM? |
|---|---|---|---|---|
| **5A — Review-queue API (read-only)** | endpoint GET list/detail + claim (lease); migration `intake_commit_audit` + colonna `documents.intake_idempotency_key UNIQUE`; estrarre `write_client_document` in servizio (NO chiamata ancora) | unit: RBAC filter, lease atomico (2 worker → 1 claim), idempotency_key unique | BASSO (no write CRM) | NO |
| **5B — Writer dry-run** | commit-worker completo dietro `INTAKE_WRITER_ENABLED=false`; approve/auto-commit calcolano la TX e loggano `intake_commit_audit(dry_run=true)` | integ: proposta reale → audit dry-run corretto; nessuna riga in documents | BASSO-MEDIO (logica completa, zero scrittura) | NO (solo audit) |
| **5C — Writer reale dietro flag** | flip `INTAKE_WRITER_ENABLED=true` per AUTO_ATTACH only; TX atomica (riuso write_client_document); rate-limit + circuit-breaker; rollback endpoint | integ: commit atomico + rollback on mid-TX fail; idempotenza re-commit no-op; cache invalidata; RBAC; rate-limit trip | **ALTO (primo write CRM reale)** — deploy in finestra bassa, su 1-2 clienti pilota, autocommit OFF | **SI** |
| **5D — Corrections + audit + evolver hook** | scrittura `intake_corrections` su ogni esito; decision-level correction (`__entity__`); aggancio digest read-only allevolver esistente (FASE 4.5 §4) | unit: ogni outcome → riga corrections; digest volume-gated no-op sotto soglia | BASSO (append-only, no CRM mutation oltre 5C) | NO (oltre 5C) |

Ordine obbligato: 5A → 5B → 5C → 5D. 5C non si abilita finche 5B non ha girato giorni in dry-run su
traffico reale con audit pulito. `INTAKE_AUTOCOMMIT_ENABLED` resta OFF anche dopo 5C: si abilita come
step separato post-validazione soglie (5C.1), mai insieme al primo write reale.

---

## 8. PANEL REVIEW (4-LLM) — RISULTATI

**Panelisti effettivi**: Codex GPT-5.5 (review completa P0/P1/P2) + DeepSeek V4 Pro (reasoning
catturato — il campo `content` e tornato vuoto per il trap v4-pro che brucia il budget in
`reasoning_content`, ma il ragionamento e sostanziale e convergente). Gemini agy: **OAuth scaduto**
(login interattivo richiesto, fuori scope read-only) — panel a 2 voci indipendenti, non 3. NB-1 non
interpellato (dominio infra, non legale). Solo il design ASTRATTO e stato inviato (nessuna PII, Law 2).

**Verdetto convergente**: *NON sicuro per write CRM reali cosi com e*. Direzione giusta, ma troppi
invarianti sono affidati allINTENZIONE del codice anziche a vincoli Postgres. FASE 5 non puo fidarsi
dellintenzione. I due panelisti hanno convergito in modo quasi 1:1 sui P0 — alta confidenza.

### P0 — bloccanti go-live (corruzione dati cliente)

| # | Finding | Fonte | Fix da incorporare |
|---|---|---|---|
| **P0-1** | **idempotency_key = content NON e identita.** `blob_sha256:doc_index:pipeline_version` collide tra clienti diversi sullo stesso file (forward, modulo vuoto, doc aziendale condiviso, template). Con UNIQUE globale → cliente B "riusa"/skippa silenziosamente il documento di cliente A. | Codex+DS | Key intake-instance: `sha256(source|source_ref|blob_hash|pipeline_version)`. Il content_hash resta SOLO evidenza-duplicato, non identita di commit. UNIQUE su (client_id, intake_key), mai globale su content. |
| **P0-2** | **SELECT+ON CONFLICT DO NOTHING non e un contratto di commit sano.** Sotto worker concorrenti, DO NOTHING puo NON ritornare doc_id → i passi 4-7 (practice, interactions, audit) proseguono con doc_id NULL/stale → audit e interactions orfani. | Codex+DS | UPSERT atomico che ritorna SEMPRE il doc_id canonico; hard-fail se la riga esistente ha client_id/file_id/document_type/proposal_id diversi. Se doc_id NULL → abortire i passi successivi. |
| **P0-3** | **Wrong-client commit ancora aperto.** RBAC al momento dell approve non basta. Il commit DEVE ri-validare DENTRO la TX sullo stato DB corrente: cliente esiste e non deleted; `practice.client_id == document.client_id`; `family_member.client_id == client_id`; il target della proposal combacia ancora con l approval. Un approval stale puo attaccarsi a un cliente cancellato/riassegnato o alla practice sbagliata. | Codex+DS | Validazioni in-TX esplicite prima dell INSERT. **practice_id NON validato contro client_id = cross-client orphan link** (DeepSeek lo isola come path di corruzione). |
| **P0-4** | **RBAC descritto ≠ comportamento reale.** `verify_client_access(allow_assigned=True)` oggi lascia accedere QUALSIASI team member a QUALSIASI cliente (crm_utils.py:155), non solo gli assegnati. Le nuove endpoint review necessitano filtri piu stretti; `approve` deve esigere il claim-holder attivo. | Codex | Filtro review-list reale per assigned; approve gated su claimed_by + lease valido. |
| **P0-5** | **Claim/lease senza claim-token = race.** `claim` con TTL non basta: `approve`/`reject`/`PATCH` devono richiedere claimed_by + lease_expires_at non scaduto + un `claim_token`. Altrimenti reviewer A approva dopo lease scaduto mentre B ha gia ri-claimato. | Codex | Aggiungere claim_token opaco, verificato su ogni mutazione. |
| **P0-6** | **Practice dual-link corruttibile.** L append a `practices.documents[]` e read-modify-write JSON (crm_practices.py:1628). Senza `SELECT practices FOR UPDATE` + membership idempotente per document_id, append concorrenti perdono/duplicano voci. | Codex+DS | FOR UPDATE sulla practice + dedup membership nel JSON + validazione client match. |
| **P0-7** | **Writer legacy puo ancora correre e duplicare.** `drive_poll_service` dedup advisory senza unique → FASE 5 puo correre contro Drive-poll o HTTP-upload sullo stesso file_id/content_hash. | Codex | Constraint DB condiviso o advisory-lock o **disabilitare l ingestion legacy sulle folder pilota** durante 5C. |
| **P0-8** | **`write_client_document` deve essere PURE-DB.** Il writer HTTP originale fa OCR-dispatch (background task), portal-notify, cache-invalidate, e `UPDATE ocr_status=pending`. Riusato as-is dal commit-worker DENTRO la TX: (a) Redis-delete non transazionale (se TX rolla back, cache gia svuotata); (b) **sovrascrive ocr_status da completed→pending annullando l OCR di FASE 3**; (c) side-effect esterni dentro TX. | Codex+DS | La funzione estratta NON deve schedulare task, notificare, o invalidare cache dentro la TX. DEVE preservare `ocr_status=completed`. Tutti i side-effect → outbox/post-commit. |
| **P0-9** | **Dry-run puo bruciare lavoro reale.** Se il dry-run avanza proposal/queue a committed/routed/done, al flip `INTAKE_WRITER_ENABLED=true` quei record SALTANO il write reale (sembrano gia fatti). | Codex+DS | Dry-run scrive SOLO audit/shadow, MAI stati terminali; oppure stato separato `dry_run_ready`. |

### P1 — alta priorita

- **P1-1 Outbox transazionale**: i post-commit (cache-invalidate, portal-notify, D3, queue→done) vanno
  accodati in una riga outbox DENTRO la TX di commit. "Reconcile tick" senza work-item durevoli non
  garantisce: doc committato puo restare con stats stale o queue bloccata su `routed`. **Riuso diretto:
  `events_outbox` gia esiste in repo** (cicatrix EventBus PG LISTEN/NOTIFY + outbox.publish/acknowledge).
- **P1-2 Audit di fallimento perso nel rollback**: `intake_commit_audit`/`intake_corrections` scritti
  dentro la TX che fa rollback spariscono. Audit-fallimento + retry/dead update vanno in una SECONDA TX
  dopo il rollback.
- **P1-3 Auto-commit ancora troppo debole**: oltre alle condizioni gia previste, esigere: unicita DB della
  strong-key (la chiave non deve gia esistere su un ALTRO cliente/family/company), >=2 segnali indipendenti
  concordi, nessun segnale negativo, nessun mismatch di doc-class. Un solo "passport exact" puo essere di
  un family member o di un record stale.
- **P1-4 Vocabolari di stato in conflitto**: `approved/committed/done` (proposal) + `review_pending/
  review_claimed/routed` (queue) si desync facilmente. Canonicalizzare UNA macchina-stati o separare
  `commit_status`; aggiungere CHECK constraint + transition test.
- **P1-5 Rollback incompleto**: deve rollare SOLO i doc creati da QUESTA intake-key, reverse/annotare
  interactions+timeline, invalidare TUTTE le cache coinvolte, emettere audit, e BLOCCARE il rollback se
  un downstream irreversibile ha gia consumato il doc.
- **P1-6 Scope cache sottospecificato**: `crm_clients_stats`/`crm_practices_stats` non bastano. Stale
  possibili anche su: document lists, client detail, practice detail, portal docs, required-doc status.

### P2 — hardening

- Allowlist clienti-pilota ENFORCED nel path SQL di commit; cap giornaliero di commit; verifica PITR/backup
  PRIMA di 5C; test di rollback della migration; shadow-run diff; dashboard commit/duplicati/rollback/dead.
- Schema guards: `intake_idempotency_key` UNIQUE nullable, `intake_proposal_id`, `intake_source_ref`,
  `content_sha256` SEPARATO dall esistente `content_hash` MD5; FK/CHECK dove possibile.
- Test che rompono di proposito: 2 worker stessa proposal; 2 proposal stesso content clienti diversi;
  race Drive-poll; approve con lease scaduto; coppia practice/client errata; dry-run→reale; fail mid-TX a
  ogni passo; rollback dopo practice-link.

### Risposte dirette del panel alle 5 domande
- **(a) Dove si rompe la TX**: idempotency-insert (P0-2), side-effect riusati dentro TX (P0-8),
  audit-fallimento nel rollback (P1-2), post-commit non-durevole (P1-1).
- **(b) Path di corruzione aperti**: wrong-client (P0-3), documenti duplicati (P0-1/P0-7), practice JSON
  persa/duplicata (P0-6), OCR status regression completed→pending (P0-8), cache stale (P1-6).
- **(c) Idempotenza sana?**: NO — la key e content-based (collisione cross-client) e l insert puo non
  ritornare doc_id. Va resa intake-instance + UPSERT-returns-id.
- **(d) Cosa manca ai guardrail**: invarianti enforced-da-DB, outbox, RBAC/claim-token stretti, allowlist
  pilota, backup/restore verificato, test di race.
- **(e) Race claim/lease e dry-run→reale**: SI entrambe — approve con lease scaduto (P0-5) e avanzamento
  di stato in dry-run (P0-9) sono race vive.

### Integrazione nel design (azioni recepite)
Le 9 P0 vanno incorporate PRIMA di 5C (il primo write reale). In sintesi, le 5 modifiche strutturali al
design originale:
1. **idempotency_key intake-instance** (non content-based) + UNIQUE su (client_id, key) + UPSERT-returns-id.
2. **Validazioni in-TX** (client non-deleted, practice.client_id==client_id, family.client_id==client_id,
   proposal-target invariato) — la firma umana NON e sufficiente, serve il re-check sullo stato corrente.
3. **`write_client_document` PURE-DB** (no OCR-dispatch, no cache, no notify dentro TX; preserva
   ocr_status=completed); tutti i side-effect via **events_outbox esistente** dentro la TX.
4. **claim_token** + lease-valid check su approve/reject/patch; **dry-run mai su stati terminali**.
5. **Disabilitare ingestion legacy (drive_poll) sulle folder pilota** durante 5C + audit-fallimento in
   seconda TX + rollback completo (interactions/timeline/cache).

Queste modifiche NON cambiano il piano in 4 parti: si assorbono dentro 5A (schema: key intake-instance,
UNIQUE, outbox reuse), 5B (write_client_document pure-DB verificato in dry-run), 5C (validazioni in-TX +
claim_token + legacy-off pilota), 5D (rollback completo + audit). Aggiungono peso a 5A (piu migration/
constraint) e a 5C (piu validazioni in-TX) — i due punti gia marcati ALTO rischio.
